import time,json,uuid
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select,func
from app.main import app
from app.models import (User,Instance,Participant,Expense,Settlement,Attachment,Notification,Session,TelegramState,TelegramLink,TelegramGrant,TelegramUpdate,TelegramAction,TelegramOutbox)
from app.telegram_config import configuration,seal,unseal
from app import telegram_bot as bot
from app.security import digest
from conftest import login
from test_api import group,expense
from test_attachments import png


class Chat:
 def __init__(self,database,uid='alice',tid=111):self.db=database;self.uid=uid;self.tid=tid;self.counter=0
 def update(self,text=None,callback=None,**kw):
  with self.db() as db:self.counter=max(self.counter,db.scalar(select(func.max(TelegramUpdate.update_id))) or 0)+1
  message={'message_id':self.counter,'date':int(time.time()),'from':{'id':self.tid,'is_bot':False},'chat':{'id':self.tid,'type':'private'}}
  if text is not None:message['text']=text
  message.update(kw)
  data={'update_id':self.counter}
  if callback:data['callback_query']={'id':str(self.counter),'from':{'id':self.tid,'is_bot':False},'message':message,'data':callback}
  else:data['message']=message
  with self.db() as db:cfg=configuration(db);bot.enqueue_update(db,cfg,data);db.commit();bot.process_update(db,cfg['generation'],self.counter)
  return data
 def click(self,label):
  with self.db() as db:
   link=db.get(TelegramLink,self.uid)
   actions=list(db.scalars(select(TelegramAction).where(TelegramAction.user_id==self.uid,TelegramAction.revision==link.action_version)))
   rows=list(db.scalars(select(TelegramOutbox).where(TelegramOutbox.user_id==self.uid).order_by(TelegramOutbox.sequence.desc())))
   current={a.token_hash for a in actions}
   for row in rows:
    if not row.payload:continue
    for line in unseal(row.payload).get('reply_markup',{}).get('inline_keyboard',[]):
     for b in line:
      if label in b['text'] and b.get('callback_data','').startswith('t:') and digest(b['callback_data'][2:]) in current:return self.update(callback=b['callback_data'])
  raise AssertionError('Button not found: '+label+' / '+str(self.messages()[-3:]))
 def messages(self):
  with self.db() as db:return [unseal(r.payload)['text'] for r in db.scalars(select(TelegramOutbox).where(TelegramOutbox.telegram_id==self.tid).order_by(TelegramOutbox.sequence)) if r.payload and r.method=='sendMessage']
 def state(self):
  with self.db() as db:return bot.draft(db.get(TelegramLink,self.uid))


def configured(database,uid='alice',tid=111,private=True,notifications=False):
 with database() as db:
  cfg={'enabled':True,'mode':'polling','username':'SganciaTestBot','bot_token':'123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_1234','generation':1,'max_messages_per_minute':60,'webhook_secret':'synthetic-webhook-secret-value'}
  db.get(Instance,1).telegram_config=seal(cfg)
  db.add(TelegramState(id=1,generation=1,username='SganciaTestBot',offset=0,error='',verified_at=int(time.time())))
  user=db.get(User,uid);db.add(TelegramLink(user_id=uid,telegram_id=tid,auth_version=user.auth_version,gate_version=1,generation=1,allow_private=private,notifications=notifications,revision=1,action_version=1,created=0));db.commit()
 return Chat(database,uid,tid)


def start_expense(chat,groupname='Weekend al mare',secret=False):
 chat.update('/spesa');chat.click(groupname);chat.update('Cena Telegram');chat.update('oggi');chat.update('Cibo');chat.click('Riservata' if secret else 'Pubblica')
 if secret:chat.click('Bob');chat.click('Conferma selezione')
 chat.update('Prima voce');chat.update('12,50 + 7,50');chat.click('In parti uguali');chat.click('Conferma selezione');chat.click('Conferma selezione')


def test_private_identity_web_link_and_revocation(client,database):
 login(client);configured(database)
 with database() as db:db.delete(db.get(TelegramLink,'alice'));db.commit()
 response=client.post('/api/v1/telegram/link',json={'telegram_id':'111','allow_private':True});assert response.status_code==200,response.text
 code=response.json()['url'].split('start=')[1]
 wrong=Chat(database,tid=222);wrong.update('/start '+code)
 assert client.get('/api/v1/telegram/account').json()['linked'] is False
 right=Chat(database);right.update('/start '+code)
 assert client.get('/api/v1/telegram/account').json()['linked'] is True
 with database() as db:assert db.get(TelegramGrant,digest(code)) is None
 right.update('/start '+code);assert 'non disponibile' in right.messages()[-1]
 assert client.delete('/api/v1/telegram/account').status_code==204
 assert client.get('/api/v1/telegram/account').json()['linked'] is False
 assert client.post('/api/v1/telegram/link',json={'telegram_id':'@username'}).status_code==422


