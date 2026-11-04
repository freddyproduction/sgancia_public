import time
from typing import Literal
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy import select, delete
from pydantic import Field
from .schemas import Strict, Credentials, GateIn
from .security import admin, recent, audit, token, digest, passwords
from .db import get_db
from .models import Instance, User, Invite, Session, GateGrant

router = APIRouter(prefix='/api/v1/admin', tags=['Amministrazione'])


class Policy(Strict):
    registration: Literal['open', 'approval', 'invite', 'disabled']


class Status(Strict):
    status: Literal['active', 'suspended']


class Invitation(Strict):
    email: str = Field(min_length=3, max_length=254)


@router.get('/users')
def users(user=Depends(admin), db=Depends(get_db)):
    return [{'id': u.id, 'name': u.name, 'email': u.email, 'status': u.status, 'admin': u.admin,'superadmin':db.get(Instance,1).superadmin_id==u.id} for u in db.scalars(select(User).order_by(User.email))]


@router.put('/registration')
def policy(body: Policy, request: Request, user=Depends(admin), db=Depends(get_db)):
    recent(request)
    db.get(Instance, 1).registration = body.registration
    audit(db, user.id, 'registration.changed')
    db.commit()
    return body.model_dump()


@router.put('/users/{user_id}/status')
def status(user_id: str, body: Status, request: Request, user=Depends(admin), db=Depends(get_db)):
    from .global_roles import locked_admin
    user,target=locked_admin(db,request,user,user_id)
    from .superadmin import is_superadmin
    if is_superadmin(db,target.id):raise HTTPException(403,'Il superadmin dell’installazione non può essere sospeso')
    if target.admin:
        raise HTTPException(403, 'Gli amministratori non possono essere sospesi da questa operazione')
    target.status = body.status
    if body.status == 'suspended':
        db.execute(delete(Session).where(Session.user_id == user_id))
    audit(db, user.id, 'user.status_changed', user_id)
    db.commit()
    return {'status': target.status}


@router.post('/invitations', status_code=201)
def invite(body: Invitation, request: Request, user=Depends(admin), db=Depends(get_db)):
    recent(request)
    clear = token()
    db.add(Invite(token_hash=digest(clear), email=body.email.strip().lower(), expires=int(time.time()) + 86400 * 7))
    audit(db, user.id, 'invitation.created')
    db.commit()
    return {'token': clear, 'expires_in': 604800}


@router.put('/gate')
def rotate_gate(body: GateIn, request: Request, user=Depends(admin), db=Depends(get_db)):
    recent(request)
    if len(body.key) < 16:
        raise HTTPException(422, 'Usa almeno 16 caratteri')
    instance = db.scalar(select(Instance).where(Instance.id == 1).with_for_update().execution_options(populate_existing=True))
    instance.gate_hash = passwords.hash(body.key)
    instance.gate_version += 1
    db.execute(delete(GateGrant))
    db.execute(delete(Session))
    audit(db, user.id, 'gate.rotated')
    db.commit()
    return {'ok': True, 'login_required': True}
