"""Encrypted, expiring outbox. No email content, address or SMTP errors in logs."""
import json,smtplib,ssl,time,logging
from email.message import EmailMessage
from sqlalchemy import select,delete
from .config import settings
from .models import MailMessage,AccountToken,Instance
from .security import cipher

def configuration(db=None):
    instance=db.get(Instance,1) if db is not None else None
    if instance and instance.smtp_config:return json.loads(cipher().decrypt(instance.smtp_config.encode()))
    return {'enabled':bool(settings.smtp_host and settings.smtp_sender),'host':settings.smtp_host,'port':settings.smtp_port,'mode':settings.smtp_mode,'username':settings.smtp_username,'password':settings.smtp_password,'sender':settings.smtp_sender}

def configured(db=None):
    config=configuration(db)
    return bool(config['enabled'] and config['host'] and config['sender'])

def enqueue(db,email,subject,body,expires,token_hash=None,notification_id=None,notification_ids=None):
    payload=cipher().encrypt(json.dumps({'email':email,'subject':subject,'body':body,'notification_id':notification_id,'notification_ids':notification_ids}).encode()).decode()
    db.add(MailMessage(payload=payload,expires=expires,token_hash=token_hash))

def send(payload):
    config=payload.pop('_smtp',None) or configuration()
    message=EmailMessage();message['From']=config['sender'];message['To']=payload['email'];message['Subject']=payload['subject'];message.set_content(payload['body'])
    cls=smtplib.SMTP_SSL if config['mode']=='ssl' else smtplib.SMTP
    options={'host':config['host'],'port':config['port'],'timeout':15}
    if config['mode']=='ssl':options['context']=ssl.create_default_context()
    with cls(**options) as smtp:
        if config['mode']=='starttls':smtp.starttls(context=ssl.create_default_context())
        if config['username']:smtp.login(config['username'],config['password'])
        smtp.send_message(message)

def deliver_one(db):
    now=int(time.time())
    for expired in db.scalars(select(MailMessage).where(MailMessage.expires<=now).with_for_update(skip_locked=True)):
        try:
            payload=json.loads(cipher().decrypt(expired.payload.encode()))
            if payload.get('notification_id'):
                from .models import Notification
                notice=db.get(Notification,payload['notification_id'])
                if notice:
                    for n in db.scalars(select(Notification).where(Notification.id.in_([notice.id]+(payload.get('notification_ids') or [])),Notification.user_id==notice.user_id)):n.email_status='expired'
        except Exception:pass  # Expiry must also remove corrupt/empty payloads.
        db.delete(expired)
    db.execute(delete(AccountToken).where(AccountToken.expires<=now))
    if not configured(db):db.commit();return False
    row=db.scalar(select(MailMessage).where(MailMessage.status=='pending',MailMessage.next_attempt<=now).order_by(MailMessage.next_attempt,MailMessage.id).with_for_update(skip_locked=True).limit(1))
    if not row:db.commit();return False
    if row.token_hash:
        grant=db.get(AccountToken,row.token_hash)
        if not grant or grant.used or grant.expires<=now:db.delete(row);db.commit();return True
    try:
        payload=json.loads(cipher().decrypt(row.payload.encode()))
        nid=payload.pop('notification_id',None)
        related=payload.pop('notification_ids',None) or []
        if nid:
            from .notifications import email_allowed
            from .models import Notification
            recipient=email_allowed(db,nid)
            notice=db.get(Notification,nid)
            if not recipient:
                if notice:
                    notice.email_status='cancelled'
                    for item in db.scalars(select(Notification).where(Notification.id.in_(related),Notification.user_id==notice.user_id)):item.email_status='cancelled'
                db.delete(row);db.commit();return True
            payload['email']=recipient.email
        payload['_smtp']=configuration(db);send(payload)
        if nid:
            notice.email_status='sent'
            for item in db.scalars(select(Notification).where(Notification.id.in_(related),Notification.user_id==notice.user_id)):item.email_status='sent'
    except Exception:
        row.attempts+=1;row.next_attempt=now+min(3600,30*2**min(row.attempts,7))
        if row.attempts>=8:
            row.status='failed';row.payload=''
            if 'nid' in locals() and nid and 'notice' in locals() and notice:
                notice.email_status='failed'
                for item in db.scalars(select(Notification).where(Notification.id.in_(related),Notification.user_id==notice.user_id)):item.email_status='failed'
        logging.warning('Sgancia: invio email non riuscito, messaggio %s',row.id)
    else:db.delete(row)
    db.commit();return True

if __name__=='__main__':
    from .db import SessionLocal
    last_heartbeat=0
    while True:
        try:
            if time.time()-last_heartbeat>30:
                from .operations import heartbeat
                heartbeat('mail');last_heartbeat=time.time()
            with SessionLocal() as db:worked=deliver_one(db)
        except Exception:logging.warning('Sgancia: servizio email temporaneamente non disponibile');worked=False
        time.sleep(1 if worked else 30)
