import base64,copy,time
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,create_engine,func
from sqlalchemy.orm import sessionmaker
from cryptography.fernet import Fernet
from app.main import app
from app.db import Base,get_db
from app.config import settings
from app.models import User,Instance,Participant,Expense,Entry,Friendship,PaymentMethod,FriendLink,Group
from app.security import cipher
from app.portable_backup import encode,decode,apply,capture,HARD_LIMIT
from conftest import login
from test_api import group,expense
from test_authority import root_login
PASS='portable-test-password'

def export(client,path):
    result=client.post(path,json={'archive_password':PASS,'password':'password-very-long','filename':'prova'})
    assert result.status_code==200,result.text
    return result.content

def restore(client,data,path='/api/v1/groups/backup/restore',**extra):
    return client.post(path,files={'file':('prova.sgp',data,'application/octet-stream')},data={'archive_password':PASS,'confirm':'true',**extra})

def test_friends_consent_links_and_group_authority(client,database):
    login(client);gid,ids=group(client)
    assert client.get('/api/v1/friends/search',params={'q':'Bob'}).json()==[]
    hits=client.get('/api/v1/friends/search',params={'q':'bob@example.org'}).json();assert len(hits)==1 and 'email' not in hits[0]
    assert client.post('/api/v1/friends/requests',json={'user_id':'bob'}).status_code==200
    request=client.get('/api/v1/friends').json()[0];assert request['state']=='outgoing'
    assert client.post('/api/v1/friends/requests/'+request['friendship_id']+'/accept').status_code==404
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.get('/api/v1/friends').json()[0]['state']=='incoming'
        assert bob.post('/api/v1/friends/requests/'+request['friendship_id']+'/accept').status_code==200
        assert bob.post('/api/v1/groups/'+gid+'/friends',json={'user_id':'alice'}).status_code==403
    second=client.post('/api/v1/groups',json={'name':'Amici'}).json()['id']
    assert client.post('/api/v1/groups/'+second+'/friends',json={'user_id':'carol'}).status_code==403
    assert client.post('/api/v1/groups/'+second+'/friends',json={'user_id':'bob','role':'viewer'}).status_code==200
    assert client.post('/api/v1/groups/'+second+'/friends',json={'user_id':'bob'}).status_code==409
    assert client.delete('/api/v1/friends/requests/'+request['friendship_id']).status_code==200
    with database() as db:assert db.scalar(select(Participant).where(Participant.group_id==second,Participant.user_id=='bob')).role=='viewer'


def test_friend_link_rotation_expiry_no_self(client,database):
    login(client);old=client.post('/api/v1/friends/link',json={'days':2}).json()['token']
    assert client.post('/api/v1/friends/link/accept',json={'token':old}).status_code==409
    new=client.post('/api/v1/friends/link',json={'days':1}).json()['token']
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.post('/api/v1/friends/link/preview',json={'token':old}).status_code==404
        assert bob.post('/api/v1/friends/link/accept',json={'token':new}).status_code==200
        assert bob.get('/api/v1/friends').json()[0]['state']=='accepted'
        client.delete('/api/v1/friends/link');assert bob.post('/api/v1/friends/link/accept',json={'token':new}).status_code==404
    assert len(client.get('/api/v1/friends').json())==1


def hidden_expense(client):
    gid,ids=group(client)
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');body=expense(ids);body['title']='Segreto Bob Carol';body['audience']=[ids['bob'],ids['carol']];body['payers']={ids['bob']:'100'}
        body['items']=[{'title':'Privato','amount':'100','mode':'equal','shares':{ids['bob']:'1',ids['carol']:'1'}}]
        result=bob.post('/api/v1/groups/'+gid+'/expenses',json=body,headers={'Idempotency-Key':'hidden-backup'});assert result.status_code==201,result.text
    assert client.get('/api/v1/groups/'+gid+'/expenses').json()==[]
    return gid,ids


