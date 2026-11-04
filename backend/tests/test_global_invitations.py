import time
from sqlalchemy import select
from conftest import login
from app.models import Invite,User,GroupInvite,Audit,Session,Instance
from app.security import digest

def create(client,email='new@example.org',days=7):
 response=client.post('/api/v1/admin/invitations',json={'email':email,'days':days});assert response.status_code==201,response.text
 return response.json()

def test_lifecycle_codes_and_filters(client,database):
 login(client);row=create(client,days=2);assert row['expires_in']==172800
 items=client.get('/api/v1/admin/invitations').json()['items'];assert items[0]['state']=='active';assert 'token' not in items[0] and 'token_hash' not in items[0]
 body={'expected_version':row['version'],'days':10}
 response=client.post('/api/v1/admin/invitations/'+row['id']+'/renew',json=body);assert response.status_code==200
 renewed=response.json();assert renewed['version']==2;assert renewed['expires']>time.time()+9*86400
 assert client.post('/api/v1/admin/invitations/'+row['id']+'/renew',json=body).status_code==409
 regenerated=client.post('/api/v1/admin/invitations/'+row['id']+'/regenerate',json={'expected_version':2,'days':3}).json();assert regenerated['token']!=row['token']
 assert client.get('/api/v1/admin/invitations?state=revoked').json()['total']==1
 registration={'email':row['email'],'password':'new-account-password','name':'New'}
 assert client.post('/api/v1/auth/register',json={**registration,'invite':row['token']}).status_code==403
 assert client.post('/api/v1/auth/register',json={**registration,'invite':regenerated['token']}).status_code==201
 assert client.get('/api/v1/admin/invitations?state=used').json()['total']==1
 assert client.post('/api/v1/admin/invitations/'+regenerated['id']+'/regenerate',json={'expected_version':1}).status_code==409
 with database() as db:
  invitation=db.get(Invite,digest(regenerated['token']));assert invitation.used_by==db.scalar(select(User.id).where(User.email==row['email']))
  assert all(row['token'] not in (a.resource or '') for a in db.scalars(select(Audit)))

def test_revoke_and_renew_expired(client,database):
 login(client);row=create(client)
 with database() as db:db.get(Invite,digest(row['token'])).expires=int(time.time())-1;db.commit()
 assert client.get('/api/v1/admin/invitations?state=expired').json()['total']==1
 assert client.post('/api/v1/admin/invitations/'+row['id']+'/renew',json={'expected_version':1,'days':1}).json()['state']=='active'
 result=client.post('/api/v1/admin/invitations/'+row['id']+'/revoke',json={'expected_version':2});assert result.json()['state']=='revoked'
 assert client.post('/api/v1/admin/invitations/'+row['id']+'/renew',json={'expected_version':3}).status_code==409
 assert client.get('/api/v1/admin/invitations?state=active').json()['total']==0

def test_email_duration_duplicate_and_existing_account(client):
 login(client)
 for body in [{'email':'bad'}, {'email':'new@example.org','days':0},{'email':'new@example.org','days':91}]:assert client.post('/api/v1/admin/invitations',json=body).status_code==422
 assert client.post('/api/v1/admin/invitations',json={'email':'bob@example.org'}).status_code==409
 row=create(client,email=' NEW@example.org ');assert row['email']=='new@example.org'
 assert client.post('/api/v1/admin/invitations',json={'email':'new@example.org'}).status_code==409
 assert client.get('/api/v1/admin/invitations?search=NEW').json()['total']==1
 assert client.get('/api/v1/admin/invitations?search=%25').json()['total']==0

def test_old_expired_invite_cannot_be_renewed_over_new_active(client,database):
 login(client);old=create(client)
 with database() as db:db.get(Invite,digest(old['token'])).expires=0;db.commit()
 create(client)
 assert client.post('/api/v1/admin/invitations/'+old['id']+'/renew',json={'expected_version':1}).status_code==409

def test_global_only_and_recent_identity(client,database):
 login(client,'bob');assert client.get('/api/v1/admin/invitations').status_code==403
 assert client.get('/api/v1/admin/registration').status_code==403
 login(client)
 with database() as db:
  for session in db.scalars(select(Session).where(Session.user_id=='alice')):session.verified=0
  db.commit()
 assert client.post('/api/v1/admin/invitations',json={'email':'new@example.org'}).status_code==403
 assert client.get('/api/v1/admin/invitations').status_code==200

def test_approval_mode_invitation_does_not_skip_moderation(client,database):
 login(client);row=create(client)
 assert client.get('/api/v1/admin/registration').json()['registration']=='open'
 assert client.put('/api/v1/admin/registration',json={'registration':'approval','expected_registration':'open'}).status_code==200
 assert client.put('/api/v1/admin/registration',json={'registration':'disabled','expected_registration':'open'}).status_code==409
 data={'name':'Applicant','email':row['email'],'password':'new-account-password','invite':row['token']}
 assert client.post('/api/v1/auth/register',json=data).json()['status']=='pending'
 with database() as db:uid=db.scalar(select(User.id).where(User.email==row['email']))
 assert client.get('/api/v1/admin/registration').json()['pending']==1
 assert client.put('/api/v1/admin/users/'+uid+'/status',json={'status':'suspended','expected_status':'pending'}).status_code==200
 assert client.put('/api/v1/admin/users/'+uid+'/status',json={'status':'active','expected_status':'pending'}).status_code==409
 assert client.get('/api/v1/admin/registration').json()['pending']==0
 with database() as db:assert not db.get(User,uid).admin

def test_approve_pending_no_autoapproval_from_policy(client,database):
 login(client)
 with database() as db:db.get(User,'bob').status='pending';db.get(Instance,1).registration='approval';db.commit()
 client.put('/api/v1/admin/registration',json={'registration':'open'})
 assert client.get('/api/v1/admin/registration').json()['pending']==1
 assert client.put('/api/v1/admin/users/bob/status',json={'status':'active','expected_status':'pending'}).status_code==200
 with database() as db:assert db.get(User,'bob').status=='active' and not db.get(User,'bob').admin

def test_group_registration_invites_are_not_managed_globally(client,database):
 from test_api import group
 login(client);gid,ids=group(client)
 result=client.post('/api/v1/groups/'+gid+'/invitations',json={'registration':True,'email':'new@example.org'});assert result.status_code==201,result.text
 with database() as db:identifier=db.get(Invite,digest(result.json()['token'])).id
 assert client.get('/api/v1/admin/invitations').json()['total']==0
 assert client.post('/api/v1/admin/invitations/'+identifier+'/revoke',json={'expected_version':1}).status_code==404

def test_concurrent_regeneration_only_one_new_code(client,database):
 import pytest
 if database.kw['bind'].dialect.name!='postgresql':pytest.skip('PostgreSQL row locks')
 from concurrent.futures import ThreadPoolExecutor
 from fastapi.testclient import TestClient
 from app.main import app
 login(client);row=create(client);cookies=dict(client.cookies);headers=dict(client.headers)
 def regenerate(_):
  with TestClient(app,base_url='http://localhost:8088',cookies=cookies,headers=headers) as other:
   return other.post('/api/v1/admin/invitations/'+row['id']+'/regenerate',json={'expected_version':1}).status_code
 with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(regenerate,range(2)))
 assert sorted(results)==[200,409]
 assert client.get('/api/v1/admin/invitations?state=active').json()['total']==1
 assert client.get('/api/v1/admin/invitations?state=revoked').json()['total']==1
