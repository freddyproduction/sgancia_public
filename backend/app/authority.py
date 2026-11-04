"""Root-only authority changes; no group visibility expansion."""
from typing import Literal
from pydantic import Field
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy import select,or_
from .db import get_db
from .models import User,Instance
from .schemas import Strict
from .security import admin,audit,throttle
from .account_security import Proof,require_password,revoke_access
from .admin_permissions import PERMISSIONS,require_superadmin,permissions
from .superadmin import is_superadmin,role
router=APIRouter(prefix='/api/v1/admin',tags=['Autorità globale'])
Role=Literal['user','admin','superadmin']
Permission=Literal['users','registrations','smtp','access','policy','guests','telegram','backups','audit','sessions']

class AuthorityIn(Proof):
    role:Role
    expected_role:Role
    permissions:list[Permission]=Field(default_factory=list,max_length=10)
    expected_auth_version:int=Field(ge=1)

@router.get('/authority-options')
def options(user=Depends(admin)):
    return {'permissions':PERMISSIONS}

@router.put('/users/{identity}/authority')
def change_authority(identity:str,body:AuthorityIn,request:Request,user=Depends(admin),db=Depends(get_db)):
    from .global_roles import locked_admin
    throttle(db,'authority-proof:'+user.id,10)
    actor,target=locked_admin(db,request,user,identity);require_superadmin(db,actor)
    require_password(db,actor,body.password,body.code)
    current=role(db,target)
    if current!=body.expected_role or target.auth_version!=body.expected_auth_version:raise HTTPException(409,'Ruolo o permessi modificati: aggiorna la lista')
    if body.role!='user' and target.status!='active':raise HTTPException(409,'Attiva prima l’account')
    if current=='superadmin' and body.role!='superadmin':
        if actor.id==target.id:raise HTTPException(403,'Solo un altro superadmin può revocare il tuo ruolo')
        instance=db.get(Instance,1)
        other=db.scalar(select(User).where(User.id!=target.id,User.admin.is_(True),User.status=='active',or_(User.superadmin.is_(True),User.id==instance.superadmin_id)).order_by(User.id).with_for_update())
        if not other:raise HTTPException(409,'Non puoi rimuovere l’ultimo superadmin')
        if instance.superadmin_id==target.id:instance.superadmin_id=other.id;db.flush()
    target.superadmin=body.role=='superadmin';target.admin=body.role!='user'
    target.admin_permissions=sorted(set(body.permissions)) if body.role=='admin' else None
    revoke_access(db,target);audit(db,actor.id,'authority.changed',target.id);db.commit()
    return {'role':role(db,target),'login_required':actor.id==target.id}

def grant_proof(db,actor,desired,password,code):
    if desired!='user':require_superadmin(db,actor);require_password(db,actor,password,code)

def invitation_role(db,invitation):
    if invitation.requested_role=='user':return 'user'
    issuer=db.get(User,invitation.issuer_id) if invitation.issuer_id else None
    if not issuer or issuer.status!='active' or not issuer.admin or not is_superadmin(db,issuer.id) or invitation.issuer_auth_version!=issuer.auth_version:raise HTTPException(403,'Invito con ruolo non più autorizzato: chiedi un nuovo invito')
    return invitation.requested_role

def approve_role(db,actor,target,body):
    desired=body.role or target.requested_role
    if desired!='user' or target.requested_role!='user':require_superadmin(db,actor)
    if body.status=='active':
        grant_proof(db,actor,desired,body.password,body.code)
        target.admin=desired!='user';target.superadmin=desired=='superadmin';target.admin_permissions=[] if desired=='admin' else None
    target.requested_role='user'
