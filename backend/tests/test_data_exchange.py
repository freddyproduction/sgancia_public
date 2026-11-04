import csv,json,time
from io import StringIO,BytesIO
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import Expense,Entry,Participant,ImportBatch,ImportedExpense,Group,GuestLink
from app.data_exchange import safe_csv,ApplyIn,apply_import
from app.security import digest
from app.models import User
from conftest import login
from test_api import group,expense
from pypdf import PdfReader


def seed(client,gid,ids,secret=False,**changes):
    body={**expense(ids,secret),**changes}
    r=client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':__import__('uuid').uuid4().hex});assert r.status_code==201,r.text
    return r.json()['id']


def preview(client,gid,content,format='json',**kw):return client.post(f'/api/v1/groups/{gid}/imports/preview',json={'format':format,'content':content,**kw})


def apply(client,gid,bid,selected=[0],force=[],**kw):return client.post(f'/api/v1/groups/{gid}/imports/{bid}/apply',json={'selected':selected,'force_duplicates':force,'confirm':True,**kw})


def target(client,source,old):
    gid,ids=group(client)
    mapping={old[k]:ids[k] for k in old}
    return gid,ids,mapping


def test_authorized_exports_json_csv_pdf_and_hidden_independence(client):
    login(client);gid,ids=group(client);seed(client,gid,ids,title='Public',tags=['pub'])
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');base=f'/api/v1/groups/{gid}/export'
        first=carol.get(base).json()
        seed(client,gid,ids,True,title='Invisible secret',tags=['not-shared'])
        assert first==carol.get(base).json()
        assert len(first['expenses'])==1 and first['total']==10000
        assert 'email' not in json.dumps(first) and 'user_id' not in json.dumps(first)
        for format in ('csv','pdf'):
            r=carol.get(base+'?format='+format);assert r.status_code==200,r.text[:100] if format=='csv' else r.status_code
            text=r.text if format=='csv' else '\n'.join(p.extract_text() for p in PdfReader(BytesIO(r.content)).pages)
            assert 'Invisible secret' not in text and 'not-shared' not in text
        assert carol.get(base+'?q=Invisible').json()['expenses']==[]


def test_json_import_roundtrip_mapping_and_atomic_repeat(client,database):
    login(client);gid,ids=group(client);seed(client,gid,ids,True,tags=['QA'])
    data=client.get(f'/api/v1/groups/{gid}/export').text
    dest,new,mapping=target(client,gid,ids)
    missing=preview(client,dest,data);assert missing.status_code==200,missing.text
    assert missing.json()['rows'][0]['status']=='error'
    ready=preview(client,dest,data,mapping=mapping);assert ready.status_code==200,ready.text
    p=ready.json();assert p['rows'][0]['status']=='ready' and p['rows'][0]['total']==10000 and p['rows'][0]['private']
    with database() as db:
        batch=db.get(ImportBatch,p['id']);assert 'Regalo' not in batch.payload and not batch.applied
        assert db.scalar(select(func.count()).select_from(Expense).where(Expense.group_id==dest))==0
    result=apply(client,dest,p['id']);assert result.status_code==200,result.text
    assert apply(client,dest,p['id']).json()==result.json()
    with database() as db:
        entries=list(db.scalars(select(Entry).where(Entry.group_id==dest)));assert sum(e.paid for e in entries)==sum(e.owed for e in entries)==10000
        assert db.scalar(select(func.count()).select_from(Expense).where(Expense.group_id==dest))==1
    repeat=preview(client,dest,data,mapping=mapping).json();assert repeat['rows'][0]['status']=='imported'
    assert apply(client,dest,repeat['id']).status_code==422


def test_csv_roundtrip_exact_private_allocations_and_names(client,database):
    login(client);gid,ids=group(client);seed(client,gid,ids,True,title="'=original",description='=HYPERLINK("bad")',tags=['t'])
    data=client.get(f'/api/v1/groups/{gid}/export?format=csv');assert data.status_code==200
    parsed=list(csv.DictReader(StringIO(data.content.decode('utf-8-sig'))));assert parsed[0]['description'].startswith("'=")
    dest,new,mapping=target(client,gid,ids)
    ready=preview(client,dest,data.content.decode('utf-8-sig'),'csv',mapping=mapping);assert ready.status_code==200,ready.text
    p=ready.json();assert p['rows'][0]['status']=='ready' and p['participants'][0]['name'] in ('Alice','Bob')
    result=apply(client,dest,p['id']);assert result.status_code==200,result.text
    row=client.get(f'/api/v1/groups/{dest}/expenses').json()[0];assert row['title']=="'=original" and row['description']=='=HYPERLINK("bad")'
    assert row['secret'] and row['total']==10000


