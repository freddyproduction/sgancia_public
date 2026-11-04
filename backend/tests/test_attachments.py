import io,json
from urllib.parse import quote
from pathlib import Path
import pytest
from PIL import Image
from pypdf import PdfWriter
from fastapi.testclient import TestClient
from sqlalchemy import select
from app.main import app
from app.config import settings
from app.models import Attachment,Participant
from conftest import login
from test_api import group,expense


def png():
    out=io.BytesIO();Image.new('RGB',(80,120),'green').save(out,format='PNG');return out.getvalue()

def upload(client,gid,eid,raw=None,key='file-upload-example',kind='expenses',name='foto.png'):
    return client.post(f'/api/v1/groups/{gid}/{kind}/{eid}/attachments',content=png() if raw is None else raw,headers={'Content-Type':'application/octet-stream','X-Filename':quote(name),'Idempotency-Key':key})

def setup(client,private=False):
    login(client);gid,ids=group(client)
    eid=client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,private),headers={'Idempotency-Key':'attachment-test-expense'}).json()['id']
    return gid,ids,eid


def test_image_normalization_download_preview_and_idempotency(client,database):
    gid,ids,eid=setup(client)
    first=upload(client,gid,eid,name='../../ricevuta strana.png')
    assert first.status_code==201,first.text
    row=first.json();assert row['preview'] and row['media_type']=='image/jpeg'
    assert '/' not in row['filename'] and row['filename'].endswith('.jpg')
    assert upload(client,gid,eid,name='../../ricevuta strana.png').json()['id']==row['id']
    url=f'/api/v1/groups/{gid}/attachments/{row["id"]}'
    response=client.get(url+'/content')
    assert response.status_code==200 and response.content.startswith(b'\xff\xd8')
    assert response.headers['content-type']=='application/octet-stream'
    assert response.headers['content-disposition'].startswith('attachment;')
    assert response.headers['cache-control']=='no-store'
    assert 'sandbox' in response.headers['content-security-policy']
    assert client.get(url+'/preview').headers['content-type']=='image/jpeg'
    with database() as db:
        item=db.get(Attachment,row['id']);assert item.expense_revision==1
        assert (Path(settings.attachment_dir)/(item.storage_key+'.blob')).is_file()


def test_private_file_visibility_and_group_isolation(client):
    gid,ids,eid=setup(client,True)
    result=upload(client,gid,eid);assert result.status_code==201,result.text
    aid=result.json()['id'];base=f'/api/v1/groups/{gid}'
    with TestClient(app,base_url='http://localhost:8088') as carol:
        login(carol,'carol')
        for suffix in (f'/expenses/{eid}/attachments',f'/attachments/{aid}/preview',f'/attachments/{aid}/content'):
            assert carol.get(base+suffix).status_code==404
        assert upload(carol,gid,eid).status_code==404
    other=client.post('/api/v1/groups',json={'name':'Altro gruppo'}).json()['id']
    assert client.get(f'/api/v1/groups/{other}/attachments/{aid}/content').status_code==404
    with TestClient(app,base_url='http://localhost:8088') as outsider:
        assert outsider.get(base+f'/attachments/{aid}/content').status_code==403


def test_attachment_and_parent_trash_restore(client):
    gid,ids,eid=setup(client);row=upload(client,gid,eid).json();base=f'/api/v1/groups/{gid}'
    assert client.delete(base+'/attachments/'+row['id']).status_code==204
    assert client.get(base+'/attachments/'+row['id']+'/content').status_code==404
    assert client.post(base+'/attachments/'+row['id']+'/restore').status_code==200
    assert client.delete(base+'/expenses/'+eid,headers={'If-Match':'1'}).status_code==204
    assert client.get(base+'/attachments/'+row['id']+'/content').status_code==404
    assert client.post(base+'/expenses/'+eid+'/restore',headers={'If-Match':'2'}).status_code==200
    assert client.get(base+'/attachments/'+row['id']+'/content').status_code==200


def test_viewer_cannot_modify_and_frozen_receipts_allowed(client,database):
    gid,ids,eid=setup(client);aid=upload(client,gid,eid).json()['id'];base=f'/api/v1/groups/{gid}'
    with database() as db:db.get(Participant,ids['bob']).role='viewer';db.commit()
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');assert bob.get(base+'/attachments/'+aid+'/content').status_code==200
        assert upload(bob,gid,eid).status_code==403
        assert bob.delete(base+'/attachments/'+aid).status_code==403
    payment=client.post(base+'/settlements',json={'sender':ids['alice'],'recipient':ids['bob'],'amount':'1'},headers={'Idempotency-Key':'receipt-test-payment'}).json()['id']
    assert client.put(base+'/state',json={'state':'frozen'}).status_code==200
    assert upload(client,gid,eid,key='frozen-file-upload').status_code==403
    response=upload(client,gid,payment,kind='settlements',key='receipt-file-upload')
    assert response.status_code==201,response.text
    client.put(base+'/state',json={'state':'archived'})
    assert upload(client,gid,payment,kind='settlements',key='archived-file-upload').status_code==403


