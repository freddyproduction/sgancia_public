import time
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select
import pytest
from app.main import app
from app.models import PlatformInvitationLink,Instance,User
from conftest import login
from test_authority import root_login


def create(client,**kw):
    r=client.post('/api/v1/admin/invitations/shared-links',json={'label':'Shared QA','hours':24,'max_uses':2,**kw});assert r.status_code==201,r.text;return r.json()

def signup(client,email,link):
    return client.post('/api/v1/auth/register',json={'email':email,'name':'Shared QA','password':'password-very-long','invite':link['url'].split('#')[1]})

def change(client,row,action,**kw):
    return client.post('/api/v1/admin/invitations/shared-links/'+row['id']+'/'+action,json={'expected_version':row['version'],**kw})

def test_shared_quota_renew_revoke_regenerate_and_atomic_failure(client,database):
    login(client);link=create(client)
    assert signup(client,'one-shared@example.org',link).status_code==201
    assert signup(client,'one-shared@example.org',link).status_code==409
    assert signup(client,'two-shared@example.org',link).status_code==201
    assert signup(client,'third-shared@example.org',link).status_code==403
    row=client.get('/api/v1/admin/invitations/shared-links').json()[0];assert row['uses']==2 and row['state']=='exhausted'
    assert change(client,link,'regenerate').status_code==409
    row=change(client,row,'regenerate').json();assert row['uses']==0 and row['total_uses']==2 and row['url']!=link['url']
    row=change(client,row,'renew',hours=48).json();assert row['expires']>time.time()+47*3600
    row=change(client,row,'revoke').json();assert row['state']=='revoked'
    assert signup(client,'fourth-shared@example.org',row).status_code==403

def test_auto_rotation_and_registration_policies(client,database):
    login(client);link=create(client,max_uses=1,auto_rotate=True)
    with database() as db:db.get(Instance,1).registration='approval';db.commit()
    result=signup(client,'pending-shared@example.org',link);assert result.status_code==201 and result.json()['status']=='pending'
    row=client.get('/api/v1/admin/invitations/shared-links').json()[0];assert row['rotations']==1 and row['uses']==0 and row['total_uses']==1 and row['url']!=link['url']
    assert signup(client,'old-link@example.org',link).status_code==403
    with database() as db:db.get(Instance,1).registration='disabled';db.commit()
    assert signup(client,'disabled-link@example.org',row).status_code==403
    with database() as db:db.get(Instance,1).registration='invite';db.commit()
    assert signup(client,'invite-link@example.org',row).status_code==201

def test_privileged_shared_links_require_root_proof_and_live_issuer(client,database):
    login(client)
    assert client.post('/api/v1/admin/invitations/shared-links',json={'label':'bad','role':'superadmin','password':'password-very-long'}).status_code==403
    root_login(client,database);link=create(client,role='admin',password='password-very-long')
    result=signup(client,'shared-admin@example.org',link);assert result.status_code==201
    with database() as db:
        user=db.scalar(select(User).where(User.email=='shared-admin@example.org'));assert user.admin and user.admin_permissions==[]
        db.get(User,'alice').auth_version+=1;db.commit()
    assert signup(client,'revoked-issuer@example.org',link).status_code==403

def test_shared_link_quota_concurrent_registrations(database):
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('Requires PostgreSQL row locks')
    with TestClient(app,base_url='http://localhost:8088') as admin:
        login(admin);link=create(admin,max_uses=1)
    def attempt(n):
        with TestClient(app,base_url='http://localhost:8088') as user:
            user.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'})
            return signup(user,f'quota-{n}@example.org',link).status_code
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt,[1,2]))
    assert sorted(results)==[201,403]

def test_existing_account_does_not_join_or_gain_role_from_platform_link(client,database):
    root_login(client,database);link=create(client,role='superadmin',password='password-very-long')
    login(client,'bob')
    result=client.post('/api/v1/group-access/preview',json={'token':link['url'].split('#')[1]})
    assert result.status_code==200 and result.json()['kind']=='platform_registration'
    assert client.post('/api/v1/group-access/accept',json={'token':link['url'].split('#')[1]}).status_code==422
    assert client.get('/api/v1/groups').json()==[]
    assert not client.get('/api/v1/auth/me').json()['admin']
