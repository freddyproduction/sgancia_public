from fastapi.testclient import TestClient
from sqlalchemy import select
import pyotp
from app.main import app
from app.models import User, Instance, Session, Entry, Expense
from app.security import cipher
from conftest import login


def group(client):
    response = client.post('/api/v1/groups',json={'name':'Weekend al mare'})
    assert response.status_code==201, response.text
    gid=response.json()['id']
    for name in ('bob','carol'):
        assert client.post(f'/api/v1/groups/{gid}/participants',json={'name':name.title(),'email':name+'@example.org'}).status_code==201
    detail=client.get(f'/api/v1/groups/{gid}').json()
    ids={p['name'].lower():p['id'] for p in detail['participants']}
    return gid,ids


def expense(ids, secret=False):
    a,b=ids['alice'],ids['bob']
    return {'title':'Regalo' if secret else 'Cena','date':'2026-11-02','payers':{a:'40',b:'60'},'items':[
        {'title':'Parte comune','amount':'40','mode':'equal','shares':{a:'1',b:'1'}},
        {'title':'Quote percentuali','amount':'60','mode':'percent','shares':{a:'25',b:'75'}}], 'audience':[a,b] if secret else None}


def test_gate_auth_csrf_and_origin(client):
    assert client.get('/api/v1/groups').status_code==403
    login(client)
    assert client.post('/api/v1/groups',json={'name':'X'},headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert client.post('/api/v1/groups',json={'name':'X'},headers={'Origin':'https://evil.test'}).status_code==403
    assert client.get('/api/v1/auth/me').json()['name']=='Alice'
    assert client.get('/api/v1/groups').headers['cache-control']=='no-store'


def test_account_and_group_isolation(client):
    login(client)
    gid,_=group(client)
    with TestClient(app, base_url='http://localhost:8088') as outsider:
        login(outsider,'dave')
        for path in ('', '/expenses','/balances'):
            assert outsider.get(f'/api/v1/groups/{gid}'+path).status_code==404
        assert outsider.get('/api/v1/admin/users').status_code==403


def test_compound_multiple_payers_and_idempotency(client,database):
    login(client)
    gid,ids=group(client)
    body=expense(ids)
    url=f'/api/v1/groups/{gid}/expenses'
    preview=client.post(url+'/preview',json=body)
    assert preview.status_code==200,preview.text
    assert preview.json()['owed']=={ids['alice']:3500,ids['bob']:6500}
    headers={'Idempotency-Key':'test-key-123'}
    first=client.post(url,json=body,headers=headers)
    assert first.status_code==201,first.text
    assert client.post(url,json=body,headers=headers).json()==first.json()
    body['title']='Changed'
    assert client.post(url,json=body,headers=headers).status_code==409
    with database() as db:
        assert len(list(db.scalars(select(Expense))))==1
        assert sum(e.paid-e.owed for e in db.scalars(select(Entry)))==0


def test_secret_no_indirect_leaks(client):
    login(client)
    gid,ids=group(client)
    with TestClient(app, base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        before={p:carol.get(f'/api/v1/groups/{gid}/{p}').json() for p in ('expenses','balances')}
        assert client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,True),headers={'Idempotency-Key':'secret-123'}).status_code==201
        after={p:carol.get(f'/api/v1/groups/{gid}/{p}').json() for p in ('expenses','balances')}
        assert before==after
    assert client.get(f'/api/v1/groups/{gid}/balances').json()[0]['private']
    body=expense(ids,True)
    body['audience']=[ids['alice']]
    assert client.post(f'/api/v1/groups/{gid}/expenses/preview',json=body).status_code==422


def test_public_and_private_scopes_separate(client):
    login(client)
    gid,ids=group(client)
    for secret in (False,True):
        assert client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,secret),headers={'Idempotency-Key':f'new-key-{secret}'}).status_code==201
    scopes=client.get(f'/api/v1/groups/{gid}/balances').json()
    assert len(scopes)==2
    assert all(sum(s['balances'].values())==0 for s in scopes)
    assert all(sum(x['amount'] for x in s['suggestions'])==500 for s in scopes)


