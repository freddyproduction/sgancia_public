"""Explicit, selective factor recovery; never a route around founder protection."""
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy import delete
from .account_security import Proof,require_password,revoke_access
from .global_roles import locked_admin
from .superadmin import is_superadmin
from .models import RecoveryCode,Passkey,InstallationPasskey
from .security import admin,audit,throttle
from .db import get_db
router=APIRouter(prefix='/api/v1/admin',tags=['Recupero fattori account'])

class RecoveryIn(Proof):
    remove_mfa:bool=False
    remove_passkeys:bool=False
    confirm_reset:bool=False

@router.post('/users/{user_id}/reset-factors')
def reset_factors(user_id:str,body:RecoveryIn,request:Request,user=Depends(admin),db=Depends(get_db)):
    throttle(db,'admin-factor-reset:'+user.id,5)
    actor,target=locked_admin(db,request,user,user_id)
    if (target.admin or target.requested_role!='user') and not is_superadmin(db,actor.id):raise HTTPException(403,'Solo un superadmin può recuperare altri amministratori')
    if is_superadmin(db,target.id):raise HTTPException(403,'Il recupero amministrativo non può modificare MFA o passkey del superadmin: usa i suoi percorsi personali o il recupero locale del server')
    if actor.id==target.id:raise HTTPException(403,'Per il tuo account usa i comandi personali di MFA e passkey')
    if not body.confirm_reset or not(body.remove_mfa or body.remove_passkeys):raise HTTPException(422,'Scegli almeno un fattore e conferma esplicitamente il recupero')
    require_password(db,actor,body.password,body.code)
    removed=0
    if body.remove_mfa:
        target.totp_secret=None;target.totp_pending=None;target.totp_last_counter=-1
        db.execute(delete(RecoveryCode).where(RecoveryCode.user_id==target.id))
        audit(db,actor.id,'account.mfa_admin_reset',target.id)
    if body.remove_passkeys:
        removed=db.execute(delete(Passkey).where(Passkey.user_id==target.id)).rowcount
        removed+=db.execute(delete(InstallationPasskey).where(InstallationPasskey.user_id==target.id)).rowcount
        audit(db,actor.id,'account.passkeys_admin_reset',target.id)
    revoke_access(db,target)
    db.commit()
    return {'ok':True,'mfa_removed':body.remove_mfa,'passkeys_removed':removed,'sessions_revoked':True}
