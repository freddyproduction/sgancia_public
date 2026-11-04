import json,time,base64,io
import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select
from PIL import Image
from app.main import app
from app.models import User,Session,AccountToken,MailMessage,RecoveryCode,PaymentMethod,Instance
from app.security import cipher,digest
from app.config import settings
from app.account_security import issue_token
from conftest import login
from test_api import group,expense


def mail(monkeypatch):
    monkeypatch.setattr(settings,'smtp_host','smtp.invalid');monkeypatch.setattr(settings,'smtp_sender','test@example.org')


def latest_token(database,purpose='verify'):
    with database() as db:
        messages=list(db.scalars(select(MailMessage)))
        payload=next(json.loads(cipher().decrypt(m.payload.encode())) for m in reversed(messages) if '#'+purpose+'.' in cipher().decrypt(m.payload.encode()).decode())
        return payload['body'].split('#'+purpose+'.')[1].split()[0]


def mfa(database):
    secret=pyotp.random_base32()
    with database() as db:
        user=db.get(User,'alice');user.totp_secret=cipher().encrypt(secret.encode()).decode();user.totp_last_counter=-1
        db.add(RecoveryCode(user_id='alice',code_hash=digest('recovery-for-testing')));db.commit()
    return secret


def test_change_password_revokes_other_sessions_but_preserves_current(client,database):
    login(client)
    with TestClient(app,base_url='http://localhost:8088') as other:
        login(other)
        assert client.put('/api/v1/auth/password',json={'password':'wrong','new_password':'new-password-long-enough'}).status_code==401
        result=client.put('/api/v1/auth/password',json={'password':'password-very-long','new_password':'new-password-long-enough'})
        assert result.status_code==200,result.text
        assert client.get('/api/v1/auth/me').status_code==200
        assert other.get('/api/v1/auth/me').status_code==401
    assert client.post('/api/v1/auth/login',json={'email':'alice@example.org','password':'password-very-long'}).status_code==401
    assert client.post('/api/v1/auth/login',json={'email':'alice@example.org','password':'new-password-long-enough'}).status_code==200


def test_mfa_recovery_renew_and_disable_require_real_factor(client,database):
    login(client);secret=mfa(database)
    proof={'password':'password-very-long','code':pyotp.TOTP(secret).now()}
    result=client.post('/api/v1/auth/mfa/recovery-codes',json=proof);assert result.status_code==200,result.text
    codes=result.json()['recovery_codes'];assert len(codes)==10
    assert client.post('/api/v1/auth/mfa/disable',json=proof).status_code==401
    assert client.post('/api/v1/auth/mfa/disable',json={'password':'password-very-long','code':'recovery-for-testing'}).status_code==401
    assert client.post('/api/v1/auth/mfa/disable',json={'password':'password-very-long','code':codes[0]}).status_code==200
    assert client.get('/api/v1/auth/me').json()['totp'] is False
    with database() as db:assert list(db.scalars(select(RecoveryCode)))==[]


def test_mfa_rotation_preserves_old_factor_until_confirmation(client,database):
    login(client);secret=mfa(database)
    result=client.post('/api/v1/auth/mfa/rotate',json={'password':'password-very-long','code':pyotp.TOTP(secret).now()});assert result.status_code==200,result.text
    fresh=result.json()['secret']
    with database() as db:assert cipher().decrypt(db.get(User,'alice').totp_secret.encode()).decode()==secret
    assert client.post('/api/v1/auth/mfa/rotate/confirm',json={'password':'wrong','code':pyotp.TOTP(fresh).now()}).status_code==401
    result=client.post('/api/v1/auth/mfa/rotate/confirm',json={'password':'password-very-long','code':pyotp.TOTP(fresh).now()});assert result.status_code==200,result.text
    with database() as db:assert cipher().decrypt(db.get(User,'alice').totp_secret.encode()).decode()==fresh
    assert len(result.json()['recovery_codes'])==10 and client.get('/api/v1/auth/me').status_code==200


