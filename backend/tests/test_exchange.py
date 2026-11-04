import time
from decimal import Decimal
from fastapi.testclient import TestClient
from app.main import app
from app import exchange
from app.models import ExpenseRevision,CurrencyChange
from sqlalchemy import select
from conftest import login
from test_api import group,expense


def quote(monkeypatch,client,base='USD',target='EUR',rate='0.9'):
    exchange._cache.clear()
    monkeypatch.setattr(exchange,'fetch_rate',lambda b,q:{'base':b,'quote':q,'rate':rate,'date':'2026-11-02','source':'Test reference'})
    response=client.get('/api/v1/exchange-rate',params={'base':base,'quote':target})
    assert response.status_code==200,response.text
    return response.json()


def test_converted_expense_preserves_exact_total_payers_shares_and_original(client,database,monkeypatch):
    login(client);gid,ids=group(client)
    fx=quote(monkeypatch,client)
    body=expense(ids,True);body.update(currency='USD',exchange_token=fx['token'])
    path=f'/api/v1/groups/{gid}/expenses'
    preview=client.post(path+'/preview',json=body)
    assert preview.status_code==200,preview.text
    data=preview.json();assert data['total']==9000
    assert sum(data['paid'].values())==sum(data['owed'].values())==9000
    created=client.post(path,json=body,headers={'Idempotency-Key':'foreign-expense-create'})
    assert created.status_code==201,created.text
    eid=created.json()['id']
    draft=client.get(path+'/'+eid).json()['draft']
    assert draft['currency']=='USD' and draft['exchange_token']==fx['token']
    # Legacy aggregate advances are reconstructed in the original currency.
    assert sum(Decimal(v) for item in draft['items'] for v in item['payers'].values())==100
    assert client.put(path+'/'+eid,json=draft,headers={'If-Match':'1'}).json()['total']==9000
    with database() as db:assert db.get(ExpenseRevision,(eid,1)).snapshot['items'][0]['amount']=='40.00'
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(path).json()==[]


def test_fx_tampering_stale_pair_manual_and_rounding(client,monkeypatch):
    login(client);gid,ids=group(client);fx=quote(monkeypatch,client,rate='0.333333333333')
    body={'title':'Piccole quote','date':'2026-11-02','currency':'USD','exchange_token':fx['token'],'items':[{'amount':'1','payers':{ids['alice']:''},'shares':{v:'1' for v in ids.values()}}]}
    path=f'/api/v1/groups/{gid}/expenses/preview'
    result=client.post(path,json=body).json();assert result['total']==33 and sum(result['owed'].values())==33
    body['currency']='GBP';assert client.post(path,json=body).status_code==422
    body['currency']='USD';body['exchange_token']=fx['token'][:-1]+'x';assert client.post(path,json=body).status_code==422
    data=exchange.read_quote(fx['token'],'USD','EUR');data['issued']=int(time.time())-86401
    body['exchange_token']=exchange.sign(data);assert client.post(path,json=body).status_code==422
    body['exchange_token']=None;body['exchange_rate']='0.5'
    assert client.post(path,json=body).json()['total']==50
    body['exchange_rate']='NaN';assert client.post(path,json=body).status_code==422
    body['exchange_rate']='0.00000001';assert client.post(path,json=body).status_code==422
    assert client.get('/api/v1/exchange-rate?base=../../x&quote=EUR').status_code==422


def test_provider_failure_no_stale_fallback_and_cache(client,monkeypatch):
    login(client);exchange._cache.clear();calls=[]
    def fetch(b,q):calls.append((b,q));return {'base':b,'quote':q,'rate':'0.9','source':'Test','date':'2026-11-02'}
    monkeypatch.setattr(exchange,'fetch_rate',fetch)
    for _ in range(2):assert client.get('/api/v1/exchange-rate?base=USD&quote=EUR').status_code==200
    assert len(calls)==1
    exchange._cache.clear()
    monkeypatch.setattr(exchange,'fetch_rate',lambda *_:(_ for _ in ()).throw(TimeoutError()))
    assert client.get('/api/v1/exchange-rate?base=USD&quote=EUR').status_code==503


