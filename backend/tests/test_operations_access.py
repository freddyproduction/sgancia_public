import time,uuid
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import Instance,User,Participant,Session,Audit,MaintenanceJob,GroupInvite,ParticipantClaim
from app.security import digest
from app.runtime_policy import Policy
from app.operations import BackupPolicy
from conftest import login
from test_api import group


def save(client,**kw):
    current=client.get('/api/v1/admin/operations/policy').json()
    return client.put('/api/v1/admin/operations/policy',json={**current,**kw})


def test_global_policy_permissions_recent_and_session_duration(client,database):
    login(client);gid,ids=group(client)
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.get('/api/v1/admin/operations/status').status_code==403
        assert bob.put('/api/v1/admin/operations/policy',json=Policy().model_dump()).status_code==403
    assert save(client,session_hours=2).status_code==200
    assert save(client,require_verified_email=True).status_code==422
    assert save(client,session_hours=0).status_code==422
    assert save(client,audit_retention_days=1).status_code==422
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        with database() as db:assert 7100<db.get(Session,digest(bob.cookies['sg_session'])).expires-time.time()<=7200
    with database() as db:db.get(Session,digest(client.cookies['sg_session'])).verified=0;db.commit()
    assert save(client,session_hours=3).status_code==403
    assert client.get('/api/v1/admin/operations/audit').status_code==403


def test_limits_audit_filter_and_telegram_secrets(client,database):
    login(client);gid,ids=group(client)
    assert save(client,attachment_max_bytes=2097152,uploads_enabled=False,invitation_days=2).status_code==200
    assert client.get(f'/api/v1/groups/{gid}/attachment-limits').json()['max_bytes']==2097152
    result=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'dave@example.org'});assert result.status_code==201 and result.json()['expires_in']==2*86400
    with database() as db:
        db.add_all([Audit(actor='alice',event='expense.created',resource='PRIVATE-GROUP'),Audit(actor='alice',event='installation.policy_changed',resource='PRIVATE-RESOURCE')]);db.commit()
    data=client.get('/api/v1/admin/operations/audit').json();assert any(r['event']=='installation.policy_changed' for r in data)
    assert all('resource' not in r and 'actor' not in r for r in data);assert 'expense.created' not in str(data) and 'PRIVATE' not in str(data)
    secret='123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_1234'
    result=client.put('/api/v1/admin/operations/telegram',json={'bot_token':secret,'max_messages_per_minute':5});assert result.status_code==200 and secret not in result.text
    result=client.get('/api/v1/admin/operations/telegram');assert result.json()['token_set'] and result.json()['available'] and not result.json()['enabled'] and secret not in result.text
    with database() as db:assert secret not in db.get(Instance,1).telegram_config


def test_backup_queue_and_schedule_deduplication(client,database):
    from app.maintenance import schedule
    login(client)
    assert client.post('/api/v1/admin/operations/backup',json={'confirm':False}).status_code==422
    first=client.post('/api/v1/admin/operations/backup',json={'confirm':True});assert first.status_code==202
    assert client.post('/api/v1/admin/operations/backup',json={'confirm':True}).json()['id']==first.json()['id']
    cfg={**BackupPolicy().model_dump(),'enabled':True,'interval_hours':1,'restore_checks':True}
    assert client.put('/api/v1/admin/operations/backups',json=cfg).status_code==200
    assert client.get('/api/v1/admin/operations/backups').json()['restore_checks']
    with database() as db:
        row=db.get(Instance,1);row.backup_policy={**cfg,'started_at':0};db.commit()
        schedule(db,100000);db.commit();schedule(db,100000);db.commit()
        assert db.scalar(select(func.count()).select_from(MaintenanceJob).where(MaintenanceJob.slot.like('scheduled:%')))==1
    assert client.get('/api/v1/admin/operations/status').status_code==200


def test_backup_worker_failure_sanitized_and_retention_safe(client,database,monkeypatch,tmp_path):
    import app.maintenance as service
    login(client);client.post('/api/v1/admin/operations/backup',json={'confirm':True})
    monkeypatch.setattr(service,'SessionLocal',database);monkeypatch.setattr(service,'directory',lambda:tmp_path)
    def fail(*args):raise RuntimeError('PRIVATE PASSWORD / FINANCIAL DATA')
    monkeypatch.setattr(service,'create_backup',fail);service.tick()
    result=client.get('/api/v1/admin/operations/status').json()['jobs'][0];assert result['status']=='failed' and result['error']=='backup_failed' and 'PRIVATE' not in str(result)
    for i in range(4):(tmp_path/f'auto-{uuid.uuid4()}.sgb').write_bytes(b'encrypted')
    manual=tmp_path/'manual-backup.sgb';manual.write_bytes(b'preserve');outside=tmp_path/'outside';outside.mkdir();(tmp_path/f'auto-{uuid.uuid4()}.sgb').symlink_to(manual)
    service.prune(2);assert manual.exists() and len([p for p in tmp_path.glob('auto-*.sgb') if not p.is_symlink()])==2