def test_csv_formula_guard_reversible_for_dangerous_prefixes():
    for value in ('=1+1','+cmd','-cmd','@SUM(A1)','\t=1','\r=1','\n=1','  =1','\ufeff=1','\u200b@SUM(A1)','＝1',"'literal"):
        escaped=safe_csv(value);assert escaped.startswith("'") and escaped[1:]==value
    assert safe_csv('Normal')=='Normal'


def test_csv_simple_errors_and_selected_valid_rows_only(client,database):
    login(client);gid,ids=group(client)
    data='date,title,amount,paid_by,split_between,source_id\n2026-11-03,Valid,40,a,a|b,one\n2026-11-03,Bad,no,a,a|b,two\n'
    p=preview(client,gid,data,'csv',mapping={'a':ids['alice'],'b':ids['bob']});assert p.status_code==200,p.text
    p=p.json();assert [r['status'] for r in p['rows']]==['ready','error']
    assert apply(client,gid,p['id'],[0,1]).status_code==422
    with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==0
    assert apply(client,gid,p['id'],[0]).status_code==200


def test_visible_duplicate_requires_explicit_force_hidden_duplicate_does_not_leak(client):
    login(client);gid,ids=group(client);seed(client,gid,ids)
    content=client.get(f'/api/v1/groups/{gid}/export').text
    p=preview(client,gid,content).json();assert p['rows'][0]['status']=='duplicate'
    assert apply(client,gid,p['id']).status_code==409
    assert apply(client,gid,p['id'],force=[0]).status_code==200


def test_repeated_source_ids_rejected_before_any_write(client,database):
    login(client);gid,ids=group(client);seed(client,gid,ids)
    data=client.get(f'/api/v1/groups/{gid}/export').json();data['expenses'].append(data['expenses'][0])
    dest,new,mapping=target(client,gid,ids);p=preview(client,dest,json.dumps(data),mapping=mapping).json()
    assert p['rows'][1]['status']=='error'
    assert apply(client,dest,p['id'],[0,1],force=[1]).status_code==422
    with database() as db:assert db.scalar(select(func.count()).select_from(Expense).where(Expense.group_id==dest))==0


def test_private_audience_cannot_omit_importer_or_collapse_people(client):
    login(client);gid,ids=group(client);seed(client,gid,ids,True)
    content=client.get(f'/api/v1/groups/{gid}/export').text
    dest,new,mapping=target(client,gid,ids);mapping[ids['alice']]=new['carol'];mapping[ids['bob']]=new['bob']
    p=preview(client,dest,content,mapping=mapping).json();assert p['rows'][0]['status']=='error'
    mapping={ids['alice']:new['alice'],ids['bob']:new['alice']}
    assert preview(client,dest,content,mapping=mapping).json()['rows'][0]['status']=='error'


def test_expired_preview_currency_change_departure_and_other_account_blocked(client,database):
    login(client);gid,ids=group(client)
    content='date,title,amount,paid_by,split_between\n2026-11-03,Import,40,a,a|b\n';mapping={'a':ids['alice'],'b':ids['bob']}
    p=preview(client,gid,content,'csv',mapping=mapping).json()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert apply(bob,gid,p['id']).status_code==404
    with database() as db:db.get(ImportBatch,p['id']).expires=1;db.commit()
    assert apply(client,gid,p['id']).status_code==409
    p=preview(client,gid,content,'csv',mapping=mapping).json()
    with database() as db:db.get(Group,gid).currency='USD';db.commit()
    assert apply(client,gid,p['id']).status_code==409
    with database() as db:db.get(Group,gid).currency='EUR';db.get(Participant,ids['bob']).active=False;db.commit()
    assert apply(client,gid,p['id']).status_code==409
    with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==0


def test_viewers_export_but_cannot_import_and_schema_bombs_rejected(client,database):
    login(client);gid,ids=group(client)
    with database() as db:db.get(Participant,ids['bob']).role='viewer';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.get(f'/api/v1/groups/{gid}/export').status_code==200
        assert preview(bob,gid,'{}').status_code==403
    for content in ('{"schema":1,"schema":2}','['*30+']'*30,'{"schema":NaN}','{"x":"\\u0000"}'):
        assert preview(client,gid,content).status_code==422
    assert preview(client,gid,'a'* (2*1024*1024+1)).status_code==422


