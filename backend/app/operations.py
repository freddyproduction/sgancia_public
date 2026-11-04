"""Global-only, sanitized operational controls. No Docker socket or arbitrary commands."""
import json,time
from typing import Literal
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import Field,SecretStr
from sqlalchemy import select,func,text,delete
from .models import Instance,Audit,User,Session,MaintenanceJob,ServiceHeartbeat,MailMessage
from .schemas import Strict
from .security import admin,audit,cipher,token
from .smtp_admin import require_admin_session
from .db import get_db,SessionLocal
from .runtime_policy import Policy,policy
router=APIRouter(prefix='/api/v1/admin/operations',tags=['Amministrazione operativa'])
SAFE_EVENTS=('installation.','user.','account.','session.','passkey.','installation_passkey.','mfa.','backup.','operations.','telegram.')

class BackupPolicy(Strict):
    enabled:bool=False
    interval_hours:int=Field(default=24,ge=1,le=168)
    keep_count:int=Field(default=14,ge=2,le=365)
    restore_check_every:int=Field(default=7,ge=1,le=90)
    restore_checks:bool=False

class Confirm(Strict):confirm:bool=False
class Telegram(Strict):
    enabled:bool=False
    mode:Literal['polling','webhook']='polling'
    username:str=Field(default='',max_length=32)
    rotate_webhook_secret:bool=False
    bot_token:SecretStr|None=None
    clear_token:bool=False
    max_messages_per_minute:int=Field(default=10,ge=1,le=60)


def instance_locked(db):return db.scalar(select(Instance).where(Instance.id==1).with_for_update().execution_options(populate_existing=True))


def schema_status(db):
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import inspect
    from pathlib import Path
    base=Path(__file__).resolve().parent.parent;config=Config(str(base/'alembic.ini'));config.set_main_option('script_location',str(base/'migrations'))
    expected=ScriptDirectory.from_config(config).get_current_head()
    actual=db.execute(text('SELECT version_num FROM alembic_version')).scalar() if inspect(db.bind).has_table('alembic_version') else None
    return {'version':'0.1.0-dev','database':actual,'expected':expected,'compatible':actual==expected}


@router.get('/policy')
def get_policy(user=Depends(admin),db=Depends(get_db)):return policy(db)


@router.put('/policy')
def save_policy(body:Policy,request:Request,user=Depends(admin),db=Depends(get_db)):
    row=instance_locked(db);user=require_admin_session(db,request,user)
    from .mail_delivery import configured
    if body.require_verified_email and (not user.email_verified or not configured(db)):raise HTTPException(422,'Prima verifica la tua email e configura SMTP, per evitare di bloccare gli accessi')
    if body.audit_retention_days and body.audit_retention_days<7:raise HTTPException(422,'Conserva almeno 7 giorni di audit oppure lascia 0 per non eliminare')
    row.runtime_policy=body.model_dump();audit(db,user.id,'installation.policy_changed');db.commit();return policy(db)


@router.get('/status')
def status(user=Depends(admin),db=Depends(get_db)):
    now=int(time.time());beats={b.service:{'at':b.at,'online':now-b.at<150} for b in db.scalars(select(ServiceHeartbeat))}
    jobs=list(db.scalars(select(MaintenanceJob).order_by(MaintenanceJob.created.desc(),MaintenanceJob.id).limit(30)))
    return {'schema':schema_status(db),'services':beats,'mail':{s:db.scalar(select(func.count()).select_from(MailMessage).where(MailMessage.status==s)) for s in ('pending','failed')},'jobs':[{'id':j.id,'kind':j.kind,'status':j.status,'created':j.created,'started':j.started,'finished':j.finished,'error':j.error,'result':j.result} for j in jobs]}


@router.get('/audit')
def events(request:Request,before:int|None=None,user=Depends(admin),db=Depends(get_db)):
    require_admin_session(db,request,user)
    q=select(Audit).order_by(Audit.at.desc(),Audit.id)
    if before is not None:q=q.where(Audit.at<before)
    rows=[]
    for row in db.scalars(q):
        if row.event.startswith(SAFE_EVENTS):rows.append({'id':row.id,'at':row.at,'event':row.event})
        if len(rows)==100:break
    return rows


@router.get('/backups')
def backups(user=Depends(admin),db=Depends(get_db)):return BackupPolicy.model_validate({k:v for k,v in (db.get(Instance,1).backup_policy or {}).items() if k!='started_at'}).model_dump()


