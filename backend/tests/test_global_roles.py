import time
import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import User,Participant,Session,Audit,RecoveryCode
from app.security import cipher,digest
from conftest import login
from test_api import group,expense


def change(client,uid,enabled,expected,**proof):
    return client.put(f'/api/v1/admin/users/{uid}/global-role',json={'enabled':enabled,'expected_admin':expected,'password':'password-very-long',**proof})


def test_global_promotion_revokes_sessions_preserves_group_role_and_private_access(client,database):
    login(client);gid,ids=group(client)
    client.put(f'/api/v1/groups/{gid}/participants/{ids["bob"]}',json={'name':'Bob','role':'admin'})
    client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,True),headers={'Idempotency-Key':'global-role-private'})
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.get('/api/v1/admin/users').status_code==403
        assert change(bob,'bob',True,False).status_code==403
        assert change(client,'bob',True,False).status_code==200
        assert bob.get('/api/v1/auth/me').status_code==401
        login(bob,'bob')
        assert bob.get('/api/v1/admin/users').status_code==200
        assert bob.get(f'/api/v1/groups/{gid}').json()['role']=='admin'
        assert change(client,'bob',False,True).status_code==200
        assert bob.get('/api/v1/admin/users').status_code==401
        login(bob,'bob')
        assert bob.get('/api/v1/admin/users').status_code==403
        assert bob.get(f'/api/v1/groups/{gid}').json()['role']=='admin'
    assert change(client,'dave',True,False).status_code==200
    with TestClient(app,base_url='http://localhost:8088') as dave:
        login(dave,'dave')
        assert dave.get('/api/v1/admin/users').status_code==200
        assert dave.get(f'/api/v1/groups/{gid}/expenses').status_code==404
    with database() as db:
        assert db.get(Participant,ids['bob']).role=='admin'
        events=list(db.scalars(select(Audit).where(Audit.event.in_(['global_admin.granted','global_admin.revoked']))))
        assert len(events)==3 and all(e.actor=='alice' for e in events)


def test_last_admin_active_target_stale_expected_and_csrf(client,database):
    login(client)
    assert change(client,'alice',False,True).status_code==409
    assert client.get('/api/v1/auth/me').json()['admin'] is True
    with database() as db:db.get(User,'bob').status='suspended';db.commit()
    assert change(client,'bob',True,False).status_code==409
    with database() as db:db.get(User,'bob').status='active';db.commit()
    assert change(client,'bob',True,False).status_code==200
    assert change(client,'bob',False,False).status_code==409
    assert client.put('/api/v1/admin/users/bob/global-role',json={'enabled':False,'expected_admin':True,'password':'password-very-long'},headers={'X-CSRF-Token':'wrong'}).status_code==403
    result=change(client,'alice',False,True);assert result.status_code==200 and result.json()['login_required']
    assert client.get('/api/v1/auth/me').status_code==401
    login(client)
    assert client.get('/api/v1/admin/users').status_code==403


def test_role_change_requires_password_mfa_and_recent_identity(client,database):
    login(client)
    assert change(client,'bob',True,False,password='wrong').status_code==401
    secret=pyotp.random_base32()
    with database() as db:
        user=db.get(User,'alice');user.totp_secret=cipher().encrypt(secret.encode()).decode();user.totp_last_counter=-1
        db.add(RecoveryCode(user_id=user.id,code_hash=digest('global-role-recovery')));db.commit()
    assert change(client,'bob',True,False).status_code==401
    assert change(client,'bob',True,False,code='global-role-recovery').status_code==200
    with database() as db:
        for session in db.scalars(select(Session).where(Session.user_id=='alice')):session.verified=int(time.time())-600
        db.commit()
    assert change(client,'bob',False,True,code=pyotp.TOTP(secret).now()).status_code==403


def test_suspended_or_pending_admin_cannot_be_the_only_remaining_admin(client,database):
    login(client)
    with database() as db:
        db.get(User,'bob').admin=True;db.get(User,'bob').status='suspended';db.commit()
    assert change(client,'alice',False,True).status_code==409
    assert client.put('/api/v1/admin/users/alice/status',json={'status':'suspended'}).status_code==403
    assert client.put('/api/v1/admin/users/alice',json={'name':'Alice','email':'alice@example.org','status':'suspended'}).status_code==403


def test_concurrent_self_demotions_keep_one_admin_on_postgres(client,database):
    import concurrent.futures,pytest
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL installation lock required')
    login(client);assert change(client,'bob',True,False).status_code==200
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(change,client,'alice',False,True);b=pool.submit(change,bob,'bob',False,True)
            assert sorted([a.result().status_code,b.result().status_code])==[200,409]
    with database() as db:assert db.scalar(select(func.count()).select_from(User).where(User.admin.is_(True),User.status=='active'))==1


def test_concurrent_revoked_actor_cannot_remove_last_admin_on_postgres(client,database):
    import concurrent.futures,pytest
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL installation lock required')
    login(client);assert change(client,'bob',True,False).status_code==200
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            a=pool.submit(change,client,'bob',False,True);b=pool.submit(change,bob,'alice',False,True)
            codes=[a.result().status_code,b.result().status_code]
            assert codes.count(200)==1 and any(c in (401,403) for c in codes)
    with database() as db:assert db.scalar(select(func.count()).select_from(User).where(User.admin.is_(True),User.status=='active'))==1
