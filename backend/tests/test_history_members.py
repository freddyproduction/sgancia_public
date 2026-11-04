import time
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.models import Participant,Group,ExpenseRevision,Entry,Settlement,VirtualDelegation,ParticipantClaim,GroupInvite,Invite
from conftest import login
from test_api import group,expense


def cost(client,gid,ids,private=False):
    response=client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,private),headers={'Idempotency-Key':'new-block-cost-'+str(private)})
    assert response.status_code==201,response.text
    return response.json()['id']


def test_history_versions_actor_rates_and_private_disputes(client):
    login(client);gid,ids=group(client);eid=cost(client,gid,ids,True);base=f'/api/v1/groups/{gid}/expenses/{eid}'
    with TestClient(app,base_url='http://localhost:8088') as bob,TestClient(app,base_url='http://localhost:8088') as carol:
        login(bob,'bob');login(carol,'carol')
        assert carol.get(base+'/history').status_code==404
        assert carol.post(base+'/disputes',json={'reason':'Quota errata'},headers={'If-Match':'1'}).status_code==404
        d=bob.post(base+'/disputes',json={'reason':'Quota errata'},headers={'If-Match':'1'})
        assert d.status_code==201,d.text
        assert bob.post(base+'/disputes',json={'reason':'Ripetuta'},headers={'If-Match':'1'}).status_code==409
        did=d.json()['id']
        assert bob.get(base+'/history').json()['can_dispute'] is False
        assert bob.put(base+'/disputes/'+did,json={'status':'resolved','reason':'Mi approvo'}).status_code==403
        body=expense(ids,True);body['title']='Quota corretta'
        assert client.put(base,json=body,headers={'If-Match':'1'}).status_code==200
        assert client.put(base+'/disputes/'+did,json={'status':'resolved','reason':'Controllate le quote nella versione 2'}).status_code==200
        data=bob.get(base+'/history').json()
        assert len(data['versions'])==2 and data['versions'][1]['actor']=='Alice' and data['versions'][1]['changed']==['title']
        assert data['disputes'][0]['status']=='resolved' and data['disputes'][0]['resolver']=='Alice'
        assert client.post(base+'/reveal',headers={'If-Match':'2'}).status_code==200
        shown=carol.get(base+'/history').json()
        assert len(shown['versions'])==1 and shown['disputes']==[]


def test_settlement_dispute_resolution_is_receiver_only_and_recorded(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}/settlements'
    row=client.post(base,json={'sender':ids['alice'],'recipient':ids['bob'],'amount':'10'},headers={'Idempotency-Key':'disputed-receipt'}).json();path=base+'/'+row['id']
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.put(path,json={'status':'disputed'}).status_code==422
        assert bob.put(path,json={'status':'disputed','reason':'Bonifico non arrivato'}).status_code==200
        assert client.put(path,json={'status':'confirmed','reason':'Ho inviato'}).status_code==403
        assert bob.put(path,json={'status':'confirmed','reason':'Bonifico arrivato oggi'}).status_code==200
        assert bob.post(path+'/undo').status_code==200
    history=client.get(path+'/history').json()['events']
    assert [e['status'] for e in history]==['pending','disputed','confirmed','cancelled']
    assert history[1]['reason']=='Bonifico non arrivato' and history[2]['actor']=='Bob'