def test_wizard_multiple_items_exact_percent_and_payers(client,database):
 login(client);gid,ids=group(client);chat=configured(database);start_expense(chat)
 assert chat.state()['items'][0]['amount']=='12,50 + 7,50'
 chat.click('Aggiungi voce');chat.update('Voce due');chat.update('10');chat.click('Percentuali');chat.click('Carol');chat.click('Conferma selezione');chat.update('25');chat.update('75');chat.click('Bob');chat.click('Conferma selezione');chat.update('4');chat.update('6')
 chat.click('Controlla e conferma');assert '30.00 EUR' in chat.messages()[-1]
 data=chat.click('Conferma e salva spesa')
 with database() as db:
  rows=list(db.scalars(select(Expense)));assert len(rows)==1 and rows[0].total==3000 and len(rows[0].items)==2
  before=db.scalar(select(func.count()).select_from(Expense));cfg=configuration(db);bot.enqueue_update(db,cfg,data);db.commit();bot.process_update(db,1,data['update_id']);assert db.scalar(select(func.count()).select_from(Expense))==before


def test_secret_visibility_and_group_messages(client,database):
 login(client);gid,ids=group(client)
 client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,True),headers={'Idempotency-Key':'private-for-bot'})
 chat=configured(database,uid='carol',tid=333,private=True);chat.update('/saldi');chat.click('Weekend al mare');text='\n'.join(chat.messages());assert 'Regalo' not in text and '100.00' not in text
 with database() as db:
  cfg=configuration(db);bad={'update_id':100,'message':{'from':{'id':333},'chat':{'id':-123,'type':'supergroup'},'text':'/saldi'}};bot.enqueue_update(db,cfg,bad);db.commit();bot.process_update(db,1,100);assert db.get(TelegramUpdate,(1,100)).status=='ignored'
  assert db.scalar(select(func.count()).select_from(TelegramOutbox).where(TelegramOutbox.telegram_id==-123))==0


def test_public_only_consent_and_delivery_rechecks(client,database,monkeypatch):
 login(client);gid,ids=group(client);chat=configured(database,private=False)
 eid=client.post(f'/api/v1/groups/{gid}/expenses',json=expense(ids,True),headers={'Idempotency-Key':'secret-scope'}).json()['id']
 chat.update('/saldi');chat.click('Weekend al mare');assert '0.00 EUR' in chat.messages()[-1]
 with database() as db:link=db.get(TelegramLink,'alice');link.allow_private=True;db.commit()
 chat.update('/saldi');chat.click('Weekend al mare')
 with database() as db:db.get(Participant,ids['alice']).active=False;db.commit()
 sent=[];monkeypatch.setattr(bot.telegram_api,'call',lambda *a,**kw:sent.append(a))
 with database() as db:
  while bot.deliver_one(db):pass
 assert not any(args[1]=='sendMessage' for args in sent)


@pytest.mark.parametrize('change',['auth','gate','generation','suspended'])
def test_credential_changes_revoke_bot_access(client,database,change):
 login(client);gid,_=group(client);chat=configured(database)
 with database() as db:
  if change=='auth':db.get(User,'alice').auth_version+=1
  elif change=='gate':db.get(Instance,1).gate_version+=1
  elif change=='generation':cfg=configuration(db);cfg['generation']+=1;db.get(Instance,1).telegram_config=seal(cfg)
  else:db.get(User,'alice').status='suspended'
  db.commit()
 chat.update('/gruppi');assert 'Weekend' not in '\n'.join(chat.messages())


def test_webhook_secret_replay_and_csrf(client,database):
 login(client);configured(database)
 with database() as db:cfg=configuration(db);cfg['mode']='webhook';db.get(Instance,1).telegram_config=seal(cfg);db.commit()
 body={'update_id':10,'message':{'from':{'id':111},'chat':{'id':111,'type':'private'},'text':'/menu'}}
 with TestClient(app,base_url='http://localhost:8088') as telegram:
  assert telegram.post('/api/v1/telegram/webhook',json=body).status_code==404
  for _ in range(2):assert telegram.post('/api/v1/telegram/webhook',json=body,headers={'X-Telegram-Bot-Api-Secret-Token':'synthetic-webhook-secret-value'}).status_code==200
 with database() as db:assert db.scalar(select(func.count()).select_from(TelegramUpdate))==1
 assert client.post('/api/v1/telegram/link',json={'telegram_id':'111'},headers={'X-CSRF-Token':'wrong'}).status_code==403
 with database() as db:db.get(Session,digest(client.cookies['sg_session'])).verified=0;db.commit()
 assert client.delete('/api/v1/telegram/account').status_code==403


