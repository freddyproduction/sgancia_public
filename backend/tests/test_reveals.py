import time,json
from datetime import datetime,timezone,timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import Expense,ExpenseRevision,Settlement,RevealJob,User,Group,Participant,Entry
from app.reveals import run_job
from conftest import login
from test_api import group,expense
from test_attachments import upload


def seed(client,gid,ids):
    r=client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,True),headers={'Idempotency-Key':__import__('uuid').uuid4().hex});assert r.status_code==201,r.text
    return r.json()['id']


def confirm(client,gid,eid,p,**kw):return client.post(f'/api/v1/groups/{gid}/expenses/{eid}/reveal-confirm',json={'fingerprint':p['fingerprint'],'confirm':True,'reconcile':p['reconciliation'],**kw},headers={'Idempotency-Key':'reveal-qa-key'})


def schedule(client,gid,eid):
    r=client.post(f'/api/v1/groups/{gid}/expenses/{eid}/reveal-schedule',json={'when':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'confirm':True},headers={'If-Match':'1'});assert r.status_code==201,r.text
    return r.json()['id']


def test_manual_reveal_keeps_old_versions_and_files_private(client,database):
    login(client);gid,ids=group(client);eid=seed(client,gid,ids);file=upload(client,gid,eid).json();base=f'/api/v1/groups/{gid}'
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(base+'/expenses/'+eid+'/reveal-preview').status_code==404
        assert carol.get(base+'/search').json()['count']==0
        p=client.get(base+'/expenses/'+eid+'/reveal-preview').json()['preview'];assert p['before']['balance']==p['after']['balance']
        result=confirm(client,gid,eid,p);assert result.status_code==200,result.text
        assert confirm(client,gid,eid,p).json()==result.json()
        assert carol.get(base+'/search').json()['count']==1
        versions=carol.get(base+'/expenses/'+eid+'/history').json()['versions'];assert [v['version'] for v in versions]==[2]
        assert carol.get(base+'/expenses/'+eid+'/attachments').json()==[]
        assert carol.get(base+'/attachments/'+file['id']+'/content').status_code==404
        assert len(client.get(base+'/expenses/'+eid+'/history').json()['versions'])==2


def test_reconcile_entire_scope_preserves_cash_and_deleted_expense(client,database):
    login(client);gid,ids=group(client);one=seed(client,gid,ids);two=seed(client,gid,ids);base=f'/api/v1/groups/{gid}'
    assert client.delete(base+'/expenses/'+two,headers={'If-Match':'1'}).status_code==204
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');r=bob.post(base+'/settlements',json={'sender':ids['bob'],'recipient':ids['alice'],'amount':'2','audience':[ids['alice'],ids['bob']],'note':'PRIVATE NOTE'},headers={'Idempotency-Key':'private-payment'});assert r.status_code==201
    sid=r.json()['id'];receipt=upload(client,gid,sid,kind='settlements',key='private-receipt').json()
    assert client.put(base+'/settlements/'+sid,json={'status':'confirmed'}).status_code==200
    before=client.get(base+'/finance').json()['summary'];p=client.get(base+'/expenses/'+one+'/reveal-preview').json()['preview']
    assert p['reconciliation'] and len(p['expenses'])==2 and len(p['payments'])==1
    assert client.post(base+'/expenses/'+one+'/reveal',headers={'If-Match':'1'}).status_code==409
    assert confirm(client,gid,one,p,reconcile=False).status_code==422
    result=confirm(client,gid,one,p);assert result.status_code==200,result.text
    after=client.get(base+'/finance').json()['summary'];assert after==before
    with database() as db:
        assert db.get(Settlement,sid).status=='cancelled' and db.get(Settlement,sid).audience is not None
        assert db.get(Expense,two).deleted and db.get(Expense,two).audience is None
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(base+'/settlements/'+sid+'/history').status_code==404
        public=carol.get(base+'/settlements').json();assert len(public)==1 and public[0]['amount']==200 and 'PRIVATE NOTE' not in json.dumps(public)
        assert carol.get(base+'/attachments/'+receipt['id']+'/content').status_code==404
        assert carol.get(base+'/expenses/'+one+'/reveal-preview').json()['jobs']==[]
    assert client.post(base+'/expenses/'+two+'/restore',headers={'If-Match':'3'}).status_code==200
    assert client.get(base+'/finance').json()['summary']['expenses_total']==20000
    assert len(confirm(client,gid,one,p).json()['payments'])==1
    with database() as db:assert db.scalar(select(func.count()).select_from(Settlement).where(Settlement.status=='confirmed'))==1


def test_pending_payment_blocks_reveal_and_scheduling(client):
    login(client);gid,ids=group(client);eid=seed(client,gid,ids);base=f'/api/v1/groups/{gid}'
    r=client.post(base+'/settlements',json={'sender':ids['alice'],'recipient':ids['bob'],'amount':'1','audience':[ids['alice'],ids['bob']]},headers={'Idempotency-Key':'pending-scope'});assert r.status_code==201
    p=client.get(base+'/expenses/'+eid+'/reveal-preview').json()['preview'];assert p['pending']
    assert confirm(client,gid,eid,p).status_code==409
    assert client.post(base+'/expenses/'+eid+'/reveal',headers={'If-Match':'1'}).status_code==409
    assert client.post(base+'/expenses/'+eid+'/reveal-schedule',json={'when':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat(),'confirm':True},headers={'If-Match':'1'}).status_code==409


