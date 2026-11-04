"""Explicit public disclosure, with private originals and immutable monetary amounts."""
import hashlib,json,time
from datetime import datetime
from copy import deepcopy
from fastapi import APIRouter,Depends,HTTPException,Header
from pydantic import Field
from sqlalchemy import select,func
from .models import Group,User,Expense,ExpenseRevision,Entry,Settlement,SettlementEvent,RevealJob,Idempotency
from .schemas import Strict
from .db import get_db,SessionLocal
from .security import current,audit
from .groups import membership,visible
from .expense_tools import reconcile_allocation_order
from .insights import records,payments,projection
router=APIRouter(prefix='/api/v1/groups',tags=['Rivelazione e privacy'])


def access(db,gid,eid,user,write=False):
    group=db.scalar(select(Group).where(Group.id==gid).with_for_update(read=not write).execution_options(populate_existing=True))
    _,actor=membership(db,gid,user,write=write)
    row=db.get(Expense,eid)
    if not row or row.group_id!=gid or row.deleted or not visible(row,actor):raise HTTPException(404,'Spesa non trovata')
    return group,actor,row


def permitted(row,actor,user):return actor.role in ('owner','admin') or row.author_id==user.id


def scope_payments(db,gid,audience):
    return [p for p in db.scalars(select(Settlement).where(Settlement.group_id==gid)) if p.audience is not None and set(p.audience)==set(audience)]


def plan(db,g,actor,row,user):
    if row.audience is None:raise HTTPException(409,'La spesa è già pubblica')
    ps=scope_payments(db,g.id,row.audience)
    confirmed=[p for p in ps if p.status=='confirmed']
    pending=any(p.status in ('pending','disputed') for p in ps)
    targets=[e for e in db.scalars(select(Expense).where(Expense.group_id==g.id)) if e.audience is not None and set(e.audience)==set(row.audience)] if confirmed else [row]
    allowed=actor.role!='viewer' and g.state=='active' and (actor.role in ('owner','admin') if confirmed else all(permitted(e,actor,user) for e in targets))
    rows=records(db,g.id,actor);pays=[{'sender':p.sender,'recipient':p.recipient,'amount':p.amount,'audience':p.audience,'status':p.status} for p in payments(db,g.id,actor)]
    before=projection(rows,pays,actor.id,g.smart_balances)
    target_ids={e.id for e in targets}
    after_rows=[{**r,'audience':None} if r['id'] in target_ids else r for r in rows]
    after_pays=[{**p,'audience':None} if p['status']=='confirmed' and p['audience'] is not None and set(p['audience'])==set(row.audience) else p for p in pays]
    after=projection(after_rows,after_pays,actor.id,g.smart_balances)
    if {k:v for k,v in before['balances'].items() if v}!={k:v for k,v in after['balances'].items() if v}:raise HTTPException(409,'Riconciliazione dei saldi non riuscita')
    state={'currency':g.currency,'smart':g.smart_balances,'state':g.state,'expenses':sorted((r['id'],r['version']) for r in rows),'trash':sorted((e.id,e.version) for e in targets if e.deleted),'payments':sorted((p.id,p.status,p.amount) for p in payments(db,g.id,actor))}
    fingerprint=hashlib.sha256(json.dumps(state,sort_keys=True).encode()).hexdigest()
    result={'fingerprint':fingerprint,'version':row.version,'allowed':allowed,'pending':pending,'reconciliation':bool(confirmed),'currency':g.currency,'expenses':[{'id':e.id,'title':e.title,'total':e.total,'deleted':e.deleted} for e in targets],'payments':[{'sender':p.sender,'recipient':p.recipient,'amount':p.amount} for p in confirmed],'before':before,'after':after}
    return result,targets,confirmed


