import time,json,base64,hashlib
from datetime import datetime,timezone
import cbor2,pytest
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import hashes
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import InstallationPasskey,Instance,User,Session,Participant,Group,Notification,NotificationPreference
from app.notifications import Preferences,scheduled_slot,cleanup
from app.security import digest
from conftest import login
from test_api import group
from test_notifications import seed,config,arm,tick


def stamp(value):return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())

def test_local_timezone_dst_and_schedules():
    pref={**Preferences().model_dump(),'timezone':'Europe/Rome','hour':9}
    assert scheduled_slot(stamp('2026-01-10T10:00:00'),'daily',pref)[0]==stamp('2026-01-10T08:00:00')
    assert scheduled_slot(stamp('2026-07-10T10:00:00'),'daily',pref)[0]==stamp('2026-07-10T07:00:00')
    pref.update(hour=2,minute=30)
    assert scheduled_slot(stamp('2026-03-29T01:45:00'),'daily',pref)[0]==stamp('2026-03-29T01:30:00')
    assert scheduled_slot(stamp('2026-10-25T00:45:00'),'daily',pref)==scheduled_slot(stamp('2026-10-25T01:45:00'),'daily',pref)
    pref.update(hour=9,minute=15,week_day=3,month_day=28)
    assert scheduled_slot(stamp('2026-07-10T10:00:00'),'weekly',pref)[0]==stamp('2026-07-09T07:15:00')
    assert scheduled_slot(stamp('2026-07-10T10:00:00'),'monthly',pref)[0]==stamp('2026-06-28T07:15:00')


def test_preferences_validation_and_retention(client,database):
    login(client);gid,ids=group(client);seed(client,gid,ids)
    for change in ({'timezone':'not/a-zone'},{'days':[]},{'days':[1,1]},{'retention_days':0},{'month_day':31}):assert config(client,**change).status_code==422
    assert config(client,timezone='Europe/Rome',retention_days=1,show_read=False,expense_events=False).status_code==200
    r=client.get('/api/v1/notifications/preferences').json()['config'];assert r['timezone']=='Europe/Rome'
    assert 'Europe/Rome' in client.get('/api/v1/notifications/options').json()['timezones']
    assert client.get('/api/v1/notifications').json()['items']==[]
    config(client,retention_days=1)
    with database() as db:
        n=db.scalar(select(Notification).where(Notification.user_id=='alice'));n.created=int(time.time())-2*86400;db.commit()
    assert client.get('/api/v1/notifications').json()['unread']==0
    with database() as db:cleanup(db,'alice',int(time.time()));db.commit();assert db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id=='alice'))==0


def test_pause_and_event_filter(client,database):
    login(client);gid,ids=group(client)
    config(client,expense_events=False);seed(client,gid,ids);assert client.get('/api/v1/notifications').json()['unread']==0
    config(client,pause_until=int(time.time())+86400);seed(client,gid,ids,key='paused-expense');tick(database)
    assert client.get('/api/v1/notifications').json()['unread']==0


def test_viewer_can_leave_archived_group_but_not_remove_others(client,database):
    login(client);gid,ids=group(client)
    with database() as db:db.get(Participant,ids['bob']).role='viewer';db.get(Group,gid).state='archived';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');base=f'/api/v1/groups/{gid}/participants/'
        assert bob.get(base+ids['carol']+'/departure-preview').status_code==403
        p=bob.get(base+ids['bob']+'/departure-preview');assert p.status_code==200,p.text
        r=bob.post(base+ids['bob']+'/depart',json={'fingerprint':p.json()['fingerprint'],'keep_balance':True});assert r.status_code==200,r.text
        assert bob.get('/api/v1/groups/'+gid).status_code==404
    assert client.get(f'/api/v1/groups/{gid}/participants/{ids["alice"]}/departure-preview').status_code==403


def b64(value):return base64.urlsafe_b64encode(value).rstrip(b'=').decode()

