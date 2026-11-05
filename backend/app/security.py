import hashlib
import secrets
import time
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from cryptography.fernet import Fernet
from fastapi import HTTPException, Request, Depends
from sqlalchemy import select, delete, update
from .config import settings,normalize_origin,LOOPBACK_HOSTS
from .db import get_db
from .models import Instance, Session, User, GateGrant, RateBucket, Audit

passwords = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)
DUMMY = passwords.hash(secrets.token_urlsafe(32))


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def token():
    return secrets.token_urlsafe(32)


def verify(encoded, clear):
    try:
        return passwords.verify(encoded, clear)
    except (VerificationError, InvalidHashError):
        return False


def cipher():
    if not settings.encryption_key:
        raise HTTPException(503, 'Chiave di cifratura non configurata')
    return Fernet(settings.encryption_key.encode())


def audit(db, actor, event, resource=None):
    db.add(Audit(actor=actor, event=event, resource=resource))


def throttle(db, name: str, limit=10, seconds=300):
    # One atomic UPSERT shared by all API workers, including failed requests.
    now = int(time.time())
    key = digest(name + ':' + str(now // seconds))
    dialect = db.bind.dialect.name
    if dialect == 'postgresql':
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    stmt = insert(RateBucket).values(key=key, hits=1, window=now)
    stmt = stmt.on_conflict_do_update(index_elements=['key'], set_={'hits': RateBucket.hits + 1}).returning(RateBucket.hits)
    hits = db.execute(stmt).scalar_one()
    db.execute(delete(RateBucket).where(RateBucket.window < now - 86400))
    db.commit()
    if hits > limit:
        raise HTTPException(429, 'Troppi tentativi. Riprova più tardi.', headers={'Retry-After': str(seconds)})


def peer(request):
    # Forwarded IPs accepted only by uvicorn's explicitly trusted proxy setting.
    return request.client.host if request.client else 'unknown'


def gate(request: Request, db=Depends(get_db)):
    instance = db.get(Instance, 1)
    if instance and not instance.gate_enabled:return instance
    grant = db.get(GateGrant, digest(request.cookies.get('sg_gate', '')))
    if not instance or not grant or grant.expires <= time.time() or grant.version != instance.gate_version:
        raise HTTPException(403, 'Chiave di accesso richiesta')
    if grant.credential_id:
        from .models import InstallationPasskey
        key=db.get(InstallationPasskey,grant.credential_id);owner=db.get(User,key.user_id) if key else None
        if not key or key.gate_version!=instance.gate_version or not owner or owner.status!='active' or key.auth_version!=owner.auth_version:raise HTTPException(403,'Passkey di installazione revocata: usa la chiave globale')
    return instance


def current(request: Request, db=Depends(get_db), instance=Depends(gate)):
    session = db.get(Session, digest(request.cookies.get('sg_session', '')))
    if not session or session.expires <= time.time() or session.gate_version != instance.gate_version:
        raise HTTPException(401, 'Sessione scaduta o non valida')
    user = db.get(User, session.user_id)
    if not user or user.status != 'active' or user.deleted or session.auth_version!=user.auth_version:
        raise HTTPException(401, 'Account non disponibile')
    if request.method not in ('GET', 'HEAD', 'OPTIONS'):
        if not secrets.compare_digest(session.csrf_hash, digest(request.headers.get('X-CSRF-Token', ''))):
            raise HTTPException(403, 'Verifica CSRF fallita')
    request.state.session = session
    return user


def admin(request:Request,user=Depends(current),db=Depends(get_db)):
    from sqlalchemy import select
    db.scalar(select(Instance).where(Instance.id==1).with_for_update().execution_options(populate_existing=True))
    from .account_security import locked_user
    from .passkeys import ensure_live_session
    user=locked_user(db,user.id);ensure_live_session(db,request,user)
    if not user or not user.admin or user.status!='active':raise HTTPException(403,'Permesso amministratore richiesto')
    from .admin_permissions import check_request
    check_request(db,user,request)
    return user


def recent(request):
    if request.state.session.verified < time.time() - 300:
        raise HTTPException(403, 'Conferma nuovamente la tua identità')


def cookie_secure(request):
    # HTTPS cookies always keep Secure, regardless of LAN or legacy local settings.
    if request.url.scheme=='https':return True
    try:origin=normalize_origin(str(request.url.replace(path='',query='',fragment='')))
    except ValueError:return True
    if origin not in settings.origins:return True
    return not (request.url.hostname in LOOPBACK_HOSTS or origin in settings.http_lan_origins)


def set_cookie(response, name, value, max_age, request):
    response.set_cookie(name, value, max_age=max_age, httponly=name != 'sg_csrf', secure=cookie_secure(request), samesite='strict', path='/')
