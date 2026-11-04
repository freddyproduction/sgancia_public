import secrets
import time
import pyotp
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select, delete, update
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import User, Instance, Session, GateGrant, Invite, RecoveryCode, GroupInvite
from .schemas import GateIn, Credentials, Register, CodeIn, PreferencesIn
from .security import gate, current, admin, recent, digest, token, verify, passwords, DUMMY, throttle, peer, set_cookie, cookie_secure, audit, cipher
from .config import settings
from .invitations import check_group_invitation, join_from_invitation, lock_invitation_group

router = APIRouter(prefix='/api/v1/auth', tags=['Autenticazione'])


def user_out(user,db):
    from .superadmin import is_superadmin
    return {'id': user.id, 'name': user.name, 'email': user.email, 'admin': user.admin, 'totp': bool(user.totp_secret), 'theme': user.theme, 'email_verified':user.email_verified,'superadmin':is_superadmin(db,user.id),'admin_permissions':__import__('app.admin_permissions',fromlist=['permissions']).permissions(db,user)}


def totp_check(db, user, code):
    secret = cipher().decrypt(user.totp_secret.encode()).decode()
    now = int(time.time()) // 30
    otp = pyotp.TOTP(secret)
    counter = next((c for c in (now, now - 1, now + 1) if secrets.compare_digest(otp.at(c * 30), code)), None)
    if counter is not None:
        updated = db.execute(update(User).where(User.id == user.id, User.totp_last_counter < counter,User.auth_version==user.auth_version).values(totp_last_counter=counter)).rowcount
        if updated:
            return True
    recovery = db.execute(delete(RecoveryCode).where(RecoveryCode.user_id == user.id, RecoveryCode.code_hash == digest(code))).rowcount
    return bool(recovery)


@router.post('/gate')
def unlock(body: GateIn, request: Request, response: Response, db=Depends(get_db)):
    throttle(db, 'gate:' + peer(request), 15)
    instance = db.get(Instance, 1)
    if not verify(instance.gate_hash if instance else DUMMY, body.key) or not instance:
        raise HTTPException(403, 'Chiave non valida')
    from .runtime_policy import access_lifetime
    duration,cookie_age=access_lifetime(db,'gate')
    clear = token()
    db.add(GateGrant(token_hash=digest(clear), expires=int(time.time()) + duration, version=instance.gate_version))
    db.commit()
    set_cookie(response, 'sg_gate', clear, cookie_age, request)
    return {'registration': instance.registration}


@router.get('/policy')
def policy(instance=Depends(gate)):
    return {'registration': instance.registration,'gate_enabled':instance.gate_enabled}


@router.get('/entry-policy')
def entry_policy(db=Depends(get_db)):
    instance=db.get(Instance,1)
    return {'gate_enabled':True if not instance else instance.gate_enabled,'registration':instance.registration if instance and not instance.gate_enabled else None}