def test_verification_is_expiring_one_use_email_bound_and_outbox_encrypted(client,database,monkeypatch):
    mail(monkeypatch);login(client)
    assert client.post('/api/v1/auth/email/send-verification').status_code==200
    first=latest_token(database)
    assert client.post('/api/v1/auth/email/send-verification').status_code==200
    second=latest_token(database)
    assert first!=second
    assert client.post('/api/v1/auth/email/verify',json={'token':first}).status_code==400
    assert client.post('/api/v1/auth/email/verify',json={'token':second}).status_code==200
    assert client.post('/api/v1/auth/email/verify',json={'token':second}).status_code==400
    assert client.get('/api/v1/auth/me').json()['email_verified'] is True
    with database() as db:
        assert db.get(AccountToken,digest(second)).used
        assert all(second not in row.payload and 'alice@example.org' not in row.payload for row in db.scalars(select(MailMessage)))


def test_email_change_invalidates_old_links_verification_and_sessions(client,database,monkeypatch):
    mail(monkeypatch);login(client)
    client.post('/api/v1/auth/email/send-verification');old=latest_token(database)
    with TestClient(app,base_url='http://localhost:8088') as other:
        login(other)
        assert client.put('/api/v1/auth/email',json={'email':'alice-new@example.org','password':'password-very-long'}).status_code==200
        assert other.get('/api/v1/auth/me').status_code==401
    assert client.post('/api/v1/auth/email/verify',json={'token':old}).status_code==400
    assert client.get('/api/v1/auth/me').json()['email_verified'] is False
    assert client.get('/api/v1/auth/me').json()['email']=='alice-new@example.org'


def test_forgot_does_not_reveal_accounts_and_reset_retains_mfa(client,database,monkeypatch):
    mail(monkeypatch);login(client);secret=mfa(database)
    with database() as db:db.get(User,'alice').email_verified=True;db.commit()
    unknown=client.post('/api/v1/auth/password/forgot',json={'email':'absent@example.org'})
    known=client.post('/api/v1/auth/password/forgot',json={'email':'alice@example.org'})
    assert known.json()==unknown.json()
    token=latest_token(database,'reset');body={'token':token,'new_password':'password-after-recovery'}
    assert client.post('/api/v1/auth/email/verify',json={'token':token}).status_code==400
    assert client.post('/api/v1/auth/password/reset',json=body).status_code==401
    assert client.post('/api/v1/auth/password/reset',json={**body,'code':pyotp.TOTP(secret).now()}).status_code==200
    assert client.post('/api/v1/auth/password/reset',json={**body,'code':'recovery-for-testing'}).status_code==400
    assert client.get('/api/v1/auth/me').status_code==401
    with database() as db:assert db.get(User,'alice').totp_secret


def test_no_mail_never_returns_token_and_recovery_token_expires(client,database):
    login(client)
    assert client.post('/api/v1/auth/email/send-verification').status_code==503
    result=client.post('/api/v1/auth/password/forgot',json={'email':'alice@example.org'})
    assert result.status_code==200 and 'token' not in result.json()
    with database() as db:
        user=db.get(User,'alice');url=issue_token(db,user,'reset',queue=False);clear=url.split('#reset.')[1];db.flush();db.get(AccountToken,digest(clear)).expires=1;db.commit()
    assert client.post('/api/v1/auth/password/reset',json={'token':clear,'new_password':'new-password-very-long'}).status_code==400


