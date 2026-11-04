from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.models import Group,Expense,GuestLink
from conftest import login
from test_api import group,expense


def test_delete_restore_preserves_expenses_and_balances(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    client.post(base+'/expenses',json=expense(ids),headers={'Idempotency-Key':'trash-preserve-cost'})
    before=client.get(base+'/finance').json()
    assert client.delete(base,headers={'If-Match':'99'}).status_code==409
    assert client.delete(base,headers={'If-Match':'1'}).status_code==204
    assert client.delete(base,headers={'If-Match':'1'}).status_code==204
    assert client.get('/api/v1/groups').json()==[]
    assert client.get('/api/v1/overview').json()['people']==[]
    for suffix in ('','/expenses','/finance','/balances','/attachment-limits'):
        assert client.get(base+suffix).status_code==404
    with database() as db:
        assert db.get(Group,gid).deleted
        assert db.scalar(select(Expense).where(Expense.group_id==gid)) is not None
    trash=client.get('/api/v1/group-trash').json();assert len(trash)==1
    assert client.post(base+'/restore',headers={'If-Match':'1'}).status_code==409
    assert client.post(base+'/restore',headers={'If-Match':str(trash[0]['metadata_version'])}).status_code==200
    assert client.get(base+'/finance').json()==before
    assert client.get('/api/v1/group-trash').json()==[]


def test_only_owner_can_delete_or_restore(client):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.delete(base,headers={'If-Match':'1'}).status_code==403
        assert client.delete(base,headers={'If-Match':'1'}).status_code==204
        assert bob.get('/api/v1/group-trash').json()==[]
        assert bob.post(base+'/restore',headers={'If-Match':'2'}).status_code==403
        assert bob.get(base).status_code==404


def test_archived_state_preserved_and_guest_revoked(client,database):
    login(client);gid,ids=group(client);base=f'/api/v1/groups/{gid}'
    with database() as db:
        db.get(Group,gid).state='archived'
        db.add(GuestLink(group_id=gid,token_hash='trash-guest-test',expires=9999999999))
        db.commit()
    assert client.delete(base,headers={'If-Match':'1'}).status_code==204
    assert client.post(base+'/restore',headers={'If-Match':'2'}).status_code==200
    assert client.get(base).json()['state']=='archived'
    with database() as db:assert db.scalar(select(GuestLink).where(GuestLink.group_id==gid)).revoked