def register(client):
    opt=client.post('/api/v1/auth/installation-passkeys/register/options');assert opt.status_code==200,opt.text
    opt=opt.json();assert opt['options']['authenticatorSelection']['residentKey']=='required'
    private=ec.generate_private_key(ec.SECP256R1());numbers=private.public_key().public_numbers();cid=b'gate-qa-credential'
    cose={1:2,3:-7,-1:1,-2:numbers.x.to_bytes(32,'big'),-3:numbers.y.to_bytes(32,'big')}
    auth=hashlib.sha256(b'localhost').digest()+b'\x45'+bytes(4)+bytes(16)+len(cid).to_bytes(2,'big')+cid+cbor2.dumps(cose)
    data=json.dumps({'type':'webauthn.create','challenge':opt['options']['challenge'],'origin':'http://localhost:8088','crossOrigin':False}).encode()
    credential={'id':b64(cid),'rawId':b64(cid),'type':'public-key','response':{'clientDataJSON':b64(data),'attestationObject':b64(cbor2.dumps({'fmt':'none','attStmt':{},'authData':auth})),'transports':['internal']}}
    r=client.post('/api/v1/auth/installation-passkeys/register/verify',json={'challenge_id':opt['challenge_id'],'credential':credential});assert r.status_code==200,r.text
    return private,cid,opt


def assertion(client,private,cid,count=1,origin='http://localhost:8088',flags=5):
    r=client.post('/api/v1/auth/installation-passkeys/unlock/options');assert r.status_code==200,r.text
    options=r.json();assert options['options'].get('allowCredentials',[])==[]
    data=json.dumps({'type':'webauthn.get','challenge':options['options']['challenge'],'origin':origin,'crossOrigin':False}).encode();auth=hashlib.sha256(b'localhost').digest()+bytes([flags])+count.to_bytes(4,'big')
    signature=private.sign(auth+hashlib.sha256(data).digest(),ec.ECDSA(hashes.SHA256()))
    return {'challenge_id':options['challenge_id'],'credential':{'id':b64(cid),'rawId':b64(cid),'type':'public-key','response':{'clientDataJSON':b64(data),'authenticatorData':b64(auth),'signature':b64(signature),'userHandle':b64(b'installation:alice')}}}


def test_gate_passkey_only_unlocks_gate_and_cannot_replay(client):
    login(client);private,cid,_=register(client)
    with TestClient(app,base_url='http://localhost:8088') as fresh:
        body=assertion(fresh,private,cid);r=fresh.post('/api/v1/auth/installation-passkeys/unlock/verify',json=body);assert r.status_code==200,r.text
        assert fresh.cookies.get('sg_gate') and not fresh.cookies.get('sg_session')
        assert fresh.get('/api/v1/auth/policy').status_code==200
        assert fresh.get('/api/v1/auth/me').status_code==401
        assert fresh.post('/api/v1/auth/installation-passkeys/unlock/verify',json=body).status_code==400
        assert fresh.post('/api/v1/auth/installation-passkeys/unlock/verify',json=assertion(fresh,private,cid,count=1)).status_code==400
        assert client.delete('/api/v1/auth/installation-passkeys/'+b64(cid)).status_code==204
        assert fresh.get('/api/v1/auth/policy').status_code==403


@pytest.mark.parametrize('bad',[{'origin':'https://evil.test'},{'flags':1}])
def test_gate_requires_correct_origin_and_user_verification(client,bad):
    login(client);private,cid,_=register(client)
    with TestClient(app,base_url='http://localhost:8088') as fresh:
        r=fresh.post('/api/v1/auth/installation-passkeys/unlock/verify',json=assertion(fresh,private,cid,**bad));assert r.status_code==400
        assert not fresh.cookies.get('sg_gate')


@pytest.mark.parametrize('change',['version','auth_version','suspended'])
def test_gate_credentials_and_grants_revoke(client,database,change):
    login(client);private,cid,_=register(client)
    with TestClient(app,base_url='http://localhost:8088') as fresh:
        assert fresh.post('/api/v1/auth/installation-passkeys/unlock/verify',json=assertion(fresh,private,cid)).status_code==200
        body=assertion(fresh,private,cid,count=2)
        with database() as db:
            if change=='version':db.get(Instance,1).gate_version+=1
            elif change=='auth_version':db.get(User,'alice').auth_version+=1
            else:db.get(User,'alice').status='suspended'
            db.commit()
        assert fresh.post('/api/v1/auth/installation-passkeys/unlock/verify',json=body).status_code==400
        assert fresh.get('/api/v1/auth/policy').status_code==403


def test_gate_enrollment_requires_recent_identity_csrf_and_own_challenge(client,database):
    login(client)
    assert client.post('/api/v1/auth/installation-passkeys/register/options',headers={'X-CSRF-Token':'bad'}).status_code==403
    with database() as db:s=db.get(Session,digest(client.cookies['sg_session']));s.verified=0;db.commit()
    assert client.post('/api/v1/auth/installation-passkeys/register/options').status_code==403
