"""Offline restore finalizer: never reconnect a restored Telegram authorization."""
from sqlalchemy import inspect,delete
from .db import SessionLocal
from .models import Instance,TelegramState,TelegramLink,TelegramGrant,TelegramUpdate,TelegramAction,TelegramOutbox
from .telegram_config import configuration,seal
from .security import token

def reset(db):
    if not inspect(db.bind).has_table('telegram_links'):return
    for cls in (TelegramOutbox,TelegramAction,TelegramGrant,TelegramUpdate,TelegramLink):db.execute(delete(cls))
    row=db.get(Instance,1)
    if row:
        cfg=configuration(db);cfg['enabled']=False;cfg['generation']+=1;cfg['webhook_secret']=token();row.telegram_config=seal(cfg)
    state=db.get(TelegramState,1)
    if state:state.username='';state.generation=0;state.offset=0;state.error=''
    db.commit()

if __name__=='__main__':
    try:
        with SessionLocal() as db:reset(db)
    except Exception:raise SystemExit('Revoca Telegram dopo ripristino non riuscita: lasciare il servizio fermo e verificare le chiavi originali.') from None
