import json,time
from typing import Literal
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import Field,SecretStr,model_validator
from sqlalchemy import select,func
from .schemas import Strict,Credentials
from .security import admin,recent,cipher,audit,throttle
from .models import Instance,MailMessage
from .db import get_db
from .mail_delivery import configuration,configured,enqueue
from .account_security import locked_user
from .passkeys import ensure_live_session
router=APIRouter(prefix='/api/v1/admin/installation',tags=['Impostazioni installazione'])

class SMTPIn(Strict):
    enabled:bool
    host:str=Field(default='',max_length=255)
    port:int=Field(default=587,ge=1,le=65535)
    mode:Literal['ssl','starttls']='starttls'
    username:str=Field(default='',max_length=254)
    password:SecretStr|None=Field(default=None)
    clear_password:bool=False
    sender:str=Field(default='',max_length=254)
    @model_validator(mode='after')
    def valid(self):
        for v in (self.host,self.username,self.sender):
            if '\r' in v or '\n' in v or '\x00' in v:raise ValueError('Valore SMTP non valido')
        if self.password and len(self.password.get_secret_value())>1000:raise ValueError('Password SMTP troppo lunga')
        if self.enabled:
            if not self.host.strip() or any(c.isspace() for c in self.host):raise ValueError('Indica un host SMTP senza spazi')
            self.sender=Credentials.email_valid(self.sender)
        return self


def require_admin_session(db,request,user):
    recent(request);user=locked_user(db,user.id);ensure_live_session(db,request,user)
    if not user.admin:raise HTTPException(403,'Solo l’amministratore globale può configurare l’installazione')
    return user


@router.get('/smtp')
def smtp_settings(user=Depends(admin),db=Depends(get_db)):
    cfg=configuration(db)
    return {**{k:cfg[k] for k in ('enabled','host','port','mode','username','sender')},'password_set':bool(cfg['password']),'source':'installation' if db.get(Instance,1).smtp_config else 'environment','pending':db.scalar(select(func.count()).select_from(MailMessage).where(MailMessage.status=='pending')),'failed':db.scalar(select(func.count()).select_from(MailMessage).where(MailMessage.status=='failed'))}


@router.put('/smtp')
def save_smtp(body:SMTPIn,request:Request,user=Depends(admin),db=Depends(get_db)):
    throttle(db,'smtp-config:'+user.id,10);instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update().execution_options(populate_existing=True))
    user=require_admin_session(db,request,user);previous=configuration(db)
    password='' if body.clear_password else (body.password.get_secret_value() if body.password and body.password.get_secret_value() else previous['password'])
    cfg={'enabled':body.enabled,'host':body.host.strip(),'port':body.port,'mode':body.mode,'username':body.username.strip(),'password':password,'sender':body.sender.strip()}
    instance.smtp_config=cipher().encrypt(json.dumps(cfg,ensure_ascii=False).encode()).decode();audit(db,user.id,'installation.smtp_changed');db.commit()
    return {'ok':True,'password_set':bool(password)}


@router.post('/smtp/test')
def test_smtp(request:Request,user=Depends(admin),db=Depends(get_db)):
    throttle(db,'smtp-test:'+user.id,3);require_admin_session(db,request,user)
    if not configured(db):raise HTTPException(503,'Salva e abilita prima una configurazione SMTP completa')
    enqueue(db,user.email,'Sgancia — prova invio email','Messaggio di prova richiesto dall’amministratore globale di Sgancia. Nessuna azione richiesta.',int(time.time())+1800)
    audit(db,user.id,'installation.smtp_test_requested');db.commit();return {'message':'Prova accodata verso l’email del tuo account. Controlla posta e stato della coda.'}
