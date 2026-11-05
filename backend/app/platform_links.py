"""Multi-account registration links with locked quotas and optional token rotation."""
import time
from typing import Literal
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import Field
from sqlalchemy import select
from .schemas import Strict
from .db import get_db
from .models import PlatformInvitationLink,User
from .security import admin,token,digest,cipher,audit,throttle
from .registration_admin import lock_admin
from .authority import grant_proof,invitation_role
from .admin_permissions import require_permission
from .config import settings
router=APIRouter(prefix='/api/v1/admin/invitations/shared-links',tags=['Inviti piattaforma condivisi'])

class LinkIn(Strict):
    label:str=Field(min_length=1,max_length=100)
    hours:int=Field(default=168,ge=1,le=8760)
    max_uses:int|None=Field(default=10,ge=1,le=10000)
    auto_rotate:bool=False
    role:Literal['user','admin','superadmin']='user'
    password:str=Field(default='',max_length=128)
    code:str=Field(default='',max_length=100)

class LinkChange(Strict):
    expected_version:int=Field(ge=1)
    hours:int=Field(default=168,ge=1,le=8760)
    password:str=Field(default='',max_length=128)
    code:str=Field(default='',max_length=100)

def rotate(row):
    clear=token();row.token_hash=digest(clear);row.secret=cipher().encrypt(clear.encode());row.uses=0;row.rotations+=1

def output(row,include_link=True):
    state='revoked' if row.revoked else 'expired' if row.expires<=time.time() else 'exhausted' if row.max_uses is not None and row.uses>=row.max_uses else 'active'
    data={'id':row.id,'label':row.label,'expires':row.expires,'uses':row.uses,'total_uses':row.total_uses,'max_uses':row.max_uses,'auto_rotate':row.auto_rotate,'rotations':row.rotations,'role':row.requested_role,'version':row.version,'state':state}
    if include_link:data['url']=settings.public_origin+'/invite?register=1#'+cipher().decrypt(row.secret).decode()
    return data

@router.get('')
def links(user=Depends(admin),db=Depends(get_db)):
    return [output(r) for r in db.scalars(select(PlatformInvitationLink).order_by(PlatformInvitationLink.created.desc(),PlatformInvitationLink.id).limit(200)) if r.requested_role=='user' or __import__('app.superadmin',fromlist=['is_superadmin']).is_superadmin(db,user.id)]

@router.post('',status_code=201)
def create(body:LinkIn,request:Request,user=Depends(admin),db=Depends(get_db)):
    throttle(db,'shared-invitation:'+user.id,30);lock_admin(db,request,user)
    grant_proof(db,user,body.role,body.password,body.code)
    if not body.label.strip() or (body.auto_rotate and body.max_uses is None):raise HTTPException(422,'Inserisci nome e limite utilizzi per la rigenerazione automatica')
    row=PlatformInvitationLink(label=body.label.strip(),expires=int(time.time())+body.hours*3600,max_uses=body.max_uses,auto_rotate=body.auto_rotate,requested_role=body.role,issuer_id=user.id,issuer_auth_version=user.auth_version,rotations=-1)
    rotate(row);db.add(row);db.flush();audit(db,user.id,'platform_link.created',row.id);db.commit();return output(row)

@router.post('/{identity}/{action}')
def change(identity:str,action:Literal['renew','regenerate','revoke'],body:LinkChange,request:Request,user=Depends(admin),db=Depends(get_db)):
    throttle(db,'shared-invitation:'+user.id,30);lock_admin(db,request,user)
    row=db.scalar(select(PlatformInvitationLink).where(PlatformInvitationLink.id==identity).with_for_update().execution_options(populate_existing=True))
    if not row:raise HTTPException(404,'Link non trovato')
    grant_proof(db,user,row.requested_role,body.password,body.code)
    if row.version!=body.expected_version:raise HTTPException(409,'Il link è cambiato o è stato utilizzato: aggiorna la lista')
    if action=='revoke':row.revoked=True
    else:
        if action=='renew' and row.revoked:raise HTTPException(409,'Rigenera un link revocato')
        if action=='regenerate':rotate(row);row.revoked=False
        row.expires=int(time.time())+body.hours*3600
        row.issuer_id=user.id;row.issuer_auth_version=user.auth_version
    row.version+=1;audit(db,user.id,'platform_link.'+action,row.id);db.commit();return output(row)

def validate(db,row):
    if output(row,False)['state']!='active':raise HTTPException(403,'Link di registrazione scaduto, revocato o con utilizzi esauriti')
    issuer=db.get(User,row.issuer_id)
    if not issuer or issuer.status!='active' or not issuer.admin or issuer.deleted:raise HTTPException(403,'Link non più autorizzato: chiedi un nuovo invito')
    require_permission(db,issuer,'registrations')
    return invitation_role(db,row)

def consume(db,row):
    row.uses+=1;row.total_uses+=1;row.version+=1
    if row.auto_rotate and row.max_uses is not None and row.uses>=row.max_uses:
        rotate(row);audit(db,None,'platform_link.auto_rotated',row.id)