def test_change_group_currency_revision_trash_restore_and_permissions(client,database,monkeypatch):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}'
    eid=client.post(path+'/expenses',json=expense(ids,True),headers={'Idempotency-Key':'rebase-private'}).json()['id']
    client.delete(path+'/expenses/'+eid,headers={'If-Match':'1'})
    fx=quote(monkeypatch,client,'EUR','USD','1.25')
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.put(path+'/currency',json={'currency':'USD','exchange_token':fx['token']},headers={'If-Match':'1'}).status_code==403
    response=client.put(path+'/currency',json={'currency':'USD','exchange_token':fx['token']},headers={'If-Match':'1'})
    assert response.status_code==200,response.text
    assert response.json()['currency']=='USD'
    assert client.put(path+'/currency',json={'currency':'GBP','exchange_rate':'1'},headers={'If-Match':'1'}).status_code==409
    assert client.post(path+'/expenses/'+eid+'/restore',headers={'If-Match':'3'}).status_code==200
    finance=client.get(path+'/finance').json();assert finance['summary']['expenses_total']==12500
    assert finance['summary']['balance']==625
    draft=client.get(path+'/expenses/'+eid).json()['draft'];assert draft['currency']=='USD'
    assert client.put(path+'/expenses/'+eid,json=draft,headers={'If-Match':'4'}).status_code==200
    with database() as db:
        assert db.get(ExpenseRevision,(eid,1)).snapshot['items'][0]['amount']=='40.00'
        assert len(list(db.scalars(select(CurrencyChange))))==1
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.get(path+'/finance').json()['summary']['expenses_total']==0


def test_undo_receipt_only_receiver_and_retry_does_not_settle_again(client):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}'
    client.post(path+'/expenses',json=expense(ids),headers={'Idempotency-Key':'receipt-undo-expense'})
    row=client.get(path+'/finance').json()['transfers'][0]
    body={'sender':row['from'],'recipient':row['to'],'components':row['components'],'fingerprint':row['fingerprint']}
    result=client.post(path+'/settlements/settle-transfer',json=body,headers={'Idempotency-Key':'undo-receipt-key'})
    assert result.status_code==200
    sid=result.json()['ids'][0]
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.post(path+'/settlements/'+sid+'/undo').status_code==403
    assert client.post(path+'/settlements/'+sid+'/undo').status_code==200
    assert client.post(path+'/settlements/'+sid+'/undo').status_code==200
    assert client.get(path+'/finance').json()['summary']['receivable']==500
    assert client.post(path+'/settlements/settle-transfer',json=body,headers={'Idempotency-Key':'undo-receipt-key'}).status_code==409
    assert client.post(path+'/settlements/settle-transfer',json=body,headers={'Idempotency-Key':'settle-new-after-undo'}).status_code==200


def test_regular_recipient_can_settle_but_debtor_cannot(client):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}'
    body={'title':'Bob anticipa','date':'2026-11-02','items':[{'amount':'20','payers':{ids['bob']:''},'shares':{ids['bob']:'1',ids['carol']:'1'}}]}
    client.post(path+'/expenses',json=body,headers={'Idempotency-Key':'bob-recipient-cost'})
    row=client.get(path+'/finance').json()['transfers'][0]
    payload={'sender':row['from'],'recipient':row['to'],'components':row['components'],'fingerprint':row['fingerprint']}
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert carol.post(path+'/settlements/settle-transfer',json=payload,headers={'Idempotency-Key':'debtor-cannot-settle'}).status_code==403
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');response=bob.post(path+'/settlements/settle-transfer',json=payload,headers={'Idempotency-Key':'recipient-can-settle'})
        assert response.status_code==200 and response.json()['status']=='confirmed'
        assert bob.post(path+'/settlements/'+response.json()['ids'][0]+'/undo').status_code==200


