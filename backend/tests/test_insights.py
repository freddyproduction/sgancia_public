from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import Expense,Entry,Settlement,ExpenseRevision,Idempotency,Group,Participant,ExpensePlan,Budget,FinalReport
from app.insights import records,projection
from app.finance import finance_view
from conftest import login
from test_api import group,expense


def post_exp(client,gid,ids,secret=False,**changes):
    body={**expense(ids,secret),**changes}
    result=client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':__import__('uuid').uuid4().hex});assert result.status_code==201,result.text
    return result.json()['id']


def budget_body(**overrides):return {'name':'Monthly','amount':'100','start':'2026-01-01','end':'2026-12-31',**overrides}


def test_search_filters_and_hidden_counts_tags_categories(client):
    login(client);gid,ids=group(client)
    post_exp(client,gid,ids,category='Dinner',tags=['food'],description='pizza')
    hidden=post_exp(client,gid,ids,True,title='Secret',category='Gift',tags=['surprise'])
    base=f'/api/v1/groups/{gid}'
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        result=carol.get(base+'/search').json();assert result['count']==1 and result['categories']==['Dinner'] and result['tags']==['food']
        assert result['stats']['total']==10000 and result['stats']['reconciled']
        for query in ('q=Secret','tag=surprise','category=Gift'):
            assert carol.get(base+'/search?'+query).json()['count']==0
        assert carol.post(base+'/simulate',json={'action':'delete','expense_id':hidden,'version':1}).status_code==404
    assert client.get(base+'/search?q=pizza&tag=food&category=Dinner&person='+ids['bob']).json()['count']==1
    assert client.get(base+'/search?start=2027-01-01').json()['count']==0
    assert client.get(base+'/search?start=2027-01-01&end=2026-01-01').status_code==422
    result=client.get(base+'/search?size=1&page=2').json();assert len(result['expenses'])==1 and result['count']==2 and result['stats']['total']==20000


