import pytest
from pydantic import ValidationError
from fastapi.testclient import TestClient
from app.config import Settings,settings
from app.main import app
from conftest import login


def configure(monkeypatch):
    config=Settings(public_origin='https://sgancia.example.org',secure_cookies=True,allowed_origins=['http://localhost:8088','http://127.0.0.1:8088'],http_lan_origins=['http://192.168.1.20:8088'])
    for field in ('public_origin','secure_cookies','allowed_origins','http_lan_origins'):monkeypatch.setattr(settings,field,getattr(config,field))


@pytest.mark.parametrize('origin,secure',[
    ('https://sgancia.example.org',True),('http://localhost:8088',False),('http://127.0.0.1:8088',False),('http://192.168.1.20:8088',False)])
def test_complete_auth_at_each_declared_origin(database,monkeypatch,origin,secure):
    configure(monkeypatch)
    with TestClient(app,base_url=origin) as client:
        client.headers['Origin']=origin
        gate=client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'})
        assert gate.status_code==200,gate.text
        assert ('; Secure' in gate.headers['set-cookie'])==secure
        response=client.post('/api/v1/auth/login',json={'email':'alice@example.org','password':'password-very-long'})
        assert response.status_code==200,response.text
        for cookie in response.headers.get_list('set-cookie'):
            assert ('; Secure' in cookie)==secure
            assert 'SameSite=strict' in cookie
            assert 'Domain=' not in cookie
        assert ('strict-transport-security' in response.headers)==secure
        client.headers['X-CSRF-Token']=client.cookies.get('sg_csrf')
        assert client.get('/api/v1/auth/me').status_code==200
        created=client.post('/api/v1/groups',json={'name':'Accesso multiplo'})
        assert created.status_code==201,created.text
        assert client.get('/api/v1/groups').json()[0]['id']==created.json()['id']
        assert client.post('/api/v1/auth/logout').status_code==204
        assert client.get('/api/v1/auth/me').status_code in (401,403)


def test_same_account_data_across_origins_and_sessions_host_scoped(database,monkeypatch):
    configure(monkeypatch)
    with TestClient(app,base_url='https://sgancia.example.org') as domain,TestClient(app,base_url='http://192.168.1.20:8088') as lan:
        login(domain)
        gid=domain.post('/api/v1/groups',json={'name':'Stessi dati'}).json()['id']
        assert lan.get('/api/v1/auth/me').status_code==403
        login(lan)
        assert lan.get('/api/v1/groups').json()[0]['id']==gid
        # A domain cookie must not be sent on a request to the LAN address.
        request=domain.build_request('GET','http://192.168.1.20:8088/api/v1/auth/me')
        assert 'cookie' not in request.headers


def test_unknown_hosts_ports_origins_and_cross_origin_posts_rejected(database,monkeypatch):
    configure(monkeypatch)
    for origin in ('http://192.168.1.21:8088','http://192.168.1.20:8089','http://sgancia.example.org','http://evil.example:8088'):
        with TestClient(app,base_url=origin) as client:
            assert client.get('/api/v1/auth/me').status_code==400
            assert client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'}).status_code==400
    with TestClient(app,base_url='http://192.168.1.20:8088') as client:
        for origin in ('https://evil.example','https://sgancia.example.org','null'):
            assert client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'},headers={'Origin':origin}).status_code==403
        assert client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'},headers={'Origin':'http://192.168.1.20:8088','Sec-Fetch-Site':'cross-site'}).status_code==403
        assert client.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'},headers={'Origin':'http://192.168.1.20:8088'}).status_code==200
        # Forged forwarding headers alone must not authorize an unknown Host.
        assert client.get('/api/v1/auth/me',headers={'Host':'evil.example','X-Forwarded-Host':'192.168.1.20:8088','X-Forwarded-Proto':'https'}).status_code==400
    with TestClient(app,base_url='http://127.0.0.1:8000') as health:
        assert health.get('/health/live').status_code==200


@pytest.mark.parametrize('origin',[
    'http://8.8.8.8:8088','http://0.0.0.0:8088','http://169.254.1.2:8088','http://224.0.0.1:8088','http://192.168.1.0/24','http://*.example.org','http://lan.example.org:8088','https://192.168.1.20:8088','http://user@192.168.1.20:8088','http://192.168.1.20:8088/path','http://192.168.1.20:8088?x=1'])
def test_lan_exceptions_only_exact_private_http_ips(origin):
    with pytest.raises(ValidationError):Settings(public_origin='https://sgancia.example.org',secure_cookies=True,http_lan_origins=[origin])


def test_canonical_ports_ipv6_and_no_implicit_lan_exception():
    config=Settings(public_origin='https://sgancia.example.org:443/',secure_cookies=True,http_lan_origins=['http://[fd12::1]:8088'])
    assert config.public_origin=='https://sgancia.example.org'
    assert 'http://[fd12::1]:8088' in config.origins
    with pytest.raises(ValidationError):Settings(public_origin='http://192.168.1.20:8088',secure_cookies=True)
    with pytest.raises(ValidationError):Settings(public_origin='https://sgancia.example.org',secure_cookies=False,http_lan_origins=['http://192.168.1.20:8088'])
