import re,secrets,time
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import Field,field_validator
from sqlalchemy import select,delete
from .schemas import Strict
from .db import get_db
from .models import Instance,TelegramState,TelegramLink,TelegramGrant,TelegramAction,TelegramOutbox
from .security import current,recent,token,digest,audit
from .smtp_admin import require_admin_session
from .passkeys import ensure_live_session
from .telegram_config import configuration,seal
router=APIRouter(prefix='/api/v1/telegram',tags=['Account Telegram'])

class LinkIn(Strict):
    telegram_id:str=Field(min_length=1,max_length=16)
    allow_private:bool=False
    notifications:bool=False
    @field_validator('telegram_id')
    @classmethod
    def valid_id(cls,value):
        if not re.fullmatch(r'[0-9]{1,16}',value) or not 0<int(value)<2**52:raise ValueError('Inserisci l’ID numerico del tuo account Telegram')
        return value


def link_live(db,link,cfg,user):
    instance=db.get(Instance,1)
    return bool(link and user and user.status=='active' and cfg['enabled'] and link.generation==cfg['generation'] and link.auth_version==user.auth_version and instance and link.gate_version==instance.gate_version)


@router.get('/account')
def account(user=Depends(current),db=Depends(get_db)):
    cfg=configuration(db);state=db.get(TelegramState,1);link=db.get(TelegramLink,user.id)
    ready=bool(cfg['enabled'] and state and state.generation==cfg['generation'] and state.username and not state.error)
    return {'enabled':cfg['enabled'],'ready':ready,'bot_url':('https://t.me/'+state.username) if ready else None,'telegram_id':str(link.telegram_id) if link else '', 'linked':link_live(db,link,cfg,user),'allow_private':link.allow_private if link else False,'notifications':link.notifications if link else False}


@router.post('/link')
def issue_link(body:LinkIn,request:Request,user=Depends(current),db=Depends(get_db)):
    recent(request)
    instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update(read=True).execution_options(populate_existing=True))
    from .account_security import locked_user
    user=locked_user(db,user.id);ensure_live_session(db,request,user)
    cfg=configuration(db);state=db.get(TelegramState,1)
    if not cfg['enabled'] or not state or state.generation!=cfg['generation'] or not state.username or state.error:raise HTTPException(409,'Bot non pronto: chiedi all’amministratore di configurare e abilitare Telegram nel pannello globale')
    other=db.scalar(select(TelegramLink).where(TelegramLink.telegram_id==int(body.telegram_id),TelegramLink.user_id!=user.id))
    if other:raise HTTPException(409,'Questo ID è già collegato: scollega prima il precedente account dal web')
    db.execute(delete(TelegramGrant).where(TelegramGrant.user_id==user.id))
    clear=token();db.add(TelegramGrant(token_hash=digest(clear),user_id=user.id,telegram_id=int(body.telegram_id),auth_version=user.auth_version,gate_version=instance.gate_version,generation=cfg['generation'],allow_private=body.allow_private,notifications=body.notifications,expires=int(time.time())+300));audit(db,user.id,'telegram.link_requested');db.commit()
    return {'url':'https://t.me/'+state.username+'?start='+clear,'expires_in':300}


def revoke(db,uid):
    for cls in (TelegramAction,TelegramGrant,TelegramOutbox):db.execute(delete(cls).where(cls.user_id==uid))
    db.execute(delete(TelegramLink).where(TelegramLink.user_id==uid))


@router.delete('/account',status_code=204)
def unlink(request:Request,user=Depends(current),db=Depends(get_db)):
    recent(request)
    from .account_security import locked_user
    user=locked_user(db,user.id);ensure_live_session(db,request,user)
    revoke(db,user.id);audit(db,user.id,'telegram.unlinked');db.commit()


@router.post('/webhook')
async def webhook(request:Request,db=Depends(get_db)):
    cfg=configuration(db)
    if not cfg['enabled'] or cfg['mode']!='webhook' or not cfg.get('webhook_secret') or not secrets.compare_digest(request.headers.get('x-telegram-bot-api-secret-token','').encode(),cfg['webhook_secret'].encode()):raise HTTPException(404,'Endpoint non disponibile')
    body=bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body)>262144:raise HTTPException(413,'Aggiornamento troppo grande')
    import json
    try:data=json.loads(body)
    except Exception:raise HTTPException(400,'Aggiornamento non valido') from None
    from .telegram_bot import enqueue_update
    enqueue_update(db,cfg,data);db.commit();return {'ok':True}
