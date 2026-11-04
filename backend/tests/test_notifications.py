import json,time
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import Notification,NotificationPreference,User,Participant,Expense,MailMessage,Settlement,SettlementEvent,Group
from app.notifications import run_user,Preferences,period
from app.mail_delivery import deliver_one
from app.security import cipher
from conftest import login
from test_api import group,expense
import pytest


def seed(client,gid,ids,secret=False,key='notify-expense'):
    r=client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,secret),headers={'Idempotency-Key':key});assert r.status_code==201,r.text
    return r.json()['id']


def config(client,gid='',**kw):
    return client.put('/api/v1/notifications/preferences'+('?group_id='+gid if gid else ''),json={**Preferences().model_dump(),**kw})


def arm(database,uid,gid='',**kw):
    with database() as db:
        p=db.get(NotificationPreference,(uid,gid))
        if not p:p=NotificationPreference(user_id=uid,scope=gid);db.add(p)
        p.config={**Preferences().model_dump(),**kw};p.started_at=int(time.time())-8*86400
        db.get(User,uid).email_verified=True;db.commit()


def tick(database,uid='alice',now=None):
    with database() as db:run_user(db,uid,now)


def smtp(monkeypatch):
    import app.mail_delivery as mail
    monkeypatch.setattr(mail,'configuration',lambda db=None:{'enabled':True,'host':'smtp.example.org','sender':'qa@example.org'})
    sent=[];monkeypatch.setattr(mail,'send',lambda payload:sent.append(payload));return sent


def test_transactional_inbox_and_private_counts(client,database):
    login(client);gid,ids=group(client);seed(client,gid,ids,True)
    with TestClient(app,base_url='http://localhost:8088') as bob,TestClient(app,base_url='http://localhost:8088') as carol:
        login(bob,'bob');login(carol,'carol')
        a=client.get('/api/v1/notifications').json();b=bob.get('/api/v1/notifications').json();c=carol.get('/api/v1/notifications').json()
        assert a['unread']==b['unread']==1 and c=={'unread':0,'items':[]}
        n=b['items'][0];assert 'Regalo' not in json.dumps(n) and n['kind']=='expense'
        assert carol.post('/api/v1/notifications/'+n['id']+'/read').status_code==404
        assert bob.post('/api/v1/notifications/'+n['id']+'/read').status_code==200
        assert bob.get('/api/v1/notifications').json()['unread']==0
    seed(client,gid,ids,True)
    assert client.get('/api/v1/notifications').json()['unread']==1  # request retry did not duplicate
    with database() as db:
        e=db.get(Expense,client.get(f'/api/v1/groups/{gid}/expenses').json()[0]['id'])
        e.audience=[ids['alice']];db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.get('/api/v1/notifications').json()=={'unread':0,'items':[]}


def test_preferences_inheritance_and_global_off(client,database):
    login(client);gid,ids=group(client)
    assert config(client,events=False).status_code==200
    seed(client,gid,ids);assert client.get('/api/v1/notifications').json()['unread']==0
    assert config(client,gid,events=True).status_code==200
    seed(client,gid,ids,key='notify-next-expense');assert client.get('/api/v1/notifications').json()['unread']==1
    assert config(client,enabled=False).status_code==200
    assert client.get('/api/v1/notifications').json()['unread']==0
    assert client.delete('/api/v1/notifications/preferences?group_id='+gid).status_code==200
    assert client.get('/api/v1/notifications/preferences?group_id='+gid).json()['override'] is False
    assert config(client,gid,threshold=0).status_code==422
    with TestClient(app,base_url='http://localhost:8088') as outsider:
        login(outsider,'dave');assert outsider.get('/api/v1/notifications/preferences?group_id='+gid).status_code==404
        assert config(outsider,gid).status_code==404


def test_transaction_rollback_has_no_notifications(client,database):
    from app.models import ExpenseRevision
    login(client);gid,ids=group(client);eid=seed(client,gid,ids)
    with database() as db:
        count=db.scalar(select(func.count()).select_from(Notification))
        db.add(ExpenseRevision(expense_id=eid,version=2,actor_id='alice',snapshot={'audience':None}));db.flush();db.rollback()
    with database() as db:assert db.scalar(select(func.count()).select_from(Notification))==count


def test_reveal_does_not_reveal_original_notifications(client,database):
    login(client);gid,ids=group(client);eid=seed(client,gid,ids,True)
    assert client.post(f'/api/v1/groups/{gid}/expenses/{eid}/reveal',headers={'If-Match':'1'}).status_code==200
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');r=carol.get('/api/v1/notifications').json();assert r['unread']==1
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id=='carol',Notification.event_key==f'expense:{eid}:1'))==0


def test_reminders_threshold_currency_and_cadence(client,database):
    login(client);gid,ids=group(client)
    body=expense(ids,True);body['payers']={ids['bob']:'100'}
    assert client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'reminder-qa-expense'}).status_code==201
    arm(database,'bob',reminder='daily',summary='weekly',threshold=100)
    tick(database,'bob');tick(database,'bob')
    with database() as db:
        ns=list(db.scalars(select(Notification).where(Notification.user_id=='bob')))
        assert len([n for n in ns if n.kind=='reminder'])==0 # Bob paid more than his share
    arm(database,'alice',reminder='daily',summary='weekly',threshold=100)
    tick(database);tick(database)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id=='alice',Notification.kind=='reminder'))==1
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id=='alice',Notification.kind=='summary'))==1
    tick(database,now=int(time.time())+86400)
    with database() as db:assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id=='alice',Notification.kind=='reminder'))==2
    arm(database,'carol',reminder='daily',threshold=1);tick(database,'carol')
    with database() as db:assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id=='carol',Notification.kind=='reminder'))==0


