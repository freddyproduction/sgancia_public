"""Group-serialized persistent jobs. Expense and completion commit together."""
from calendar import monthrange
from copy import deepcopy
from datetime import date,timedelta
from decimal import InvalidOperation
import time
import hashlib
import json
from zoneinfo import ZoneInfo
from datetime import datetime
from typing import Literal
from fastapi import APIRouter,Depends,Header,HTTPException
from pydantic import Field
from sqlalchemy import select,func
from .schemas import Strict,ExpenseIn
from .models import ExpensePlan,ExpenseJob,Group,User,Participant,Expense,ExpenseRevision,Idempotency
from .db import get_db,SessionLocal
from .security import current
from .groups import membership,visible,build_expense,record_expense
from .expense_tools import expense_snapshot

router=APIRouter(prefix='/api/v1/groups',tags=['Modelli e ricorrenze'])


def today():return datetime.now(ZoneInfo('Europe/Rome')).date()


def occurrence(start,frequency,interval,index):
    anchor=date.fromisoformat(start);step=interval*index
    if frequency in ('daily','weekly'):return anchor+timedelta(days=step*(7 if frequency=='weekly' else 1))
    months=anchor.year*12+anchor.month-1+step*(12 if frequency=='yearly' else 1)
    year,month=divmod(months,12);month+=1
    return date(year,month,min(anchor.day,monthrange(year,month)[1]))


def next_date(plan):
    try:return occurrence(plan.start,plan.frequency,plan.interval,plan.cursor)
    except (ValueError,OverflowError):return None


class PlanIn(Strict):
    name:str=Field(min_length=1,max_length=100)
    kind:Literal['template','recurring']='template'
    draft:ExpenseIn
    start:date
    until:date|None=None
    frequency:Literal['daily','weekly','monthly','yearly']='monthly'
    interval:int=Field(default=1,ge=1,le=365)
    auto_fx:bool=False
    authorize:bool=False


class SwitchIn(Strict):
    enabled:bool
    catch_up:bool=False


def plan_draft(body,target,auto_fx):
    draft=expense_snapshot(body)
    if draft.get('exchange_token') and not auto_fx:
        from .exchange import read_quote
        draft['exchange_rate']=read_quote(draft['exchange_token'],body.currency,target)['rate']
    draft['exchange_token']=None
    draft['currency']=body.currency or target
    return draft


def references(draft):
    refs=set(draft.get('audience') or [])|set(draft.get('payers',{}))
    for item in draft['items']:refs.update(item['shares']);refs.update(item.get('payers') or {})
    return refs


def validate(db,g,actor,body,auto_fx=False):
    active=set(db.scalars(select(Participant.id).where(Participant.group_id==g.id,Participant.active.is_(True),Participant.merged_into.is_(None))))
    if not references(body.model_dump())<=active:raise HTTPException(409,'Partecipanti cambiati: aggiorna il modello')
    check=body.model_copy(deep=True)
    if auto_fx and check.currency and check.currency!=g.currency:
        # Validate allocation independent of the temporary FX quote. Worker fetches a fresh quote.
        check.exchange_token=None;check.exchange_rate='1'
    try:build_expense(db,g.id,check,actor)
    except (ValueError,InvalidOperation) as exc:raise HTTPException(422,str(exc)) from None


def plan_out(db,row,actor):
    dates=[]
    for index in range(row.cursor,row.cursor+12):
        try:due=occurrence(row.start,row.frequency,row.interval,index)
        except (ValueError,OverflowError):break
        if row.until and due.isoformat()>row.until:break
        dates.append(due.isoformat())
    jobs=db.scalars(select(ExpenseJob).where(ExpenseJob.plan_id==row.id).order_by(ExpenseJob.date.desc()).limit(100))
    return {'id':row.id,'name':row.name,'kind':row.kind,'draft':row.draft,'start':row.start,'until':row.until,'frequency':row.frequency,'interval':row.interval,'auto_fx':row.auto_fx,'enabled':row.enabled,'version':row.version,'error':row.error,'currency':row.currency,'mine':row.owner_id==actor.user_id,'calendar':dates if row.kind=='recurring' else [],'jobs':[{'date':j.date,'status':j.status,'error':j.error,'expense_id':j.expense_id} for j in jobs if visible(j,actor)]}