def test_pdf_validation_active_content_and_bad_uploads(client,monkeypatch):
    gid,ids,eid=setup(client)
    out=io.BytesIO();writer=PdfWriter();writer.add_blank_page(width=300,height=400);writer.write(out)
    result=upload(client,gid,eid,raw=out.getvalue(),name='scontrino.pdf')
    assert result.status_code==201,result.text
    assert result.json()['media_type']=='application/pdf' and not result.json()['preview']
    writer.add_js('app.alert("no")');out=io.BytesIO();writer.write(out)
    assert upload(client,gid,eid,raw=out.getvalue(),key='active-pdf-file').status_code==422
    for i,raw in enumerate((b'<svg onload="alert(1)"/>',b'<html>not image</html>',b'%PDF-invalid',b'')):
        assert upload(client,gid,eid,raw=raw,key=f'invalid-upload-{i}').status_code==422
    monkeypatch.setattr(settings,'attachment_max_bytes',1024)
    assert upload(client,gid,eid,raw=b'x'*1025,key='oversize-file').status_code==413


def test_limits_and_csrf_and_corrupted_file_fail_closed(client,database,monkeypatch):
    gid,ids,eid=setup(client)
    assert client.post(f'/api/v1/groups/{gid}/expenses/{eid}/attachments',content=png(),headers={'Idempotency-Key':'no-csrf-test','X-CSRF-Token':'wrong'}).status_code==403
    monkeypatch.setattr(settings,'attachment_max_count',1)
    row=upload(client,gid,eid).json()
    assert upload(client,gid,eid,key='too-many-files').status_code==422
    with database() as db:
        item=db.get(Attachment,row['id']);(Path(settings.attachment_dir)/(item.storage_key+'.blob')).write_bytes(b'broken')
    assert client.get(f'/api/v1/groups/{gid}/attachments/{row["id"]}/content').status_code==503


def test_guest_file_grant_public_only_revocation_and_usage(client):
    gid,ids,eid=setup(client);row=upload(client,gid,eid).json();base=f'/api/v1/groups/{gid}'
    secret_id=client.post(base+'/expenses',json=expense(ids,True),headers={'Idempotency-Key':'guest-private-file'}).json()['id']
    secret=upload(client,gid,secret_id,key='guest-secret-upload').json()['id']
    assert client.post(base+'/guest-links',json={'show_attachments':True,'show_names':False}).status_code==422
    link=client.post(base+'/guest-links',json={'show_attachments':True,'password':'guest-pass','max_uses':1}).json()
    token=link['url'].split('#')[1]
    with TestClient(app,base_url='http://localhost:8088') as guest:
        body={'token':token,'password':'guest-pass'}
        view=guest.post('/api/v1/guest/view',json=body).json()
        assert len(view['expenses'])==1 and view['expenses'][0]['attachments'][0]['id']==row['id']
        assert view['file_access']
        data={**body,'view_token':view['file_access']}
        url='/api/v1/guest/attachments/'+row['id']
        assert guest.post(url,json=data).status_code==200
        assert guest.post('/api/v1/guest/attachments/'+secret,json=data).status_code==404
        assert guest.post(url,json={**data,'password':'wrong'}).status_code==403
        assert guest.post(url,json={**data,'view_token':'invalid-grant-value'*3}).status_code==404
        assert guest.post('/api/v1/guest/view',json=body).status_code==404
        assert client.delete(base+'/guest-links/'+link['id']).status_code==204
        assert guest.post(url,json=data).status_code==404


def test_guest_no_attachment_policy_does_not_leak_metadata(client):
    gid,ids,eid=setup(client);upload(client,gid,eid)
    token=client.post(f'/api/v1/groups/{gid}/guest-links',json={}).json()['url'].split('#')[1]
    with TestClient(app,base_url='http://localhost:8088') as guest:
        result=guest.post('/api/v1/guest/view',json={'token':token}).json()
        assert result['file_access'] is None and result['expenses'][0]['attachments']==[]


def test_ambiguous_commit_retains_blob_and_retry_is_safe(client,database,monkeypatch):
    from sqlalchemy.orm import Session
    gid,ids,eid=setup(client)
    original=Session.commit;failed=[]
    def commit_then_disconnect(db):
        has_file=any(isinstance(row,Attachment) for row in db.identity_map.values())
        original(db)
        if has_file and not failed:
            failed.append(True);raise RuntimeError('Simulated lost commit acknowledgement')
    monkeypatch.setattr(Session,'commit',commit_then_disconnect)
    with TestClient(app,base_url='http://localhost:8088',raise_server_exceptions=False) as retry:
        login(retry)
        response=upload(retry,gid,eid,key='lost-commit-file')
        assert response.status_code==500
        response=upload(retry,gid,eid,key='lost-commit-file')
        assert response.status_code==201,response.text
        assert retry.get(f'/api/v1/groups/{gid}/attachments/{response.json()["id"]}/content').status_code==200
    with database() as db:assert len(list(db.scalars(select(Attachment))))==1