@router.post('/register', status_code=201)
def register(body: Register, request: Request, db=Depends(get_db), instance=Depends(gate)):
    throttle(db, 'register:' + peer(request), 5)
    instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update().execution_options(populate_existing=True))
    if instance.registration == 'disabled':
        raise HTTPException(403, 'Registrazioni disabilitate')
    invitation = None
    group_invitation = None
    if body.invite.strip():
        lock_invitation_group(db,digest(body.invite.strip()))
        invitation = db.scalar(select(Invite).where(Invite.token_hash == digest(body.invite.strip())).with_for_update())
        group_invitation = db.scalar(select(GroupInvite).where(GroupInvite.token_hash == digest(body.invite.strip())).with_for_update().execution_options(populate_existing=True))
        if invitation and (invitation.used or invitation.revoked or invitation.expires <= time.time() or invitation.email != body.email):
            raise HTTPException(403, 'Invito di registrazione scaduto, già usato o destinato a un’altra email')
        if not invitation and not group_invitation:
            raise HTTPException(403, 'Codice invito non riconosciuto: copia il codice completo senza modificarlo')
    if instance.registration == 'invite' and not invitation:
        if group_invitation:
            raise HTTPException(403, 'Questo codice serve solo a entrare nel gruppo con un account esistente. Chiedi all’amministratore un invito “Nuovo account + gruppo”.')
        raise HTTPException(403, 'Per creare un account è richiesto un invito di registrazione')
    if group_invitation:
        check_group_invitation(db, group_invitation, body.email,new_account=True)
    from .authority import invitation_role
    requested_role=invitation_role(db,invitation) if invitation else 'user'
    if invitation:
        invitation.used = True
    user = User(email=body.email, name=body.name.strip(), password_hash=passwords.hash(body.password), status='pending' if instance.registration == 'approval' else 'active')
    user.requested_role=requested_role if user.status=='pending' else 'user'
    if user.status=='active' and requested_role!='user':user.admin=True;user.superadmin=requested_role=='superadmin';user.admin_permissions=[]
    db.add(user)
    try:
        db.flush()
        if invitation:invitation.used_by=user.id
        group = join_from_invitation(db, group_invitation, user) if group_invitation else None
        from .mail_delivery import configured
        if configured(db):
            from .account_security import issue_token
            issue_token(db,user,'verify')
        audit(db, user.id, 'user.registered')
        if group:
            audit(db, user.id, 'group_invitation.accepted', group.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Registrazione non disponibile per questi dati. Se hai già un account, accedi e usa “Ho un invito”.') from None
    return {'status': user.status, 'joined_group': group.id if group else None}


@router.post('/login')
def login(body: Credentials, request: Request, response: Response, db=Depends(get_db), instance=Depends(gate)):
    throttle(db, 'login-ip:' + peer(request), 30)
    throttle(db, 'login-user:' + body.email, 10)
    user = db.scalar(select(User).where(User.email == body.email))
    valid = verify(user.password_hash if user else DUMMY, body.password)
    if not valid or not user or user.status != 'active':
        raise HTTPException(401, 'Credenziali non valide o account non attivo')
    if user.totp_secret and not totp_check(db, user, body.code):
        raise HTTPException(401, 'Codice MFA richiesto o non valido')
    old = db.get(Session, digest(request.cookies.get('sg_session', '')))
    if old:
        db.delete(old)
    clear, csrf = token(), token()
    from .runtime_policy import policy,check_verified
    check_verified(db,user)
    from .runtime_policy import access_lifetime
    duration,cookie_age=access_lifetime(db,'session')
    db.add(Session(token_hash=digest(clear), csrf_hash=digest(csrf), user_id=user.id, expires=int(time.time()) + duration, gate_version=instance.gate_version,auth_version=user.auth_version))
    audit(db, user.id, 'session.created')
    db.commit()
    set_cookie(response, 'sg_session', clear, cookie_age, request)
    set_cookie(response, 'sg_csrf', csrf, cookie_age, request)
    return user_out(user,db)


@router.get('/me')
def me(user=Depends(current),db=Depends(get_db)):
    return user_out(user,db)


@router.put('/preferences')
def preferences(body:PreferencesIn,user=Depends(current),db=Depends(get_db)):
    row=db.scalar(select(User).where(User.id==user.id).with_for_update())
    row.theme=body.theme
    db.commit()
    return user_out(row,db)


@router.post('/logout', status_code=204)
def logout(request: Request, response: Response, user=Depends(current), db=Depends(get_db)):
    db.delete(request.state.session)
    audit(db, user.id, 'session.revoked')
    db.commit()
    for name in ('sg_session', 'sg_csrf'):
        response.delete_cookie(name, path='/', secure=cookie_secure(request), httponly=name != 'sg_csrf', samesite='strict')


@router.post('/gate/forget',status_code=204)
def forget_gate(request:Request,response:Response,db=Depends(get_db)):
    session=db.get(Session,digest(request.cookies.get('sg_session','')))
    if session and session.expires>time.time() and not secrets.compare_digest(session.csrf_hash,digest(request.headers.get('X-CSRF-Token',''))):raise HTTPException(403,'Verifica CSRF fallita')
    grant=db.get(GateGrant,digest(request.cookies.get('sg_gate','')))
    if grant:db.delete(grant)
    if session:
        db.delete(session);audit(db,session.user_id,'session.revoked')
    db.commit()
    for name in ('sg_gate','sg_session','sg_csrf'):
        response.delete_cookie(name,path='/',secure=cookie_secure(request),httponly=name!='sg_csrf',samesite='strict')


@router.get('/sessions')
def sessions(request: Request, user=Depends(current), db=Depends(get_db)):
    return [{'id': s.token_hash, 'created': s.created, 'expires': s.expires, 'current': s.token_hash == request.state.session.token_hash} for s in db.scalars(select(Session).where(Session.user_id == user.id, Session.expires > time.time()))]


@router.delete('/sessions/{session_id}', status_code=204)
def revoke(session_id: str, user=Depends(current), db=Depends(get_db)):
    db.execute(delete(Session).where(Session.token_hash == session_id, Session.user_id == user.id))
    audit(db, user.id, 'session.revoked')
    db.commit()


@router.post('/reauth')
def reauth(body: Credentials, request: Request, user=Depends(current), db=Depends(get_db)):
    throttle(db, 'reauth:' + user.id, 10)
    if body.email != user.email or not verify(user.password_hash, body.password) or (user.totp_secret and not totp_check(db, user, body.code)):
        raise HTTPException(401, 'Verifica identità fallita')
    request.state.session.verified = int(time.time())
    db.commit()
    return {'ok': True}


@router.post('/totp/setup')
def setup_totp(request: Request, user=Depends(current), db=Depends(get_db)):
    recent(request)
    from .account_security import locked_user
    user=locked_user(db,user.id)
    if user.totp_secret:
        raise HTTPException(409, 'MFA già attiva')
    secret = pyotp.random_base32()
    user.totp_pending = cipher().encrypt(secret.encode()).decode()
    db.commit()
    return {'secret': secret, 'uri': pyotp.TOTP(secret).provisioning_uri(user.email, issuer_name='Sgancia')}


@router.post('/totp/confirm')
def confirm_totp(body: CodeIn, request: Request, user=Depends(current), db=Depends(get_db)):
    recent(request)
    throttle(db, 'totp:' + user.id, 10)
    from .account_security import locked_user,revoke_access
    user=locked_user(db,user.id)
    if not user.totp_pending or user.totp_secret:
        raise HTTPException(409, 'Configurazione non disponibile')
    secret = cipher().decrypt(user.totp_pending.encode()).decode()
    now = int(time.time()) // 30
    if not pyotp.TOTP(secret).verify(body.code, for_time=now * 30):
        raise HTTPException(400, 'Codice non valido')
    user.totp_secret, user.totp_pending, user.totp_last_counter = user.totp_pending, None, now
    codes = [token()[:20] for _ in range(10)]
    for code in codes:
        db.add(RecoveryCode(code_hash=digest(code), user_id=user.id))
    db.execute(delete(Session).where(Session.user_id == user.id, Session.token_hash != request.state.session.token_hash))
    revoke_access(db,user,request.state.session)
    audit(db, user.id, 'mfa.enabled')
    db.commit()
    return {'recovery_codes': codes}