def test_scheduled_reveal_exactly_once_and_privacy(client,database):
    login(client);gid,ids=group(client);eid=seed(client,gid,ids);jid=schedule(client,gid,eid);base=f'/api/v1/groups/{gid}'
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(base+'/expenses/'+eid+'/reveal-preview').status_code==404
    with database() as db:db.get(RevealJob,jid).run_at=1;db.commit()
    with database() as db:run_job(db,jid);run_job(db,jid)
    with database() as db:assert db.get(Expense,eid).version==2 and db.get(RevealJob,jid).status=='done'
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(base+'/expenses/'+eid+'/reveal-preview').json()['jobs']==[]


def test_schedule_revalidates_expense_account_and_group(client,database):
    login(client);gid,ids=group(client)
    for change in ('version','viewer','suspended','frozen','access_version'):
        eid=seed(client,gid,ids);jid=schedule(client,gid,eid)
        with database() as db:
            job=db.get(RevealJob,jid);job.run_at=1
            if change=='version':db.get(Expense,eid).version+=1
            if change=='viewer':db.get(Participant,ids['alice']).role='viewer'
            if change=='suspended':db.get(User,'alice').status='suspended'
            if change=='frozen':db.get(Group,gid).state='frozen'
            if change=='access_version':db.get(User,'alice').auth_version+=1
            db.commit();run_job(db,jid)
            assert db.get(RevealJob,jid).status=='blocked' and db.get(Expense,eid).audience is not None
            db.get(Participant,ids['alice']).role='owner';db.get(User,'alice').status='active';db.get(Group,gid).state='active'
            if change=='access_version':db.get(User,'alice').auth_version-=1
            db.commit()


def test_schedule_cancel_and_new_payments_require_review(client,database):
    login(client);gid,ids=group(client);eid=seed(client,gid,ids);base=f'/api/v1/groups/{gid}/expenses/{eid}'
    old=schedule(client,gid,eid);new=schedule(client,gid,eid)
    with database() as db:assert db.get(RevealJob,old).status=='cancelled'
    assert client.delete(base+'/reveal-schedule/'+new).json()['status']=='cancelled'
    jid=schedule(client,gid,eid)
    with database() as db:
        db.get(RevealJob,jid).run_at=1;db.add(Settlement(group_id=gid,sender=ids['bob'],recipient=ids['alice'],amount=1,audience=[ids['alice'],ids['bob']],author_id='bob',status='confirmed'));db.commit();run_job(db,jid)
        assert db.get(RevealJob,jid).status=='blocked' and db.get(Expense,eid).audience is not None


def test_hidden_activity_does_not_change_preview_and_stale_visible_data_rejected(client):
    login(client);gid,ids=group(client);eid=seed(client,gid,ids);base=f'/api/v1/groups/{gid}'
    p=client.get(base+'/expenses/'+eid+'/reveal-preview').json()['preview']
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');other={'alice':ids['bob'],'bob':ids['carol']};seed(bob,gid,other)
    assert p==client.get(base+'/expenses/'+eid+'/reveal-preview').json()['preview']
    client.post(base+'/expenses',json=expense(ids),headers={'Idempotency-Key':'public-changes'})
    assert confirm(client,gid,eid,p).status_code==409


def test_excluded_admin_and_nonmanager_cannot_reconcile(client,database):
    login(client);gid,ids=group(client);eid=seed(client,gid,ids);base=f'/api/v1/groups/{gid}'
    with database() as db:
        db.get(Participant,ids['carol']).role='admin';db.add(Settlement(group_id=gid,sender=ids['bob'],recipient=ids['alice'],amount=1,audience=[ids['alice'],ids['bob']],author_id='bob',status='confirmed'));db.commit()
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(base+'/expenses/'+eid+'/reveal-preview').status_code==404
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');p=bob.get(base+'/expenses/'+eid+'/reveal-preview').json()['preview'];assert not p['allowed']
        assert confirm(bob,gid,eid,p).status_code==403


def test_guest_old_files_remain_private_after_reveal(client):
    login(client);gid,ids=group(client);eid=seed(client,gid,ids);file=upload(client,gid,eid).json();base=f'/api/v1/groups/{gid}'
    r=client.post(base+'/guest-links',json={'show_attachments':True,'show_exports':True}).json();token=r['url'].split('#')[1]
    p=client.get(base+'/expenses/'+eid+'/reveal-preview').json()['preview'];assert confirm(client,gid,eid,p).status_code==200
    view=client.post('/api/v1/guest/view',json={'token':token}).json();assert len(view['expenses'])==1 and view['expenses'][0]['attachments']==[]
    assert client.post('/api/v1/guest/attachments/'+file['id'],json={'token':token,'view_token':view['file_access']}).status_code==404
    exported=client.post('/api/v1/guest/export',json={'token':token,'format':'json'}).json();assert len(exported['expenses'])==1 and 'attachments' not in exported['expenses'][0]


def test_job_concurrency_postgresql(client,database):
    import pytest
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row locks')
    login(client);gid,ids=group(client);eid=seed(client,gid,ids);jid=schedule(client,gid,eid)
    with database() as db:db.get(RevealJob,jid).run_at=1;db.commit()
    def worker(_):
        with database() as db:run_job(db,jid)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(worker,range(2)))
    with database() as db:assert db.get(Expense,eid).version==2 and db.get(RevealJob,jid).status=='done'
