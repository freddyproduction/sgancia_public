from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.models import User,Instance,Group,Participant,Expense,Entry,Session
from conftest import login
from test_authority import root_login
from test_api import group,expense


def action(client,person,kind,**kw):
    row=next(u for u in client.get('/api/v1/admin/users').json() if u['id']==person)
    return client.post('/api/v1/admin/users/'+person+'/lifecycle',json={'action':kind,'expected_status':row['status'],'expected_auth_version':row['auth_version'],'password':'password-very-long',**kw})

def test_only_root_can_suspend_admin_and_reactivate_without_old_sessions(client,database):
    with database() as db:bob=db.get(User,'bob');bob.admin=True;bob.admin_permissions=[];db.commit()
    login(client);row=next(u for u in client.get('/api/v1/admin/users').json() if u['id']=='bob')
    assert client.post('/api/v1/admin/users/bob/lifecycle',json={'action':'suspend','expected_status':'active','expected_auth_version':row['auth_version'],'password':'password-very-long'}).status_code==403
    root_login(client,database)
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert action(client,'bob','suspend').status_code==200
        assert bob.get('/api/v1/auth/me').status_code==401
        assert action(client,'bob','activate').status_code==200
        assert bob.get('/api/v1/auth/me').status_code==401
        login(bob,'bob');assert bob.get('/api/v1/auth/me').json()['admin']

def test_other_root_suspension_anchor_transfer_and_last_protected(client,database):
    root_login(client,database)
    with database() as db:
        bob=db.get(User,'bob');bob.admin=True;bob.superadmin=True;db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert action(bob,'alice','suspend').status_code==200
        with database() as db:assert db.get(Instance,1).superadmin_id=='bob' and db.get(User,'alice').superadmin
        assert action(bob,'bob','suspend').status_code==403
        # Even an inactive superadmin cannot be used as the remaining active anchor.
        assert action(bob,'alice','activate').status_code==200
        assert action(bob,'alice','delete',confirmation='alice@example.org').status_code==200
        with database() as db:assert db.get(User,'alice').deleted and db.get(Instance,1).superadmin_id=='bob'

def test_delete_anonymizes_preserves_ledger_and_transfers_groups(client,database):
    root_login(client,database);gid,ids=group(client);base='/api/v1/groups/'+gid
    assert client.post(base+'/expenses',json=expense(ids),headers={'Idempotency-Key':'delete-ledger-test'}).status_code==201
    # Bob owns a second group. Alice's global authority alone reveals no private group details.
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');owned=bob.post('/api/v1/groups',json={'name':'Private title not exposed'}).json()['id']
        bob.post('/api/v1/groups/'+owned+'/participants',json={'name':'Carol','email':'carol@example.org'})
    preview=client.get('/api/v1/admin/users/bob/deletion-preview').json();assert preview['transferable_groups']==1 and 'Private title' not in str(preview)
    assert action(client,'bob','delete',confirmation='wrong').status_code==422
    result=action(client,'bob','delete',confirmation='bob@example.org');assert result.status_code==200,result.text
    with database() as db:
        user=db.get(User,'bob');assert user.deleted and user.status=='suspended' and user.email.endswith('@deleted.invalid') and user.avatar is None
        p=db.get(Participant,ids['bob']);assert p.user_id is None and not p.active and p.name=='Utente eliminato'
        assert db.get(Group,owned).owner_id=='carol'
        assert db.scalar(select(Expense).where(Expense.group_id==gid)) is not None
        assert list(db.scalars(select(Entry).where(Entry.participant_id==ids['bob'])))
    assert client.put('/api/v1/admin/users/bob/status',json={'status':'active'}).status_code==409
    assert action(client,'bob','activate').status_code==409
    with TestClient(app,base_url='http://localhost:8088') as bob:
        bob.post('/api/v1/auth/gate',json={'key':'gate-secret-long-enough'})
        assert bob.post('/api/v1/auth/login',json={'email':'bob@example.org','password':'password-very-long'}).status_code==401


def test_concurrent_roots_cannot_suspend_each_other_both(database):
    import pytest,threading
    from concurrent.futures import ThreadPoolExecutor
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('Requires PostgreSQL locking')
        db.get(Instance,1).superadmin_id='alice'
        for uid in ('alice','bob'):
            u=db.get(User,uid);u.admin=True;u.superadmin=True
        db.commit()
    clients=[]
    for uid in ('alice','bob'):
        c=TestClient(app,base_url='http://localhost:8088');login(c,uid);clients.append(c)
    barrier=threading.Barrier(2)
    def attempt(pair):
        client,target=pair;row=next(u for u in client.get('/api/v1/admin/users').json() if u['id']==target);barrier.wait(timeout=10)
        return client.post('/api/v1/admin/users/'+target+'/lifecycle',json={'action':'suspend','expected_status':'active','expected_auth_version':row['auth_version'],'password':'password-very-long'}).status_code
    try:
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt,zip(clients,['bob','alice'])))
        assert results.count(200)==1 and any(r in (401,403) for r in results)
        with database() as db:assert len(list(db.scalars(select(User).where(User.superadmin.is_(True),User.status=='active'))))==1
    finally:
        for c in clients:c.close()


def test_account_delete_serializes_with_group_creation(database):
    import pytest,threading
    from concurrent.futures import ThreadPoolExecutor
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('Requires PostgreSQL locking')
    root=TestClient(app,base_url='http://localhost:8088');bob=TestClient(app,base_url='http://localhost:8088')
    root_login(root,database);login(bob,'bob');barrier=threading.Barrier(2)
    def remove():barrier.wait(timeout=10);return action(root,'bob','delete',confirmation='bob@example.org').status_code
    def create():barrier.wait(timeout=10);return bob.post('/api/v1/groups',json={'name':'Concurrent create'}).status_code
    try:
        with ThreadPoolExecutor(2) as pool:
            r=pool.submit(remove);c=pool.submit(create);assert r.result(timeout=20)==200;assert c.result(timeout=20) in (201,401,403)
        with database() as db:
            assert db.get(User,'bob').deleted
            assert not list(db.scalars(select(Group).where(Group.owner_id=='bob',Group.deleted.is_(False))))
            assert not list(db.scalars(select(Participant).where(Participant.user_id=='bob',Participant.active.is_(True))))
    finally:root.close();bob.close()
