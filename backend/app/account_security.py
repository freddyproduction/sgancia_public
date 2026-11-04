import time
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import Field,field_validator
from sqlalchemy import select,delete,update
from .schemas import Strict,Credentials
from .models import User,Session,RecoveryCode,AccountToken,Instance,GateGrant,Passkey,WebChallenge
from .db import get_db
from .security import current,admin,recent,verify,passwords,cipher,token,digest,audit,throttle,peer
from .config import settings
from .mail_delivery import configured,enqueue
router=APIRouter(prefix='/api/v1',tags=['Sicurezza account'])


def locked_user(db,uid):return db.scalar(select(User).where(User.id==uid).with_for_update().execution_options(populate_existing=True))


def revoke_access(db,user,session=None):
    user.auth_version+=1
    condition=[Session.user_id==user.id]
    if session:
        condition.append(Session.token_hash!=session.token_hash);session.auth_version=user.auth_version;session.verified=int(time.time())
    db.execute(delete(Session).where(*condition))
    db.execute(delete(WebChallenge).where(WebChallenge.user_id==user.id))
    db.execute(update(AccountToken).where(AccountToken.user_id==user.id).values(used=True))


def require_password(db,user,password,code=''):
    from .auth import totp_check
    if not verify(user.password_hash,password) or (user.totp_secret and not totp_check(db,user,code)):raise HTTPException(401,'Password o codice di verifica non valido')


def issue_token(db,user,purpose,queue=True):
    clear=token();expires=int(time.time())+(86400 if purpose=='verify' else 1800)
    db.execute(update(AccountToken).where(AccountToken.user_id==user.id,AccountToken.purpose==purpose).values(used=True))
    db.add(AccountToken(token_hash=digest(clear),user_id=user.id,purpose=purpose,email=user.email,auth_version=user.auth_version,expires=expires))
    url=settings.public_origin+'/account-action#'+purpose+'.'+clear
    if queue:enqueue(db,user.email,'Sgancia — '+('verifica email' if purpose=='verify' else 'recupero password'),'Apri questo link e conferma l’operazione entro '+('24 ore' if purpose=='verify' else '30 minuti')+':\n'+url+'\n\nSe non hai richiesto questa operazione, ignora il messaggio. Non condividere il link.',expires,token_hash=digest(clear))
    return url


class Proof(Strict):
    password:str=Field(min_length=1,max_length=128)
    code:str=Field(default='',max_length=100)

class PasswordChange(Proof):
    new_password:str=Field(min_length=12,max_length=128)


@router.put('/auth/password')
def change_password(body:PasswordChange,request:Request,user=Depends(current),db=Depends(get_db)):
    throttle(db,'password:'+user.id,10);user=locked_user(db,user.id);require_password(db,user,body.password,body.code)
    user.password_hash=passwords.hash(body.new_password);revoke_access(db,user,request.state.session)
    audit(db,user.id,'password.changed');db.commit();return {'ok':True,'other_sessions_revoked':True}


@router.post('/auth/mfa/recovery-codes')
def renew_codes(body:Proof,request:Request,user=Depends(current),db=Depends(get_db)):
    throttle(db,'mfa-manage:'+user.id,10);user=locked_user(db,user.id)
    if not user.totp_secret:raise HTTPException(409,'Autenticazione a due fattori non attiva')
    require_password(db,user,body.password,body.code)
    codes=[token()[:20] for _ in range(10)];db.execute(delete(RecoveryCode).where(RecoveryCode.user_id==user.id))
    for code in codes:db.add(RecoveryCode(user_id=user.id,code_hash=digest(code)))
    revoke_access(db,user,request.state.session);audit(db,user.id,'mfa.recovery_renewed');db.commit();return {'recovery_codes':codes}


@router.post('/auth/mfa/disable')
def disable_mfa(body:Proof,request:Request,user=Depends(current),db=Depends(get_db)):
    throttle(db,'mfa-manage:'+user.id,10);user=locked_user(db,user.id)
    if not user.totp_secret:raise HTTPException(409,'Autenticazione a due fattori non attiva')
    require_password(db,user,body.password,body.code)
    user.totp_secret=None;user.totp_pending=None;user.totp_last_counter=-1
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id==user.id));revoke_access(db,user,request.state.session)
    audit(db,user.id,'mfa.disabled');db.commit();return {'ok':True}


@router.post('/auth/mfa/rotate')
def rotate_mfa(body:Proof,request:Request,user=Depends(current),db=Depends(get_db)):
    import pyotp
    throttle(db,'mfa-manage:'+user.id,10);user=locked_user(db,user.id)
    if not user.totp_secret:raise HTTPException(409,'Autenticazione a due fattori non attiva')
    require_password(db,user,body.password,body.code)
    secret=pyotp.random_base32();user.totp_pending=cipher().encrypt(secret.encode()).decode()
    request.state.session.verified=int(time.time());audit(db,user.id,'mfa.rotation_started');db.commit()
    return {'secret':secret,'uri':pyotp.TOTP(secret).provisioning_uri(user.email,issuer_name='Sgancia')}