def test_group_backup_complete_preserves_secret_audience_and_identity(client,database):
    login(client);gid,ids=hidden_expense(client)
    packet=export(client,'/api/v1/groups/'+gid+'/backup');decoded=decode(packet,PASS,HARD_LIMIT)
    assert decoded['tables']['expenses'][0]['title']=='Segreto Bob Carol'
    assert not any('email' in row for row in decoded['tables']['participants'])
    result=restore(client,packet);assert result.status_code==200,result.text
    new=result.json()['group_id'];assert new!=gid
    details=client.get('/api/v1/groups/'+new).json();assert details['state']=='frozen' and details['role']=='owner'
    assert client.get('/api/v1/groups/'+new+'/expenses').json()==[]
    with database() as db:
        e=db.scalar(select(Expense).where(Expense.group_id==new));assert e and len(e.audience)==2 and details['my_participant'] not in e.audience
        rows=list(db.scalars(select(Entry).where(Entry.group_id==new)));assert sum(r.paid for r in rows)==sum(r.owed for r in rows)==10000
        assert db.scalar(select(func.count()).select_from(User).where(User.archival.is_(True)))>=1
    # Group members cannot produce a complete export.
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.post('/api/v1/groups/'+gid+'/backup',json={'archive_password':PASS}).status_code==403


def test_group_backup_tamper_atomic_policy_and_wrong_scope(client,database):
    root_login(client,database);gid,ids=group(client);packet=export(client,'/api/v1/groups/'+gid+'/backup')
    bad=bytearray(packet);bad[-4]^=1
    assert restore(client,bytes(bad)).status_code==422
    assert restore(client,packet[:-5]).status_code==422
    changed=decode(packet,PASS,HARD_LIMIT);changed['tables']['participants'][0]['group_id']='wrong'
    assert restore(client,encode(changed,PASS,HARD_LIMIT)).status_code==422
    with database() as db:assert db.scalar(select(func.count()).select_from(Group))==1
    assert client.put('/api/v1/admin/operations/portable',json={'groups_enabled':False,'max_archive_mb':20,'filename_prefix':'safe'}).status_code==200
    assert restore(client,packet).status_code==403
    assert client.post('/api/v1/groups/'+gid+'/backup',json={'archive_password':PASS}).status_code==403
    # Saving scheduled policy must not erase the independent platform group policy.
    assert client.put('/api/v1/admin/operations/backups',json={'enabled':False}).status_code==200
    assert not client.get('/api/v1/backup-policy').json()['groups_enabled']


def test_installation_restore_before_bootstrap_rekeys_and_revokes(client,database,tmp_path,monkeypatch):
    root_login(client,database);gid,ids=hidden_expense(client)
    with database() as db:
        db.add(PaymentMethod(user_id='bob',payload=cipher().encrypt(b'{"label":"bank","instructions":"test"}').decode()));db.commit()
    packet=export(client,'/api/v1/admin/operations/portable/export')
    assert restore(client,packet,'/api/v1/setup/restore',setup_key=settings.encryption_key).status_code==409
    engine=create_engine('sqlite:///'+str(tmp_path/'new.db'))
    from sqlalchemy import event
    @event.listens_for(engine,'connect')
    def foreign_keys(connection,_):connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    old_override=app.dependency_overrides[get_db]
    def fresh():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=fresh
    monkeypatch.setattr(settings,'encryption_key',Fernet.generate_key().decode())
    try:
        with TestClient(app,base_url='http://localhost:8088') as fresh_client:
            assert fresh_client.get('/api/v1/setup/status').json()=={'configured':False}
            assert restore(fresh_client,packet,'/api/v1/setup/restore',setup_key='wrong').status_code==403
            restored=restore(fresh_client,packet,'/api/v1/setup/restore',setup_key=settings.encryption_key);assert restored.status_code==200,restored.text
            assert fresh_client.get('/api/v1/setup/status').json()=={'configured':True}
            login(fresh_client);assert fresh_client.get('/api/v1/auth/me').json()['superadmin']
            assert fresh_client.get('/api/v1/groups/'+gid+'/expenses').json()==[]
            with factory() as db:
                p=db.scalar(select(PaymentMethod));assert cipher().decrypt(p.payload.encode())==b'{"label":"bank","instructions":"test"}'
                assert db.get(Instance,1).superadmin_id=='alice' and not db.get(Instance,1).guest_links_enabled
                assert db.scalar(select(func.count()).select_from(User))==4
            assert restore(fresh_client,packet,'/api/v1/setup/restore',setup_key=settings.encryption_key).status_code==409
    finally:app.dependency_overrides[get_db]=old_override;engine.dispose()


