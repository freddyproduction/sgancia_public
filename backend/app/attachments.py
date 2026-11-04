import hashlib,json,re,subprocess,sys,uuid
from pathlib import Path
from urllib.parse import unquote,quote
from fastapi import APIRouter,Depends,HTTPException,Request,Header,Response
from sqlalchemy import select,func
from starlette.concurrency import run_in_threadpool
from .db import get_db
from .models import Attachment,Expense,Settlement,Group,Idempotency
from .security import current,digest,audit,throttle,peer
from .groups import membership,visible
from .config import settings
from .runtime_policy import policy
from .attachment_storage import storage_lock,write_blob,read_blob,path_for
router=APIRouter(prefix='/api/v1/groups',tags=['Allegati e ricevute'])


def parent(db,gid,kind,target_id,user,write=False):
    group,actor=membership(db,gid,user)
    cls=Expense if kind=='expenses' else Settlement
    row=db.get(cls,target_id)
    if not row or row.group_id!=gid or not visible(row,actor) or (kind=='expenses' and row.deleted):raise HTTPException(404,'Spesa o rimborso non trovato')
    if write and (actor.role=='viewer' or group.state=='archived' or (kind=='expenses' and group.state!='active')):raise HTTPException(403,'Modifica allegati non consentita')
    return group,actor,row


def output(row):
    return {'id':row.id,'filename':row.filename,'media_type':row.media_type,'size':row.size,'deleted':row.deleted,'preview':bool(row.preview_size),'created':row.created,'expense_revision':row.expense_revision}


def validate_file(raw,max_bytes=None):
    try:
        result=subprocess.run([sys.executable,'-m','app.file_validation',str(max_bytes or settings.attachment_max_bytes)],input=raw,capture_output=True,timeout=9,cwd=Path(__file__).resolve().parent.parent)
        if result.returncode:raise ValueError()
        header,data=result.stdout.split(b'\n',1);meta=json.loads(header)
        if len(data)!=meta['size']+meta['preview_size']:raise ValueError()
        return meta,data[:meta['size']],data[meta['size']:]
    except Exception:raise HTTPException(422,'File non valido: usa JPG, PNG, WebP o PDF non protetto (massimo 50 pagine, senza contenuti attivi).') from None


def safe_filename(value,extension):
    name=unquote(value).replace('\\','/').split('/')[-1]
    name=''.join(c for c in name if c.isprintable() and c not in '<>"|')
    stem=name.rsplit('.',1)[0].strip(' .')[:140] or 'allegato'
    return stem+'.'+extension


@router.get('/{gid}/{kind}/{target_id}/attachments')
def list_attachments(gid:str,kind:str,target_id:str,user=Depends(current),db=Depends(get_db)):
    if kind not in ('expenses','settlements'):raise HTTPException(404)
    _,actor,_=parent(db,gid,kind,target_id,user)
    column=Attachment.expense_id if kind=='expenses' else Attachment.settlement_id
    return [output(row) for row in db.scalars(select(Attachment).where(Attachment.group_id==gid,column==target_id).order_by(Attachment.created,Attachment.id)) if revision_visible(db,row,actor)]


@router.post('/{gid}/{kind}/{target_id}/attachments',status_code=201)
async def upload(gid:str,kind:str,target_id:str,request:Request,x_filename:str=Header(default='allegato',max_length=1000),idempotency_key:str=Header(min_length=8,max_length=150),user=Depends(current),db=Depends(get_db)):
    if kind not in ('expenses','settlements'):raise HTTPException(404)
    parent(db,gid,kind,target_id,user,write=True)
    throttle(db,'attachment:'+peer(request),30)
    from .runtime_policy import policy
    limits=policy(db)
    if not limits['uploads_enabled']:raise HTTPException(403,'Caricamenti disabilitati dall’amministratore globale')
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>limits['attachment_max_bytes']:raise HTTPException(413,'Il file supera il limite di caricamento')
    meta,data,preview=await run_in_threadpool(validate_file,bytes(raw),limits['attachment_max_bytes'])
    return persist_attachment(db,gid,kind,target_id,user,bytes(raw),x_filename,idempotency_key,meta,data,preview)