def test_unified_invite_preserves_person_and_retries(client,database):
    login(client);gid,ids=group(client)
    person=client.post(f'/api/v1/groups/{gid}/participants',json={'name':'Persona esistente'}).json()['id']
    result=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'dave@example.org','participant_id':person,'role':'viewer'});assert result.status_code==201,result.text
    code=result.json()['token']
    with TestClient(app,base_url='http://localhost:8088') as dave:
        login(dave,'dave');p=dave.post('/api/v1/group-access/preview',json={'token':code});assert p.status_code==200,p.text
        assert p.json()['person']=='Persona esistente' and p.json()['role']=='viewer'
        accepted=dave.post('/api/v1/group-access/accept',json={'token':code});assert accepted.status_code==200,accepted.text
        assert dave.post('/api/v1/group-access/accept',json={'token':code}).json()['already_member'] is True
    with database() as db:assert db.get(Participant,person).user_id=='dave'
    listed=client.get(f'/api/v1/groups/{gid}/access-invitations').json();assert code not in str(listed)


def test_revocation_wrong_email_and_former_issuer(client,database):
    login(client);gid,_=group(client)
    code=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'dave@example.org'}).json()['token']
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.post('/api/v1/group-access/preview',json={'token':code}).status_code==404
    with database() as db:i=db.get(GroupInvite,digest(code));iid=i.id
    assert client.delete(f'/api/v1/groups/{gid}/access-invitations/{iid}').status_code==204
    with TestClient(app,base_url='http://localhost:8088') as dave:
        login(dave,'dave');assert dave.post('/api/v1/group-access/accept',json={'token':code}).status_code==404
    code=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'dave@example.org'}).json()['token']
    with database() as db:db.get(User,'alice').status='suspended';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as dave:
        login(dave,'dave');assert dave.post('/api/v1/group-access/preview',json={'token':code}).status_code==404


def test_claim_code_and_guest_are_distinct(client,database):
    login(client);gid,_=group(client);person=client.post(f'/api/v1/groups/{gid}/participants',json={'name':'Virtuale'}).json()['id']
    code=client.post(f'/api/v1/groups/{gid}/participants/{person}/claim',json={'email':'dave@example.org'}).json()['token']
    with TestClient(app,base_url='http://localhost:8088') as dave:
        login(dave,'dave');assert dave.post('/api/v1/group-access/preview',json={'token':code}).json()['kind']=='association'
        assert dave.post('/api/v1/group-access/accept',json={'token':code}).status_code==200
    guest=client.post(f'/api/v1/groups/{gid}/guest-links',json={}).json()['url'].split('#')[1]
    assert client.post('/api/v1/group-access/preview',json={'token':guest}).status_code==404
    assert client.put('/api/v1/admin/installation/guest-links',json={'enabled':False}).status_code==200
    with TestClient(app,base_url='http://localhost:8088') as anonymous:assert anonymous.post('/api/v1/guest/view',json={'token':guest}).status_code==403


def test_real_encrypted_backup_and_isolated_restore(client,database,monkeypatch,tmp_path):
    import os,base64
    from pathlib import Path
    from sqlalchemy import text
    import app.db as db_module
    import app.maintenance as service
    from app.config import settings
    from test_attachments import upload
    from test_api import expense
    with database() as db:
        if db.bind.dialect.name!='postgresql':
            import pytest;pytest.skip('Real pg_dump/pg_restore require disposable PostgreSQL')
        engine=db.bind
    login(client);gid,ids=group(client)
    eid=client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids),headers={'Idempotency-Key':'probe-expense'}).json()['id']
    assert upload(client,gid,eid).status_code==201
    monkeypatch.setattr(settings,'database_url',os.environ['SGANCIA_TEST_DATABASE_URL']);monkeypatch.setattr(db_module,'engine',engine)
    monkeypatch.setattr(service,'SessionLocal',database);monkeypatch.setattr(service,'directory',lambda:tmp_path/'backups');monkeypatch.setenv('SGANCIA_BACKUP_KEY',base64.urlsafe_b64encode(os.urandom(32)).decode())
    with engine.begin() as conn:conn.execute(text('CREATE TABLE IF NOT EXISTS alembic_version(version_num varchar(32) NOT NULL)'));conn.execute(text('DELETE FROM alembic_version'));conn.execute(text("INSERT INTO alembic_version VALUES('f214a762bd16')"))
    try:
        with database() as db:db.get(Instance,1).backup_policy={**BackupPolicy().model_dump(),'restore_checks':True,'restore_check_every':1};db.commit()
        assert client.post('/api/v1/admin/operations/backup',json={'confirm':True}).status_code==202
        service.tick()
        with database() as db:
            job=db.scalar(select(MaintenanceJob));assert job.status=='done',(job.error,job.result)
            assert job.result['restore']=='verified' and job.result['files']>=1
            filename=service.directory()/job.result['filename'];assert filename.exists()
            assert db.scalar(select(func.count()).select_from(Participant).where(Participant.group_id==gid))==3
        damaged=tmp_path/'damaged.sgb';damaged.write_bytes(filename.read_bytes()[:-10])
        import pytest
        with pytest.raises(Exception):service.restore_probe(damaged)
    finally:
        with engine.begin() as conn:conn.execute(text('DROP TABLE alembic_version'))


def test_registration_invite_loses_creation_power_with_global_role(client,database):
    login(client);gid,_=group(client)
    response=client.post(f'/api/v1/groups/{gid}/invitations',json={'email':'newcomer@example.org','registration':True});assert response.status_code==201,response.text
    code=response.json()['token']
    with database() as db:db.get(User,'alice').admin=False;db.commit()
    with TestClient(app,base_url='http://localhost:8088') as fresh:
        assert fresh.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'}).status_code==200
        result=fresh.post('/api/v1/auth/register',json={'email':'newcomer@example.org','name':'Newcomer','password':'password-very-long','invite':code});assert result.status_code==403,result.text
