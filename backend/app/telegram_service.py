"""Optional Compose process. A PostgreSQL advisory lock keeps one polling consumer."""
import time
from sqlalchemy import text
from .db import engine
from .operations import heartbeat
from .telegram_bot import tick
if __name__=='__main__':
    while True:
        try:
            with engine.connect().execution_options(isolation_level='AUTOCOMMIT') as leader:
                if not leader.execute(text('SELECT pg_try_advisory_lock(77110211)')).scalar():time.sleep(10);continue
                try:
                    while True:
                        leader.execute(text('SELECT 1'));heartbeat('telegram')
                        try:tick()
                        except Exception:print('Servizio Telegram temporaneamente non disponibile',flush=True)
                        time.sleep(2)
                finally:leader.execute(text('SELECT pg_advisory_unlock(77110211)'))
        except Exception:print('Collegamento servizio Telegram da riprovare',flush=True);time.sleep(10)