def test_schedule_waits_until_next_slot(client,database):
    login(client);gid,ids=group(client);seed(client,gid,ids)
    config(client,summary='daily',hour=(time.gmtime().tm_hour+1)%24)
    tick(database)
    with database() as db:assert db.scalar(select(func.count()).select_from(Notification).where(Notification.kind=='summary'))==0
    tick(database,now=int(time.time())+86400)
    with database() as db:assert db.scalar(select(func.count()).select_from(Notification).where(Notification.kind=='summary'))==1
    assert period(4*86400+9*3600,'weekly',9)==0 # Monday 1970-01-05


def test_email_opt_in_generic_dedup_and_sent_state(client,database,monkeypatch):
    sent=smtp(monkeypatch);login(client);gid,ids=group(client);seed(client,gid,ids,True)
    tick(database)
    with database() as db:assert db.scalar(select(func.count()).select_from(MailMessage))==0
    arm(database,'alice',email=True);tick(database);tick(database)
    with database() as db:
        assert db.scalar(select(func.count()).select_from(MailMessage))==1
        mail=db.scalar(select(MailMessage));payload=json.loads(cipher().decrypt(mail.payload.encode()))
        assert all(word not in payload['body']+payload['subject'] for word in ['Regalo','Weekend','100','Bob'])
        assert deliver_one(db)
    assert len(sent)==1
    r=client.get('/api/v1/notifications').json();assert len(r['items'])==1 and r['items'][0]['email_status']=='sent'


@pytest.mark.parametrize('revocation',['preference','membership','audience','verification','suspended'])
def test_queued_email_rechecks_authorization(client,database,monkeypatch,revocation):
    sent=smtp(monkeypatch);login(client);gid,ids=group(client);eid=seed(client,gid,ids,True)
    arm(database,'bob',email=True);tick(database,'bob')
    with database() as db:
        assert db.scalar(select(func.count()).select_from(MailMessage))==1
        if revocation=='preference':db.get(NotificationPreference,('bob','')).config=Preferences().model_dump()
        if revocation=='membership':db.get(Participant,ids['bob']).active=False
        if revocation=='audience':db.get(Expense,eid).audience=[ids['alice']]
        if revocation=='verification':db.get(User,'bob').email_verified=False
        if revocation=='suspended':db.get(User,'bob').status='suspended'
        db.commit();assert deliver_one(db)
    assert sent==[]


def test_mail_retry_cap_and_disable(client,database,monkeypatch):
    smtp(monkeypatch);login(client);gid,ids=group(client);seed(client,gid,ids)
    arm(database,'alice',email=True);tick(database)
    import app.mail_delivery as mail
    def fail(payload):raise RuntimeError('private smtp error')
    monkeypatch.setattr(mail,'send',fail)
    with database() as db:
        for i in range(8):
            row=db.scalar(select(MailMessage));row.next_attempt=0;db.commit();assert deliver_one(db)
        row=db.scalar(select(MailMessage));assert row.status=='failed' and row.payload==''
        assert db.scalar(select(Notification).where(Notification.user_id=='alice',Notification.kind=='expense')).email_status=='failed'


def test_payment_and_group_events_private(client,database):
    from app.models import GroupOperation
    login(client);gid,ids=group(client)
    with database() as db:
        s=Settlement(group_id=gid,sender=ids['alice'],recipient=ids['bob'],amount=100,audience=[ids['alice'],ids['bob']],author_id='alice',status='pending');db.add(s);db.flush()
        db.add(SettlementEvent(settlement_id=s.id,actor_id='alice',status='pending',reason='PRIVATE REASON'))
        db.add(GroupOperation(group_id=gid,actor_id='alice',kind='test',snapshot={'PRIVATE':'NO OUTPUT'}));db.commit()
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');r=carol.get('/api/v1/notifications').json();assert [n['kind'] for n in r['items']]==['group'];assert 'PRIVATE' not in json.dumps(r)


def test_concurrent_workers_deduplicate(client,database):
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row locks required')
    login(client);gid,ids=group(client);seed(client,gid,ids);arm(database,'alice',reminder='daily',summary='daily')
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:tick(database),range(2)))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id=='alice',Notification.kind=='summary'))==1


def test_read_all_and_expired_delivery(client,database,monkeypatch):
    smtp(monkeypatch);login(client);gid,ids=group(client);seed(client,gid,ids)
    arm(database,'alice',email=True);tick(database)
    with database() as db:
        row=db.scalar(select(MailMessage));row.expires=int(time.time())-1;db.commit();deliver_one(db)
        assert db.scalar(select(Notification).where(Notification.user_id=='alice',Notification.kind=='expense')).email_status=='expired'
    assert client.post('/api/v1/notifications/read-all').status_code==200
    assert client.get('/api/v1/notifications').json()['unread']==0