def publish(db,row,user):
    latest=db.scalar(select(func.max(Entry.revision)).where(Entry.expense_id==row.id))
    entries=list(db.scalars(select(Entry).where(Entry.expense_id==row.id,Entry.revision==latest)))
    snapshot=deepcopy(db.get(ExpenseRevision,(row.id,row.version)).snapshot)
    snapshot['audience']=None;reconcile_allocation_order(snapshot)
    row.audience=None;row.version+=1
    for entry in entries:db.add(Entry(expense_id=row.id,group_id=row.group_id,participant_id=entry.participant_id,revision=row.version,paid=entry.paid,owed=entry.owed))
    db.add(ExpenseRevision(expense_id=row.id,version=row.version,actor_id=user.id,snapshot=snapshot))
    for job in db.scalars(select(RevealJob).where(RevealJob.expense_id==row.id,RevealJob.status=='pending')):job.status='cancelled';job.error='revealed_elsewhere'
    audit(db,user.id,'expense.revealed')


def simple_reveal(gid,eid,version,user,db):
    g,actor,row=access(db,gid,eid,user,True)
    if not permitted(row,actor,user):raise HTTPException(403,'Operazione riservata all’autore o agli amministratori autorizzati')
    if row.version!=version:raise HTTPException(409,'Versione non aggiornata')
    if row.audience is None:return {'id':row.id,'version':row.version}
    if any(p.status in ('pending','disputed','confirmed') for p in scope_payments(db,gid,row.audience)):raise HTTPException(409,'Usa l’anteprima di rivelazione e risolvi i pagamenti in attesa prima di riconciliare')
    publish(db,row,user);db.commit();return {'id':row.id,'version':row.version}


@router.get('/{gid}/expenses/{eid}/reveal-preview')
def preview(gid:str,eid:str,user=Depends(current),db=Depends(get_db)):
    g,actor,row=access(db,gid,eid,user)
    result=plan(db,g,actor,row,user)[0] if row.audience is not None else None
    jobs=[{'id':j.id,'run_at':j.run_at,'status':j.status,'error':j.error,'can_cancel':j.status=='pending' and (j.user_id==user.id or actor.role in ('owner','admin'))} for j in db.scalars(select(RevealJob).where(RevealJob.expense_id==eid).order_by(RevealJob.run_at.desc())) if visible(j,actor)][:20]
    return {'preview':result,'jobs':jobs}


class RevealIn(Strict):
    fingerprint:str=Field(min_length=64,max_length=64)
    confirm:bool=False
    reconcile:bool=False


@router.post('/{gid}/expenses/{eid}/reveal-confirm')
def confirm_reveal(gid:str,eid:str,body:RevealIn,idempotency_key:str=Header(min_length=8,max_length=150),user=Depends(current),db=Depends(get_db)):
    g,actor,row=access(db,gid,eid,user,True)
    key='reveal:'+gid+':'+idempotency_key;hashed=hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True).encode()).hexdigest()
    prior=db.get(Idempotency,(key,user.id))
    if prior:
        if prior.request_hash!=hashed:raise HTTPException(409,'Chiave già usata per una diversa conferma')
        if prior.response['_participant']!=actor.id:raise HTTPException(404,'Conferma non disponibile')
        return {k:v for k,v in prior.response.items() if not k.startswith('_')}
    p,targets,confirmed=plan(db,g,actor,row,user)
    if not p['allowed']:raise HTTPException(403,'Devi poter rivelare tutte le spese coinvolte; chiedi a un amministratore del gruppo incluso nel pubblico')
    if not body.confirm or (confirmed and not body.reconcile):raise HTTPException(422,'Conferma esplicitamente pubblicazione e riconciliazione')
    if p['fingerprint']!=body.fingerprint:raise HTTPException(409,'I dati visibili sono cambiati: ricarica l’anteprima')
    if p['pending']:raise HTTPException(409,'Risolvi prima i pagamenti in attesa o contestati di questo ambito')
    mirrors=[]
    for payment in confirmed:
        mirror=Settlement(group_id=gid,sender=payment.sender,recipient=payment.recipient,amount=payment.amount,audience=None,status='confirmed',kind=payment.kind,note='Pagamento conservato nella pubblicazione delle spese.',author_id=user.id,created=payment.created)
        db.add(mirror);db.flush();mirrors.append(mirror.id)
        db.add(SettlementEvent(settlement_id=mirror.id,actor_id=user.id,status='confirmed',reason='Conferma di incasso già registrata conservata durante la riconciliazione.'))
        payment.status='cancelled'
        db.add(SettlementEvent(settlement_id=payment.id,actor_id=user.id,status='cancelled',reason='Incasso trasferito nel pagamento pubblico '+mirror.id+' durante la riconciliazione; ricevute originali riservate.'))
    for target in targets:publish(db,target,user)
    result={'ids':[e.id for e in targets],'payments':mirrors}
    db.add(Idempotency(key=key,user_id=user.id,request_hash=hashed,response={**result,'_participant':actor.id}));db.commit();return result