def locked(db,gid,pid,user):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    g,actor=membership(db,gid,user,write=True)
    row=db.scalar(select(ExpensePlan).where(ExpensePlan.id==pid,ExpensePlan.group_id==gid).with_for_update())
    if not row or not visible(row,actor):raise HTTPException(404,'Modello non trovato')
    return g,actor,row


@router.get('/{gid}/plans')
def plans(gid:str,user=Depends(current),db=Depends(get_db)):
    _,actor=membership(db,gid,user)
    return [plan_out(db,r,actor) for r in db.scalars(select(ExpensePlan).where(ExpensePlan.group_id==gid).order_by(ExpensePlan.name)) if visible(r,actor)]


@router.post('/{gid}/plans',status_code=201)
def create_plan(gid:str,body:PlanIn,idempotency_key:str=Header(min_length=8,max_length=150),user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    g,actor=membership(db,gid,user,write=True)
    key='plan:'+gid+':'+idempotency_key
    request_hash=hashlib.sha256(json.dumps(body.model_dump(mode='json'),sort_keys=True).encode()).hexdigest()
    prior=db.get(Idempotency,(key,user.id))
    if prior:
        if prior.request_hash!=request_hash:raise HTTPException(409,'Chiave già usata per un modello differente')
        existing=db.get(ExpensePlan,prior.response['id'])
        if not existing or existing.participant_id!=actor.id or not visible(existing,actor):raise HTTPException(404,'Modello non disponibile')
        return plan_out(db,existing,actor)
    if db.scalar(select(func.count()).select_from(ExpensePlan).where(ExpensePlan.group_id==gid))>=200:raise HTTPException(409,'Limite di 200 modelli per gruppo')
    if body.kind=='recurring' and (not body.authorize or body.start<today()):raise HTTPException(422,'Autorizza la ricorrenza e scegli una data da oggi in poi')
    if body.until and body.until<body.start:raise HTTPException(422,'Fine precedente all’inizio')
    validate(db,g,actor,body.draft,body.auto_fx)
    draft=plan_draft(body.draft,g.currency,body.auto_fx)
    row=ExpensePlan(group_id=gid,owner_id=user.id,participant_id=actor.id,name=body.name.strip(),kind=body.kind,draft=draft,audience=draft['audience'],currency=g.currency,frequency=body.frequency,interval=body.interval,start=body.start.isoformat(),until=body.until.isoformat() if body.until else None,auto_fx=body.auto_fx,enabled=body.kind=='recurring')
    if not row.name:raise HTTPException(422,'Nome obbligatorio')
    db.add(row);g.metadata_version+=1;db.flush();result=plan_out(db,row,actor);db.add(Idempotency(key=key,user_id=user.id,request_hash=request_hash,response={'id':row.id}));db.commit();return result


@router.put('/{gid}/plans/{pid}')
def update_plan(gid:str,pid:str,body:PlanIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    g,actor,row=locked(db,gid,pid,user)
    if row.owner_id!=user.id:raise HTTPException(403,'Solo l’autore può modificare il modello')
    if row.version!=if_match:raise HTTPException(409,'Modello modificato: ricarica')
    if body.kind!=row.kind:raise HTTPException(422,'Il tipo del modello non può cambiare')
    if body.until and body.until<body.start:raise HTTPException(422,'Fine precedente all’inizio')
    validate(db,g,actor,body.draft,body.auto_fx)
    changed=(row.start,row.frequency,row.interval)!=(body.start.isoformat(),body.frequency,body.interval)
    if changed and body.start<today():raise HTTPException(422,'Il nuovo calendario deve partire da oggi in poi')
    row.name=body.name.strip()
    if not row.name:raise HTTPException(422,'Nome obbligatorio')
    row.draft=plan_draft(body.draft,g.currency,body.auto_fx);row.audience=row.draft['audience'];row.currency=g.currency
    row.start=body.start.isoformat();row.until=body.until.isoformat() if body.until else None;row.frequency=body.frequency;row.interval=body.interval;row.auto_fx=body.auto_fx
    row.enabled=False;row.error='review_required' if row.kind=='recurring' else '';row.version+=1
    for job in db.scalars(select(ExpenseJob).where(ExpenseJob.plan_id==pid,ExpenseJob.expense_id.is_(None))):
        if changed:job.status='cancelled'
        elif job.status not in ('skipped','cancelled'):job.status='paused'
    if changed:row.cursor=0
    g.metadata_version+=1;db.commit();return plan_out(db,row,actor)


@router.put('/{gid}/plans/{pid}/state')
def switch(gid:str,pid:str,body:SwitchIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    g,actor,row=locked(db,gid,pid,user)
    if row.version!=if_match:raise HTTPException(409,'Modello modificato: ricarica')
    if row.kind!='recurring':raise HTTPException(422,'Non è una ricorrenza')
    if row.owner_id!=user.id and (body.enabled or actor.role not in ('owner','admin')):raise HTTPException(403,'Solo l’autore può riattivare la ricorrenza')
    if body.enabled:
        if row.currency!=g.currency:raise HTTPException(409,'Valuta del gruppo cambiata: modifica e ricontrolla il modello')
        if row.participant_id!=actor.id:raise HTTPException(409,'Autorizzazione cambiata: crea un nuovo modello')
        validate(db,g,actor,ExpenseIn.model_validate(row.draft),row.auto_fx)
        if not body.catch_up:
            while next_date(row) and next_date(row)<today():row.cursor+=1
    for job in db.scalars(select(ExpenseJob).where(ExpenseJob.plan_id==pid,ExpenseJob.expense_id.is_(None),ExpenseJob.status!='cancelled')):
        job.status='pending' if body.enabled and (body.catch_up or job.date>=today().isoformat()) and (not row.until or job.date<=row.until) and job.date>=row.start else 'skipped' if body.enabled else 'paused'
        job.attempts=0;job.next_attempt=0;job.error=''
    row.enabled=body.enabled;row.error='';row.version+=1;g.metadata_version+=1;db.commit();return plan_out(db,row,actor)


@router.delete('/{gid}/plans/{pid}')
def delete_plan(gid:str,pid:str,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    g,actor,row=locked(db,gid,pid,user)
    if row.owner_id!=user.id and actor.role not in ('owner','admin'):raise HTTPException(403,'Operazione non consentita')
    if row.version!=if_match:raise HTTPException(409,'Modello modificato: ricarica')
    # Keep completed expenses and their own immutable history.
    for job in db.scalars(select(ExpenseJob).where(ExpenseJob.plan_id==pid)):db.delete(job)
    db.delete(row);g.metadata_version+=1;db.commit();return {'deleted':True}


@router.get('/{gid}/expenses/{eid}/duplicate')
def duplicate(gid:str,eid:str,user=Depends(current),db=Depends(get_db)):
    from .editing import expense_draft
    g,actor=membership(db,gid,user,write=True)
    result=expense_draft(gid,eid,user,db)
    draft=deepcopy(result['draft']);draft['date']=today().isoformat();draft['exchange_token']=None
    active=set(db.scalars(select(Participant.id).where(Participant.group_id==gid,Participant.active.is_(True),Participant.merged_into.is_(None))))
    if draft['audience'] is not None:draft['audience']=[p for p in draft['audience'] if p in active]
    draft['payers']={p:v for p,v in draft.get('payers',{}).items() if p in active}
    for item in draft['items']:
        item['shares']={p:v for p,v in item['shares'].items() if p in active}
        if item.get('payers') is not None:item['payers']={p:v for p,v in item['payers'].items() if p in active}
    if draft.get('allocation_order') is not None:draft['allocation_order']=[p for p in draft['allocation_order'] if p in references(draft)]
    return draft


@router.get('/{gid}/tags')
def tags(gid:str,user=Depends(current),db=Depends(get_db)):
    _,actor=membership(db,gid,user);result=set()
    for e in db.scalars(select(Expense).where(Expense.group_id==gid,Expense.deleted.is_(False))):
        if visible(e,actor):result.update(db.get(ExpenseRevision,(e.id,e.version)).snapshot.get('tags',[]))
    return sorted(result,key=str.casefold)


def run_plan(db,pid):
    """One group lock serializes workers, edits, deletion, settlement and scheduling."""
    row=db.get(ExpensePlan,pid)
    if not row:return
    db.scalar(select(Group).where(Group.id==row.group_id).with_for_update())
    user=db.scalar(select(User).where(User.id==row.owner_id).with_for_update().execution_options(populate_existing=True))
    row=db.scalar(select(ExpensePlan).where(ExpensePlan.id==pid).with_for_update().execution_options(populate_existing=True))
    if not row or not row.enabled:return
    try:
        if not user or user.status!='active':raise ValueError()
        g,actor=membership(db,row.group_id,user,write=True)
        if g.currency!=row.currency or actor.id!=row.participant_id:raise ValueError()
        validate(db,g,actor,ExpenseIn.model_validate(row.draft),row.auto_fx)
    except (HTTPException,ValueError):
        row.enabled=False;row.error='authorization_changed';db.commit();return
    for _ in range(10):
        due=next_date(row)
        if not due or due>today() or (row.until and due.isoformat()>row.until):break
        job=db.scalar(select(ExpenseJob).where(ExpenseJob.plan_id==pid,ExpenseJob.date==due.isoformat()))
        if not job:
            job=ExpenseJob(plan_id=pid,date=due.isoformat(),audience=row.audience);db.add(job);db.flush()
        elif job.status=='cancelled':
            job.status='pending';job.attempts=0;job.next_attempt=0
        row.cursor+=1
    db.flush()
    jobs=list(db.scalars(select(ExpenseJob).where(ExpenseJob.plan_id==pid,ExpenseJob.status.in_(['pending','retry']),ExpenseJob.date>=row.start,ExpenseJob.date<=min(today().isoformat(),row.until or today().isoformat()),ExpenseJob.next_attempt<=int(time.time())).order_by(ExpenseJob.date).limit(10)))
    for job in jobs:
        try:
            with db.begin_nested():
                draft=deepcopy(row.draft);draft['date']=job.date
                if row.auto_fx and draft.get('currency') and draft['currency']!=g.currency:
                    from .exchange import exchange_rate
                    draft['exchange_token']=exchange_rate(draft['currency'],g.currency,user)['token'];draft['exchange_rate']=None
                body=ExpenseIn.model_validate(draft)
                result=record_expense(g.id,body,'recurrence:'+pid+':'+job.date,user,db,commit=False)
                job.expense_id=result['id'];job.status='done';job.error='';db.flush()
        except HTTPException as exc:
            job.attempts+=1
            if exc.status_code==503:
                job.error='exchange_unavailable';job.status='retry';job.next_attempt=int(time.time())+min(3600,30*2**job.attempts)
            else:job.error='review_required';job.status='blocked'
            if job.attempts>=8 or job.status=='blocked':row.enabled=False;row.error=job.error;break
        except (ValueError,InvalidOperation):
            job.status='blocked';job.error='review_required';row.enabled=False;row.error=job.error;break
    db.commit()


def tick():
    with SessionLocal() as db:ids=list(db.scalars(select(ExpensePlan.id).where(ExpensePlan.kind=='recurring',ExpensePlan.enabled.is_(True))))
    for pid in ids:
        try:
            with SessionLocal() as db:run_plan(db,pid)
        except Exception:
            # Transaction rollback leaves pending jobs safe for the next iteration.
            print('Ricorrenza temporaneamente non elaborata',flush=True)


if __name__=='__main__':
    from . import notifications  # register transactional listeners before recurring mutations
    while True:
        tick()
        from .reveals import tick as reveal_tick
        reveal_tick()
        from .notifications import tick as notification_tick
        notification_tick()
        from .operations import heartbeat
        heartbeat('worker');time.sleep(30)
