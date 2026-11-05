import time
from typing import Literal
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select, delete
from pydantic import Field,field_validator
from .schemas import Strict, Credentials, GateIn
from .security import admin, recent, audit, token, digest, passwords
from .db import get_db
from .models import Instance, User, Invite, Session, GateGrant

router = APIRouter(prefix='/api/v1/admin', tags=['Amministrazione'])


class Policy(Strict):
    registration: Literal['open', 'approval', 'invite', 'disabled']
    expected_registration: Literal['open','approval','invite','disabled'] | None = None


class Status(Strict):
    status: Literal['active', 'suspended']
    role: Literal['user','admin','superadmin'] | None = None
    password: str = Field(default='',max_length=128)
    code: str = Field(default='',max_length=100)
    expected_status: Literal['pending','active','suspended'] | None = None


class Invitation(Strict):
    email: str = Field(min_length=3, max_length=254)
    days: int = Field(default=7,ge=1,le=90)
    role: Literal['user','admin','superadmin']='user'
    password: str = Field(default='',max_length=128)
    code: str = Field(default='',max_length=100)
    @field_validator('email')
    @classmethod
    def valid_email(cls,value):return Credentials.email_valid(value)


@router.get('/users')
def users(user=Depends(admin), db=Depends(get_db)):
    return [{'id': u.id, 'name': u.name, 'email': u.email, 'deleted':u.deleted,'status': u.status, 'admin': u.admin,'email_verified':u.email_verified,'superadmin':__import__('app.superadmin',fromlist=['is_superadmin']).is_superadmin(db,u.id),'admin_permissions':__import__('app.admin_permissions',fromlist=['permissions']).permissions(db,u),'requested_role':u.requested_role,'auth_version':u.auth_version} for u in db.scalars(select(User).order_by(User.email))]


@router.put('/registration')
def policy(body: Policy, request: Request, user=Depends(admin), db=Depends(get_db)):
    from .registration_admin import lock_admin
    instance=lock_admin(db,request,user)
    if body.expected_registration is not None and instance.registration!=body.expected_registration:raise HTTPException(409,'La modalità è cambiata: aggiorna prima di salvare')
    instance.registration = body.registration
    audit(db, user.id, 'registration.changed')
    db.commit()
    return {'registration':instance.registration}


@router.put('/users/{user_id}/status')
def status(user_id: str, body: Status, request: Request, user=Depends(admin), db=Depends(get_db)):
    from .global_roles import locked_admin
    preliminary=db.get(User,user_id)
    if body.role in ('admin','superadmin') or (preliminary and preliminary.requested_role!='user'):
        from .security import throttle
        throttle(db,'authority-proof:'+user.id,10)
    user,target=locked_admin(db,request,user,user_id)
    from .superadmin import is_superadmin
    if is_superadmin(db,target.id):raise HTTPException(403,'Il superadmin dell’installazione non può essere sospeso')
    if target.admin:
        raise HTTPException(403, 'Gli amministratori non possono essere sospesi da questa operazione')
    if body.expected_status is not None and target.status!=body.expected_status:raise HTTPException(409,'La richiesta è già stata gestita: aggiorna la lista')
    if target.deleted:raise HTTPException(409,'Account eliminato: non può essere riattivato')
    was_pending=target.status=='pending'
    from .admin_permissions import require_permission
    require_permission(db,user,'registrations' if was_pending else 'users')
    if was_pending:
        from .authority import approve_role
        approve_role(db,user,target,body)
    elif body.role is not None:raise HTTPException(409,'Modifica il ruolo dalla gestione dei ruoli')
    target.status = body.status
    if body.status == 'suspended':
        db.execute(delete(Session).where(Session.user_id == user_id))
    audit(db,user.id,('user.registration_approved' if body.status=='active' else 'user.registration_rejected') if was_pending else 'user.status_changed',user_id)
    db.commit()
    return {'status': target.status}


@router.post('/invitations', status_code=201)
def invite(body: Invitation, request: Request, user=Depends(admin), db=Depends(get_db)):
    from .registration_admin import create_invite
    return create_invite(body,request,user,db)


@router.put('/gate')
def rotate_gate(body: GateIn, request: Request, user=Depends(admin), db=Depends(get_db)):
    recent(request)
    if len(body.key) < 16:
        raise HTTPException(422, 'Usa almeno 16 caratteri')
    instance = db.scalar(select(Instance).where(Instance.id == 1).with_for_update().execution_options(populate_existing=True))
    from .smtp_admin import require_admin_session
    require_admin_session(db,request,user)
    instance.gate_hash = passwords.hash(body.key)
    instance.gate_version += 1
    db.execute(delete(GateGrant))
    db.execute(delete(Session))
    audit(db, user.id, 'gate.rotated')
    db.commit()
    return {'ok': True, 'login_required': True}