def test_suspended_and_rotated_gate(client):
    login(client)
    with TestClient(app, base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert client.put('/api/v1/admin/users/bob/status',json={'status':'suspended'}).status_code==200
        assert bob.get('/api/v1/auth/me').status_code==401
    assert client.put('/api/v1/admin/gate',json={'key':'new-global-secret-value'}).status_code==200
    assert client.get('/api/v1/auth/me').status_code==403


def test_registration_approval_invitation_and_disabled(client):
    login(client)
    new={'email':'new@example.org','name':'New','password':'a-very-long-password'}
    client.put('/api/v1/admin/registration',json={'registration':'disabled'})
    assert client.post('/api/v1/auth/register',json=new).status_code==403
    client.put('/api/v1/admin/registration',json={'registration':'approval'})
    assert client.post('/api/v1/auth/register',json=new).json()['status']=='pending'
    client.put('/api/v1/admin/registration',json={'registration':'invite'})
    new['email']='invited@example.org'
    invite=client.post('/api/v1/admin/invitations',json={'email':new['email']}).json()['token']
    assert client.post('/api/v1/auth/register',json={**new,'invite':invite}).status_code==201
    assert client.post('/api/v1/auth/register',json={**new,'invite':invite}).status_code==403


def test_rate_limit_shared(client,monkeypatch):
    # Keep this assertion inside one fixed rate-limit window, even at a real clock boundary.
    import app.security as security
    from types import SimpleNamespace
    fixed=int(__import__('time').time())//300*300+10
    monkeypatch.setattr(security,'time',SimpleNamespace(time=lambda:fixed))
    for _ in range(15):
        assert client.post('/api/v1/auth/gate',json={'key':'wrong'}).status_code==403
    assert client.post('/api/v1/auth/gate',json={'key':'wrong'}).status_code==429


def test_totp_encrypted_and_recovery_one_use(client,database):
    login(client)
    setup=client.post('/api/v1/auth/totp/setup').json()
    secret=setup['secret']
    response=client.post('/api/v1/auth/totp/confirm',json={'code':pyotp.TOTP(secret).now()})
    assert response.status_code==200,response.text
    recovery=response.json()['recovery_codes'][0]
    with database() as db:
        user=db.get(User,'alice')
        assert user.totp_secret!=secret
        assert cipher().decrypt(user.totp_secret.encode()).decode()==secret
    client.post('/api/v1/auth/logout')
    client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'})
    payload={'email':'alice@example.org','password':'password-very-long','code':recovery}
    assert client.post('/api/v1/auth/login',json=payload).status_code==200
    assert client.post('/api/v1/auth/login',json=payload).status_code==401


def test_viewer_cannot_write(client,database):
    login(client)
    gid,ids=group(client)
    from app.models import Participant
    with database() as db:
        db.get(Participant,ids['bob']).role='viewer'
        db.commit()
    with TestClient(app, base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.post(f'/api/v1/groups/{gid}/expenses/preview',json=expense(ids)).status_code==403


def test_reimbursement_requires_recipient_confirmation(client):
    login(client)
    gid,ids=group(client)
    client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids),headers={'Idempotency-Key':'settlement-test'})
    before=client.get(f'/api/v1/groups/{gid}/balances').json()
    created=client.post(f'/api/v1/groups/{gid}/settlements',headers={'Idempotency-Key':'payment-request-123'},json={'sender':ids['alice'],'recipient':ids['bob'],'amount':'2.50'})
    assert created.status_code==201,created.text
    sid=created.json()['id']
    url=f'/api/v1/groups/{gid}/settlements/{sid}'
    assert client.put(url,json={'status':'confirmed'}).status_code==403
    assert client.get(f'/api/v1/groups/{gid}/balances').json()==before
    with TestClient(app, base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.put(url,json={'status':'confirmed'}).status_code==200
        assert bob.put(url,json={'status':'confirmed'}).status_code==200
        assert bob.put(url,json={'status':'cancelled'}).status_code==409
    after=client.get(f'/api/v1/groups/{gid}/balances').json()
    assert after[0]['balances'][ids['alice']]==before[0]['balances'][ids['alice']]+250


def test_passkey_challenge_authentication_and_single_use(client):
    assert client.post('/api/v1/auth/passkeys/register/options').status_code==403
    login(client)
    options=client.post('/api/v1/auth/passkeys/register/options')
    assert options.status_code==200,options.text
    data=options.json()
    assert data['options']['rp']['id']=='localhost'
    body={'challenge_id':data['challenge_id'],'credential':{}}
    assert client.post('/api/v1/auth/passkeys/register/verify',json=body).status_code==400
    retry=client.post('/api/v1/auth/passkeys/register/verify',json=body)
    assert retry.status_code==400
    assert 'già usata' in retry.json()['detail']


def test_passkey_real_signature_registration_and_login(client):
    import base64, hashlib, json
    import cbor2
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    def b64(value): return base64.urlsafe_b64encode(value).rstrip(b'=').decode()
    login(client)
    options=client.post('/api/v1/auth/passkeys/register/options').json()
    private=ec.generate_private_key(ec.SECP256R1())
    numbers=private.public_key().public_numbers()
    cred_id=b'local-test-authenticator-credential'
    cose={1:2,3:-7,-1:1,-2:numbers.x.to_bytes(32,'big'),-3:numbers.y.to_bytes(32,'big')}
    auth_data=hashlib.sha256(b'localhost').digest()+b'\x45'+(0).to_bytes(4,'big')+bytes(16)+len(cred_id).to_bytes(2,'big')+cred_id+cbor2.dumps(cose)
    client_data=json.dumps({'type':'webauthn.create','challenge':options['options']['challenge'],'origin':'http://localhost:8088','crossOrigin':False}).encode()
    attestation=cbor2.dumps({'fmt':'none','attStmt':{},'authData':auth_data})
    credential={'id':b64(cred_id),'rawId':b64(cred_id),'type':'public-key','response':{'clientDataJSON':b64(client_data),'attestationObject':b64(attestation),'transports':['internal']}}
    result=client.post('/api/v1/auth/passkeys/register/verify',json={'challenge_id':options['challenge_id'],'credential':credential})
    assert result.status_code==200,result.text
    keys=client.get('/api/v1/auth/passkeys').json()
    assert len(keys)==1
    for count,expected in ((1,200),(1,400)):
        options=client.post('/api/v1/auth/passkeys/login/options',json={'email':'alice@example.org'}).json()
        client_data=json.dumps({'type':'webauthn.get','challenge':options['options']['challenge'],'origin':'http://localhost:8088','crossOrigin':False}).encode()
        auth_data=hashlib.sha256(b'localhost').digest()+b'\x05'+count.to_bytes(4,'big')
        signature=private.sign(auth_data+hashlib.sha256(client_data).digest(),ec.ECDSA(hashes.SHA256()))
        assertion={'id':b64(cred_id),'rawId':b64(cred_id),'type':'public-key','response':{'clientDataJSON':b64(client_data),'authenticatorData':b64(auth_data),'signature':b64(signature)}}
        result=client.post('/api/v1/auth/passkeys/login/verify',json={'challenge_id':options['challenge_id'],'credential':assertion})
        assert result.status_code==expected,result.text
    assert client.get('/api/v1/auth/me').status_code==200
    client.headers['X-CSRF-Token']=client.cookies.get('sg_csrf')
    pending=client.post('/api/v1/auth/passkeys/login/options',json={'email':'alice@example.org'}).json()
    with TestClient(app,base_url='http://localhost:8088') as other:
        login(other)
        assert client.delete('/api/v1/auth/passkeys/'+keys[0]['id']).status_code==204
        assert other.get('/api/v1/auth/me').status_code==401
    assert client.post('/api/v1/auth/passkeys/login/verify',json={'challenge_id':pending['challenge_id'],'credential':assertion}).status_code==400
    assert client.get('/api/v1/auth/passkeys').json()==[]


def test_guest_links_restrict_secrets_password_uses_and_revocation(client):
    login(client)
    gid,ids=group(client)
    for secret in (True,False):
        client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,secret),headers={'Idempotency-Key':f'guest-expense-{secret}'})
    result=client.post(f'/api/v1/groups/{gid}/guest-links',json={'password':'guest-password','max_uses':1,'show_details':False,'show_names':False})
    assert result.status_code==201,result.text
    link=result.json();token=link['url'].split('#')[1]
    with TestClient(app, base_url='http://localhost:8088') as guest:
        assert guest.post('/api/v1/guest/view',json={'token':token}).status_code==403
        response=guest.post('/api/v1/guest/view',json={'token':token,'password':'guest-password'})
        assert response.status_code==200,response.text
        data=response.json()
        assert len(data['expenses'])==1 and data['total']==10000
        assert data['expenses'][0]['title']=='Spesa condivisa'
        assert 'Regalo' not in response.text and 'Alice' not in response.text
        assert guest.get(f'/api/v1/groups/{gid}').status_code==403
        assert guest.post('/api/v1/guest/view',json={'token':token,'password':'guest-password'}).status_code==404
    new=client.post(f'/api/v1/groups/{gid}/guest-links',json={}).json()
    client.delete(f'/api/v1/groups/{gid}/guest-links/'+new['id'])
    assert client.post('/api/v1/guest/view',json={'token':new['url'].split('#')[1]}).status_code==404


