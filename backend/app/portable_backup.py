"""Non-executable, password-encrypted portable snapshots. Restore never overwrites an installation."""
import base64,hashlib,hmac,json,os,re,time,zlib,uuid
from contextlib import contextmanager
from fastapi import APIRouter,Depends,HTTPException,Request,Response,UploadFile,File,Form
from pydantic import Field,SecretStr
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select,func,LargeBinary,text
from sqlalchemy.orm import Session as DBSession
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt
from .db import Base,get_db
from .models import Instance,User,Group,Participant,Attachment,GroupOperation
from .schemas import Strict
from .config import settings
from .security import admin,current,audit,cipher,throttle,passwords
from .admin_permissions import require_superadmin,require_permission
from .smtp_admin import require_admin_session
from .account_security import require_password,live_group_user
from .groups import membership
from .attachment_storage import storage_lock,path_for,write_blob
from .attachment_backup import file_hash

router=APIRouter(prefix='/api/v1',tags=['Backup portabile e configurazione'])
MAGIC=b'SGANCIA-PORTABLE-1\n'
SCHEMA='fb24a762bd25'
HARD_LIMIT=512*1024*1024
# No sessions, bearer invitations, transient queues, installation credentials or external actions are resurrected.
EXCLUDED={'sessions','gate_grants','webauthn_challenges','installation_challenges','installation_passkeys','account_tokens','invitations','platform_invitation_links','group_invitations','participant_claims','guest_links','group_join_codes','friend_links','maintenance_jobs','service_heartbeats','rate_buckets','mail_messages','telegram_links','telegram_grants','telegram_actions','telegram_updates','telegram_outbox','telegram_state','idempotency_records','import_batches'}
GROUP_TABLES={'groups','participants','expenses','expense_versions','ledger_entries','settlements','settlement_events','attachments','categories','expense_disputes','imported_expenses','budgets','final_reports','currency_changes','group_operations','expense_plans','expense_jobs','reveal_jobs','virtual_delegations'}
SEALED={'users':{'totp_secret','totp_pending'},'instance':{'smtp_config','telegram_config'},'payment_methods':{'payload'}}

class BackupOptions(Strict):
    groups_enabled:bool=True
    max_archive_mb:int=Field(default=128,ge=1,le=512)
    filename_prefix:str=Field(default='sgancia',pattern=r'^[A-Za-z0-9_-]{1,40}$')
class Export(Strict):
    archive_password:SecretStr=Field(min_length=12,max_length=128)
    password:SecretStr=Field(default=SecretStr(''),max_length=128)
    code:str=Field(default='',max_length=100)
    filename:str=Field(default='sgancia',pattern=r'^[A-Za-z0-9_-]{1,60}$')
class RestoreConfirm(Strict):
    archive_password:SecretStr=Field(min_length=12,max_length=128)


def policy(db):
    instance=db.get(Instance,1)
    return BackupOptions.model_validate((instance.backup_policy or {}).get('portable',{}) if instance else {}).model_dump()

@router.get('/admin/operations/portable')
def get_policy(user=Depends(admin),db=Depends(get_db)):
    require_permission(db,user,'backups');return policy(db)

@router.put('/admin/operations/portable')
def save_policy(body:BackupOptions,request:Request,user=Depends(admin),db=Depends(get_db)):
    require_permission(db,user,'backups');require_admin_session(db,request,user)
    row=db.get(Instance,1);row.backup_policy={**(row.backup_policy or {}),'portable':body.model_dump()};audit(db,user.id,'backup.portable_policy');db.commit();return body

@router.get('/backup-policy')
def member_policy(user=Depends(current),db=Depends(get_db)):return policy(db)

def derive(password,salt):return Scrypt(salt=salt,length=32,n=2**14,r=8,p=1).derive(password.encode())

def encode(payload,password,limit):
    data=json.dumps(payload,ensure_ascii=False,separators=(',',':')).encode()
    if len(data)>limit:raise HTTPException(413,'Archivio oltre il limite configurato; usa il backup server per installazioni grandi')
    salt=os.urandom(16);nonce=os.urandom(12)
    return MAGIC+salt+nonce+AESGCM(derive(password,salt)).encrypt(nonce,zlib.compress(data,6),MAGIC)

