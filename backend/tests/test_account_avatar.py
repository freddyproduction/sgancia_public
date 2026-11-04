import base64,io
from PIL import Image
from conftest import login

def sample():
    out=io.BytesIO();Image.new('RGB',(800,400),'red').save(out,format='PNG');return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()

def test_avatar_image_icon_and_privacy(client,database):
    login(client);me=client.get('/api/v1/auth/me').json();assert me['avatar_version']==1 and me['avatar_url'] is None
    result=client.put('/api/v1/account/avatar',headers={'If-Match':'1'},json={'icon':'🐱','image':sample()})
    assert result.status_code==200
    assert result.json()['avatar_icon']=='🐱' and result.json()['avatar_version']==2
    response=client.get(result.json()['avatar_url']);assert response.status_code==200 and 'no-store' in response.headers['cache-control']
    with Image.open(io.BytesIO(response.content)) as im:assert im.size==(512,256) and im.format=='WEBP' and not im.getexif()
    assert client.put('/api/v1/account/avatar',headers={'If-Match':'1'},json={'icon':'x'}).status_code==409
    login(client,'bob');assert client.get('/api/v1/account/avatar').status_code==404
    login(client);result=client.put('/api/v1/account/avatar',headers={'If-Match':'2'},json={'icon':'⭐','image':None})
    assert result.status_code==200 and result.json()['avatar_url'] is None
    assert client.get('/api/v1/account/avatar').status_code==404

def test_invalid_avatar_is_not_saved(client):
    assert client.get('/api/v1/account/avatar').status_code in (401,403)
    login(client)
    assert client.put('/api/v1/account/avatar',headers={'If-Match':'1'},json={'image':'not-a-picture'}).status_code==422
    assert client.put('/api/v1/account/avatar',headers={'If-Match':'1'},json={'icon':'x'*17}).status_code==422
    assert client.get('/api/v1/auth/me').json()['avatar_version']==1

def test_avatar_follows_account_in_groups_with_membership_checks(client,database):
    from app.models import Group,Participant
    with database() as db:
        db.add(Group(id='avatar-g',name='Avatar group',owner_id='alice'));db.flush()
        db.add_all([Participant(id='avatar-a',group_id='avatar-g',name='Name in group',user_id='alice',role='owner'),Participant(id='avatar-b',group_id='avatar-g',name='Bob',user_id='bob')]);db.commit()
    login(client)
    assert client.put('/api/v1/account/avatar',headers={'If-Match':'1'},json={'icon':'🌻','image':sample()}).status_code==200
    person=client.get('/api/v1/groups/avatar-g').json()['participants'][0]
    # Display name remains group-specific; appearance follows the account.
    people={p['id']:p for p in client.get('/api/v1/groups/avatar-g').json()['participants']};person=people['avatar-a']
    assert person['name']=='Name in group' and person['avatar_icon']=='🌻' and person['avatar_url']
    login(client,'bob');assert client.get(person['avatar_url']).status_code==200
    assert client.get('/api/v1/account/avatar').status_code==404
    login(client,'carol');assert client.get(person['avatar_url']).status_code==404
    login(client)
    assert client.put('/api/v1/account/avatar',headers={'If-Match':'2'},json={'icon':'😎','image':None}).status_code==200
    people={p['id']:p for p in client.get('/api/v1/groups/avatar-g').json()['participants']}
    assert people['avatar-a']['avatar_icon']=='😎' and people['avatar-a']['avatar_url'] is None
    assert client.get(person['avatar_url']).status_code==404
