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