@router.put('/backups')
def save_backups(body:BackupPolicy,request:Request,user=Depends(admin),db=Depends(get_db)):
    row=instance_locked(db);require_admin_session(db,request,user)
    row.backup_policy={**body.model_dump(),'started_at':int(time.time())};audit(db,user.id,'installation.backup_policy_changed');db.commit();return {'saved':True}


@router.post('/backup',status_code=202)
def queue_backup(body:Confirm,request:Request,user=Depends(admin),db=Depends(get_db)):
    instance_locked(db);require_admin_session(db,request,user)
    if not body.confirm:raise HTTPException(422,'Conferma la creazione del backup cifrato')
    # One pending manual backup per installation; serialize through the same instance row.
    existing=db.scalar(select(MaintenanceJob).where(MaintenanceJob.status.in_(['pending','running'])))
    if existing:return {'id':existing.id,'status':existing.status}
    job=MaintenanceJob(slot='manual:'+token(),kind='backup',requested_by=user.id);db.add(job);db.flush();audit(db,user.id,'backup.requested');db.commit();return {'id':job.id,'status':'pending'}


@router.get('/telegram')
def telegram(user=Depends(admin),db=Depends(get_db)):
    from .telegram_config import configuration
    from .models import TelegramState
    cfg=configuration(db);state=db.get(TelegramState,1)
    return {'token_set':bool(cfg.get('bot_token')),'enabled':cfg['enabled'],'mode':cfg['mode'],'username':cfg['username'],'webhook_secret_set':bool(cfg.get('webhook_secret')),'max_messages_per_minute':cfg['max_messages_per_minute'],'available':True,'ready':bool(cfg['enabled'] and state and state.generation==cfg['generation'] and state.username and not state.error),'error':state.error if state else '', 'status':'Avvio automatico con Sgancia; attivazione e arresto del bot da questo pannello'}


@router.put('/telegram')
def telegram_save(body:Telegram,request:Request,user=Depends(admin),db=Depends(get_db)):
    row=instance_locked(db);require_admin_session(db,request,user)
    from .telegram_config import configuration,seal
    from .models import TelegramState,TelegramGrant,TelegramAction,TelegramOutbox
    from urllib.parse import urlsplit
    cfg=configuration(db);previous=dict(cfg)
    if body.clear_token:cfg.pop('bot_token',None)
    if body.bot_token:
        value=body.bot_token.get_secret_value()
        import re
        if not re.fullmatch(r'[0-9]{5,20}:[A-Za-z0-9_-]{20,160}',value):raise HTTPException(422,'Formato token Telegram non valido')
        cfg['bot_token']=value
    name=body.username.strip().lstrip('@')
    import re
    if name and not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}',name):raise HTTPException(422,'Nome bot Telegram non valido, senza link o spazi')
    if body.enabled and not cfg.get('bot_token'):raise HTTPException(422,'Inserisci prima il token del bot')
    if body.enabled and body.mode=='webhook' and urlsplit(__import__('app.config',fromlist=['settings']).settings.public_origin).scheme!='https':raise HTTPException(422,'Il webhook richiede HTTPS pubblico; per localhost usa polling')
    cfg.update(enabled=body.enabled,mode=body.mode,username=name,max_messages_per_minute=body.max_messages_per_minute)
    if body.rotate_webhook_secret or not cfg.get('webhook_secret'):cfg['webhook_secret']=token()
    changed=any(previous.get(k)!=cfg.get(k) for k in ('enabled','bot_token','mode','username','webhook_secret'))
    if changed:
        cfg['generation']=previous['generation']+1
        db.execute(delete(TelegramGrant));db.execute(delete(TelegramAction))
        db.execute(delete(TelegramOutbox))
        state=db.get(TelegramState,1)
        if state:state.error='';state.username='';state.offset=0
    row.telegram_config=seal(cfg);audit(db,user.id,'installation.telegram_config_changed');db.commit();return {'saved':True,'available':True,'relink_required':changed}


@router.post('/revoke-sessions')
def revoke_sessions(body:Confirm,request:Request,user=Depends(admin),db=Depends(get_db)):
    require_admin_session(db,request,user)
    if not body.confirm:raise HTTPException(422,'Conferma la revoca')
    root=db.get(Instance,1).superadmin_id
    q=delete(Session).where(Session.token_hash!=request.state.session.token_hash)
    if user.id!=root:q=q.where(Session.user_id!=root)
    count=db.execute(q).rowcount;audit(db,user.id,'operations.sessions_revoked');db.commit();return {'revoked':count}


def heartbeat(service):
    with SessionLocal() as db:
        row=db.get(ServiceHeartbeat,service)
        if row:row.at=int(time.time())
        else:db.add(ServiceHeartbeat(service=service,at=int(time.time())))
        db.commit()