def test_historical_fx_is_preserved_with_original_amounts(client,database,monkeypatch):
    from app.exchange import sign
    login(client);gid,ids=group(client)
    quote={'base':'USD','quote':'EUR','rate':'0.9','source':'QA BCE','date':'2026-11-02','issued':int(time.time())}
    seed(client,gid,ids,currency='USD',exchange_token=sign(quote))
    exported=client.get(f'/api/v1/groups/{gid}/export').json();assert exported['expenses'][0]['draft']['exchange_rate']=='0.9'
    dest,new,mapping=target(client,gid,ids)
    p=preview(client,dest,json.dumps(exported),mapping=mapping).json();assert p['rows'][0]['total']==9000
    result=apply(client,dest,p['id']);assert result.status_code==200,result.text
    history=client.get(f"/api/v1/groups/{dest}/expenses/{result.json()['ids'][0]}/history").json()
    conversion=history['versions'][0]['conversion'];assert conversion['rate']=='0.9' and conversion['date']=='2026-11-02' and 'QA BCE' in conversion['source'] and 'Importato' in conversion['source']
    original=exported['expenses'][0]['draft'];assert original['items'][0]['amount']=='40.00' and exported['expenses'][0]['total']==9000


def test_guest_exports_opt_in_redact_names_details_and_recheck_revocation(client,database):
    login(client);gid,ids=group(client);seed(client,gid,ids,title='Visible title');seed(client,gid,ids,True,title='Hidden title')
    path=f'/api/v1/groups/{gid}/guest-links'
    def link(**kw):
        r=client.post(path,json=kw);assert r.status_code==201,r.text
        data=r.json();return data['id'],data['url'].split('#')[1]
    lid,token=link()
    assert client.post('/api/v1/guest/export',json={'token':token}).status_code==404
    lid,token=link(show_exports=True,show_names=False,show_details=False,password='qa-password')
    for format in ('json','csv','pdf'):
        r=client.post('/api/v1/guest/export',json={'token':token,'password':'qa-password','format':format});assert r.status_code==200,r.text[:100] if format!='pdf' else r.status_code
        text=r.text if format!='pdf' else '\n'.join(p.extract_text() for p in PdfReader(BytesIO(r.content)).pages)
        for secret in ('Alice','Bob','Visible title','Hidden title',ids['alice']):assert secret not in text
    assert client.post('/api/v1/guest/export',json={'token':token,'password':'wrong'}).status_code==403
    assert client.delete(path+'/'+lid).status_code==204
    assert client.post('/api/v1/guest/export',json={'token':token,'password':'qa-password'}).status_code==404


def test_guest_export_counts_uses_and_expiry(client,database):
    login(client);gid,ids=group(client);path=f'/api/v1/groups/{gid}/guest-links'
    r=client.post(path,json={'show_exports':True,'max_uses':1}).json();token=r['url'].split('#')[1]
    assert client.post('/api/v1/guest/export',json={'token':token,'format':'json'}).status_code==200
    assert client.post('/api/v1/guest/export',json={'token':token,'format':'json'}).status_code==404
    r=client.post(path,json={'show_exports':True}).json();token=r['url'].split('#')[1]
    with database() as db:db.get(GuestLink,r['id']).expires=1;db.commit()
    assert client.post('/api/v1/guest/export',json={'token':token}).status_code==404


def test_concurrent_import_is_idempotent_postgresql(client,database):
    import pytest
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row locks')
    login(client);gid,ids=group(client);content='date,title,amount,paid_by,split_between\n2026-11-03,Concurrent,40,a,a|b\n'
    p=preview(client,gid,content,'csv',mapping={'a':ids['alice'],'b':ids['bob']}).json()
    def worker(_):
        with database() as db:return apply_import(gid,p['id'],ApplyIn(selected=[0],confirm=True),db.get(User,'alice'),db)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(worker,range(2)))
    assert results[0]==results[1]
    with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==1