def test_group_invitation_bound_to_email_single_use(client):
    login(client)
    gid,_=group(client)
    invitation=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'dave@example.org','role':'viewer'}).json()
    with TestClient(app, base_url='http://localhost:8088') as dave:
        login(dave,'dave')
        assert dave.post('/api/v1/invitations/accept',json=invitation).status_code==422
        assert dave.post('/api/v1/invitations/accept',json={'token':invitation['token']}).status_code==200
        assert dave.post('/api/v1/invitations/accept',json={'token':invitation['token']}).status_code==404
        assert dave.get(f'/api/v1/groups/{gid}').json()['role']=='viewer'


def test_versions_do_not_double_count_and_reject_conflicts(client,database):
    login(client)
    gid,ids=group(client)
    body=expense(ids,True)
    result=client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'revision-test'}).json()
    eid=result['id'];url=f'/api/v1/groups/{gid}/expenses/{eid}'
    before=client.get(f'/api/v1/groups/{gid}/balances').json()
    body['title']='Regalo aggiornato'
    response=client.put(url,json=body,headers={'If-Match':'1'})
    assert response.status_code==200,response.text
    assert client.get(f'/api/v1/groups/{gid}/balances').json()==before
    assert client.put(url,json=body,headers={'If-Match':'1'}).status_code==409
    with TestClient(app, base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        assert carol.get(url+'/versions').status_code==404
        assert carol.post(url+'/reveal',headers={'If-Match':'2'}).status_code==404
        assert client.post(url+'/reveal',headers={'If-Match':'2'}).status_code==200
        # Revelation exposes the current public revision, not older private snapshots.
        assert [v['version'] for v in carol.get(url+'/versions').json()]==[3]
        assert carol.get(f'/api/v1/groups/{gid}/balances').json()[0]['private']==False
    with database() as db:
        assert len(list(db.scalars(select(Entry).where(Entry.expense_id==eid))))==6


def test_group_states_and_virtual_claim_preserve_identity(client):
    login(client)
    gid,ids=group(client)
    virtual=client.post(f'/api/v1/groups/{gid}/participants',json={'name':'Davide'}).json()
    token=client.post(f'/api/v1/groups/{gid}/participants/{virtual["id"]}/claim',json={'email':'dave@example.org'}).json()['token']
    with TestClient(app, base_url='http://localhost:8088') as dave:
        login(dave,'dave')
        result=dave.post('/api/v1/participants/claim',json={'token':token})
        assert result.status_code==200,result.text
        assert result.json()['participant_id']==virtual['id']
        assert dave.post('/api/v1/participants/claim',json={'token':token}).status_code==404
    assert client.put(f'/api/v1/groups/{gid}/state',json={'state':'frozen'}).status_code==200
    assert client.post(f'/api/v1/groups/{gid}/expenses/preview',json=expense(ids)).status_code==409
    assert client.post(f'/api/v1/groups/{gid}/settlements',headers={'Idempotency-Key':'payment-request-123'},json={'sender':ids['alice'],'recipient':ids['bob'],'amount':'1'}).status_code==201
    client.put(f'/api/v1/groups/{gid}/state',json={'state':'archived'})
    assert client.post(f'/api/v1/groups/{gid}/settlements',headers={'Idempotency-Key':'payment-request-123'},json={'sender':ids['alice'],'recipient':ids['bob'],'amount':'1'}).status_code==403


def test_concurrent_retries_create_one_expense_on_postgres(client,database):
    import concurrent.futures
    import pytest
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('Row-lock behavior requires PostgreSQL')
    login(client)
    gid,ids=group(client)
    body=expense(ids)
    def submit(_):
        return client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'concurrent-same-key'})
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        results=list(pool.map(submit,range(10)))
    assert all(r.status_code==201 for r in results),[(r.status_code,r.text) for r in results]
    assert len({r.json()['id'] for r in results})==1
    assert len(client.get(f'/api/v1/groups/{gid}/expenses').json())==1