def test_photo_receipt_and_changed_scope(client,database,monkeypatch):
 login(client);gid,ids=group(client);chat=configured(database);start_expense(chat);chat.click('Controlla e conferma');chat.click('Conferma e salva spesa');chat.click('Allega scontrino')
 chat.update(photo=[{'file_id':'fake-file-id','file_size':100}])
 monkeypatch.setattr(bot.telegram_api,'download',lambda *a,**kw:png());chat.click('Conferma allegato')
 with database() as db:assert db.scalar(select(func.count()).select_from(Attachment))==1
 chat.update('/foto');chat.click('Weekend al mare');chat.click('Cena Telegram');chat.click('Allega scontrino');chat.update(photo=[{'file_id':'fake-file-id','file_size':100}])
 with database() as db:e=db.scalar(select(Expense));e.version+=1;db.commit()
 chat.click('Conferma allegato')
 with database() as db:assert db.scalar(select(func.count()).select_from(Attachment))==1


def test_reimbursements_only_recipient_confirms(client,database):
 login(client);gid,ids=group(client);configured(database,uid='bob',tid=222)
 # Alice paid 100; Bob owes 50. Both users will have independent linked identities.
 body={'title':'Cena','date':'2026-11-04','items':[{'title':'Cena','amount':'100','mode':'equal','shares':{ids['alice']:'1',ids['bob']:'1'},'payers':{ids['alice']:''}}]}
 client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'bot-payment-base'})
 bob=Chat(database,'bob',222);bob.update('/rimborsi');bob.click('Weekend al mare');bob.click('Segnala pagamento');bob.click('Conferma operazione')
 with database() as db:
  row=db.scalar(select(Settlement));assert row.status=='pending'
  db.add(TelegramLink(user_id='alice',telegram_id=111,auth_version=1,gate_version=1,generation=1,allow_private=True,revision=1,action_version=1));db.commit()
 alice=Chat(database);alice.counter=100;alice.update('/rimborsi');alice.click('Weekend al mare');alice.click('Conferma rimborso');alice.click('Conferma operazione')
 with database() as db:assert db.scalar(select(Settlement)).status=='confirmed'
 alice.update('/rimborsi');alice.click('Weekend al mare');alice.click('Ripristina debito');alice.click('Conferma operazione')
 with database() as db:assert db.scalar(select(Settlement)).status=='cancelled'


def test_modify_duplicate_delete_restore_with_versions(client,database):
 login(client);gid,ids=group(client);chat=configured(database);start_expense(chat);chat.click('Controlla e conferma');chat.click('Conferma e salva spesa')
 chat.update('/spese');chat.click('Weekend al mare');chat.click('Cena Telegram');chat.click('Modifica voci');chat.click('Titolo, data e categoria');chat.update('Cena corretta');chat.update('oggi');chat.update('Cibo');chat.click('Conferma e salva spesa')
 with database() as db:e=db.scalar(select(Expense));assert e.version==2 and e.title=='Cena corretta'
 chat.update('/spese');chat.click('Weekend al mare');chat.click('Cena corretta');chat.click('Elimina spesa');chat.click('Conferma operazione')
 with database() as db:assert db.scalar(select(Expense)).deleted
 chat.update('/cestino');chat.click('Weekend al mare');chat.click('Cena corretta');chat.click('Ripristina spesa');chat.click('Conferma operazione')
 with database() as db:assert not db.scalar(select(Expense)).deleted


def test_admin_setup_never_sends_without_enabled_and_rejects_bad_identity(client,database,monkeypatch):
 from app.operations import Telegram
 login(client);calls=[];monkeypatch.setattr(bot.telegram_api,'call',lambda cfg,m,data=None:calls.append(m) or {'is_bot':True,'username':'SganciaTestBot'})
 with database() as db:assert not bot.setup_remote(db)
 assert calls==[]
 assert client.put('/api/v1/admin/operations/telegram',json={'enabled':True,'bot_token':'123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZ_1234','username':'WrongBot'}).status_code==200
 with database() as db:assert not bot.setup_remote(db);assert db.get(TelegramState,1).error=='bot_identity_mismatch'
 assert 'sendMessage' not in calls


def test_stale_and_stolen_callback_cannot_repeat_mutation(client,database):
 login(client);gid,ids=group(client);chat=configured(database);start_expense(chat);chat.click('Controlla e conferma');data=chat.click('Conferma e salva spesa')
 chat.update(callback=data['callback_query']['data'])
 with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==1
 with database() as db:db.add(TelegramLink(user_id='bob',telegram_id=222,auth_version=1,gate_version=1,generation=1,revision=1,action_version=1));db.commit()
 other=Chat(database,'bob',222);other.update(callback=data['callback_query']['data'])
 with database() as db:assert db.scalar(select(func.count()).select_from(Expense))==1