def decode(data,password,limit):
    try:
        if len(data)>limit or not data.startswith(MAGIC):raise ValueError()
        offset=len(MAGIC);salt=data[offset:offset+16];nonce=data[offset+16:offset+28]
        packed=AESGCM(derive(password,salt)).decrypt(nonce,data[offset+28:],MAGIC)
        decoder=zlib.decompressobj();clear=decoder.decompress(packed,limit+1)
        if len(clear)>limit or not decoder.eof or decoder.unused_data or decoder.unconsumed_tail:raise ValueError()
        result=json.loads(clear)
        if result.get('format')!='sgancia-portable-1' or result.get('schema')!=SCHEMA or result.get('scope') not in ('installation','group'):raise ValueError()
        tables=result['tables'];allowed=set(Base.metadata.tables)-EXCLUDED if result['scope']=='installation' else GROUP_TABLES
        if not isinstance(tables,dict) or set(tables)-allowed:raise ValueError()
        for name,rows in tables.items():
            if not isinstance(rows,list) or len(rows)>200000:raise ValueError()
            columns=set(Base.metadata.tables[name].columns.keys())
            if any(not isinstance(row,dict) or set(row)!=columns for row in rows):raise ValueError()
        return result
    except HTTPException:raise
    except Exception:raise HTTPException(422,'Archivio non valido, incompleto, incompatibile o password errata') from None

def wire(table,row):
    value=dict(row)
    for col in table.columns:
        if value[col.name] is not None and isinstance(col.type,LargeBinary):value[col.name]={'base64':base64.b64encode(value[col.name]).decode()}
    for col in SEALED.get(table.name,()):
        if value[col]:value[col]=cipher().decrypt(value[col].encode()).decode()
    return value

def unwire(table,row):
    value=dict(row)
    for col in table.columns:
        if value[col.name] is not None and isinstance(col.type,LargeBinary):value[col.name]=base64.b64decode(value[col.name]['base64'],validate=True)
    for col in SEALED.get(table.name,()):
        if value[col]:value[col]=cipher().encrypt(value[col].encode()).decode()
    return value

@contextmanager
def snapshot(db):
    # One consistent MVCC snapshot; immutable blobs are collected under the storage lock.
    if db.bind.dialect.name=='postgresql':
        with db.bind.connect().execution_options(isolation_level='REPEATABLE READ') as conn:
            with conn.begin():
                with DBSession(bind=conn) as snap:yield snap
    else:yield db