def test_https_cookie_policy_and_nonlocal_http_config_rejected(client):
    import pytest
    from pydantic import ValidationError
    from app.config import Settings
    with pytest.raises(ValidationError):Settings(public_origin='http://192.168.1.20:8088',secure_cookies=False)
    with pytest.raises(ValidationError):Settings(public_origin='https://sgancia.example.org',secure_cookies=False)
    from app.security import cookie_secure
    from starlette.requests import Request
    assert cookie_secure(Request({'type':'http','scheme':'http','server':('192.168.1.20',8088),'path':'/','headers':[]}))
    assert cookie_secure(Request({'type':'http','scheme':'https','server':('sgancia.example.org',443),'path':'/','headers':[]}))


def test_member_can_edit_another_expense_but_viewer_and_excluded_cannot(client,database):
    login(client)
    gid,ids=group(client);body=expense(ids)
    eid=client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'edit-other-expense'}).json()['id']
    url=f'/api/v1/groups/{gid}/expenses/{eid}'
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');body['title']='Aggiornata da un altro membro'
        assert bob.put(url,json=body,headers={'If-Match':'1'}).status_code==200
        from app.models import Participant
        with database() as db:
            db.get(Participant,ids['bob']).role='viewer';db.commit()
        assert bob.put(url,json=body,headers={'If-Match':'2'}).status_code==403
    secret=expense(ids,True)
    eid=client.post(f'/api/v1/groups/{gid}/expenses',json=secret,headers={'Idempotency-Key':'edit-other-secret'}).json()['id']
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        assert carol.get(f'/api/v1/groups/{gid}/expenses/{eid}').status_code==404
        assert carol.put(f'/api/v1/groups/{gid}/expenses/{eid}',json=secret,headers={'If-Match':'1'}).status_code==404