def test_ownership_offer_accept_stale_and_old_owner_cannot_delete(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    assert client.post(base+'/ownership',json={'target':ids['bob']},headers={'If-Match':'99'}).status_code==409
    op=client.post(base+'/ownership',json={'target':ids['bob']},headers={'If-Match':'1'}).json()
    assert client.post(base+'/ownership/'+op['id']+'/accept').status_code==403
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.get(base+'/operations').json()[0]['can_accept']
        assert bob.post(base+'/ownership/'+op['id']+'/accept').status_code==200
        assert bob.get(base).json()['role']=='owner'
        assert client.get(base).json()['role']=='admin'
        assert client.delete(base,headers={'If-Match':'3'}).status_code==403
        assert bob.post(base+'/ownership/'+op['id']+'/accept').status_code==404


def test_depart_with_balance_requires_explicit_retention_and_revokes_access(client,database):
    login(client);gid,ids=group(client);cost(client,gid,ids);base=f'/api/v1/groups/{gid}'
    with database() as db:
        db.add(GroupInvite(token_hash='departure-email-invite',group_id=gid,role='member',email='bob@example.org',expires=int(time.time())+3600));db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');preview=bob.get(base+f'/participants/{ids["bob"]}/departure-preview').json()
        assert preview['keep_balance_required']
        path=base+f'/participants/{ids["bob"]}/depart'
        assert bob.post(path,json={'fingerprint':preview['fingerprint']}).status_code==409
        assert bob.post(path,json={'fingerprint':preview['fingerprint'],'keep_balance':True}).status_code==200
        assert bob.get(base).status_code==404 and bob.get('/api/v1/groups').json()==[]
        assert bob.get('/api/v1/overview').json()['people']==[]
    with database() as db:
        p=db.get(Participant,ids['bob']);assert p.user_id is None and not p.active
        assert db.get(GroupInvite,'departure-email-invite').used
    assert client.get(base+'/finance').json()['summary']['receivable']==500
    assert client.post(base+f'/participants/{ids["bob"]}/reactivate').status_code==200
    assert client.get(base).json()['participants'][1]['active'] is True


def test_owner_cannot_leave_and_preview_stales(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    assert client.get(base+f'/participants/{ids["alice"]}/departure-preview').status_code==403
    preview=client.get(base+f'/participants/{ids["bob"]}/departure-preview').json()
    cost(client,gid,ids)
    assert client.post(base+f'/participants/{ids["bob"]}/depart',json={'keep_balance':True,'fingerprint':preview['fingerprint']}).status_code==409


def test_delegated_payment_attestation_and_revocation(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    v=client.post(base+'/participants',json={'name':'Virtuale'}).json()['id']
    body={'virtual_id':v,'delegate_id':ids['bob'],'pay':True,'attest':True,'days':1}
    grant=client.post(base+'/delegations',json=body);assert grant.status_code==201
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');payment={'sender':v,'recipient':ids['alice'],'amount':'3'}
        p=bob.post(base+'/settlements',json=payment,headers={'Idempotency-Key':'delegate-payment-test'})
        assert p.status_code==201,p.text
        assert client.put(base+'/settlements/'+p.json()['id'],json={'status':'confirmed'}).status_code==200
        incoming=client.post(base+'/settlements',json={'sender':ids['alice'],'recipient':v,'amount':'2'},headers={'Idempotency-Key':'virtual-receive-test'}).json()['id']
        assert bob.put(base+'/settlements/'+incoming,json={'status':'confirmed'}).status_code==200
        assert bob.post(base+'/settlements/'+incoming+'/undo').status_code==200
        assert bob.delete(base+'/delegations/'+grant.json()['id']).status_code==403
        assert client.delete(base+'/delegations/'+grant.json()['id']).status_code==204
        assert bob.post(base+'/settlements',json=payment,headers={'Idempotency-Key':'delegate-after-revoke'}).status_code==403
        assert bob.get(base+'/delegations').json()==[]


def test_claim_revokes_delegation_and_pending_tokens(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    v=client.post(base+'/participants',json={'name':'Virtuale'}).json()['id']
    client.post(base+'/delegations',json={'virtual_id':v,'delegate_id':ids['bob'],'attest':True})
    token=client.post(base+f'/participants/{v}/claim',json={'email':'dave@example.org'}).json()['token']
    with TestClient(app,base_url='http://localhost:8088') as dave:
        login(dave,'dave');assert dave.post('/api/v1/participants/claim',json={'token':token}).status_code==200
        assert dave.post('/api/v1/participants/claim',json={'token':token}).status_code==404
    with database() as db:assert db.scalar(select(VirtualDelegation).where(VirtualDelegation.virtual_id==v)).revoked


def merge_setup(client):
    gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    v=client.post(base+'/participants',json={'name':'Duplicato Bob'}).json()['id']
    body={'title':'Quote esatte','date':'2026-11-03','items':[{'amount':'10','mode':'exact','shares':{v:'3',ids['bob']:'7'},'payers':{ids['alice']:''}}]}
    eid=client.post(base+'/expenses',json=body,headers={'Idempotency-Key':'merge-exact-cost'}).json()['id']
    return base,ids,v,eid


def test_merge_preserves_totals_old_revisions_and_undo(client,database):
    login(client);base,ids,v,eid=merge_setup(client);body={'source':v,'target':ids['bob']}
    before=client.get(base+'/finance').json()['summary']
    preview=client.post(base+'/merge/preview',json=body);assert preview.status_code==200,preview.text
    result=client.post(base+'/merge',json={**body,'fingerprint':preview.json()['fingerprint']});assert result.status_code==200,result.text
    after=client.get(base+'/finance').json()['summary'];assert after==before
    draft=client.get(base+'/expenses/'+eid).json();assert draft['draft']['items'][0]['shares']=={ids['bob']:'10.00'}
    with database() as db:
        assert db.get(ExpenseRevision,(eid,1)).snapshot['items'][0]['shares'][v]=='3.00'
        assert db.get(Participant,v).merged_into==ids['bob']
    assert client.post(base+'/operations/'+result.json()['id']+'/undo-merge').status_code==200
    restored=client.get(base+'/expenses/'+eid).json();assert restored['draft']['items'][0]['shares'][v]=='3.00'
    assert restored['version']==3


def test_merge_blocks_private_audience_mismatch_and_stale_preview(client):
    login(client);base,ids,v,eid=merge_setup(client);body={'source':v,'target':ids['bob']}
    preview=client.post(base+'/merge/preview',json=body).json()
    client.post(base+'/participants',json={'name':'Nuova persona'})
    assert client.post(base+'/merge',json={**body,'fingerprint':preview['fingerprint']}).status_code==409
    private={'title':'Segreto','date':'2026-11-03','audience':[ids['alice'],v],'items':[{'amount':'4','shares':{v:'1'},'payers':{ids['alice']:''}}]}
    assert client.post(base+'/expenses',json=private,headers={'Idempotency-Key':'merge-private-mismatch'}).status_code==201
    assert client.post(base+'/merge/preview',json=body).status_code==409
    assert client.get(base+'/expenses/'+eid).json()['version']==1


def test_viewer_cannot_dispute_or_manage_and_cross_group_opaque(client,database):
    login(client);base,ids,v,eid=merge_setup(client)
    with database() as db:db.get(Participant,ids['bob']).role='viewer';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob,TestClient(app,base_url='http://localhost:8088') as dave:
        login(bob,'bob');login(dave,'dave')
        assert bob.get(base+'/expenses/'+eid+'/history').status_code==200
        assert bob.post(base+'/expenses/'+eid+'/disputes',json={'reason':'No quote'},headers={'If-Match':'1'}).status_code==403
        assert bob.post(base+'/merge/preview',json={'source':v,'target':ids['bob']}).status_code==403
        assert dave.get(base+'/operations').status_code==404
        assert dave.get(base+'/expenses/'+eid+'/history').status_code==404


def test_merge_undo_refuses_later_changes_and_pending_invites_revoked(client,database):
    login(client);base,ids,v,eid=merge_setup(client)
    claim=client.post(base+f'/participants/{v}/claim',json={'email':'dave@example.org'}).json()['token']
    from app.security import digest
    with database() as db:
        gid=base.split('/')[-1]
        db.add(GroupInvite(token_hash='merge-invitation-hash',group_id=gid,participant_id=v,role='member',email='dave@example.org',expires=int(time.time())+3600))
        db.add(Invite(token_hash='merge-invitation-hash',email='dave@example.org',expires=int(time.time())+3600));db.commit()
    body={'source':v,'target':ids['bob']};preview=client.post(base+'/merge/preview',json=body).json()
    merged=client.post(base+'/merge',json={**body,'fingerprint':preview['fingerprint']}).json()
    with database() as db:
        assert db.get(ParticipantClaim,digest(claim)).used
        assert db.get(GroupInvite,'merge-invitation-hash').used and db.get(Invite,'merge-invitation-hash').used
    client.post(base+'/participants',json={'name':'Dopo fusione'})
    assert client.post(base+'/operations/'+merged['id']+'/undo-merge').status_code==409


def test_delegation_expiry_and_private_audience_do_not_grant_access(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}';eid=cost(client,gid,ids,True)
    v=client.post(base+'/participants',json={'name':'Virtuale'}).json()['id']
    grant=client.post(base+'/delegations',json={'virtual_id':v,'delegate_id':ids['carol'],'pay':True,'attest':True}).json()['id']
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        assert carol.get(base+'/expenses/'+eid+'/history').status_code==404
        with database() as db:db.get(VirtualDelegation,grant).expires=1;db.commit()
        assert carol.post(base+'/settlements',json={'sender':v,'recipient':ids['alice'],'amount':'1'},headers={'Idempotency-Key':'expired-delegation'}).status_code==403


def test_concurrent_merges_apply_once_on_postgres(client,database):
    import concurrent.futures,pytest
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row locks required')
    login(client);base,ids,v,eid=merge_setup(client);body={'source':v,'target':ids['bob']}
    preview=client.post(base+'/merge/preview',json=body).json();body['fingerprint']=preview['fingerprint']
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        responses=list(pool.map(lambda _:client.post(base+'/merge',json=body),range(2)))
    assert sorted(r.status_code for r in responses)==[200,404]
    assert client.get(base+'/expenses/'+eid).json()['version']==2
    assert client.get(base+'/finance').json()['summary']['receivable']==1000


def test_private_revision_files_remain_private_after_revelation(client):
    from test_attachments import upload
    login(client);gid,ids=group(client);eid=cost(client,gid,ids,True);base=f'/api/v1/groups/{gid}'
    file=upload(client,gid,eid).json()['id']
    assert client.post(base+'/expenses/'+eid+'/reveal',headers={'If-Match':'1'}).status_code==200
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        assert carol.get(base+'/expenses/'+eid+'/history').status_code==200
        assert carol.get(base+'/expenses/'+eid+'/attachments').json()==[]
        assert carol.get(base+'/attachments/'+file+'/content').status_code==404
    assert client.get(base+'/attachments/'+file+'/content').status_code==200


def test_departure_does_not_expose_hidden_balances_to_manager(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        body={'title':'Tra Bob e Carol','date':'2026-11-03','audience':[ids['bob'],ids['carol']],'items':[{'amount':'9','shares':{ids['carol']:'1'},'payers':{ids['bob']:''}}]}
        assert bob.post(base+'/expenses',json=body,headers={'Idempotency-Key':'private-departure-cost'}).status_code==201
    preview=client.get(base+f'/participants/{ids["bob"]}/departure-preview').json()
    assert preview['limited'] is True and preview['amounts']==[] and preview['pending'] is None
    assert client.get(base+'/operations').json()==[]


def test_history_keeps_original_manual_currency_after_conversion(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    body={'title':'Valuta storica','date':'2026-11-03','currency':'USD','exchange_rate':'0.8','items':[{'amount':'10','shares':{ids['bob']:'1'},'payers':{ids['alice']:''}}]}
    eid=client.post(base+'/expenses',json=body,headers={'Idempotency-Key':'historic-rate-cost'}).json()['id']
    response=client.put(base+'/currency',json={'currency':'GBP','exchange_rate':'0.9'},headers={'If-Match':'1'});assert response.status_code==200,response.text
    versions=client.get(base+'/expenses/'+eid+'/history').json()['versions']
    assert versions[0]['currency']=='USD' and versions[0]['conversion']=={'rate':'0.8','source':'Manuale','date':'2026-11-03'}
    assert versions[1]['currency']=='GBP' and versions[1]['snapshot']['items'][0]['amount']=='7.20'


def test_departure_checks_direct_cycle_gross_debts(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    for index,(debtor,payer) in enumerate((('alice','bob'),('bob','carol'),('carol','alice'))):
        body={'title':'Ciclo diretto','date':'2026-11-03','items':[{'amount':'4','shares':{ids[debtor]:'1'},'payers':{ids[payer]:''}}]}
        assert client.post(base+'/expenses',json=body,headers={'Idempotency-Key':f'direct-departure-{index}'}).status_code==201
    assert client.put(base+'/smart-balances',json={'enabled':False},headers={'If-Match':'1'}).status_code==200
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');preview=bob.get(base+f'/participants/{ids["bob"]}/departure-preview').json()
        assert all(a['balance']==0 for a in preview['amounts']) and preview['keep_balance_required']
        assert bob.post(base+f'/participants/{ids["bob"]}/depart',json={'fingerprint':preview['fingerprint']}).status_code==409