def test_global_gate_toggle_default_enabled_and_group_owner_not_global_admin(client):
    login(client)
    with TestClient(app,base_url='http://localhost:8088') as bob,TestClient(app,base_url='http://localhost:8088') as fresh:
        login(bob,'bob');bob.post('/api/v1/groups',json={'name':'Gruppo Bob'})
        assert bob.put('/api/v1/admin/access-policy',json={'enabled':False}).status_code==403
        assert fresh.post('/api/v1/auth/login',json={'email':'alice@example.org','password':'password-very-long'}).status_code==403
        assert client.get('/api/v1/admin/access-policy').json()['gate_enabled'] is True
        assert client.put('/api/v1/admin/access-policy',json={'enabled':False}).status_code==200
        assert client.get('/api/v1/auth/me').status_code==401
        assert fresh.get('/api/v1/auth/entry-policy').json()['gate_enabled'] is False
        assert fresh.post('/api/v1/auth/login',json={'email':'alice@example.org','password':'password-very-long'}).status_code==200
        assert fresh.post('/api/v1/groups',json={'name':'CSRF mancante'}).status_code==403
        fresh.headers['X-CSRF-Token']=fresh.cookies.get('sg_csrf')
        assert fresh.put('/api/v1/admin/access-policy',json={'enabled':True}).status_code==200
        assert fresh.get('/api/v1/auth/me').status_code==403


def test_gate_change_requires_recent_identity(client,database):
    login(client)
    with database() as db:
        for row in db.scalars(select(Session)):row.verified=1
        db.commit()
    assert client.put('/api/v1/admin/access-policy',json={'enabled':False}).status_code==403


def test_methods_private_encrypted_unlimited_count_unicode_and_conflicts(client,database):
    login(client);base='/api/v1/account/payment-methods'
    for index in range(21):
        r=client.post(base,json={'label':f'Metodo {index}','instructions':'漢'*4000 if index==0 else 'Istruzioni sintetiche'})
        assert r.status_code==201,r.text
    rows=client.get(base).json();assert len(rows)==21
    row=rows[0]
    assert client.put(base+'/'+row['id'],json={'label':'Modificato','instructions':'Nuove istruzioni'},headers={'If-Match':'99'}).status_code==409
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob')
        assert bob.get(base).json()==[]
        assert bob.delete(base+'/'+row['id'],headers={'If-Match':'1'}).status_code==404
    with database() as db:
        assert all('Istruzioni sintetiche' not in m.payload for m in db.scalars(select(PaymentMethod)))


def image():
    out=io.BytesIO();Image.new('RGB',(40,60),'blue').save(out,format='PNG');return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


def test_shared_methods_only_visible_to_actual_visible_debtor_until_settled(client,database):
    login(client);gid,ids=group(client);base='/api/v1/account/payment-methods'
    body={'label':'Bonifico di prova','instructions':'Recapito sintetico','shared':True,'image':image()}
    assert client.post(base,json=body).status_code==403
    with database() as db:db.get(User,'alice').email_verified=True;db.commit()
    row=client.post(base,json=body);assert row.status_code==201,row.text
    method=row.json();assert client.get(method['image_url']).status_code==200
    gidbase=f'/api/v1/groups/{gid}'
    client.post(gidbase+'/expenses',json=expense(ids,True),headers={'Idempotency-Key':'method-private-cost'})
    path=gidbase+f'/participants/{ids["alice"]}/payment-methods'
    with TestClient(app,base_url='http://localhost:8088') as bob,TestClient(app,base_url='http://localhost:8088') as carol:
        login(bob,'bob');login(carol,'carol')
        assert carol.get(path).status_code==404
        shared=bob.get(path);assert shared.status_code==200,shared.text
        assert len(shared.json())==1
        img=shared.json()[0]['image_url'];assert bob.get(img).status_code==200 and carol.get(img).status_code==404
        transfer=client.get(gidbase+'/finance').json()['transfers'][0]
        assert client.post(gidbase+'/settlements/settle-transfer',json={'sender':transfer['from'],'recipient':transfer['to'],'components':transfer['components'],'fingerprint':transfer['fingerprint']},headers={'Idempotency-Key':'method-repaid-cost'}).status_code==200
        assert bob.get(path).status_code==404 and bob.get(img).status_code==404