def test_item_payers_with_secret_exclusion_precise_error_and_legacy_edit(client):
    login(client);gid,ids=group(client)
    a,b,c=ids['alice'],ids['bob'],ids['carol']
    body={'title':'Regalo','date':'2026-11-02','audience':[a,b],'items':[{'title':'Libro','amount':'60','shares':{a:'1',b:'1'},'payers':{a:''}}]}
    preview=client.post(f'/api/v1/groups/{gid}/expenses/preview',json=body)
    assert preview.status_code==200,preview.text
    assert preview.json()['paid']=={a:6000}
    body['items'][0]['shares'][c]='1'
    bad=client.post(f'/api/v1/groups/{gid}/expenses/preview',json=body)
    assert bad.status_code==422 and 'esclusa' in bad.json()['detail']
    del body['items'][0]['shares'][c]
    body['items'][0]['payers']={a:'10',b:''}
    assert client.post(f'/api/v1/groups/{gid}/expenses/preview',json=body).json()['paid']=={a:1000,b:5000}
    legacy=expense(ids)
    eid=client.post(f'/api/v1/groups/{gid}/expenses',json=legacy,headers={'Idempotency-Key':'legacy-draft-test'}).json()['id']
    draft=client.get(f'/api/v1/groups/{gid}/expenses/{eid}').json()['draft']
    normalized=client.post(f'/api/v1/groups/{gid}/expenses/preview',json=draft)
    assert normalized.status_code==200,normalized.text
    assert normalized.json()['paid']=={a:4000,b:6000}


def test_edit_users_and_participants_preserves_identity_and_prevents_escalation(client):
    login(client);gid,ids=group(client)
    response=client.put(f'/api/v1/groups/{gid}/participants/{ids["bob"]}',json={'name':'Bobby','role':'member'})
    assert response.status_code==200,response.text
    assert response.json()['id']==ids['bob']
    assert client.put(f'/api/v1/groups/{gid}/participants/{ids["alice"]}',json={'name':'Alice','role':'member'}).status_code==403
    edited=client.put('/api/v1/admin/users/bob',json={'name':'Roberto','email':'roberto@example.org','status':'active'})
    assert edited.status_code==200,edited.text
    assert edited.json()['id']=='bob'
    assert client.put('/api/v1/admin/users/bob',json={'name':'Bob','email':'alice@example.org','status':'active'}).status_code==409


def test_group_categories_are_unique_and_do_not_discover_secrets(client):
    login(client);gid,ids=group(client)
    url=f'/api/v1/groups/{gid}/categories'
    assert client.post(url,json={'name':'  Benzina  '}).status_code==201
    assert client.post(url,json={'name':'benzina'}).status_code==409
    assert 'Benzina' in client.get(url).json()
    body=expense(ids,True);body['category']='Categoria segreta non condivisa'
    client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'secret-category-test'})
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol');assert 'Categoria segreta non condivisa' not in carol.get(url).text


def test_settle_suggestion_virtual_confirmed_registered_pending_and_retry(client):
    login(client);gid,ids=group(client)
    virtual=client.post(f'/api/v1/groups/{gid}/participants',json={'name':'Virtuale'}).json()['id']
    a=ids['alice']
    body={'title':'Conto','date':'2026-11-02','items':[{'amount':'30','shares':{a:'1',virtual:'1'},'payers':{virtual:''}}]}
    client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'settle-virtual-expense'})
    path=f'/api/v1/groups/{gid}/settlements/settle-suggestion'
    payment={'sender':a,'recipient':virtual,'amount':'15','audience':None}
    response=client.post(path,json=payment,headers={'Idempotency-Key':'settle-virtual-now'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='confirmed'
    assert client.post(path,json=payment,headers={'Idempotency-Key':'settle-virtual-now'}).json()==response.json()
    assert client.get(f'/api/v1/groups/{gid}/balances').json()[0]['suggestions']==[]
    assert client.post(path,json=payment,headers={'Idempotency-Key':'settle-stale-now'}).status_code==409
    client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids),headers={'Idempotency-Key':'settle-registered-expense'})
    body={'sender':ids['bob'],'recipient':a,'amount':'5'}
    # Existing example has Alice as creditor and Bob as debtor.
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        result=bob.post(path,json=body,headers={'Idempotency-Key':'registered-pending'})
        assert result.status_code==403,result.text
        pending=bob.post(f'/api/v1/groups/{gid}/settlements',json=body,headers={'Idempotency-Key':'registered-manual-pending'})
        assert pending.status_code==201 and pending.json()['status']=='pending'
    confirmed=client.post(path,json=body,headers={'Idempotency-Key':'registered-recipient-confirm'})
    assert confirmed.status_code==200 and confirmed.json()['status']=='confirmed'