class ScheduleIn(Strict):
    when:datetime
    confirm:bool=False


@router.post('/{gid}/expenses/{eid}/reveal-schedule',status_code=201)
def schedule(gid:str,eid:str,body:ScheduleIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    g,actor,row=access(db,gid,eid,user,True)
    if not permitted(row,actor,user):raise HTTPException(403,'Operazione non consentita')
    if row.version!=if_match or row.audience is None:raise HTTPException(409,'Spesa già pubblica o modificata')
    if not body.confirm or body.when.tzinfo is None:raise HTTPException(422,'Conferma la programmazione con data, ora e fuso orario')
    when=int(body.when.timestamp())
    if not int(time.time())<when<=int(time.time())+366*86400:raise HTTPException(422,'Scegli una data futura entro un anno')
    if any(p.status in ('pending','disputed','confirmed') for p in scope_payments(db,gid,row.audience)):raise HTTPException(409,'Per questo ambito serve una riconciliazione manuale')
    for old in db.scalars(select(RevealJob).where(RevealJob.expense_id==eid,RevealJob.status=='pending')):old.status='cancelled';old.error='replaced'
    job=RevealJob(group_id=gid,expense_id=eid,user_id=user.id,participant_id=actor.id,audience=list(row.audience),expense_version=row.version,auth_version=user.auth_version,run_at=when)
    db.add(job);db.flush();result={'id':job.id};db.commit();return result


@router.delete('/{gid}/expenses/{eid}/reveal-schedule/{jid}')
def cancel(gid:str,eid:str,jid:str,user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    g,actor,row=access(db,gid,eid,user,False)
    job=db.get(RevealJob,jid)
    if not job or job.expense_id!=eid or not visible(job,actor):raise HTTPException(404,'Programmazione non disponibile')
    if job.user_id!=user.id and actor.role not in ('owner','admin'):raise HTTPException(403,'Operazione non consentita')
    if job.status=='pending':job.status='cancelled';job.error=''
    db.commit();return {'status':job.status}


def run_job(db,jid):
    first=db.get(RevealJob,jid)
    if not first:return
    db.scalar(select(Group).where(Group.id==first.group_id).with_for_update())
    user=db.scalar(select(User).where(User.id==first.user_id).with_for_update().execution_options(populate_existing=True))
    job=db.scalar(select(RevealJob).where(RevealJob.id==jid).with_for_update().execution_options(populate_existing=True))
    if not job or job.status!='pending' or job.run_at>time.time():return
    try:
        if not user or user.status!='active' or user.auth_version!=job.auth_version:raise ValueError()
        g,actor,row=access(db,job.group_id,job.expense_id,user,True)
        if actor.id!=job.participant_id or row.version!=job.expense_version or set(row.audience or [])!=set(job.audience) or not permitted(row,actor,user):raise ValueError()
        if any(p.status in ('pending','disputed','confirmed') for p in scope_payments(db,g.id,row.audience)):raise ValueError()
    except (HTTPException,ValueError):job.status='blocked';job.error='review_required';db.commit();return
    publish(db,row,user);job.status='done';job.error='';db.commit()


def tick():
    with SessionLocal() as db:ids=list(db.scalars(select(RevealJob.id).where(RevealJob.status=='pending',RevealJob.run_at<=int(time.time()))))
    for jid in ids:
        try:
            with SessionLocal() as db:run_job(db,jid)
        except Exception:print('Rivelazione temporaneamente non elaborata',flush=True)
