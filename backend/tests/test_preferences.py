from fastapi.testclient import TestClient
from app.main import app
from conftest import login


def test_theme_saved_per_account_shared_across_sessions_and_login(client):
    login(client)
    assert client.get('/api/v1/auth/me').json()['theme']=='dark'
    response=client.put('/api/v1/auth/preferences',json={'theme':'dark'})
    assert response.status_code==200,response.text
    assert response.json()['theme']=='dark'
    with TestClient(app,base_url='http://localhost:8088') as other:
        login(other)
        assert other.get('/api/v1/auth/me').json()['theme']=='dark'
        assert other.put('/api/v1/auth/preferences',json={'theme':'light'}).status_code==200
        assert client.get('/api/v1/auth/me').json()['theme']=='light'
    assert client.get('/api/v1/auth/me').json()['admin'] is True


def test_theme_isolated_between_accounts_and_validated(client):
    login(client)
    assert client.put('/api/v1/auth/preferences',json={'theme':'light'}).status_code==200
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.get('/api/v1/auth/me').json()['theme']=='dark'
        assert bob.put('/api/v1/auth/preferences',json={'theme':'dark','user_id':'alice'}).status_code==422
        assert bob.put('/api/v1/auth/preferences',json={'theme':'system'}).status_code==422
        assert bob.put('/api/v1/auth/preferences',json={}).status_code==422
        assert bob.get('/api/v1/auth/me').json()['theme']=='dark'
    assert client.get('/api/v1/auth/me').json()['theme']=='light'


def test_theme_requires_session_and_csrf(client):
    assert client.put('/api/v1/auth/preferences',json={'theme':'dark'}).status_code==403
    login(client)
    assert client.put('/api/v1/auth/preferences',json={'theme':'dark'},headers={'X-CSRF-Token':'wrong'}).status_code==403
    assert client.put('/api/v1/auth/preferences',json={'theme':'dark'},headers={'Origin':'https://evil.example'}).status_code==403
    assert client.get('/api/v1/auth/me').json()['theme']=='dark'