def test_method_images_validation_and_private_quota(client,monkeypatch):
    login(client);base='/api/v1/account/payment-methods'
    assert client.post(base,json={'label':'Invalid','instructions':'Test','image':'data:image/svg+xml;base64,PHN2Zz4='}).status_code==422
    row=client.post(base,json={'label':'Immagine','instructions':'Test','image':image()}).json()
    assert row['image_url'] and client.get(row['image_url']).headers['content-type']=='image/webp'
    assert client.put(base+'/'+row['id'],json={'label':'Immagine','instructions':'Test','image':None},headers={'If-Match':'1'}).status_code==200
    assert client.get(row['image_url']).status_code==404


def test_mail_delivery_retry_redacts_errors_and_discards_expired(database,monkeypatch,caplog):
    from app import mail_delivery
    mail(monkeypatch)
    with database() as db:
        mail_delivery.enqueue(db,'private@example.org','Verifica','token-privato',int(time.time())+300);db.commit()
        def fail(_):raise ValueError('SMTP password segreta private@example.org token-privato')
        monkeypatch.setattr(mail_delivery,'send',fail)
        assert mail_delivery.deliver_one(db)
        row=db.scalar(select(MailMessage));assert row.attempts==1 and row.next_attempt>time.time()
        assert 'password segreta' not in caplog.text and 'private@example.org' not in caplog.text and 'token-privato' not in caplog.text
        row.next_attempt=0;db.commit();sent=[];monkeypatch.setattr(mail_delivery,'send',sent.append)
        assert mail_delivery.deliver_one(db) and len(sent)==1
        assert db.scalar(select(MailMessage)) is None


def test_concurrent_recovery_token_used_once_on_postgres(client,database):
    import concurrent.futures,pytest
    login(client)
    with database() as db:
        if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL locks required')
        url=issue_token(db,db.get(User,'alice'),'reset',queue=False);db.commit()
    body={'token':url.split('#reset.')[1],'new_password':'concurrent-password-new'}
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:client.post('/api/v1/auth/password/reset',json=body),range(2)))
    assert sorted(r.status_code for r in results)==[200,400]


def test_local_recovery_without_mail_after_manual_identity_check(client,database,monkeypatch,capsys):
    from app import recover
    import sys
    login(client);mfa(database)
    monkeypatch.setattr(recover,'SessionLocal',database)
    monkeypatch.setattr(sys,'argv',['recover','--reset-mfa'])
    answers=iter(['IDENTITA VERIFICATA','alice@example.org','REVOCA TUTTI I FATTORI'])
    monkeypatch.setattr('builtins.input',lambda _:next(answers))
    recover.main();output=capsys.readouterr().out;clear=output.split('#reset.')[1].strip()
    assert client.get('/api/v1/auth/me').status_code==401
    assert client.post('/api/v1/auth/password/reset',json={'token':clear,'new_password':'recovered-local-password'}).status_code==200
    with database() as db:assert db.get(User,'alice').totp_secret is None


def test_email_resend_rate_limit_and_csrf_protected_account_writes(client,database,monkeypatch):
    mail(monkeypatch);login(client)
    for _ in range(3):assert client.post('/api/v1/auth/email/send-verification').status_code==200
    assert client.post('/api/v1/auth/email/send-verification').status_code==429
    assert client.put('/api/v1/auth/password',json={'password':'password-very-long','new_password':'different-password-long'},headers={'X-CSRF-Token':'wrong'}).status_code==403
    with database() as db:
        user=db.get(User,'alice');user.auth_version+=1;db.commit()
    assert client.get('/api/v1/auth/me').status_code==401


def test_worker_does_not_deliver_superseded_verification_links(client,database,monkeypatch):
    from app import mail_delivery
    mail(monkeypatch);login(client)
    client.post('/api/v1/auth/email/send-verification');first=latest_token(database)
    client.post('/api/v1/auth/email/send-verification');second=latest_token(database)
    sent=[];monkeypatch.setattr(mail_delivery,'send',sent.append)
    with database() as db:
        for _ in range(3):mail_delivery.deliver_one(db)
    assert len(sent)==1 and second in sent[0]['body'] and first not in sent[0]['body']


