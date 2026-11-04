from datetime import date,timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import Expense,ExpenseRevision,ExpensePlan,ExpenseJob,Participant,User,Group
from app.automation import occurrence,today,run_plan
from conftest import login
from test_api import group,expense


def make(client,ids,gid,**overrides):
    body={'name':'Affitto QA','kind':'recurring','draft':expense(ids),'start':today().isoformat(),'frequency':'monthly','interval':1,'authorize':True,**overrides}
    result=client.post(f'/api/v1/groups/{gid}/plans',json=body,headers={'Idempotency-Key':__import__('uuid').uuid4().hex})
    assert result.status_code==201,result.text
    return result.json()


def work(database,pid):
    with database() as db:run_plan(db,pid)


def test_calendar_keeps_original_day_and_leap_anchor():
    assert occurrence('2024-01-31','monthly',1,1)==date(2024,2,29)
    assert occurrence('2024-01-31','monthly',1,2)==date(2024,3,31)
    assert occurrence('2024-02-29','yearly',1,1)==date(2025,2,28)
    assert occurrence('2024-02-29','yearly',1,4)==date(2028,2,29)
    assert occurrence('2026-01-01','weekly',2,2)==date(2026,1,29)


def test_formula_opt_in_and_private_tags(client,database):
    login(client);gid,ids=group(client);body=expense(ids,True);body['items'][0]['amount']='20+20';body['tags']=[' Casa ','casa','regalo']
    url=f'/api/v1/groups/{gid}/expenses'
    result=client.post(url,json=body,headers={'Idempotency-Key':'formula-one'});assert result.status_code==201,result.text
    eid=result.json()['id']
    with database() as db:
        snap=db.get(ExpenseRevision,(eid,1)).snapshot
        assert snap['items'][0]['amount']=='40.00' and snap['tags']==['Casa','regalo']
        assert db.get(Expense,eid).items[0]['expression']=='40.00'
    body['remember_expressions']=True
    result=client.post(url,json=body,headers={'Idempotency-Key':'formula-two'});assert result.status_code==201
    with database() as db:assert db.get(ExpenseRevision,(result.json()['id'],1)).snapshot['items'][0]['amount']=='20+20'
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(f'/api/v1/groups/{gid}/tags').json()==[]
        assert carol.get(url+'/'+eid+'/duplicate').status_code==404
    assert client.get(f'/api/v1/groups/{gid}/tags').json()==['Casa','regalo']


def test_duplicate_filters_inactive_and_does_not_write(client,database):
    login(client);gid,ids=group(client);body=expense(ids)
    result=client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'dup-source'});assert result.status_code==201
    with database() as db:db.get(Participant,ids['bob']).active=False;db.commit()
    copied=client.get(f'/api/v1/groups/{gid}/expenses/'+result.json()['id']+'/duplicate');assert copied.status_code==200,copied.text
    draft=copied.json();assert draft['date']==today().isoformat() and ids['bob'] not in draft['payers']
    assert all(ids['bob'] not in i['shares'] for i in draft['items'])
    with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==1


def test_worker_once_atomic_and_template_no_economic_effect(client,database):
    login(client);gid,ids=group(client);template=make(client,ids,gid,kind='template',authorize=False)
    work(database,template['id'])
    plan=make(client,ids,gid)
    work(database,plan['id']);work(database,plan['id'])
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Expense))==1
        jobs=list(db.scalars(select(ExpenseJob)));assert len(jobs)==1 and jobs[0].status=='done' and jobs[0].expense_id
        assert db.get(ExpenseRevision,(jobs[0].expense_id,1)).snapshot['date']==today().isoformat()
    result=client.delete(f'/api/v1/groups/{gid}/plans/'+plan['id'],headers={'If-Match':'1'});assert result.status_code==200
    with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==1


def test_permission_currency_participant_changes_block(client,database):
    login(client);gid,ids=group(client)
    for change in ('viewer','currency','inactive','suspended'):
        plan=make(client,ids,gid)
        with database() as db:
            if change=='viewer':db.get(Participant,ids['alice']).role='viewer'
            elif change=='currency':db.get(Group,gid).currency='USD'
            elif change=='inactive':db.get(Participant,ids['bob']).active=False
            else:db.get(User,'alice').status='suspended'
            db.commit()
        work(database,plan['id'])
        with database() as db:
            assert not db.get(ExpensePlan,plan['id']).enabled
            assert db.scalar(select(func.count()).select_from(Expense))==0
            db.get(Participant,ids['alice']).role='owner';db.get(Group,gid).currency='EUR';db.get(Participant,ids['bob']).active=True;db.get(User,'alice').status='active';db.commit()


