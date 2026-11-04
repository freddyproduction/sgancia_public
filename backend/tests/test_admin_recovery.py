import time,pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import User,Instance,Passkey,RecoveryCode,WebChallenge,AccountToken,Session,Audit
from app.security import cipher,digest
from conftest import login
from test_api import group


def add_factors(database,uid='bob'):
    secret=pyotp.random_base32()
    with database() as db:
        target=db.get(User,uid);target.totp_secret=cipher().encrypt(secret.encode()).decode();target.totp_pending=target.totp_secret
        db.add(RecoveryCode(user_id=uid,code_hash=digest('recovery-'+uid)))
        db.add(Passkey(credential_id='key-'+uid,user_id=uid,public_key='synthetic-key',sign_count=0,name='QA key'))
        db.add(WebChallenge(id='challenge-'+uid,user_id=uid,purpose='login',challenge='synthetic-challenge',expires=int(time.time())+300))
        db.add(AccountToken(token_hash=digest('token-'+uid),user_id=uid,purpose='reset',email=target.email,auth_version=target.auth_version,expires=int(time.time())+300));db.commit()
    return secret


def reset(client,uid='bob',**overrides):
    return client.post(f'/api/v1/admin/users/{uid}/reset-factors',json={'password':'password-very-long','remove_mfa':True,'remove_passkeys':True,'confirm_reset':True,**overrides})


def test_admin_reset_removes_selected_factors_and_revokes_target_access(client,database):
    login(client)
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');add_factors(database)
        assert reset(client).status_code==200
        assert bob.get('/api/v1/auth/me').status_code==401
        login(bob,'bob')
        assert bob.get('/api/v1/auth/me').json()['totp'] is False
    with database() as db:
        target=db.get(User,'bob');assert target.admin is False and target.status=='active' and target.email=='bob@example.org'
        assert target.totp_secret is None and target.totp_pending is None
        assert db.get(Passkey,'key-bob') is None
        assert db.scalar(select(func.count()).select_from(RecoveryCode).where(RecoveryCode.user_id=='bob'))==0
        assert db.get(WebChallenge,'challenge-bob') is None
        assert db.get(AccountToken,digest('token-bob')).used
        assert db.scalar(select(func.count()).select_from(Audit).where(Audit.actor=='alice',Audit.resource=='bob',Audit.event.in_(['account.mfa_admin_reset','account.passkeys_admin_reset'])))==2
    assert client.get('/api/v1/auth/me').status_code==200


def test_reset_mfa_only_preserves_passkeys(client,database):
    login(client);add_factors(database)
    assert reset(client,remove_passkeys=False).status_code==200
    with database() as db:
        assert db.get(User,'bob').totp_secret is None
        assert db.get(Passkey,'key-bob') is not None


def test_reset_passkeys_only_preserves_mfa_and_codes(client,database):
    login(client);add_factors(database)
    assert reset(client,remove_mfa=False).status_code==200
    with database() as db:
        assert db.get(User,'bob').totp_secret
        assert db.get(RecoveryCode,digest('recovery-bob')) is not None
        assert db.get(Passkey,'key-bob') is None


def test_superadmin_excluded_self_route_excluded_and_group_admin_not_authorized(client,database):
    login(client);gid,ids=group(client)
    client.put(f'/api/v1/groups/{gid}/participants/{ids["bob"]}',json={'name':'Bob','role':'admin'})
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert reset(bob,'alice').status_code==403
        with database() as db:
            db.get(Instance,1).superadmin_id='alice';db.get(User,'bob').admin=True;db.commit()
        assert reset(bob,'alice').status_code==403
        assert reset(bob,'bob').status_code==403
    with database() as db:assert db.get(Instance,1).superadmin_id=='alice' and db.get(User,'alice').admin


def test_password_mfa_confirmation_and_csrf_all_required(client,database):
    login(client);add_factors(database)
    assert reset(client,password='wrong').status_code==401
    assert reset(client,confirm_reset=False).status_code==422
    assert reset(client,remove_mfa=False,remove_passkeys=False).status_code==422
    assert client.post('/api/v1/admin/users/bob/reset-factors',json={'password':'password-very-long','remove_mfa':True,'confirm_reset':True},headers={'X-CSRF-Token':'wrong'}).status_code==403
    secret=add_factors(database,'alice')
    assert reset(client).status_code==401
    assert reset(client,code=pyotp.TOTP(secret).now()).status_code==200


def test_admin_recovery_requires_recent_identity(client,database):
    login(client)
    with database() as db:
        for session in db.scalars(select(Session).where(Session.user_id=='alice')):session.verified=1
        db.commit()
    assert reset(client).status_code==403