def test_smtp_web_settings_global_admin_only_encrypted_and_keep_secret(client,database):
    from app.mail_delivery import configured,configuration
    login(client);gid,ids=group(client)
    with TestClient(app,base_url='http://localhost:8088') as bob:
        login(bob,'bob');bob.post('/api/v1/groups',json={'name':'Owner non globale'})
        assert bob.get('/api/v1/admin/installation/smtp').status_code==403
        assert bob.put('/api/v1/admin/installation/smtp',json={'enabled':False}).status_code==403
    body={'enabled':True,'host':'smtp.test.invalid','port':465,'mode':'ssl','sender':'noreply@example.org','username':'smtp-user','password':'private-smtp-test-secret'}
    assert client.put('/api/v1/admin/installation/smtp',json=body).status_code==200
    result=client.get('/api/v1/admin/installation/smtp');assert result.status_code==200
    assert 'password' not in result.json() and result.json()['password_set'] and 'private-smtp-test-secret' not in result.text
    with database() as db:
        assert 'private-smtp-test-secret' not in db.get(Instance,1).smtp_config
        assert configured(db) and configuration(db)['mode']=='ssl'
    body['password']=None;body['port']=587;body['mode']='starttls'
    assert client.put('/api/v1/admin/installation/smtp',json=body).status_code==200
    with database() as db:assert configuration(db)['password']=='private-smtp-test-secret'
    body['clear_password']=True
    assert client.put('/api/v1/admin/installation/smtp',json=body).status_code==200
    assert client.get('/api/v1/admin/installation/smtp').json()['password_set'] is False


def test_smtp_saved_in_web_used_by_worker_and_test_recipient_is_current_admin(client,database,monkeypatch):
    from app import mail_delivery
    login(client)
    body={'enabled':True,'host':'smtp.test.invalid','sender':'noreply@example.org','mode':'starttls','username':'test','password':'web-password'}
    assert client.put('/api/v1/admin/installation/smtp',json=body).status_code==200
    assert client.post('/api/v1/admin/installation/smtp/test').status_code==200
    with database() as db:
        sent=[];monkeypatch.setattr(mail_delivery,'send',sent.append);mail_delivery.deliver_one(db)
        assert len(sent)==1 and sent[0]['email']=='alice@example.org'
        assert sent[0]['_smtp']['host']=='smtp.test.invalid' and sent[0]['_smtp']['password']=='web-password'
    assert client.post('/api/v1/auth/email/send-verification').status_code==200
    body['enabled']=False
    assert client.put('/api/v1/admin/installation/smtp',json=body).status_code==200
    assert client.post('/api/v1/admin/installation/smtp/test').status_code==503
    assert client.get('/api/v1/auth/email/status').json()['delivery_available'] is False


def test_smtp_rejects_header_injection_plaintext_and_stale_identity(client,database):
    login(client);path='/api/v1/admin/installation/smtp'
    for patch in ({'mode':'plain'},{'sender':'foo@example.org\r\nBcc: victim@example.org'},{'host':'smtp.invalid\nother'},{'port':0}):
        assert client.put(path,json={'enabled':True,'host':'smtp.invalid','sender':'noreply@example.org',**patch}).status_code==422
    with database() as db:
        for row in db.scalars(select(Session)):row.verified=1
        db.commit()
    assert client.put(path,json={'enabled':False}).status_code==403
    assert client.post(path+'/test').status_code==403


def test_validation_errors_never_echo_smtp_or_account_passwords(client):
    login(client)
    response=client.put('/api/v1/admin/installation/smtp',json={'enabled':True,'host':'invalid host','sender':'noreply@example.org','password':'must-never-echo-secret'})
    assert response.status_code==422 and 'must-never-echo-secret' not in response.text
    response=client.put('/api/v1/auth/password',json={'password':'must-never-echo-current','new_password':'short-pw'})
    assert response.status_code==422 and 'short-pw' not in response.text and 'must-never-echo-current' not in response.text
