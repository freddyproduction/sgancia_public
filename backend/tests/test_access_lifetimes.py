import time
import pytest
from sqlalchemy import select
from conftest import login
from app.models import Instance,GateGrant,Session
from app.security import digest
from app.runtime_policy import Duration,access_lifetime

def save(client,**fields):
 cfg=client.get('/api/v1/admin/operations/policy').json()
 return client.put('/api/v1/admin/operations/policy',json={**cfg,**fields})

def test_logout_keeps_gate_and_forget_explicitly_revokes(client,database):
 login(client);gate=client.cookies['sg_gate'];session=client.cookies['sg_session']
 assert client.post('/api/v1/auth/logout').status_code==204
 assert client.cookies.get('sg_gate')==gate and not client.cookies.get('sg_session')
 assert client.get('/api/v1/auth/policy').status_code==200
 with database() as db:assert db.get(Session,digest(session)) is None and db.get(GateGrant,digest(gate)) is not None
 assert client.post('/api/v1/auth/gate/forget').status_code==204
 assert not client.cookies.get('sg_gate')
 with database() as db:assert db.get(GateGrant,digest(gate)) is None
 assert client.get('/api/v1/auth/policy').status_code==403

@pytest.mark.parametrize('unit,value,seconds',[('minutes',3,180),('hours',4,14400),('days',5,432000),('months',2,5184000),('years',2,63072000)])
def test_independent_units_and_cookie_lifetimes(client,database,unit,value,seconds):
 login(client)
 assert save(client,gate_duration={'unit':unit,'value':value},session_duration={'unit':'hours','value':2}).status_code==200
 response=client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'});assert response.status_code==200
 assert f'Max-Age={seconds}' in response.headers['set-cookie']
 with database() as db:assert seconds-5<db.get(GateGrant,digest(client.cookies['sg_gate'])).expires-time.time()<=seconds
 response=client.post('/api/v1/auth/login',json={'email':'alice@example.org','password':'password-very-long'});assert response.status_code==200
 assert 'Max-Age=7200' in response.headers['set-cookie']
 with database() as db:assert 7195<db.get(Session,digest(client.cookies['sg_session'])).expires-time.time()<=7200


def test_browser_only_cookies_and_server_bound(client,database):
 login(client);assert save(client,gate_duration={'unit':'browser','value':1},session_duration={'unit':'browser','value':1}).status_code==200
 gate=client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'})
 session=client.post('/api/v1/auth/login',json={'email':'alice@example.org','password':'password-very-long'})
 for response in (gate,session):
  assert 'Max-Age' not in response.headers['set-cookie'] and 'expires=' not in response.headers['set-cookie'].lower()
 with database() as db:
  assert 30*86400-5<db.get(Session,digest(client.cookies['sg_session'])).expires-time.time()<=30*86400


def test_expiry_and_rotation_still_apply(client,database):
 login(client)
 with database() as db:db.get(GateGrant,digest(client.cookies['sg_gate'])).expires=0;db.commit()
 assert client.get('/api/v1/auth/policy').status_code==403
 client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'})
 assert client.put('/api/v1/admin/gate',json={'key':'replacement-gate-key-long'}).status_code==200
 assert client.get('/api/v1/auth/policy').status_code==403


def test_invalid_durations_and_no_retroactive_extension(client,database):
 login(client)
 with database() as db:before=db.get(Session,digest(client.cookies['sg_session'])).expires
 for duration in [{'unit':'years','value':101},{'unit':'hours','value':0},{'unit':'forever','value':1}]:assert save(client,session_duration=duration).status_code==422
 assert save(client,session_duration={'unit':'years','value':2}).status_code==200
 with database() as db:assert db.get(Session,digest(client.cookies['sg_session'])).expires==before

def test_gate_passkey_uses_custom_browser_lifetime(client):
 from fastapi.testclient import TestClient
 from app.main import app
 from test_09a import register,assertion
 login(client);private,cid,_=register(client)
 assert save(client,gate_duration={'unit':'browser','value':1}).status_code==200
 with TestClient(app,base_url='http://localhost:8088') as fresh:
  response=fresh.post('/api/v1/auth/installation-passkeys/unlock/verify',json=assertion(fresh,private,cid));assert response.status_code==200
  assert 'Max-Age' not in response.headers['set-cookie']
  assert fresh.get('/api/v1/auth/policy').status_code==200
  assert fresh.get('/api/v1/auth/me').status_code==401


def test_forget_requires_csrf_when_account_is_still_logged_in(client):
 login(client);client.headers.pop('X-CSRF-Token')
 assert client.post('/api/v1/auth/gate/forget').status_code==403
 assert client.get('/api/v1/auth/me').status_code==200
 client.headers['X-CSRF-Token']=client.cookies['sg_csrf']
 assert client.post('/api/v1/auth/gate/forget').status_code==204
 assert client.get('/api/v1/auth/me').status_code==403