@router.post('/auth/mfa/rotate/confirm')
def confirm_rotation(body:Proof,request:Request,user=Depends(current),db=Depends(get_db)):
    import pyotp
    throttle(db,'mfa-rotate:'+user.id,10);recent(request);user=locked_user(db,user.id)
    if not user.totp_secret or not user.totp_pending:raise HTTPException(409,'Rotazione non disponibile')
    if not verify(user.password_hash,body.password):raise HTTPException(401,'Password non valida')
    secret=cipher().decrypt(user.totp_pending.encode()).decode();counter=int(time.time())//30
    if not pyotp.TOTP(secret).verify(body.code,for_time=counter*30):raise HTTPException(401,'Codice del nuovo autenticatore non valido')
    user.totp_secret=user.totp_pending;user.totp_pending=None;user.totp_last_counter=counter
    db.execute(delete(RecoveryCode).where(RecoveryCode.user_id==user.id));codes=[token()[:20] for _ in range(10)]
    for code in codes:db.add(RecoveryCode(user_id=user.id,code_hash=digest(code)))
    revoke_access(db,user,request.state.session);audit(db,user.id,'mfa.rotated');db.commit();return {'recovery_codes':codes}


class EmailIn(Strict):
    email:str=Field(min_length=3,max_length=254)
    @field_validator('email')
    @classmethod
    def valid(cls,v):return Credentials.email_valid(v)

class EmailChange(EmailIn,Proof):pass


@router.put('/auth/email')
def email_change(body:EmailChange,request:Request,user=Depends(current),db=Depends(get_db)):
    from sqlalchemy.exc import IntegrityError
    throttle(db,'email-change:'+user.id,5);user=locked_user(db,user.id);require_password(db,user,body.password,body.code)
    if body.email==user.email:raise HTTPException(409,'L’account usa già questa email')
    user.email=body.email;user.email_verified=False;revoke_access(db,user,request.state.session)
    try:
        db.flush()
        if configured(db):issue_token(db,user,'verify')
        audit(db,user.id,'email.changed');db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Indirizzo non disponibile') from None
    return {'ok':True,'email_verified':False}


@router.get('/auth/email/status')
def email_status(user=Depends(current),db=Depends(get_db)):
    return {'verified':user.email_verified,'delivery_available':configured(db)}


@router.post('/auth/email/send-verification')
def resend(request:Request,user=Depends(current),db=Depends(get_db)):
    throttle(db,'verify-email:'+user.id,3,300)
    if not configured(db):raise HTTPException(503,'Invio email non configurato: chiedi all’amministratore del server')
    user=locked_user(db,user.id)
    if user.email_verified:return {'ok':True}
    issue_token(db,user,'verify');db.commit();return {'ok':True}


@router.post('/auth/password/forgot')
def forgot(body:EmailIn,request:Request,db=Depends(get_db)):
    throttle(db,'forgot-ip:'+peer(request),10);throttle(db,'forgot-email:'+body.email,3)
    user=db.scalar(select(User).where(User.email==body.email).with_for_update())
    if user and user.status=='active' and user.email_verified and configured(db):issue_token(db,user,'reset');db.commit()
    return {'message':'Se l’account è idoneo e l’invio email è configurato, riceverai le istruzioni. In alternativa contatta l’amministratore del server.'}


class TokenIn(Strict):
    token:str=Field(min_length=20,max_length=100)

class ResetIn(TokenIn):
    new_password:str=Field(min_length=12,max_length=128)
    code:str=Field(default='',max_length=100)


def consume(db,clear,purpose):
    initial=db.get(AccountToken,digest(clear))
    if not initial:raise HTTPException(400,'Link non valido o scaduto')
    user=locked_user(db,initial.user_id)
    row=db.scalar(select(AccountToken).where(AccountToken.token_hash==digest(clear)).with_for_update().execution_options(populate_existing=True))
    if row.used or row.purpose!=purpose or row.expires<=time.time() or row.email!=user.email or row.auth_version!=user.auth_version or user.status!='active':raise HTTPException(400,'Link non valido o scaduto')
    row.used=True;return user


@router.post('/auth/email/verify')
def confirm_email(body:TokenIn,request:Request,db=Depends(get_db)):
    throttle(db,'verify-token:'+peer(request),20)
    user=consume(db,body.token,'verify');user.email_verified=True;audit(db,user.id,'email.verified');db.commit();return {'ok':True}


@router.post('/auth/password/reset')
def reset_password(body:ResetIn,request:Request,db=Depends(get_db)):
    from .auth import totp_check
    throttle(db,'reset-token:'+peer(request),10);user=consume(db,body.token,'reset')
    if user.totp_secret and not totp_check(db,user,body.code):raise HTTPException(401,'Serve il codice MFA o un codice di recupero valido')
    user.password_hash=passwords.hash(body.new_password);revoke_access(db,user)
    audit(db,user.id,'password.recovered');db.commit();return {'ok':True,'login_required':True}


class GatePolicy(Strict):enabled:bool


@router.get('/admin/access-policy')
def access_policy(user=Depends(admin),db=Depends(get_db)):
    return {'gate_enabled':db.get(Instance,1).gate_enabled,'smtp_configured':configured(db)}


@router.put('/admin/access-policy')
def change_gate(body:GatePolicy,request:Request,user=Depends(admin),db=Depends(get_db)):
    recent(request);instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update().execution_options(populate_existing=True))
    user=locked_user(db,user.id)
    from .passkeys import ensure_live_session
    ensure_live_session(db,request,user)
    if not user.admin:raise HTTPException(403,'Solo l’amministratore globale può modificare il gate')
    if instance.gate_enabled==body.enabled:return {'ok':True,'login_required':False}
    instance.gate_enabled=body.enabled;instance.gate_version+=1
    db.execute(delete(GateGrant));db.execute(delete(Session));audit(db,user.id,'gate.enabled' if body.enabled else 'gate.disabled');db.commit()
    return {'ok':True,'login_required':True}
