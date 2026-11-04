from app import project_info as info

def test_public_info_has_no_fake_contacts(client,monkeypatch):
 for field in ('DEVELOPER_EMAIL','DONATION_URL','REPOSITORY_URL'):monkeypatch.setattr(info,field,'')
 r=client.get('/api/v1/project');assert r.status_code==200
 body=r.json();assert body['developer']=='PjChaosEOW';assert body['version']==client.get('/api/openapi.json').json()['info']['version']
 assert body['email'] is None and body['donation_url'] is None and body['repository_url'] is None

def test_contact_validation_and_donation_consent(monkeypatch):
 monkeypatch.setattr(info,'DONATION_DISCLAIMER_APPROVED',False)
 monkeypatch.setattr(info,'DEVELOPER_EMAIL','dev@example.org');monkeypatch.setattr(info,'DONATION_URL','https://buymeacoffee.com/example');monkeypatch.setattr(info,'REPOSITORY_URL','https://github.com/example/sgancia')
 assert info.project()['donation_url'] is None
 monkeypatch.setattr(info,'DONATION_DISCLAIMER_APPROVED',True)
 assert info.project()['donation_url'];assert 'volontaria' in info.project()['donation_disclaimer']
 assert info.project()['repository_url'];assert info.project()['email']=='dev@example.org'
 for value in ['javascript:alert(1)','http://github.com/a','https://github.com.evil.org/a','https://user:pass@github.com/a','https://github.com:8443/a']:
  monkeypatch.setattr(info,'REPOSITORY_URL',value);assert info.project()['repository_url'] is None
 monkeypatch.setattr(info,'DEVELOPER_EMAIL','bad\r\nBcc:other@example.org');assert info.project()['email'] is None


def test_configured_public_contacts_are_exposed(client,monkeypatch):
 monkeypatch.setattr(info,'DEVELOPER_EMAIL','dev@example.org')
 monkeypatch.setattr(info,'REPOSITORY_URL','https://github.com/example/sgancia')
 monkeypatch.setattr(info,'DONATION_URL','')
 body=client.get('/api/v1/project').json()
 assert body['email']=='dev@example.org'
 assert body['repository_url']=='https://github.com/example/sgancia'
 assert body['donation_url'] is None
