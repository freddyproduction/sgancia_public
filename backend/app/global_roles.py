"""Installation roles are independent of Participant.role and group visibility."""
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy import select,func
from .schemas import Strict
from .account_security import Proof,require_password,revoke_access
from .models import User,Instance
from .security import admin,recent,audit,throttle
from .passkeys import ensure_live_session
from .db import get_db
router=APIRouter(prefix='/api/v1/admin',tags=['Ruoli globali'])


def locked_admin(db,request,user,target_id):
    # One installation mutex serializes role changes with suspensions/edits.
    db.scalar(select(Instance).where(Instance.id==1).with_for_update().execution_options(populate_existing=True))
    people={u.id:u for u in db.scalars(select(User).where(User.id.in_({user.id,target_id})).order_by(User.id).with_for_update().execution_options(populate_existing=True))}
    actor=people.get(user.id)
    if not actor or not actor.admin or actor.status!='active':raise HTTPException(403,'Permesso amministratore globale richiesto')
    ensure_live_session(db,request,actor);recent(request)
    target=people.get(target_id)
    if not target:raise HTTPException(404,'Account non trovato')
    return actor,target


class GlobalRoleIn(Proof):
    enabled:bool
    expected_admin:bool


@router.put('/users/{user_id}/global-role')
def change_role(user_id:str,body:GlobalRoleIn,request:Request,user=Depends(admin),db=Depends(get_db)):
    throttle(db,'global-role:'+user.id,10)
    actor,target=locked_admin(db,request,user,user_id)
    require_password(db,actor,body.password,body.code)
    from .superadmin import is_superadmin
    if is_superadmin(db,target.id) and not body.enabled:raise HTTPException(403,'Il superadmin dell’installazione è permanente e non può essere rimosso dal ruolo')
    if target.admin!=body.expected_admin:raise HTTPException(409,'Il ruolo è cambiato: aggiorna la lista utenti')
    if target.admin==body.enabled:return {'admin':target.admin,'login_required':False,'sessions_revoked':False}
    if body.enabled and target.status!='active':raise HTTPException(409,'Attiva prima l’account: non puoi promuovere un account sospeso o in attesa')
    if not body.enabled and target.status=='active':
        count=db.scalar(select(func.count()).select_from(User).where(User.admin.is_(True),User.status=='active'))
        if count<=1:raise HTTPException(409,'Non puoi rimuovere l’ultimo amministratore globale attivo: nominane prima un altro')
    target.admin=body.enabled
    revoke_access(db,target)
    audit(db,actor.id,'global_admin.granted' if body.enabled else 'global_admin.revoked',target.id)
    db.commit()
    return {'admin':target.admin,'login_required':actor.id==target.id,'sessions_revoked':True}