def test_budgets_personal_private_public_secret_independence(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    post_exp(client,gid,ids)
    result=client.post(base+'/budgets',json=budget_body(scope='public'));assert result.status_code==201,result.text
    public=result.json();assert public['spent']==10000 and public['status']=='exceeded'
    result=client.post(base+'/budgets',json=budget_body());assert result.status_code==201
    own=result.json();assert own['spent']==3500
    post_exp(client,gid,ids,True)
    rows=client.get(base+'/budgets').json();assert next(r for r in rows if r['id']==public['id'])['spent']==10000
    assert next(r for r in rows if r['id']==own['id'])['spent']==7000
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');rows=bob.get(base+'/budgets').json();assert len(rows)==1 and rows[0]['spent']==10000
        assert bob.put(base+'/budgets/'+own['id'],json=budget_body(),headers={'If-Match':'1'}).status_code==404
        assert bob.put(base+'/budgets/'+public['id'],json=budget_body(scope='public'),headers={'If-Match':'1'}).status_code==403
        assert bob.post(base+'/budgets',json=budget_body(scope='public')).status_code==403
    assert client.put(base+'/budgets/'+own['id'],json=budget_body(amount='80',threshold=80),headers={'If-Match':'1'}).json()['status']=='threshold'
    assert client.delete(base+'/budgets/'+own['id'],headers={'If-Match':'1'}).status_code==409


def test_budget_currency_change_requires_explicit_review(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    result=client.post(base+'/budgets',json=budget_body());bid=result.json()['id']
    assert client.put(base+'/currency',json={'currency':'USD','exchange_rate':'1.2'},headers={'If-Match':'1'}).status_code==200
    row=client.get(base+'/budgets').json()[0];assert row['status']=='currency_changed' and row['spent'] is None and row['currency']=='EUR'
    row=client.put(base+'/budgets/'+bid,json=budget_body(amount='120'),headers={'If-Match':'1'}).json();assert row['status']=='ok' and row['currency']=='USD'


def test_personal_statistics_separate_currencies_and_only_own_shares(client):
    login(client);gid,ids=group(client);post_exp(client,gid,ids);post_exp(client,gid,ids,True)
    other,ids2=group(client)
    assert client.put(f'/api/v1/groups/{other}/currency',json={'currency':'USD','exchange_rate':'1'},headers={'If-Match':'1'}).status_code==200
    post_exp(client,other,ids2)
    rows=client.get('/api/v1/statistics').json();assert {r['currency']:r['total'] for r in rows}=={'EUR':7000,'USD':3500}
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert all(r['total']==0 for r in carol.get('/api/v1/statistics').json())


def test_simulation_matches_real_finance_but_does_not_write(client,database):
    login(client);gid,ids=group(client);eid=post_exp(client,gid,ids);base=f'/api/v1/groups/{gid}'
    with database() as db:
        counts=[db.scalar(select(func.count()).select_from(model)) for model in (Expense,Entry,ExpenseRevision,Settlement,Idempotency)]
    body=expense(ids,True)
    for smart in (True,False):
        with database() as db:db.get(Group,gid).smart_balances=smart;db.commit()
        initial=client.get(base+'/finance').json()['summary']
        sim=client.post(base+'/simulate',json={'action':'add','draft':body});assert sim.status_code==200,sim.text
        for key in ('balance','receivable','payable','expenses_total'):assert sim.json()['before'][key]==initial[key]
        assert sim.json()['after']['expenses_total']==20000 and sim.json()['after']['balance']==initial['balance']*2
        deletion=client.post(base+'/simulate',json={'action':'delete','expense_id':eid,'version':1}).json()['after'];assert deletion['expenses_total']==0
        edited={**expense(ids),'title':'Changed'}
        sim=client.post(base+'/simulate',json={'action':'edit','expense_id':eid,'version':1,'draft':edited});assert sim.status_code==200
        assert sim.json()['before']==sim.json()['after']
    with database() as db:assert counts==[db.scalar(select(func.count()).select_from(model)) for model in (Expense,Entry,ExpenseRevision,Settlement,Idempotency)]


def test_simulated_payment_matches_confirmation_and_no_cross_scope_netting(client,database):
    login(client);gid,ids=group(client);post_exp(client,gid,ids);post_exp(client,gid,ids,True);base=f'/api/v1/groups/{gid}'
    body={'sender':ids['bob'],'recipient':ids['alice'],'amount':'5','audience':[ids['alice'],ids['bob']]}
    sim=client.post(base+'/simulate',json={'action':'payment',**body});assert sim.status_code==200,sim.text
    payment=client.post(base+'/settlements',json=body,headers={'Idempotency-Key':'insights-payment'})
    # Bob must submit his own payment; Alice cannot impersonate him.
    assert payment.status_code==403
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');payment=bob.post(base+'/settlements',json=body,headers={'Idempotency-Key':'insights-payment'});assert payment.status_code==201
    assert client.put(base+'/settlements/'+payment.json()['id'],json={'status':'confirmed'}).status_code==200
    real=client.get(base+'/finance').json()['summary']
    for key in ('balance','receivable','payable','expenses_total'):assert sim.json()['after'][key]==real[key]


def test_simulation_stale_version_and_private_audience_guard(client):
    login(client);gid,ids=group(client);eid=post_exp(client,gid,ids,True);base=f'/api/v1/groups/{gid}'
    assert client.post(base+'/simulate',json={'action':'delete','expense_id':eid,'version':2}).status_code==409
    assert client.post(base+'/simulate',json={'action':'edit','expense_id':eid,'version':1,'draft':expense(ids)}).status_code==422
    assert client.post(base+'/simulate',json={'action':'payment','sender':ids['alice'],'recipient':ids['bob'],'amount':'2','audience':[ids['bob']]}).status_code==422


def test_closing_preserves_hidden_debts_and_reports_are_personal(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    # Bob/Carol-only secret expense: no evidence about it in Alice's closing response.
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');secret=expense({'alice':ids['bob'],'bob':ids['carol']},True)
        result=bob.post(base+'/expenses',json=secret,headers={'Idempotency-Key':'closing-secret'});assert result.status_code==201
    view=client.get(base+'/closing').json();assert view['stats']['count']==0 and view['pending']==0 and view['transfers']==[]
    headers={'Idempotency-Key':'closing-key'}
    assert client.post(base+'/close',json={'fingerprint':view['fingerprint'],'retain_balances':True},headers=headers).status_code==409
    assert client.put(base+'/state',json={'state':'frozen'}).status_code==200
    view=client.get(base+'/closing').json()
    assert client.post(base+'/close',json={'fingerprint':view['fingerprint']},headers=headers).status_code==422
    body={'fingerprint':view['fingerprint'],'retain_balances':True}
    result=client.post(base+'/close',json=body,headers=headers);assert result.status_code==200,result.text
    assert client.post(base+'/close',json=body,headers=headers).json()==result.json()
    reports=client.get(base+'/reports').json();assert len(reports)==1 and reports[0]['snapshot']['stats']['total']==0
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.get(base+'/reports').json()==[]
        assert bob.post(base+'/reports').status_code==201
        own=bob.get(base+'/reports').json();assert own[0]['snapshot']['stats']['total']==10000
    with database() as db:
        assert db.scalar(select(func.count()).select_from(Expense))==1
        assert db.get(Group,gid).state=='archived'


def test_hidden_activity_does_not_change_closing_fingerprint(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    before=client.get(base+'/closing').json()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');body=expense({'alice':ids['bob'],'bob':ids['carol']},True)
        assert bob.post(base+'/expenses',json=body,headers={'Idempotency-Key':'hidden-closing'}).status_code==201
    assert before==client.get(base+'/closing').json()


def test_closing_owner_only_and_visible_change_invalidates_preview(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    client.put(base+'/state',json={'state':'frozen'});view=client.get(base+'/closing').json()
    with database() as db:db.get(Group,gid).smart_balances=False;db.commit()
    assert client.post(base+'/close',json={'fingerprint':view['fingerprint'],'retain_balances':True},headers={'Idempotency-Key':'close-changed'}).status_code==409
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');v=bob.get(base+'/closing').json()
        assert bob.post(base+'/close',json={'fingerprint':v['fingerprint'],'retain_balances':True},headers={'Idempotency-Key':'close-denied'}).status_code==403


def test_viewer_search_allowed_mutation_denied(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}';post_exp(client,gid,ids)
    with database() as db:db.get(Participant,ids['bob']).role='viewer';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.get(base+'/search').status_code==200
        assert bob.post(base+'/budgets',json=budget_body()).status_code==403
        assert bob.post(base+'/simulate',json={'action':'add','draft':expense(ids)}).status_code==403
