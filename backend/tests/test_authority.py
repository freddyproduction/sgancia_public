import pytest
from fastapi import HTTPException
from app.models import Instance,User
from app.admin_permissions import permissions,require_permission,require_superadmin

def test_capabilities_deny_by_default_for_new_admin_and_legacy_compatibility(database):
 with database() as db:
  bob=db.get(User,'bob');bob.admin=True;bob.admin_permissions=[];db.commit()
  assert permissions(db,bob)==[]
  with pytest.raises(HTTPException):require_permission(db,bob,'users')
  bob.admin_permissions=['smtp'];db.commit();require_permission(db,bob,'smtp')
  with pytest.raises(HTTPException):require_superadmin(db,bob)
  bob.admin_permissions=None;db.commit();assert 'users' in permissions(db,bob)
  db.get(Instance,1).superadmin_id='alice';db.commit();require_superadmin(db,db.get(User,'alice'))

@pytest.mark.parametrize('path,permission',[('/api/v1/admin/registration','registrations'),('/api/v1/admin/users','users'),('/api/v1/admin/installation/smtp','smtp'),('/api/v1/admin/access-policy','access'),('/api/v1/admin/installation/guest-links','guests'),('/api/v1/admin/operations/policy','policy'),('/api/v1/admin/operations/backups','backups'),('/api/v1/admin/operations/telegram','telegram'),('/api/v1/admin/operations/audit','audit'),('/api/v1/admin/operations/revoke-sessions','sessions')])
def test_route_capability_matrix(database,path,permission):
 from starlette.requests import Request
 from app.admin_permissions import check_request
 request=Request({'type':'http','method':'POST','path':path,'headers':[]})
 with database() as db:
  user=db.get(User,'bob');user.admin=True;user.admin_permissions=[];db.commit()
  with pytest.raises(HTTPException):check_request(db,user,request)
  user.admin_permissions=[permission];db.commit();check_request(db,user,request)

@pytest.mark.parametrize('path',['/api/v1/admin/users/bob/authority','/api/v1/admin/users/bob/global-role','/api/v1/admin/authority-options','/api/v1/admin/unknown'])
def test_privilege_and_unknown_routes_fail_closed(database,path):
 from starlette.requests import Request
 from app.admin_permissions import check_request,PERMISSIONS
 with database() as db:
  user=db.get(User,'bob');user.admin=True;user.admin_permissions=list(PERMISSIONS);db.commit()
  with pytest.raises(HTTPException):check_request(db,user,Request({'type':'http','method':'POST','path':path,'headers':[]}))

def root_login(client,database):
 from conftest import login
 with database() as db:db.get(Instance,1).superadmin_id='alice';db.get(User,'alice').superadmin=True;db.commit()
 login(client)

def authority(client,identity,desired,current,version,rights=None):
 return client.put('/api/v1/admin/users/'+identity+'/authority',json={'role':desired,'expected_role':current,'expected_auth_version':version,'permissions':rights or [],'password':'password-very-long'})

def test_root_can_delegate_permissions_but_admin_cannot_escalate(client,database):
 from conftest import login
 root_login(client,database)
 assert authority(client,'bob','admin','user',1,['users']).status_code==200
 login(client,'bob');assert client.get('/api/v1/admin/users').status_code==200
 assert client.get('/api/v1/admin/operations/backups').status_code==403
 assert authority(client,'bob','superadmin','admin',2).status_code==403
 assert client.put('/api/v1/admin/users/alice',json={'name':'Changed','email':'other@example.org','status':'active'}).status_code==403

def test_other_root_can_revoke_anchor_but_not_itself(client,database):
 from conftest import login
 root_login(client,database)
 assert authority(client,'alice','user','superadmin',1).status_code==403
 assert authority(client,'bob','superadmin','user',1).status_code==200
 login(client,'bob')
 assert authority(client,'alice','admin','superadmin',1,['registrations']).status_code==200
 with database() as db:assert db.get(Instance,1).superadmin_id=='bob';assert not db.get(User,'alice').superadmin
 assert authority(client,'bob','user','superadmin',2).status_code==403

def test_invitation_role_and_approval_never_bypass_root(client,database):
 from conftest import login
 root_login(client,database)
 invite=client.post('/api/v1/admin/invitations',json={'email':'new@example.org','role':'superadmin','password':'password-very-long'});assert invite.status_code==201,invite.text
 client.put('/api/v1/admin/registration',json={'registration':'approval'})
 response=client.post('/api/v1/auth/register',json={'email':'new@example.org','password':'new-password-long','name':'New','invite':invite.json()['token']});assert response.json()['status']=='pending'
 from sqlalchemy import select
 with database() as db:
  new=db.scalar(select(User).where(User.email=='new@example.org'));identity=new.id;assert not new.admin and not new.superadmin
 assert authority(client,'bob','admin','user',1,['registrations']).status_code==200
 login(client,'bob');assert client.put('/api/v1/admin/users/'+identity+'/status',json={'status':'active','expected_status':'pending'}).status_code==403
 login(client)
 assert client.put('/api/v1/admin/users/'+identity+'/status',json={'status':'active','expected_status':'pending','role':'superadmin','password':'password-very-long'}).status_code==200
 with database() as db:assert db.get(User,identity).superadmin and db.get(User,identity).admin

def test_privileged_invite_invalid_after_issuer_security_change(client,database):
 root_login(client,database)
 invite=client.post('/api/v1/admin/invitations',json={'email':'new@example.org','role':'admin','password':'password-very-long'}).json()
 with database() as db:db.get(User,'alice').auth_version+=1;db.commit()
 # Registration still has the installation grant; no valid privileged issuer pin remains.
 assert client.post('/api/v1/auth/register',json={'email':'new@example.org','password':'new-password-long','name':'New','invite':invite['token']}).status_code==403

def test_every_admin_endpoint_has_a_policy(database):
 from app.main import app
 from app.security import admin
 from app.admin_permissions import check_request
 from starlette.requests import Request
 def guarded(dep):return dep.call is admin or any(guarded(d) for d in dep.dependencies)
 with database() as db:
  db.get(Instance,1).superadmin_id='alice';db.commit();user=db.get(User,'alice')
  def walk(router):
   for route in router.routes:
    if hasattr(route,'original_router'):yield from walk(route.original_router)
    else:yield route
  routes=[r for r in walk(app) if hasattr(r,'dependant') and guarded(r.dependant)]
  assert len(routes)>20
  for r in routes:check_request(db,user,Request({'type':'http','method':next(iter(r.methods)),'path':r.path,'headers':[]}))

def test_mutual_revocation_serializes_and_keeps_one_root(client,database):
 from conftest import login
 from fastapi.testclient import TestClient
 from app.main import app
 from concurrent.futures import ThreadPoolExecutor
 from sqlalchemy import select,func
 with database() as db:
  if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL locks')
 root_login(client,database);assert authority(client,'bob','superadmin','user',1).status_code==200
 with TestClient(app,base_url='http://localhost:8088') as bob:
  login(bob,'bob')
  with ThreadPoolExecutor(max_workers=2) as pool:
   first=pool.submit(authority,client,'bob','user','superadmin',2)
   second=pool.submit(authority,bob,'alice','user','superadmin',1)
   codes=[first.result().status_code,second.result().status_code]
   assert codes.count(200)==1 and any(c in (401,403) for c in codes)
 with database() as db:
  assert db.scalar(select(func.count()).select_from(User).where(User.superadmin.is_(True),User.admin.is_(True),User.status=='active'))==1
