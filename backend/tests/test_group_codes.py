from conftest import login
from app.models import Group,Participant,User
from app.group_access import preview_access,accept,JoinAccept
from app.group_codes import codes
from fastapi import HTTPException
import pytest

def setup(database):
    with database() as db:
        db.add(Group(id='g',name='Trip',owner_id='alice'));db.flush()
        db.add_all([Participant(id='a',group_id='g',user_id='alice',name='Alice',role='owner'),Participant(id='b',group_id='g',user_id='bob',name='Bob'),Participant(id='v',group_id='g',name='Virtual')]);db.commit()

def test_visibility_rotation_and_join(database):
    setup(database)
    with database() as db:
        alice=db.get(User,'alice');bob=db.get(User,'bob');carol=db.get(User,'carol')
        all_codes={c['role']:c['token'] for c in codes(db,'g',alice)}
        assert len(set(all_codes.values()))==3
        assert {c['role'] for c in codes(db,'g',bob)}=={'member','viewer'}
        with pytest.raises(HTTPException):codes(db,'g',bob,'admin')
        db.rollback()
        data=preview_access(db,all_codes['member'],carol)
        assert data['virtuals']==[{'id':'v','name':'Virtual'}]
        result=accept(JoinAccept(token=all_codes['member'],participant_id='v',name='New name'),carol,db)
        assert result['group_id']=='g'
        p=db.get(Participant,'v');assert (p.user_id,p.role,p.name)==('carol','member','New name')
        # Existing member cannot gain admin by presenting the admin code.
        accept(JoinAccept(token=all_codes['admin']),carol,db)
        assert p.role=='member'
        old=all_codes['viewer'];new={c['role']:c['token'] for c in codes(db,'g',alice,'viewer')}
        assert new['viewer']!=old and new['member']==all_codes['member']
        with pytest.raises(HTTPException):preview_access(db,old,db.get(User,'dave'))

def test_roles_and_stale_virtual(database):
    setup(database)
    with database() as db:
        alice=db.get(User,'alice');carol=db.get(User,'carol');dave=db.get(User,'dave')
        tokens={c['role']:c['token'] for c in codes(db,'g',alice)}
        accept(JoinAccept(token=tokens['viewer']),carol,db)
        assert [c['role'] for c in codes(db,'g',carol)]==['viewer']
        assert db.query(Participant).filter_by(user_id='carol',group_id='g').one().role=='viewer'
        with pytest.raises(HTTPException):accept(JoinAccept(token=tokens['member'],participant_id='b'),dave,db)
        db.rollback()
        accept(JoinAccept(token=tokens['admin'],name='Dave'),dave,db)
        assert db.query(Participant).filter_by(user_id='dave',group_id='g').one().role=='admin'
        group=db.get(Group,'g');group.state='archived';db.commit()
        with pytest.raises(HTTPException):preview_access(db,tokens['member'],alice)

def test_api_visibility(database,client):
    setup(database);login(client,'bob')
    r=client.get('/api/v1/groups/g/join-codes');assert r.status_code==200
    assert {c['role'] for c in r.json()}=={'member','viewer'}
    assert client.post('/api/v1/groups/g/join-codes/admin/rotate').status_code==403
    login(client,'dave')
    assert client.get('/api/v1/groups/g/join-codes').status_code==404

def test_concurrent_virtual_claim(database):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    setup(database)
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('Requires PostgreSQL row locks')
        clear=codes(db,'g',db.get(User,'alice'))[0]['token']
    barrier=threading.Barrier(2)
    def attempt(uid):
        with database() as db:
            user=db.get(User,uid);assert preview_access(db,clear,user)['virtuals'];barrier.wait(timeout=10)
            try:return accept(JoinAccept(token=clear,participant_id='v'),user,db),uid
            except HTTPException as e:db.rollback();return e.status_code,uid
    with ThreadPoolExecutor(2) as pool:results=list(pool.map(attempt,['carol','dave']))
    assert sum(isinstance(r[0],dict) for r in results)==1
    assert sum(r[0]==409 for r in results)==1
    with database() as db:assert db.get(Participant,'v').user_id in ('carol','dave')


def test_delete_restore_invalidates_codes(database,client):
    setup(database);login(client)
    tokens=client.get('/api/v1/groups/g/join-codes').json()
    assert client.delete('/api/v1/groups/g',headers={'If-Match':'1'}).status_code==204
    assert client.post('/api/v1/groups/g/restore',headers={'If-Match':'2'}).status_code==200
    fresh=client.get('/api/v1/groups/g/join-codes').json()
    assert not ({c['token'] for c in tokens}&{c['token'] for c in fresh})
