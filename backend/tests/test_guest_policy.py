from fastapi.testclient import TestClient
from app.main import app
from app.models import Instance
from conftest import login
from test_api import group


def test_global_switch_blocks_existing_links_creation_exports_and_files(client,database):
    login(client);gid,_=group(client)
    created=client.post(f'/api/v1/groups/{gid}/guest-links',json={'show_exports':True}).json()
    token=created['url'].split('#')[1]
    assert client.post('/api/v1/guest/view',json={'token':token}).status_code==200
    r=client.put('/api/v1/admin/installation/guest-links',json={'enabled':False});assert r.status_code==200,r.text
    assert client.get('/api/v1/guest-policy').json()=={'enabled':False}
    assert client.post(f'/api/v1/groups/{gid}/guest-links',json={}).status_code==403
    assert client.post('/api/v1/guest/view',json={'token':token}).status_code==403
    assert client.post('/api/v1/guest/export',json={'token':token,'format':'json'}).status_code==403
    assert client.post('/api/v1/guest/attachments/qa-file',json={'token':token,'view_token':'qa-token-long-enough-for-grant'}).status_code==403
    assert client.put('/api/v1/admin/installation/guest-links',json={'enabled':True}).status_code==200
    assert client.post('/api/v1/guest/view',json={'token':token}).status_code==200
    assert client.post('/api/v1/guest/export',json={'token':token,'format':'json'}).status_code==200


def test_group_admin_cannot_change_installation_policy_and_new_default_is_off(client,database):
    login(client);gid,ids=group(client)
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        # A group owner with no global role still cannot change the installation.
        assert bob.post('/api/v1/groups',json={'name':'Bob owner'}).status_code==201
        assert bob.get('/api/v1/admin/installation/guest-links').status_code==403
        assert bob.put('/api/v1/admin/installation/guest-links',json={'enabled':False}).status_code==403
    with database() as db:
        from app.security import passwords
        db.add(Instance(id=2,gate_hash=passwords.hash('qa-gate-unused')));db.flush()
        assert db.get(Instance,2).guest_links_enabled is False