@pytest.mark.parametrize('mode',['exact','weight','quantity'])
def test_split_modes_preserve_web_arithmetic(client,database,mode):
 login(client);gid,ids=group(client);chat=configured(database)
 chat.update('/spesa');chat.click('Weekend al mare');chat.update('Voci');chat.update('oggi');chat.update('Altro');chat.click('Pubblica');chat.update('Voce');chat.update('12');chat.click({'exact':'Importi esatti','weight':'Pesi','quantity':'Quantità'}[mode]);chat.click('Conferma selezione')
 for value in (['4','4','4'] if mode=='exact' else ['1','2','3']):chat.update(value)
 chat.click('Conferma selezione');chat.click('Controlla e conferma');chat.click('Conferma e salva spesa')
 with database() as db:assert db.scalar(select(Expense)).total==1200


def test_private_wizard_public_only_reminders_and_viewer_denial(client,database):
 from app.notifications import Preferences
 from app.models import NotificationPreference, Notification
 login(client);gid,ids=group(client);chat=configured(database,private=False)
 body=expense(ids,True);body['payers']={ids['bob']:'100'}
 client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'private-reminder'})
 with database() as db:db.add(NotificationPreference(user_id='alice',scope='',config={**Preferences().model_dump(),'reminder':'daily'}));db.add(Notification(user_id='alice',group_id=gid,participant_id=ids['alice'],event_key='test-reminder',kind='reminder',resource=gid));db.commit()
 chat.update('/notifiche');assert chat.messages()[-1].startswith('Aggiornamenti recenti non letti autorizzati: 0')
 with database() as db:db.get(Participant,ids['alice']).role='viewer';db.commit()
 chat.update('/spesa');chat.click('Weekend al mare')
 assert not chat.state().get('step')


def test_notifications_use_scopes_dedup_and_current_membership(client,database,monkeypatch):
 login(client);gid,ids=group(client);chat=configured(database,notifications=True)
 body=expense(ids);client.post(f'/api/v1/groups/{gid}/expenses',json=body,headers={'Idempotency-Key':'tg-notify'})
 with database() as db:bot.notification_digest(db);bot.notification_digest(db);rows=list(db.scalars(select(TelegramOutbox).where(TelegramOutbox.notification_id.is_not(None))));assert len(rows)==1;assert 'Cena' not in unseal(rows[0].payload)['text']
 with database() as db:db.get(Participant,ids['alice']).active=False;db.commit()
 sent=[];monkeypatch.setattr(bot.telegram_api,'call',lambda *args:sent.append(args))
 with database() as db:bot.deliver_one(db)
 assert sent==[]


def test_network_retry_and_restore_revoke_integration(client,database,monkeypatch):
 from app.telegram_recovery import reset
 login(client);gid,ids=group(client);chat=configured(database);chat.update('/menu')
 def fail(*args):raise bot.telegram_api.TelegramError('api_unavailable')
 monkeypatch.setattr(bot.telegram_api,'call',fail)
 with database() as db:
  assert bot.deliver_one(db);row=db.scalar(select(TelegramOutbox));assert row.status=='pending' and row.attempts==1
  reset(db);assert not configuration(db)['enabled'];assert db.scalar(select(func.count()).select_from(TelegramLink))==0;assert db.scalar(select(func.count()).select_from(TelegramOutbox))==0


def test_polling_uses_api_only_when_enabled_and_offsets_are_durable(client,database,monkeypatch):
 login(client);configured(database);methods=[]
 def api(cfg,method,data=None):
  methods.append((method,data))
  if method=='getUpdates':return [{'update_id':10,'message':{'from':{'id':111},'chat':{'id':111,'type':'private'},'text':'/id'}}] if data['offset']==0 else []
  return True
 monkeypatch.setattr(bot,'SessionLocal',database);monkeypatch.setattr(bot.telegram_api,'call',api)
 bot.tick();bot.tick()
 with database() as db:assert db.get(TelegramState,1).offset==11;assert db.scalar(select(func.count()).select_from(TelegramUpdate))==1
 assert len([m for m,d in methods if m=='sendMessage'])==1


def test_forwards_and_false_private_chats_are_ignored(client,database):
 login(client);configured(database)
 for i,extra in enumerate([{'forward_origin':{'type':'user'}},{'via_bot':{'id':999}},{'sender_chat':{'id':1}}],1):
  data={'update_id':i,'message':{'from':{'id':111},'chat':{'id':111,'type':'private'},'text':'/menu',**extra}}
  with database() as db:bot.enqueue_update(db,configuration(db),data);db.commit();bot.process_update(db,1,i)
 with database() as db:assert db.scalar(select(func.count()).select_from(TelegramOutbox))==0
