from fastapi.testclient import TestClient
from fastapi import HTTPException
from sqlalchemy import select,func
from app.main import app
from app.models import Participant,Settlement
from conftest import login
from test_api import group,expense


def smart(client,gid,enabled,version=1):return client.put(f'/api/v1/groups/{gid}/smart-balances',json={'enabled':enabled},headers={'If-Match':str(version)})


def test_smart_default_and_direct_chain_and_permissions(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    assert client.get(base).json()['smart_balances'] is True
    a,b,c=(ids[n] for n in ('alice','bob','carol'))
    for i,(debtor,payer) in enumerate(((a,b),(b,c))):
        body={'title':'Anticipo','date':'2026-11-03','items':[{'amount':'10','shares':{debtor:'1'},'payers':{payer:''}}]}
        assert client.post(base+'/expenses',json=body,headers={'Idempotency-Key':f'chain-expense-{i}'}).status_code==201
    rows=client.get(base+'/finance').json()['transfers'];assert [(r['from'],r['to'],r['amount']) for r in rows]==[(a,c,1000)]
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert smart(bob,gid,False).status_code==403
    assert smart(client,gid,False).status_code==200
    rows=client.get(base+'/finance').json()['transfers']
    assert {(r['from'],r['to'],r['amount']) for r in rows}=={(a,b,1000),(b,c,1000)}
    assert smart(client,gid,True).status_code==409
    assert smart(client,gid,True,2).status_code==200
    assert len(client.get(base+'/finance').json()['transfers'])==1


def test_direct_cycles_have_gross_receivable_and_payable_and_receipt(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    a,b,c=(ids[n] for n in ('alice','bob','carol'))
    for i,(debtor,payer) in enumerate(((a,b),(b,c),(c,a))):
        body={'title':'Ciclo','date':'2026-11-03','items':[{'amount':'10','shares':{debtor:'1'},'payers':{payer:''}}]}
        client.post(base+'/expenses',json=body,headers={'Idempotency-Key':f'cycle-expense-{i}'})
    assert client.get(base+'/finance').json()['transfers']==[]
    smart(client,gid,False)
    view=client.get(base+'/finance').json()
    assert view['summary']['balance']==0 and view['summary']['receivable']==view['summary']['payable']==1000
    row=next(r for r in view['transfers'] if r['to']==a)
    result=client.post(base+'/settlements/settle-transfer',json={'sender':row['from'],'recipient':row['to'],'components':row['components'],'fingerprint':row['fingerprint']},headers={'Idempotency-Key':'direct-cycle-receipt'})
    assert result.status_code==200,result.text
    assert client.get(base+'/finance').json()['summary']['receivable']==0


def test_global_registered_identity_aggregates_groups_and_receives_atomically(client):
    login(client);gids=[]
    for index in range(2):
        gid,ids=group(client);gids.append(gid)
        for private in (False,True):client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,private),headers={'Idempotency-Key':f'overview-cost-{index}-{private}'})
        client.put(f'/api/v1/groups/{gid}/participants/{ids["bob"]}',json={'name':f'Alias Bob {index}','role':'member'})
    view=client.get('/api/v1/overview').json();assert view['totals']==[{'currency':'EUR','receive':2000,'pay':0}]
    assert len(view['people'])==1;row=view['people'][0]
    assert row['name']=='Bob' and row['amount']==2000 and len(row['groups'])==2
    body={'key':row['key'],'fingerprint':row['fingerprint']};headers={'Idempotency-Key':'global-receive-together'}
    received=client.post('/api/v1/overview/settle',json=body,headers=headers)
    assert received.status_code==200,received.text
    assert len(received.json()['ids'])==4 and received.json()['group_count']==2
    assert client.post('/api/v1/overview/settle',json=body,headers=headers).json()==received.json()
    assert client.get('/api/v1/overview').json()['people']==[]
    for gid in gids:assert client.get(f'/api/v1/groups/{gid}/finance').json()['summary']['receivable']==0
    assert client.post('/api/v1/overview/settle',json=body,headers={'Idempotency-Key':'stale-global-receive'}).status_code==409


def test_overview_keeps_virtual_names_and_currencies_separate(client):
    login(client)
    for index,currency in enumerate(('EUR','EUR','USD')):
        gid=client.post('/api/v1/groups',json={'name':f'Gruppo {index}','currency':currency}).json()['id']
        virtual=client.post(f'/api/v1/groups/{gid}/participants',json={'name':'Stesso nome'}).json()['id']
        actor=client.get(f'/api/v1/groups/{gid}').json()['my_participant']
        body={'title':'Conto','date':'2026-11-03','items':[{'amount':'10','shares':{virtual:'1'},'payers':{actor:''}}]}
        client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'virtual-different-person'})
    view=client.get('/api/v1/overview').json();assert len(view['people'])==3
    assert view['totals']==[{'currency':'EUR','receive':2000,'pay':0},{'currency':'USD','receive':1000,'pay':0}]


def test_overview_privacy_sender_cannot_receive_and_viewer_cannot_settle(client,database):
    login(client);gid,ids=group(client)
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');before=carol.get('/api/v1/overview').json()
        client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,True),headers={'Idempotency-Key':'private-global-cost'})
        assert carol.get('/api/v1/overview').json()==before
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');row=bob.get('/api/v1/overview').json()['people'][0]
        assert row['direction']=='pay'
        assert bob.post('/api/v1/overview/settle',json={'key':row['key'],'fingerprint':row['fingerprint']},headers={'Idempotency-Key':'sender-global-forbidden'}).status_code==403
    with database() as db:db.get(Participant,ids['alice']).role='viewer';db.commit()
    row=client.get('/api/v1/overview').json()['people'][0];assert row['can_settle'] is False
    assert client.post('/api/v1/overview/settle',json={'key':row['key'],'fingerprint':row['fingerprint']},headers={'Idempotency-Key':'viewer-global-forbidden'}).status_code==403


def test_overview_all_groups_rollback_on_partial_failure(client,database,monkeypatch):
    from app import overview
    login(client)
    for index in range(2):
        gid,ids=group(client)
        client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids),headers={'Idempotency-Key':f'rollback-overview-{index}'})
    row=client.get('/api/v1/overview').json()['people'][0];original=overview.record_transfer;calls=[]
    def fail_second(*args,**kwargs):
        calls.append(True)
        if len(calls)==2:raise HTTPException(409,'Simulazione conflitto')
        return original(*args,**kwargs)
    monkeypatch.setattr(overview,'record_transfer',fail_second)
    response=client.post('/api/v1/overview/settle',json={'key':row['key'],'fingerprint':row['fingerprint']},headers={'Idempotency-Key':'atomic-overview-failure'})
    assert response.status_code==409
    with database() as db:assert db.scalar(select(func.count()).select_from(Settlement))==0
    assert client.get('/api/v1/overview').json()['totals'][0]['receive']==1000