def persist_attachment(db,gid,kind,target_id,user,raw,x_filename,idempotency_key,meta,data,preview,commit=True):
    if not policy(db)['uploads_enabled']:raise HTTPException(403,'Caricamenti disabilitati')
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    db.flush();db.expire_all()
    _,_,target=parent(db,gid,kind,target_id,user,write=True)
    key='attachment:'+gid+':'+idempotency_key
    request_hash=digest(kind+target_id+x_filename+hashlib.sha256(raw).hexdigest())
    prior=db.get(Idempotency,(key,user.id))
    if prior:
        if prior.request_hash!=request_hash:raise HTTPException(409,'Chiave già usata per un altro file')
        row=db.get(Attachment,prior.response['id'])
        if not row or row.deleted:raise HTTPException(409,'Allegato rimosso: aggiorna la lista')
        return output(row)
    column=Attachment.expense_id if kind=='expenses' else Attachment.settlement_id
    count=db.scalar(select(func.count()).select_from(Attachment).where(column==target_id,Attachment.deleted.is_(False)))
    used=db.scalar(select(func.coalesce(func.sum(Attachment.size+Attachment.preview_size),0)).where(Attachment.group_id==gid,Attachment.uploader_id==user.id))
    if count>=policy(db)['attachment_max_count']:raise HTTPException(422,'Raggiunto il numero massimo di allegati per spesa o rimborso')
    if used+len(data)+len(preview)>policy(db)['attachment_group_bytes']:raise HTTPException(422,'Spazio personale per allegati nel gruppo esaurito; il cestino è incluso')
    storage_key=uuid.uuid4().hex
    row=Attachment(group_id=gid,expense_id=target_id if kind=='expenses' else None,expense_revision=target.version if kind=='expenses' else None,settlement_id=target_id if kind=='settlements' else None,uploader_id=user.id,storage_key=storage_key,filename=safe_filename(x_filename,meta['extension']),media_type=meta['media_type'],size=len(data),preview_size=len(preview),sha256=hashlib.sha256(data).hexdigest())
    with storage_lock():
        try:
            write_blob(storage_key+'.blob',data)
            if preview:write_blob(storage_key+'.preview',preview)
            db.add(row);db.flush();result=output(row)
            db.add(Idempotency(key=key,user_id=user.id,request_hash=request_hash,response=result));audit(db,user.id,'attachment.created')
            if commit:db.commit()
            else:db.flush()
        except Exception:
            # A commit may have succeeded even if the connection failed while acknowledging it.
            # Keep published immutable blobs; unreferenced ones can be cleaned by operator maintenance.
            if commit:db.rollback()
            raise
    return result


def accessible(db,gid,aid,user,write=False,deleted=False):
    row=db.get(Attachment,aid)
    if not row or row.group_id!=gid or (row.deleted and not deleted):raise HTTPException(404,'Allegato non trovato')
    _,actor,_=parent(db,gid,'expenses' if row.expense_id else 'settlements',row.expense_id or row.settlement_id,user,write)
    if not revision_visible(db,row,actor):raise HTTPException(404,'Allegato non trovato')
    return row


def content(row,preview=False):
    try:data=read_blob(row.storage_key+('.preview' if preview else '.blob'),None if preview else row.sha256)
    except (OSError,ValueError):raise HTTPException(503,'File non disponibile o danneggiato: contatta l’amministratore') from None
    if preview:
        if not row.preview_size:raise HTTPException(404,'Anteprima non disponibile')
        return Response(data,media_type='image/jpeg',headers={'Content-Security-Policy':"sandbox; default-src 'none'"})
    # Never serve user PDF as an active same-origin document.
    return Response(data,media_type='application/octet-stream',headers={'Content-Disposition':"attachment; filename*=UTF-8''"+quote(row.filename),'Content-Security-Policy':"sandbox; default-src 'none'"})

@router.get('/{gid}/attachments/{aid}/content')
def download(gid:str,aid:str,user=Depends(current),db=Depends(get_db)):
    return content(accessible(db,gid,aid,user))

@router.get('/{gid}/attachments/{aid}/preview')
def preview(gid:str,aid:str,user=Depends(current),db=Depends(get_db)):
    row=accessible(db,gid,aid,user)
    if not row.preview_size:raise HTTPException(404,'Anteprima non disponibile')
    return content(row,True)

@router.delete('/{gid}/attachments/{aid}',status_code=204)
def remove(gid:str,aid:str,user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    row=accessible(db,gid,aid,user,write=True,deleted=True);row.deleted=True;audit(db,user.id,'attachment.deleted');db.commit()

@router.post('/{gid}/attachments/{aid}/restore')
def restore(gid:str,aid:str,user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    row=accessible(db,gid,aid,user,write=True,deleted=True)
    column=Attachment.expense_id if row.expense_id else Attachment.settlement_id
    if row.deleted and db.scalar(select(func.count()).select_from(Attachment).where(column==(row.expense_id or row.settlement_id),Attachment.deleted.is_(False)))>=policy(db)['attachment_max_count']:raise HTTPException(422,'Troppi allegati attivi: rimuovine uno prima di ripristinare')
    row.deleted=False;audit(db,user.id,'attachment.restored');db.commit();return output(row)


@router.get('/{gid}/attachment-limits')
def limits(gid:str,user=Depends(current),db=Depends(get_db)):
    membership(db,gid,user)
    from .runtime_policy import policy
    limits=policy(db)
    return {'max_bytes':limits['attachment_max_bytes'],'group_bytes_per_account':limits['attachment_group_bytes'],'max_count':limits['attachment_max_count'],'uploads_enabled':limits['uploads_enabled']}


def revision_visible(db,row,actor):
    if not row.expense_id:return True
    from .models import ExpenseRevision
    version=db.get(ExpenseRevision,(row.expense_id,row.expense_revision))
    return bool(version and (version.snapshot.get('audience') is None or actor.id in version.snapshot['audience']))
