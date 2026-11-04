"""Installation policy overrides; environment values remain the initial defaults."""
from pydantic import Field
from .schemas import Strict
from .config import settings
from .models import Instance
class Policy(Strict):
    session_hours:int=Field(default=24,ge=1,le=168)
    require_verified_email:bool=False
    uploads_enabled:bool=True
    attachment_max_bytes:int=Field(default=10485760,ge=1024,le=20971520)
    attachment_group_bytes:int=Field(default=104857600,ge=1024,le=10737418240)
    attachment_max_count:int=Field(default=20,ge=1,le=100)
    invitation_days:int=Field(default=7,ge=1,le=30)
    guest_allow_unlimited:bool=True
    guest_days:int=Field(default=365,ge=1,le=365)
    guest_max_uses:int=Field(default=100000,ge=1,le=100000)
    audit_retention_days:int=Field(default=0,ge=0,le=3650)


def policy(db):
    instance=db.get(Instance,1)
    defaults={k:getattr(settings,k) for k in ('session_hours','attachment_max_bytes','attachment_group_bytes','attachment_max_count')}
    return Policy.model_validate({**defaults,**(instance.runtime_policy or {} if instance else {})}).model_dump()


def check_verified(db,user):
    if policy(db)['require_verified_email'] and not user.email_verified:
        from .account_security import issue_token
        from .mail_delivery import configured
        from fastapi import HTTPException
        # A successful proof of password/passkey is required before reaching this helper.
        if configured(db):issue_token(db,user,'verify');db.commit()
        raise HTTPException(403,'Verifica prima la tua email: controlla il messaggio ricevuto e riprova l’accesso')
