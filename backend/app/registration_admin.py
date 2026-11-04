"""Installation invitations only. Group-bound grants stay in group settings."""
import time
from fastapi import APIRouter,Depends,Request,HTTPException,Query
from sqlalchemy import select,func
from pydantic import Field
from .schemas import Strict
from .db import get_db
from .security import admin,audit,token,digest
from .models import Instance,Invite,GroupInvite,User
from .smtp_admin import require_admin_session
from .config import settings
router=APIRouter(prefix='/api/v1/admin',tags=['Registrazioni e inviti globali'])

class Change(Strict):
    expected_version:int=Field(ge=1)
    days:int=Field(default=7,ge=1,le=90)

def lock_admin(db,request,user):
    instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update().execution_options(populate_existing=True))
    require_admin_session(db,request,user)
    return instance

def state(row):
    return 'revoked' if row.revoked else 'used' if row.used else 'expired' if row.expires<=time.time() else 'active'

def output(row):
    return {'id':row.id,'email':row.email,'expires':row.expires,'created':row.created,'state':state(row),'version':row.version,'used_by':row.used_by}

def standalone():return ~select(GroupInvite.token_hash).where(GroupInvite.token_hash==Invite.token_hash).exists()

def available_email(db,email,exclude_id=None):
    if db.scalar(select(User.id).where(User.email==email)):raise HTTPException(409,'Esiste già un account con questa email: gestiscilo nella lista utenti o richieste in attesa')
    if db.scalar(select(Invite.id).where(Invite.email==email,Invite.used.is_(False),Invite.revoked.is_(False),Invite.expires>time.time(),standalone(),Invite.id!=exclude_id if exclude_id else True)):raise HTTPException(409,'Esiste già un invito attivo per questa email: rinnova o rigenera quello esistente')

def issue(db,email,days,user):
    clear=token();row=Invite(token_hash=digest(clear),email=email,expires=int(time.time())+86400*days,issuer_id=user.id)
    db.add(row);db.flush()
    return row,{'token':clear,'expires_in':days*86400,'url':settings.public_origin+'/invite?register=1#'+clear,**output(row)}

def create_invite(body,request,user,db):
    lock_admin(db,request,user);available_email(db,body.email)
    row,result=issue(db,body.email,body.days,user);audit(db,user.id,'invitation.created',row.id);db.commit();return result

@router.get('/registration')
def registration(user=Depends(admin),db=Depends(get_db)):
    return {'registration':db.get(Instance,1).registration,'pending':db.scalar(select(func.count()).select_from(User).where(User.status=='pending'))}

@router.get('/invitations')
def invitations(state_filter:str=Query('all',alias='state',pattern='^(all|active|used|expired|revoked)$'),search:str=Query('',max_length=254),page:int=Query(1,ge=1),user=Depends(admin),db=Depends(get_db)):
    filters=[standalone()]
    if search.strip():filters.append(Invite.email.contains(search.strip().lower(),autoescape=True))
    if state_filter=='revoked':filters.append(Invite.revoked.is_(True))
    elif state_filter=='used':filters.extend([Invite.revoked.is_(False),Invite.used.is_(True)])
    elif state_filter in ('active','expired'):filters.extend([Invite.revoked.is_(False),Invite.used.is_(False),Invite.expires>time.time() if state_filter=='active' else Invite.expires<=time.time()])
    total=db.scalar(select(func.count()).select_from(Invite).where(*filters));rows=db.scalars(select(Invite).where(*filters).order_by(Invite.created.desc(),Invite.id).offset((page-1)*30).limit(30))
    return {'items':[output(r) for r in rows],'total':total,'page':page,'pages':max(1,(total+29)//30)}

def editable(db,identity,version):
    row=db.scalar(select(Invite).where(Invite.id==identity,standalone()).with_for_update().execution_options(populate_existing=True))
    if not row:raise HTTPException(404,'Invito globale non trovato: gli inviti account + gruppo si gestiscono nel gruppo')
    if row.version!=version:raise HTTPException(409,'Invito modificato nel frattempo: aggiorna la lista')
    return row

@router.post('/invitations/{identity}/renew')
def renew(identity:str,body:Change,request:Request,user=Depends(admin),db=Depends(get_db)):
    lock_admin(db,request,user);row=editable(db,identity,body.expected_version)
    if row.used or row.revoked:raise HTTPException(409,'Un invito usato o revocato non si può rinnovare')
    available_email(db,row.email,row.id)
    row.expires=int(time.time())+body.days*86400;row.version+=1;audit(db,user.id,'invitation.renewed',row.id);db.commit();return output(row)

@router.post('/invitations/{identity}/regenerate')
def regenerate(identity:str,body:Change,request:Request,user=Depends(admin),db=Depends(get_db)):
    lock_admin(db,request,user);row=editable(db,identity,body.expected_version)
    if row.used:raise HTTPException(409,'Un invito utilizzato non si può rigenerare: gestisci l’account creato')
    row.revoked=True;row.version+=1;db.flush();available_email(db,row.email)
    new,result=issue(db,row.email,body.days,user);audit(db,user.id,'invitation.regenerated',row.id);db.commit();return result

@router.post('/invitations/{identity}/revoke')
def revoke(identity:str,body:Change,request:Request,user=Depends(admin),db=Depends(get_db)):
    lock_admin(db,request,user);row=editable(db,identity,body.expected_version)
    if row.used:raise HTTPException(409,'Invito già utilizzato: gestisci l’account creato')
    row.revoked=True;row.version+=1;audit(db,user.id,'invitation.revoked',row.id);db.commit();return output(row)