def test_private_plans_and_manager_cannot_impersonate_author(client,database):
    login(client);gid,ids=group(client);plan=make(client,ids,gid,draft=expense(ids,True));path=f'/api/v1/groups/{gid}/plans'
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(path).json()==[]
        assert carol.delete(path+'/'+plan['id'],headers={'If-Match':'1'}).status_code==404
    with database() as db:db.get(Participant,ids['bob']).role='admin';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');result=bob.put(path+'/'+plan['id']+'/state',json={'enabled':False},headers={'If-Match':'1'});assert result.status_code==200
        assert bob.put(path+'/'+plan['id']+'/state',json={'enabled':True},headers={'If-Match':'2'}).status_code==403
    assert client.put(path+'/'+plan['id']+'/state',json={'enabled':True},headers={'If-Match':'1'}).status_code==409


def test_resume_skip_or_catchup_is_explicit(client,database):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}/plans'
    for catch in (False,True):
        plan=make(client,ids,gid,frequency='daily')
        with database() as db:
            row=db.get(ExpensePlan,plan['id']);row.start=(today()-timedelta(days=3)).isoformat();row.enabled=False;db.commit()
        result=client.put(path+'/'+plan['id']+'/state',json={'enabled':True,'catch_up':catch},headers={'If-Match':'1'});assert result.status_code==200,result.text
        work(database,plan['id'])
        with database() as db:
            jobs=list(db.scalars(select(ExpenseJob).where(ExpenseJob.plan_id==plan['id'])));assert len(jobs)==(4 if catch else 1) and all(j.status=='done' for j in jobs)


def test_fx_retry_and_transaction_rollback(client,database,monkeypatch):
    from fastapi import HTTPException
    import app.exchange as fx
    login(client);gid,ids=group(client);draft=expense(ids);draft['currency']='USD'
    plan=make(client,ids,gid,draft=draft,auto_fx=True)
    monkeypatch.setattr(fx,'exchange_rate',lambda *args:(_ for _ in ()).throw(HTTPException(503,'QA unavailable')))
    work(database,plan['id'])
    with database() as db:
        j=db.scalar(select(ExpenseJob));assert j.status=='retry' and j.attempts==1
        assert db.scalar(select(func.count()).select_from(Expense))==0
        j.next_attempt=0;db.commit()
    import app.automation as au
    original=au.record_expense
    def fail(*args,**kwargs):original(*args,**kwargs);raise ValueError('QA interrupted')
    monkeypatch.setattr(fx,'exchange_rate',lambda *args:{'token':fx.sign({'base':'USD','quote':'EUR','rate':'0.9','date':today().isoformat(),'issued':__import__('time').time(),'source':'QA'})})
    monkeypatch.setattr(au,'record_expense',fail)
    work(database,plan['id'])
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Expense))==0
        assert db.scalar(select(ExpenseJob)).status=='blocked'


def test_plan_edit_preserves_jobs_and_requires_resume(client,database):
    login(client);gid,ids=group(client);plan=make(client,ids,gid);path=f'/api/v1/groups/{gid}/plans/'+plan['id']
    body={'name':'Changed','kind':'recurring','draft':expense(ids),'start':today().isoformat(),'authorize':True}
    result=client.put(path,json=body,headers={'If-Match':'1'});assert result.status_code==200,result.text
    assert result.json()['enabled'] is False
    work(database,plan['id'])
    with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==0
    assert client.put(path+'/state',json={'enabled':True},headers={'If-Match':'2'}).status_code==200
    work(database,plan['id'])
    with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==1