def test_hidden_import_origin_is_not_disclosed_to_another_participant(client):
    login(client);gid,ids=group(client);seed(client,gid,ids,True)
    exported=client.get(f'/api/v1/groups/{gid}/export').text
    dest,new,mapping=target(client,gid,ids)
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');other={ids['alice']:new['carol'],ids['bob']:new['bob']}
        before=preview(carol,dest,exported,mapping=other).json()
        own=preview(client,dest,exported,mapping=mapping).json();assert apply(client,dest,own['id']).status_code==200
        after=preview(carol,dest,exported,mapping=other).json()
        assert before['rows']==after['rows'] and after['rows'][0]['status']=='ready'


def test_failed_guest_report_does_not_consume_last_use(client,database,monkeypatch):
    import app.data_exchange as exchange
    from fastapi import HTTPException
    login(client);gid,ids=group(client)
    r=client.post(f'/api/v1/groups/{gid}/guest-links',json={'show_exports':True,'max_uses':1}).json();token=r['url'].split('#')[1]
    monkeypatch.setattr(exchange,'download',lambda *args,**kw:(_ for _ in ()).throw(HTTPException(413,'QA too large')))
    assert client.post('/api/v1/guest/export',json={'token':token}).status_code==413
    with database() as db:assert db.get(GuestLink,r['id']).uses==0


def test_pdf_escapes_markup_and_preserves_accents(client):
    login(client);gid,ids=group(client);seed(client,gid,ids,title='Caffè e città <img src="file:///private">',description='<a href="https://example.org">link</a>')
    pdf=client.get(f'/api/v1/groups/{gid}/export?format=pdf');assert pdf.status_code==200
    reader=PdfReader(BytesIO(pdf.content));text='\n'.join(p.extract_text() for p in reader.pages)
    assert 'Caffè e città' in text and '<img src=' in text and '<a href=' in text
    assert not reader.trailer['/Root'].get('/OpenAction') and not reader.trailer['/Root'].get('/Names')
    assert all(not p.get('/Annots') for p in reader.pages)


def test_native_import_preserves_cent_allocation_with_reversed_id_mapping_and_fx(client,database):
    from app.models import ExpenseRevision
    from app.exchange import sign
    login(client);gid,ids=group(client)
    ordered=sorted([ids['alice'],ids['bob']]);first,second=ordered
    draft={'title':'Tie FX','payers':{},'date':'2026-11-03','currency':'USD','exchange_token':sign({'base':'USD','quote':'EUR','rate':'1000','source':'QA','date':'2026-11-03','issued':int(time.time())}),'items':[{'title':'One cent','amount':'0.01','mode':'equal','shares':{first:'1',second:'1'},'payers':{first:'',second:''}}]}
    eid=seed(client,gid,ids,**draft)
    exported=client.get(f'/api/v1/groups/{gid}/export').json()
    dest,new,_=target(client,gid,ids);new_sorted=sorted([new['alice'],new['bob']]);mapping={first:new_sorted[1],second:new_sorted[0]}
    p=preview(client,dest,json.dumps(exported),mapping=mapping).json();assert p['rows'][0]['status']=='ready'
    result=apply(client,dest,p['id']);assert result.status_code==200,result.text
    with database() as db:
        old={e.participant_id:(e.paid,e.owed) for e in db.scalars(select(Entry).where(Entry.expense_id==eid))}
        actual={e.participant_id:(e.paid,e.owed) for e in db.scalars(select(Entry).where(Entry.expense_id==result.json()['ids'][0]))}
        assert actual=={mapping[ref]:value for ref,value in old.items()}
        assert actual[mapping[first]]==(1000,1000) and actual[mapping[second]]==(0,0)


def test_revealing_imported_expense_removes_observer_only_rounding_reference(client,database):
    from app.models import ExpenseRevision
    login(client);gid,ids=group(client)
    draft={'title':'Rounding audience','payers':{},'audience':list(ids.values()),'allocation_order':list(ids.values()),'items':[{'title':'Tiny','amount':'0.01','mode':'equal','shares':{ids['alice']:'1',ids['bob']:'1'},'payers':{ids['alice']:''}}]}
    eid=seed(client,gid,ids,**draft)
    result=client.post(f'/api/v1/groups/{gid}/expenses/{eid}/reveal',headers={'If-Match':'1'});assert result.status_code==200,result.text
    data=client.get(f'/api/v1/groups/{gid}/export').json()['expenses'][0]['draft']
    assert ids['carol'] not in data['allocation_order']
    with database() as db:assert ids['carol'] in db.get(ExpenseRevision,(eid,1)).snapshot['audience']