def test_rebase_preserves_item_payers_and_converts_confirmed_receipt(client,database):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}'
    a,b=ids['alice'],ids['bob']
    body={'title':'Due pagatori','date':'2026-11-02','items':[{'amount':'20','shares':{a:'1',b:'1'},'payers':{a:''}},{'amount':'10','shares':{a:'1',b:'1'},'payers':{b:''}}]}
    eid=client.post(path+'/expenses',json=body,headers={'Idempotency-Key':'two-payer-rebase'}).json()['id']
    row=client.get(path+'/finance').json()['transfers'][0]
    payload={'sender':row['from'],'recipient':row['to'],'components':row['components'],'fingerprint':row['fingerprint']}
    receipt=client.post(path+'/settlements/settle-transfer',json=payload,headers={'Idempotency-Key':'pre-rebase-receipt'}).json()
    assert client.put(path+'/currency',json={'currency':'USD','exchange_rate':'1.25'},headers={'If-Match':'1'}).status_code==200
    finance=client.get(path+'/finance').json();assert finance['transfers']==[]
    draft=client.get(path+'/expenses/'+eid).json()['draft']
    assert draft['items'][0]['payers']=={a:'25.00'}
    assert draft['items'][1]['payers']=={b:'12.50'}
    assert client.get(path+'/settlements').json()[0]['amount']==625
    with database() as db:
        change=db.scalar(select(CurrencyChange));assert change.snapshot['settlements'][0]['before']==500
    assert client.post(path+'/settlements/'+receipt['ids'][0]+'/undo').status_code==200
    assert client.get(path+'/finance').json()['summary']['receivable']==625


def test_failed_rebase_rolls_back_every_revision_and_currency(client,database):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}'
    for i,amount in enumerate(('10000','0.01')):
        body={'title':'Voce','date':'2026-11-02','items':[{'amount':amount,'payers':{ids['alice']:''},'shares':{ids['alice']:'1',ids['bob']:'1'}}]}
        assert client.post(path+'/expenses',json=body,headers={'Idempotency-Key':f'atomic-rebase-{i}'}).status_code==201
    before=client.get(path+'/expenses').json()
    result=client.put(path+'/currency',json={'currency':'USD','exchange_rate':'0.001'},headers={'If-Match':'1'})
    assert result.status_code==422
    assert client.get(path).json()['currency']=='EUR'
    assert client.get(path+'/expenses').json()==before
    with database() as db:assert list(db.scalars(select(CurrencyChange)))==[]


def test_historical_automatic_quote_kept_on_edit_but_not_new_expense(client,monkeypatch):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}/expenses'
    fx=quote(monkeypatch,client)
    body=expense(ids);body.update(currency='USD',exchange_token=fx['token'])
    created=client.post(path,json=body,headers={'Idempotency-Key':'historical-quote-first'}).json()
    original_time=exchange.time.time
    from types import SimpleNamespace
    monkeypatch.setattr(exchange,'time',SimpleNamespace(time=lambda:original_time()+90000))
    draft=client.get(path+'/'+created['id']).json()['draft']
    draft['title']='Correzione titolo'
    assert client.post(path+'/preview',json=draft).status_code==200
    result=client.put(path+'/'+created['id'],json=draft,headers={'If-Match':'1'})
    assert result.status_code==200,result.text
    assert result.json()['total']==9000
    assert client.post(path,json=body,headers={'Idempotency-Key':'historical-quote-not-new'}).status_code==422


def test_live_currency_calculator_uses_same_exact_rounding(client,monkeypatch):
    login(client);fx=quote(monkeypatch,client,rate='0.9')
    response=client.post('/api/v1/currency-conversion',json={'amount':'(10+2.50)*2','base':'USD','quote':'EUR','token':fx['token']})
    assert response.status_code==200,response.text
    assert response.json()=={'original':2500,'converted':2250,'currency':'EUR'}
    assert client.post('/api/v1/currency-conversion',json={'amount':'10','base':'USD','quote':'GBP','token':fx['token']}).status_code==422
