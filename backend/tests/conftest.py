import os
os.environ['SGANCIA_DATABASE_URL'] = 'sqlite://'
os.environ['SGANCIA_SECURE_COOKIES'] = 'false'
os.environ['SGANCIA_PUBLIC_ORIGIN'] = 'http://localhost:8088'
from cryptography.fernet import Fernet
os.environ['SGANCIA_ENCRYPTION_KEY'] = Fernet.generate_key().decode()
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine, event
from app.db import Base, get_db
from app.main import app
from app.models import User, Instance
from app.security import passwords


@pytest.fixture
def database(tmp_path,monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings,'attachment_dir',str(tmp_path/'storage'))
    url = os.environ.get('SGANCIA_TEST_DATABASE_URL', 'sqlite://')
    engine = create_engine(url, **({'connect_args': {'check_same_thread': False}, 'poolclass': StaticPool} if url.startswith('sqlite') else {}))
    if url.startswith('sqlite'):
        @event.listens_for(engine, 'connect')
        def fk(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        db.add(Instance(id=1, gate_hash=passwords.hash('gate-secret-long-enough'), registration='open',guest_links_enabled=True))
        for name in ('alice', 'bob', 'carol', 'dave'):
            db.add(User(id=name, email=f'{name}@example.org', name=name.title(), password_hash=passwords.hash('password-very-long'), admin=name == 'alice'))
        db.commit()
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    yield factory
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def client(database):
    with TestClient(app, base_url='http://localhost:8088') as client:
        yield client


def login(client, name='alice'):
    assert client.post('/api/v1/auth/gate', json={'key': 'gate-secret-long-enough'}).status_code == 200
    assert client.post('/api/v1/auth/login', json={'email': name+'@example.org', 'password': 'password-very-long'}).status_code == 200
    client.headers['X-CSRF-Token'] = client.cookies.get('sg_csrf')
    return client