def test_advance_receiver_confirmation_and_balance(client,database):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}/settlements'
    result=client.post(path,json={'sender':ids['alice'],'recipient':ids['bob'],'amount':'40','kind':'advance','note':'Fondo cassa'},headers={'Idempotency-Key':'advance-001'});assert result.status_code==201,result.text
    payment=result.json();assert payment['kind']=='advance' and payment['note']=='Fondo cassa'
    assert client.put(path+'/'+payment['id'],json={'status':'confirmed'}).status_code==403
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.put(path+'/'+payment['id'],json={'status':'confirmed'}).status_code==200
    scopes=client.get(f'/api/v1/groups/{gid}/balances').json();assert sum(s['total'] for s in scopes)==0
    assert sum(s['balances'].get(ids['alice'],0) for s in scopes)==4000


def test_worker_concurrent_postgres(client,database):
    import pytest
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row locks')
    login(client);gid,ids=group(client);plan=make(client,ids,gid)
    with ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(lambda _:work(database,plan['id']),range(2)))
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Expense))==1
        assert db.scalar(select(func.count()).select_from(ExpenseJob))==1


def test_plan_creation_idempotence_and_explicit_authorization(client,database):
    login(client);gid,ids=group(client);url=f'/api/v1/groups/{gid}/plans'
    body={'name':'QA','kind':'recurring','draft':expense(ids),'start':today().isoformat()}
    headers={'Idempotency-Key':'same-plan-key'}
    assert client.post(url,json=body,headers=headers).status_code==422
    body['authorize']=True
    first=client.post(url,json=body,headers=headers);assert first.status_code==201,first.text
    second=client.post(url,json=body,headers=headers);assert second.status_code==201 and first.json()['id']==second.json()['id']
    body['name']='Different';assert client.post(url,json=body,headers=headers).status_code==409
    with database() as db:assert db.scalar(select(func.count()).select_from(ExpensePlan))==1


def test_manual_fx_plan_persists_authorized_rate_without_expiring_token(client,database,monkeypatch):
    import app.exchange as fx
    login(client);gid,ids=group(client)
    draft=expense(ids);draft['currency']='USD';draft['exchange_token']=fx.sign({'base':'USD','quote':'EUR','rate':'0.9','date':today().isoformat(),'issued':__import__('time').time(),'source':'QA'})
    plan=make(client,ids,gid,draft=draft,auto_fx=False)
    assert plan['draft']['exchange_rate']=='0.9' and plan['draft']['exchange_token'] is None
    work(database,plan['id'])
    with database() as db:assert db.scalar(select(Expense)).total==9000


def test_tags_preserved_by_group_currency_conversion(client,database):
    login(client);gid,ids=group(client);draft=expense(ids);draft['tags']=['Trip'];draft['remember_expressions']=True;draft['items'][0]['amount']='20+20'
    base=f'/api/v1/groups/{gid}'
    result=client.post(base+'/expenses',json=draft,headers={'Idempotency-Key':'tag-convert'});assert result.status_code==201
    eid=result.json()['id']
    result=client.put(base+'/currency',json={'currency':'USD','exchange_rate':'1.2'},headers={'If-Match':'1'});assert result.status_code==200,result.text
    with database() as db:
        assert db.get(ExpenseRevision,(eid,1)).snapshot['items'][0]['amount']=='20+20'
        assert db.get(ExpenseRevision,(eid,2)).snapshot['tags']==['Trip']
        assert db.get(ExpenseRevision,(eid,2)).snapshot['remember_expressions'] is False


def test_shortened_calendar_does_not_execute_old_pending_job(client,database):
    login(client);gid,ids=group(client);plan=make(client,ids,gid);pid=plan['id'];yesterday=(today()-timedelta(days=1)).isoformat()
    with database() as db:
        row=db.get(ExpensePlan,pid);row.start=yesterday;row.until=yesterday;row.enabled=False
        db.add(ExpenseJob(plan_id=pid,date=today().isoformat(),audience=None,status='paused'));db.commit()
    path=f'/api/v1/groups/{gid}/plans/'+pid+'/state'
    result=client.put(path,json={'enabled':True,'catch_up':True},headers={'If-Match':'1'});assert result.status_code==200,result.text
    work(database,pid)
    with database() as db:
        assert db.scalar(select(ExpenseJob).where(ExpenseJob.date==today().isoformat())).status=='skipped'
        assert db.scalar(select(func.count()).select_from(Expense))==1
        assert db.scalar(select(Expense)).date==yesterday
