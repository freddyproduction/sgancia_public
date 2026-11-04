from conftest import login
from test_api import group,expense
from app.models import Participant,Group,Notification
from sqlalchemy import select

def test_group_admin_remove_and_restore(client,database):
    login(client);gid,ids=group(client);base='/api/v1/groups/'+gid
    with database() as db:db.get(Participant,ids['bob']).role='admin';db.commit()
    assert client.delete(base,headers={'If-Match':'1'}).status_code==204
    login(client,'bob');assert any(g['id']==gid for g in client.get('/api/v1/group-trash').json())
    assert client.post(base+'/restore',headers={'If-Match':'2'}).status_code==200
    assert client.put(base+'/state',json={'state':'archived'}).status_code==200
    assert client.put(base+'/state',json={'state':'active'}).status_code==200
    preview=client.get(base+'/participants/'+ids['carol']+'/departure-preview').json()
    assert client.post(base+'/participants/'+ids['carol']+'/depart',json={'keep_balance':True,'fingerprint':preview['fingerprint']}).status_code==200
    assert client.get(base+'/participants/'+ids['alice']+'/departure-preview').status_code==403
    login(client,'carol');assert client.get(base).status_code==404

def test_last_owner_with_virtuals_can_leave_and_restore(client,database):
    login(client);gid=client.post('/api/v1/groups',json={'name':'Only virtuals'}).json()['id'];base='/api/v1/groups/'+gid
    owner=client.get(base).json()['my_participant'];client.post(base+'/participants',json={'name':'Virtual'})
    preview=client.get(base+'/participants/'+owner+'/departure-preview');assert preview.status_code==200
    assert client.post(base+'/participants/'+owner+'/depart',json={'keep_balance':True,'fingerprint':preview.json()['fingerprint']}).status_code==200
    assert client.get(base).status_code==404
    trash=client.get('/api/v1/group-trash').json();assert len(trash)==1
    assert client.post(base+'/restore',headers={'If-Match':str(trash[0]['metadata_version'])}).status_code==200
    assert client.get(base).json()['role']=='owner'

def test_owner_must_transfer_to_real_account_and_owner_has_admin_powers(client,database):
    login(client);gid,ids=group(client);base='/api/v1/groups/'+gid
    virtual=client.post(base+'/participants',json={'name':'Virtual'}).json()['id']
    assert client.post(base+'/ownership',headers={'If-Match':'1'},json={'target':virtual}).status_code==422
    assert client.get(base+'/participants/'+ids['alice']+'/departure-preview').status_code==403
    # The owner may explicitly offer ownership even to a real viewer account.
    with database() as db:db.get(Participant,ids['bob']).role='viewer';db.commit()
    op=client.post(base+'/ownership',headers={'If-Match':'1'},json={'target':ids['bob']});assert op.status_code==201
    login(client,'bob');assert client.post(base+'/ownership/'+op.json()['id']+'/accept').status_code==200
    assert client.get(base+'/join-codes').status_code==200
    assert {c['role'] for c in client.get(base+'/join-codes').json()}=={'admin','member','viewer'}

def test_role_codes_only_claim_matching_virtuals(client,database):
    login(client);gid,ids=group(client);base='/api/v1/groups/'+gid
    virtuals={}
    for role in ('admin','member','viewer'):
        pid=client.post(base+'/participants',json={'name':'Virtual '+role}).json()['id'];virtuals[role]=pid
        with database() as db:db.get(Participant,pid).role=role;db.commit()
    tokens={c['role']:c['token'] for c in client.get(base+'/join-codes').json()}
    login(client,'dave')
    for role,token in tokens.items():
        result=client.post('/api/v1/group-access/preview',json={'token':token}).json()
        assert [p['id'] for p in result['virtuals']]==[virtuals[role]]
    assert client.post('/api/v1/group-access/accept',json={'token':tokens['admin'],'participant_id':virtuals['member']}).status_code==409
    assert client.post('/api/v1/group-access/accept',json={'token':tokens['viewer'],'participant_id':virtuals['admin']}).status_code==409
    assert client.post('/api/v1/group-access/accept',json={'token':tokens['admin'],'participant_id':virtuals['admin']}).status_code==200

def test_notification_folders_are_private_and_recoverable(client,database):
    login(client);gid,ids=group(client);base='/api/v1/groups/'+gid
    assert client.post(base+'/expenses',json=expense(ids),headers={'Idempotency-Key':'inbox-folders-test'}).status_code==201
    rows=client.get('/api/v1/notifications').json();nid=next(n['id'] for n in rows['items'] if n['kind']=='expense')
    path='/api/v1/notifications/'+nid+'/action'
    assert client.post(path,json={'action':'read'}).status_code==200
    assert nid not in [n['id'] for n in client.get('/api/v1/notifications?folder=unread').json()['items']]
    assert client.post(path,json={'action':'unread'}).status_code==200
    assert client.post(path,json={'action':'archive'}).status_code==200
    assert nid in [n['id'] for n in client.get('/api/v1/notifications?folder=archived').json()['items']]
    assert nid not in [n['id'] for n in client.get('/api/v1/notifications').json()['items']]
    assert client.post(path,json={'action':'trash'}).status_code==200
    assert nid in [n['id'] for n in client.get('/api/v1/notifications?folder=trash').json()['items']]
    login(client,'bob');assert client.post(path,json={'action':'restore'}).status_code==404
    login(client);assert client.post(path,json={'action':'restore'}).status_code==200
    assert nid in [n['id'] for n in client.get('/api/v1/notifications').json()['items']]
    # Existing visibility checks also apply inside archive/trash.
    with database() as db:db.get(Participant,ids['alice']).active=False;db.commit()
    assert client.post(path,json={'action':'trash'}).status_code==404

def test_last_owner_preview_rechecked_if_a_real_account_joins(client):
    login(client);gid=client.post('/api/v1/groups',json={'name':'Race guard'}).json()['id'];base='/api/v1/groups/'+gid
    owner=client.get(base).json()['my_participant'];preview=client.get(base+'/participants/'+owner+'/departure-preview').json()
    token=next(c['token'] for c in client.get(base+'/join-codes').json() if c['role']=='member')
    login(client,'dave');assert client.post('/api/v1/group-access/accept',json={'token':token}).status_code==200
    login(client);assert client.post(base+'/participants/'+owner+'/depart',json={'keep_balance':True,'fingerprint':preview['fingerprint']}).status_code==403
    assert client.get(base).json()['role']=='owner'