def test_account_and_group_invitation_registers_and_links_virtual_atomically(client,database):
    from app.models import Participant,GroupInvite,Invite
    login(client);gid,_=group(client)
    person=client.post(f'/api/v1/groups/{gid}/participants',json={'name':'Carly virtuale'}).json()['id']
    invitation=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'newcarly@example.org','registration':True,'participant_id':person,'role':'member'})
    assert invitation.status_code==201,invitation.text
    data=invitation.json();assert data['kind']=='account_and_group'
    assert '/invite?register=1#' in data['url']
    payload={'name':'Carly','email':'newcarly@example.org','password':'password-for-new-account','invite':data['token']}
    assert client.put('/api/v1/admin/registration',json={'registration':'invite'}).status_code==200
    response=client.post('/api/v1/auth/register',json=payload)
    assert response.status_code==201,response.text
    assert response.json()['joined_group']==gid
    with database() as db:
        user=db.scalar(select(User).where(User.email==payload['email']))
        assert db.get(Participant,person).user_id==user.id
        assert len(list(db.scalars(select(Participant).where(Participant.group_id==gid,Participant.user_id==user.id))))==1
        from app.security import digest
        assert db.get(GroupInvite,digest(data['token'])).used
        assert db.get(Invite,digest(data['token'])).used
    assert client.post('/api/v1/auth/register',json=payload).status_code==403


def test_group_only_code_explains_registration_error_and_admin_capability(client,database):
    from app.models import Participant
    login(client);gid,ids=group(client)
    client.put('/api/v1/admin/registration',json={'registration':'invite'})
    invite=client.post(f'/api/v1/groups/{gid}/invitations',json={}).json()['token']
    response=client.post('/api/v1/auth/register',json={'name':'New','email':'new@example.org','password':'new-long-password','invite':invite})
    assert response.status_code==403
    assert 'Nuovo account + gruppo' in response.json()['detail']
    with database() as db:
        db.get(Participant,ids['bob']).role='admin';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        response=bob.post(f'/api/v1/groups/{gid}/invitations',json={'email':'other@example.org','registration':True})
        assert response.status_code==403
    assert client.post(f'/api/v1/groups/{gid}/invitations',json={'registration':True}).status_code==422


def test_combined_invite_does_not_override_approval_disabled_or_email_binding(client):
    login(client);gid,_=group(client)
    invite=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'new@example.org','registration':True}).json()['token']
    new={'email':'wrong@example.org','name':'New','password':'long-password-for-user','invite':invite}
    client.put('/api/v1/admin/registration',json={'registration':'invite'})
    assert client.post('/api/v1/auth/register',json=new).status_code==403
    new['email']='new@example.org'
    client.put('/api/v1/admin/registration',json={'registration':'disabled'})
    assert client.post('/api/v1/auth/register',json=new).status_code==403
    client.put('/api/v1/admin/registration',json={'registration':'approval'})
    registered=client.post('/api/v1/auth/register',json=new)
    assert registered.status_code==201 and registered.json()['status']=='pending'


def test_combined_invitation_rolls_back_when_email_already_exists(client,database):
    from app.models import Invite,GroupInvite
    from app.security import digest
    login(client);gid,_=group(client)
    code=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'dave@example.org','registration':True}).json()['token']
    response=client.post('/api/v1/auth/register',json={'name':'Duplicate','email':'dave@example.org','password':'duplicate-password-long','invite':code})
    assert response.status_code==409,response.text
    with database() as db:
        assert not db.get(Invite,digest(code)).used
        assert not db.get(GroupInvite,digest(code)).used


def test_new_account_invitation_requires_recent_identity_and_can_reauthenticate(client,database):
    import time
    login(client);gid,_=group(client)
    with database() as db:
        session=db.scalar(select(Session).where(Session.user_id=='alice'))
        session.verified=int(time.time())-600;db.commit()
    payload={'email':'recent@example.org','registration':True}
    assert client.post(f'/api/v1/groups/{gid}/invitations',json=payload).status_code==403
    assert client.post('/api/v1/auth/reauth',json={'email':'alice@example.org','password':'password-very-long'}).status_code==200
    assert client.post(f'/api/v1/groups/{gid}/invitations',json=payload).status_code==201