def capture(db,gid=None,actor=None,limit=128*1024**2):
    with storage_lock(),snapshot(db) as source:
        tables={};expenses=set();settlements=set();plans=set();size=0;identities={};aliases={}
        for table in Base.metadata.sorted_tables:
            name=table.name
            if name in EXCLUDED or (gid and name not in GROUP_TABLES):continue
            query=select(table)
            if gid:
                if name=='groups':query=query.where(table.c.id==gid)
                elif 'group_id' in table.c:query=query.where(table.c.group_id==gid)
                elif 'expense_id' in table.c:query=query.where(table.c.expense_id.in_(expenses))
                elif 'settlement_id' in table.c:query=query.where(table.c.settlement_id.in_(settlements))
                elif 'plan_id' in table.c:query=query.where(table.c.plan_id.in_(plans))
                else:continue
            values=[]
            for row in source.execute(query).mappings():
                value=wire(table,row);size+=len(json.dumps(value).encode())
                if size>limit:raise HTTPException(413,'Dati oltre il limite del backup portabile')
                values.append(value)
            if name=='expenses':expenses={v['id'] for v in values}
            if name=='settlements':settlements={v['id'] for v in values}
            if name=='expense_plans':plans={v['id'] for v in values}
            if gid:
                # No account IDs/emails/credentials in a group package. Actor references are restored as import provenance.
                for row in values:
                    for col in table.columns:
                        if any(fk.target_fullname=='users.id' for fk in col.foreign_keys):
                            original=row[col.name]
                            if original and original not in aliases:
                                alias='archive-user-'+str(len(aliases));aliases[original]=alias;account=source.get(User,original);identities[alias]=account.name if account else 'Autore storico'
                            row[col.name]=aliases.get(original)
            tables[name]=values
        def alias_json(value):
            if isinstance(value,str):return aliases.get(value,value)
            if isinstance(value,list):return [alias_json(v) for v in value]
            if isinstance(value,dict):return {aliases.get(k,k):alias_json(v) for k,v in value.items()}
            return value
        if gid:tables=alias_json(tables)
        blobs={}
        for attachment in tables.get('attachments',[]):
            for suffix in ('.blob','.preview') if attachment['preview_size'] else ('.blob',):
                key=attachment['storage_key']+suffix;path=path_for(key)
                if not path.is_file() or path.is_symlink() or (suffix=='.blob' and file_hash(path)!=attachment['sha256']):raise HTTPException(409,'Allegato mancante o danneggiato: backup interrotto')
                size+=((path.stat().st_size+2)//3)*4
                if size>limit:raise HTTPException(413,'Dati e allegati oltre il limite del backup portabile')
                blobs[key]=base64.b64encode(path.read_bytes()).decode()
        return {'format':'sgancia-portable-1','schema':SCHEMA,'scope':'group' if gid else 'installation','created':int(time.time()),'actor_participant':actor,'identities':identities,'tables':tables,'blobs':blobs}

def archive_response(payload,body,limits):
    return Response(encode(payload,body.archive_password.get_secret_value(),limits['max_archive_mb']*1024**2),media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{body.filename}-{time.strftime("%Y%m%d-%H%M%S",time.gmtime())}.sgp"'})

@router.post('/admin/operations/portable/export')
def export_installation(body:Export,request:Request,user=Depends(admin),db=Depends(get_db)):
    throttle(db,'portable-export:'+user.id,6);user=require_admin_session(db,request,user);require_superadmin(db,user)
    require_password(db,user,body.password.get_secret_value(),body.code)
    limits=policy(db);payload=capture(db,limit=limits['max_archive_mb']*1024**2);audit(db,user.id,'backup.portable_exported');db.commit();return archive_response(payload,body,limits)

@router.post('/groups/{gid}/backup')
def export_group(gid:str,body:Export,user=Depends(current),db=Depends(get_db)):
    membership(db,gid,user,manage=True);throttle(db,'group-backup:'+user.id,10)
    if not policy(db)['groups_enabled']:raise HTTPException(403,'Backup gruppi disabilitati dalla piattaforma')
    user=live_group_user(db,user);db.scalar(select(Group).where(Group.id==gid).with_for_update());_,actor=membership(db,gid,user,manage=True);payload=capture(db,gid,actor.id,policy(db)['max_archive_mb']*1024**2);audit(db,user.id,'backup.group_exported',gid);db.commit();return archive_response(payload,body,policy(db))

async def upload(file,limit):
    data=await file.read(limit+1)
    if len(data)>limit:raise HTTPException(413,'File oltre il limite consentito')
    return data

def verified_blobs(payload):
    expected={}
    for a in payload['tables'].get('attachments',[]):
        expected[a['storage_key']+'.blob']=(a['size'],a['sha256'])
        if a['preview_size']:expected[a['storage_key']+'.preview']=(a['preview_size'],None)
    if set(payload['blobs'])!=set(expected):raise ValueError('File mancanti o inattesi')
    result={}
    for key,(size,sha) in expected.items():
        data=base64.b64decode(payload['blobs'][key],validate=True)
        if not re.fullmatch(r'[0-9a-f]{32}\.(blob|preview)',key) or len(data)!=size or (sha and hashlib.sha256(data).hexdigest()!=sha):raise ValueError('Allegato non valido')
        result[key]=data
    return result

def empty_lock(db):
    if db.bind.dialect.name=='postgresql':db.execute(text('SELECT pg_advisory_xact_lock(71309224)'))
    if db.get(Instance,1) or db.scalar(select(func.count()).select_from(User)):raise HTTPException(409,'Installazione già configurata: il ripristino completo richiede una destinazione vuota')

def sanitize_installation(tables):
    for row in tables.get('users',[]):row['auth_version']+=1;row['totp_pending']=None
    for row in tables.get('instance',[]):
        row['gate_version']+=1;row['guest_links_enabled']=False
        row['backup_policy']={**(row['backup_policy'] or {}),'enabled':False}
        for name in ('smtp_config','telegram_config'):
            if row[name]:
                config=json.loads(row[name]);config['enabled']=False;row[name]=json.dumps(config)
            elif name=='smtp_config':row[name]=json.dumps({'enabled':False,'host':'','port':587,'mode':'starttls','username':'','password':'','sender':''})
    for row in tables.get('notification_preferences',[]):row['config']={**(row['config'] or {}),'enabled':False}
    for row in tables.get('notifications',[]):
        if row['email_status']=='queued':row['email_status']='cancelled'
    for row in tables.get('expense_plans',[]):row['enabled']=False;row['error']='restore_review'
    for row in tables.get('reveal_jobs',[]):
        if row['status']=='pending':row['status']='cancelled';row['error']='restore_review'
    for row in tables.get('expense_jobs',[]):
        if row['status'] in ('pending','running'):row['status']='failed';row['error']='restore_review'


def validate_group(tables,identities):
    if set(tables)-GROUP_TABLES or len(tables.get('groups',[]))!=1:raise ValueError('Gruppo non valido')
    gid=tables['groups'][0]['id']
    # Group packages cannot attach records to any pre-existing destination account/group.
    references={(name,col.name):{r[col.name] for r in rows} for name,rows in tables.items() for col in Base.metadata.tables[name].columns if col.primary_key or col.name in ('id','group_id','expense_id','version')}
    references[('users','id')]=set(identities)
    for name,rows in tables.items():
        table=Base.metadata.tables[name]
        for row in rows:
            if 'group_id' in row and row['group_id']!=gid:raise ValueError('Riferimento a un altro gruppo')
            for col in table.columns:
                for fk in col.foreign_keys:
                    value=row[col.name]
                    if value is not None and value not in references.get((fk.column.table.name,fk.column.name),set()):raise ValueError('Riferimento esterno non consentito')
    people=references.get(('participants','id'),set())
    for name in ('expenses','settlements','expense_jobs','reveal_jobs','expense_plans'):
        for row in tables.get(name,[]):
            if row.get('audience') is not None and (not isinstance(row['audience'],list) or not set(row['audience'])<=people):raise ValueError('Destinatari non validi')

def apply(db,payload,user=None):
    tables=payload['tables'];group=payload['scope']=='group';mapping={};files=verified_blobs(payload)
    if group:
        if not user:raise ValueError('Backup gruppo non valido in configurazione iniziale')
        validate_group(tables,payload.get('identities',{}))
        # Remap every entity ID and storage key, including JSON audiences, shares and historic snapshots.
        actor_row=next((p for p in tables.get('participants',[]) if p['id']==payload['actor_participant']),None)
        if not actor_row:raise ValueError('Partecipante originale mancante')
        source_user=actor_row['user_id']
        for alias,label in payload.get('identities',{}).items():
            if not re.fullmatch(r'archive-user-[0-9]+',alias) or not isinstance(label,str):raise ValueError('Autore non valido')
            if alias==source_user:mapping[alias]=user.id
            else:
                identity=str(uuid.uuid4());mapping[alias]=identity
                db.add(User(id=identity,email='archive-'+identity+'@group-backup.invalid',name=label[:100],password_hash=passwords.hash(uuid.uuid4().hex),status='suspended',deleted=True,archival=True,admin=False,superadmin=False))
        db.flush()
        for name,rows in tables.items():
            for row in rows:
                if 'id' in row:mapping[row['id']]=str(uuid.uuid4())
        for row in tables.get('attachments',[]):mapping[row['storage_key']]=uuid.uuid4().hex
        def replace(v):
            if isinstance(v,str):return mapping.get(v,v)
            if isinstance(v,list):return [replace(x) for x in v]
            if isinstance(v,dict):return {mapping.get(k,k):replace(x) for k,x in v.items()}
            return v
        tables=replace(tables);source_actor=mapping.get(payload['actor_participant']);people=tables.get('participants',[])
        if source_actor not in {p['id'] for p in people}:raise ValueError('Partecipante originale mancante')
        for p in people:
            p['user_id']=user.id if p['id']==source_actor else None
            p['role']='owner' if p['id']==source_actor else 'member' if p['role']=='owner' else p['role']
            if p['id']==source_actor:p['active']=True
        g=tables['groups'][0];g['owner_id']=user.id;g['deleted']=False;g['state']='frozen';g['name']=(g['name']+' · ripristino')[:100]
        for row in tables.get('expense_plans',[]):row['enabled']=False;row['error']='restore_review'
        for row in tables.get('expense_jobs',[]):
            if row['status'] in ('pending','running'):row['status']='failed';row['error']='restore_review'
        for row in tables.get('reveal_jobs',[]):row['status']='cancelled';row['error']='restore_review'
        for row in tables.get('virtual_delegations',[]):row['revoked']=True
        files={mapping.get(k.rsplit('.',1)[0],k.rsplit('.',1)[0])+'.'+k.rsplit('.',1)[1]:v for k,v in files.items()}
    else:
        empty_lock(db)
        users=tables.get('users',[]);instances=tables.get('instance',[])
        if len(instances)!=1 or instances[0]['id']!=1 or not any(u['id']==instances[0]['superadmin_id'] and u['superadmin'] and u['admin'] and u['status']=='active' and not u['deleted'] for u in users):raise ValueError('Superadmin attivo mancante')
        sanitize_installation(tables)
    # Publish immutable files first; rollback can leave only harmless unreferenced blobs.
    with storage_lock(exclusive=True):
        for key,data in files.items():
            path=path_for(key)
            if path.exists():
                if path.is_symlink() or file_hash(path)!=hashlib.sha256(data).hexdigest():raise ValueError('Conflitto allegati')
            else:write_blob(key,data)
        for table in Base.metadata.sorted_tables:
            for row in tables.get(table.name,[]):db.execute(table.insert().values(**unwire(table,row)))
        # Validate all historic financial revisions before committing anything.
        for name in ('ledger_entries',):
            table=Base.metadata.tables[name];q=select(table.c.expense_id).group_by(table.c.expense_id,table.c.revision).having(func.sum(table.c.paid)!=func.sum(table.c.owed)).limit(1)
            if db.execute(q).first():raise ValueError('Contabilità non coerente')
        if group:db.add(GroupOperation(group_id=tables['groups'][0]['id'],actor_id=user.id,kind='backup_restored',snapshot={'source':'portable','accounts':'virtual','automations':'disabled'}))
        audit(db,user.id if user else None,'backup.group_restored' if group else 'installation.restored');db.commit()
    return {'restored':True,'group_id':tables['groups'][0]['id'] if group else None}

@router.post('/groups/backup/restore')
async def restore_group(file:UploadFile=File(...),archive_password:str=Form(...,min_length=12,max_length=128),confirm:bool=Form(False),user=Depends(current),db=Depends(get_db)):
    if not confirm:raise HTTPException(422,'Conferma creazione di una copia separata')
    if not policy(db)['groups_enabled']:raise HTTPException(403,'Backup gruppi disabilitati dalla piattaforma')
    throttle(db,'group-restore:'+user.id,5);user=live_group_user(db,user)
    payload=decode(await upload(file,policy(db)['max_archive_mb']*1024**2),archive_password,policy(db)['max_archive_mb']*1024**2)
    if payload['scope']!='group':raise HTTPException(422,'Scegli un archivio di gruppo')
    try:return await run_in_threadpool(apply,db,payload,user)
    except HTTPException:db.rollback();raise
    except Exception:db.rollback();raise HTTPException(422,'Ripristino annullato: archivio o riferimenti non validi') from None

@router.get('/setup/status')
def setup_status(db=Depends(get_db)):return {'configured':bool(db.get(Instance,1))}

def setup_authority(db,request,secret):
    throttle(db,'setup:'+request.client.host,5)
    if not settings.encryption_key or not hmac.compare_digest(secret,settings.encryption_key):raise HTTPException(403,'Chiave del nuovo server non valida')
    empty_lock(db)

@router.post('/setup/restore')
async def setup_restore(request:Request,file:UploadFile=File(...),archive_password:str=Form(...,min_length=12,max_length=128),setup_key:str=Form(...,max_length=128),confirm:bool=Form(False),db=Depends(get_db)):
    setup_authority(db,request,setup_key)
    if not confirm:raise HTTPException(422,'Conferma il ripristino sulla nuova installazione')
    payload=decode(await upload(file,HARD_LIMIT),archive_password,HARD_LIMIT)
    if payload['scope']!='installation':raise HTTPException(422,'Qui serve un backup completo dell’installazione')
    try:return await run_in_threadpool(apply,db,payload)
    except HTTPException:db.rollback();raise
    except Exception:db.rollback();raise HTTPException(422,'Ripristino annullato: archivio o riferimenti non validi') from None

class Init(Strict):
    setup_key:SecretStr=Field(max_length=128)
    email:str=Field(min_length=3,max_length=254)
    name:str=Field(min_length=1,max_length=100)
    password:SecretStr=Field(min_length=12,max_length=128)
    gate_key:SecretStr=Field(min_length=16,max_length=128)
@router.post('/setup/initialize')
def initialize(body:Init,request:Request,db=Depends(get_db)):
    setup_authority(db,request,body.setup_key.get_secret_value())
    email=body.email.strip().lower()
    if '@' not in email or not body.name.strip():raise HTTPException(422,'Nome ed email non validi')
    founder=User(email=email,name=body.name.strip(),password_hash=passwords.hash(body.password.get_secret_value()),admin=True,superadmin=True);db.add(founder);db.flush()
    db.add(Instance(id=1,gate_hash=passwords.hash(body.gate_key.get_secret_value()),superadmin_id=founder.id));audit(db,founder.id,'installation.initialized');db.commit();return {'configured':True}
