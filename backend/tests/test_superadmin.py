import importlib.util
from pathlib import Path
import pytest
from sqlalchemy import select,text,delete
from sqlalchemy.exc import DBAPIError
from fastapi.testclient import TestClient
from app.main import app
from app.models import User,Instance
from conftest import login


def founder(database):
    with database() as db:
        db.get(Instance,1).superadmin_id='alice';db.get(User,'bob').admin=True;db.commit()


def test_superadmin_not_demotable_even_with_other_admin_and_rename_does_not_transfer(client,database):
    founder(database);login(client)
    assert client.get('/api/v1/auth/me').json()['superadmin'] is True
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        rows=bob.get('/api/v1/admin/users').json()
        assert [p['id'] for p in rows if p['superadmin']]==['alice']
        assert bob.put('/api/v1/admin/users/alice/global-role',json={'enabled':False,'expected_admin':True,'password':'password-very-long'}).status_code==403
        assert bob.put('/api/v1/admin/users/alice/status',json={'status':'suspended'}).status_code==403
        assert bob.put('/api/v1/admin/users/alice',json={'name':'Changed','email':'other@example.org','status':'active'}).status_code==403
        assert bob.get('/api/v1/auth/me').json()['superadmin'] is False
    assert client.put('/api/v1/admin/users/alice/global-role',json={'enabled':False,'expected_admin':True,'password':'password-very-long'}).status_code==403
    assert client.put('/api/v1/admin/users/alice',json={'name':'New display name','email':'alice@example.org','status':'active'}).status_code==200
    assert client.get('/api/v1/auth/me').json()['superadmin'] is True
    assert client.put('/api/v1/admin/users/alice',json={'name':'New display name','email':'other@example.org','status':'active'}).status_code==403
    assert client.put('/api/v1/auth/email',json={'email':'new-owner@example.org','password':'password-very-long'}).status_code==200
    assert client.get('/api/v1/auth/me').json()['superadmin'] is True


def test_global_admin_stays_manageable_without_affecting_founder(client,database):
    founder(database);login(client)
    result=client.put('/api/v1/admin/users/bob/global-role',json={'enabled':False,'expected_admin':True,'password':'password-very-long'})
    assert result.status_code==200
    with database() as db:
        assert db.get(User,'alice').admin and db.get(User,'alice').status=='active'
        assert not db.get(User,'bob').admin
        assert db.get(Instance,1).superadmin_id=='alice'


def test_bootstrap_binds_first_created_account_regardless_of_name(database,monkeypatch,capsys):
    from app import cli
    import sys
    with database() as db:
        db.delete(db.get(Instance,1));db.execute(delete(User));db.commit()
    monkeypatch.setattr(cli,'SessionLocal',database)
    monkeypatch.setattr(sys,'argv',['cli','init'])
    answers=iter(['founder@example.org','Any chosen name'])
    passwords=iter(['password-of-the-founder','password-of-the-founder','installation-gate-secret','installation-gate-secret'])
    monkeypatch.setattr('builtins.input',lambda _:next(answers));monkeypatch.setattr(cli,'getpass',lambda _:next(passwords))
    cli.main();assert 'superadmin protetto' in capsys.readouterr().out
    with database() as db:
        users=list(db.scalars(select(User)));assert len(users)==1
        assert db.get(Instance,1).superadmin_id==users[0].id and users[0].admin and users[0].status=='active'
    with pytest.raises(SystemExit,match='già inizializzata'):cli.main()


def test_database_guards_protect_founder_and_binding_on_postgres(database):
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL trigger guards')
    founder(database)
    spec=importlib.util.spec_from_file_location('superadmin_migration',Path(__file__).resolve().parents[1]/'migrations/versions/f913a762bd08_installation_superadmin.py')
    migration=importlib.util.module_from_spec(spec);spec.loader.exec_module(migration)
    with database() as db:migration.install_guards(db.connection());db.commit()
    for statement in ("UPDATE users SET admin=false WHERE id='alice'","UPDATE users SET status='suspended' WHERE id='alice'","UPDATE users SET id='replacement' WHERE id='alice'","DELETE FROM users WHERE id='alice'","UPDATE instance SET superadmin_id=NULL WHERE id=1","UPDATE instance SET superadmin_id='bob' WHERE id=1","DELETE FROM instance WHERE id=1"):
        with database() as db:
            with pytest.raises(DBAPIError,match='Superadmin protetto'):db.execute(text(statement))
            db.rollback()
    with database() as db:
        db.execute(text("UPDATE users SET name='Renamed founder' WHERE id='alice'"));db.commit()
        assert db.get(Instance,1).superadmin_id=='alice' and db.get(User,'alice').admin