def test_finance_aggregates_visible_rows_and_includes_private_without_leaking(client):
    login(client);gid,ids=group(client)
    for i,audience in enumerate((None,[ids['alice'],ids['bob']],[ids['alice'],ids['bob'],ids['carol']])):
        body=expense(ids);body['audience']=audience
        assert client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':f'finance-scope-{i}'}).status_code==201
    finance=client.get(f'/api/v1/groups/{gid}/finance').json()
    assert finance['summary']['paid']==12000
    assert finance['summary']['receivable']==1500
    assert len(finance['transfers'])==1 and finance['transfers'][0]['amount']==1500
    assert len(finance['transfers'][0]['components'])==3
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        view=carol.get(f'/api/v1/groups/{gid}/finance').json()
        assert view['summary']['expenses_total']==20000
        assert view['transfers'][0]['amount']==1000
        assert len(view['transfers'][0]['components'])==2


def test_receiver_one_click_settles_combined_scopes_atomically_and_retry_safe(client):
    login(client);gid,ids=group(client)
    for i,secret in enumerate((False,True)):
        client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,secret),headers={'Idempotency-Key':f'combined-receipt-{i}'})
    row=client.get(f'/api/v1/groups/{gid}/finance').json()['transfers'][0]
    body={'sender':row['from'],'recipient':row['to'],'components':row['components'],'fingerprint':row['fingerprint']}
    url=f'/api/v1/groups/{gid}/settlements/settle-transfer'
    # Alice is the registered recipient, so no prior sender action is required.
    response=client.post(url,json=body,headers={'Idempotency-Key':'receiver-combined-one-click'})
    assert response.status_code==200,response.text
    assert response.json()['status']=='confirmed' and len(response.json()['ids'])==2
    assert client.post(url,json=body,headers={'Idempotency-Key':'receiver-combined-one-click'}).json()==response.json()
    assert client.get(f'/api/v1/groups/{gid}/finance').json()['summary']['receivable']==0
    assert client.get(f'/api/v1/groups/{gid}/finance').json()['transfers']==[]
    assert client.post(url,json=body,headers={'Idempotency-Key':'stale-transfer-again'}).status_code==409


def test_expense_delete_restore_and_versions_leave_money_and_privacy_correct(client,database):
    login(client);gid,ids=group(client)
    eid=client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,True),headers={'Idempotency-Key':'delete-secret-test'}).json()['id']
    url=f'/api/v1/groups/{gid}/expenses/{eid}'
    original=client.get(f'/api/v1/groups/{gid}/finance').json()
    assert client.delete(url,headers={'If-Match':'9'}).status_code==409
    assert client.delete(url,headers={'If-Match':'1'}).status_code==204
    assert client.delete(url,headers={'If-Match':'1'}).status_code==204
    assert client.get(f'/api/v1/groups/{gid}/expenses').json()==[]
    assert client.get(f'/api/v1/groups/{gid}/finance').json()['summary']['paid']==0
    trash=client.get(f'/api/v1/groups/{gid}/trash').json();assert len(trash)==1
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        assert carol.get(f'/api/v1/groups/{gid}/trash').json()==[]
        assert carol.delete(url,headers={'If-Match':'2'}).status_code==404
    assert client.post(url+'/restore',headers={'If-Match':'2'}).status_code==200
    assert client.get(f'/api/v1/groups/{gid}/finance').json()==original
    assert len(client.get(url+'/versions').json())==3


def test_group_settings_image_roles_and_conflicts(client):
    import base64,io
    from PIL import Image
    login(client);gid,_=group(client)
    image=Image.new('RGB',(32,32),'green');out=io.BytesIO();image.save(out,format='PNG')
    body={'name':'Nuovo titolo','description':'Un gruppo per le prove','icon':'🏖️','image':'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()}
    response=client.put(f'/api/v1/groups/{gid}',json=body,headers={'If-Match':'1'})
    assert response.status_code==200,response.text
    assert response.json()['metadata_version']==2
    assert client.get(f'/api/v1/groups/{gid}/image').headers['content-type']=='image/webp'
    assert client.put(f'/api/v1/groups/{gid}',json=body,headers={'If-Match':'1'}).status_code==409
    body['image']=base64.b64encode(b'<svg/>').decode()
    assert client.put(f'/api/v1/groups/{gid}',json=body,headers={'If-Match':'2'}).status_code==422
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.put(f'/api/v1/groups/{gid}',json=body,headers={'If-Match':'2'}).status_code==403
    with TestClient(app,base_url='http://localhost:8088') as dave:
        login(dave,'dave');assert dave.get(f'/api/v1/groups/{gid}/image').status_code==404


def test_carly_style_summary_distinguishes_advances_net_and_private_debt(client):
    login(client);gid,ids=group(client);a,b=ids['alice'],ids['bob']
    body={'title':'Quote pubbliche','date':'2026-11-02','payers':{a:'41.08',b:'13'},'items':[{'amount':'54.08','mode':'exact','shares':{a:'13',b:'41.08'}}]}
    client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'carly-public-example'})
    secret={'title':'Regalo','date':'2026-11-02','audience':[a,b],'items':[{'amount':'15','shares':{a:'1',b:'1'},'payers':{a:''}}]}
    client.post(f'/api/v1/groups/{gid}/expenses',json=secret,headers={'Idempotency-Key':'carly-private-example'})
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');view=bob.get(f'/api/v1/groups/{gid}/finance').json()
        assert view['summary']['paid']==1300
        assert view['summary']['owed']==4858
        assert view['summary']['payable']==3558
        assert view['summary']['balance']==-3558
        assert view['transfers'][0]['amount']==3558 and len(view['transfers'])==1