def test_invalid_archive_formats_are_not_executed():
    with pytest.raises(Exception):decode(b'PGDMP' + b'evil',PASS,HARD_LIMIT)
    bad={'format':'sgancia-portable-1','schema':'future','scope':'installation','tables':{},'blobs':{}}
    with pytest.raises(Exception):decode(encode(bad,PASS,HARD_LIMIT),PASS,HARD_LIMIT)


def test_concurrent_mutual_friend_requests_are_one_pending_pair(client,database):
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('Row locks require PostgreSQL')
    from concurrent.futures import ThreadPoolExecutor
    def request(who,target):
        with TestClient(app,base_url='http://localhost:8088') as session:
            login(session,who);return session.post('/api/v1/friends/requests',json={'user_id':target}).status_code
    with ThreadPoolExecutor(2) as pool:
        a=pool.submit(request,'alice','bob');b=pool.submit(request,'bob','alice');assert a.result()==b.result()==200
    with database() as db:
        rows=list(db.scalars(select(Friendship)));assert len(rows)==1 and not rows[0].accepted


def test_group_history_private_budgets_templates_and_files_stay_scoped(client,database):
    import hashlib
    from app.models import Budget,ExpensePlan,Attachment,ExpenseRevision
    from app.attachment_storage import storage_lock,write_blob
    login(client);gid,ids=hidden_expense(client)
    with database() as db:
        private=db.scalar(select(Expense).where(Expense.group_id==gid))
        db.add(Budget(group_id=gid,user_id='bob',participant_id=ids['bob'],name='Budget personale Bob',scope='personal',currency='EUR',amount=20000,start='2026-01-01',end='2026-12-31'))
        db.add(ExpensePlan(group_id=gid,owner_id='bob',participant_id=ids['bob'],name='Modello privato Bob',kind='recurring',draft={'title':'Privato'},audience=[ids['bob'],ids['carol']],currency='EUR',start='2026-11-01',enabled=True))
        raw=b'%PDF-test-synthetic';key='ab'*16
        with storage_lock():write_blob(key+'.blob',raw)
        db.add(Attachment(group_id=gid,expense_id=private.id,expense_revision=private.version,uploader_id='bob',storage_key=key,filename='prova.pdf',media_type='application/pdf',size=len(raw),sha256=hashlib.sha256(raw).hexdigest()));db.commit()
    packet=export(client,'/api/v1/groups/'+gid+'/backup');result=restore(client,packet);assert result.status_code==200,result.text
    new=result.json()['group_id']
    with database() as db:
        budget=db.scalar(select(Budget).where(Budget.group_id==new));assert budget.name=='Budget personale Bob' and budget.user_id!='alice' and db.get(User,budget.user_id).archival
        plan=db.scalar(select(ExpensePlan).where(ExpensePlan.group_id==new));assert not plan.enabled and plan.owner_id==budget.user_id
        attachment=db.scalar(select(Attachment).where(Attachment.group_id==new));assert attachment.storage_key!=key
        from app.attachment_storage import read_blob
        assert read_blob(attachment.storage_key+'.blob',attachment.sha256)==raw
    assert client.get('/api/v1/groups/'+new+'/expenses').json()==[]
    listed=client.get('/api/v1/groups/'+new+'/plans');assert listed.status_code==200 and not listed.json()
    assert client.get('/api/v1/groups/'+new+'/attachments/'+attachment.id+'/download').status_code in (403,404)


def test_group_package_cannot_write_into_existing_destination_group(client,database):
    login(client);gid,ids=group(client);other=client.post('/api/v1/groups',json={'name':'Destinazione protetta'}).json()['id']
    packet=decode(export(client,'/api/v1/groups/'+gid+'/backup'),PASS,HARD_LIMIT)
    packet['tables']['participants'][0]['group_id']=other
    response=restore(client,encode(packet,PASS,HARD_LIMIT));assert response.status_code==422
    assert len(client.get('/api/v1/groups/'+other).json()['participants'])==1