def test_confirming_combined_pending_transfer_does_not_duplicate_any_payment(client):
    login(client);gid,ids=group(client)
    for i,private in enumerate((False,True)):
        client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,private),headers={'Idempotency-Key':f'pending-batch-{i}'})
    row=client.get(f'/api/v1/groups/{gid}/finance').json()['transfers'][0]
    body={'sender':row['from'],'recipient':row['to'],'components':row['components'],'fingerprint':row['fingerprint']}
    url=f'/api/v1/groups/{gid}/settlements/settle-transfer'
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        first=bob.post(url,json=body,headers={'Idempotency-Key':'pending-combined-one'})
        assert first.status_code==403
        pending_ids=[]
        for i,c in enumerate(row['components']):
            pending=bob.post(f'/api/v1/groups/{gid}/settlements',json={'sender':row['from'],'recipient':row['to'],'amount':format(c['amount']/100,'.2f'),'audience':c['audience']},headers={'Idempotency-Key':f'manual-combined-{i}'})
            assert pending.status_code==201
            pending_ids.append(pending.json()['id'])
    received=client.post(url,json=body,headers={'Idempotency-Key':'receive-combined-all'})
    assert received.json()['status']=='confirmed'
    assert set(received.json()['ids'])==set(pending_ids)
    assert client.get(f'/api/v1/groups/{gid}/finance').json()['transfers']==[]


def test_consolidated_transfer_rejects_tampered_private_components_and_viewer(client,database):
    from app.models import Participant
    login(client);gid,ids=group(client)
    client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids),headers={'Idempotency-Key':'tamper-batch-expense'})
    row=client.get(f'/api/v1/groups/{gid}/finance').json()['transfers'][0]
    body={'sender':row['from'],'recipient':row['to'],'components':[{'audience':[ids['alice'],ids['bob']],'amount':row['amount']}],'fingerprint':row['fingerprint']}
    url=f'/api/v1/groups/{gid}/settlements/settle-transfer'
    assert client.post(url,json=body,headers={'Idempotency-Key':'tamper-batch-now'}).status_code==409
    with database() as db:
        db.get(Participant,ids['bob']).role='viewer';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');body['components']=row['components']
        assert bob.post(url,json=body,headers={'Idempotency-Key':'viewer-batch-now'}).status_code==403


def test_deleted_public_expense_disappears_from_guest_projection(client):
    login(client);gid,ids=group(client)
    eid=client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids),headers={'Idempotency-Key':'guest-delete-expense'}).json()['id']
    token=client.post(f'/api/v1/groups/{gid}/guest-links',json={}).json()['url'].split('#')[1]
    assert client.post('/api/v1/guest/view',json={'token':token}).json()['total']==10000
    client.delete(f'/api/v1/groups/{gid}/expenses/{eid}',headers={'If-Match':'1'})
    assert client.post('/api/v1/guest/view',json={'token':token}).json()['total']==0


def test_finance_reads_stay_coherent_during_concurrent_expense_writes(client,database):
    import concurrent.futures
    import pytest
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('Shared row locks require PostgreSQL')
    login(client);gid,ids=group(client);body=expense(ids)
    def operation(index):
        if index%3==0:
            response=client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':f'live-money-{index}'})
            assert response.status_code==201,response.text
        else:
            response=client.get(f'/api/v1/groups/{gid}/finance')
            assert response.status_code==200,response.text
            summary=response.json()['summary'];count=summary['paid']//4000
            assert summary['paid']==count*4000
            assert summary['owed']==count*3500
            assert summary['receivable']==count*500
            assert summary['expenses_total']==count*10000
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        list(pool.map(operation,range(18)))
