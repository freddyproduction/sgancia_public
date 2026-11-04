"""Resource-scoped history: never return installation-wide audit events."""
import time
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Header
from pydantic import Field
from sqlalchemy import select
from .db import get_db
from .schemas import Strict
from .security import current
from .models import Group,Expense,ExpenseRevision,ExpenseDispute,Settlement,SettlementEvent,User,Participant,Entry,CurrencyChange
from .groups import membership,visible
router=APIRouter(prefix='/api/v1/groups',tags=['Cronologia e contestazioni'])


def expense_access(db,gid,eid,user,write=False):
    group,actor=membership(db,gid,user)
    if write and (actor.role=='viewer' or group.state=='archived'):raise HTTPException(403,'Operazione non consentita')
    row=db.get(Expense,eid)
    if not row or row.group_id!=gid or not visible(row,actor):raise HTTPException(404,'Spesa non trovata')
    return group,actor,row


def actor_name(db,uid):
    person=db.get(User,uid)
    return person.name if person else 'Account non disponibile'


@router.get('/{gid}/expenses/{eid}/history')
def expense_history(gid:str,eid:str,user=Depends(current),db=Depends(get_db)):
    group,actor,row=expense_access(db,gid,eid,user)
    changes=list(db.scalars(select(CurrencyChange).where(CurrencyChange.group_id==gid).order_by(CurrencyChange.created)))
    versions=[];previous={}
    for revision in db.scalars(select(ExpenseRevision).where(ExpenseRevision.expense_id==eid).order_by(ExpenseRevision.version)):
        snapshot=revision.snapshot
        # A revealed expense does not expose its older private snapshots to new readers.
        if snapshot.get('audience') is not None and actor.id not in snapshot['audience']:continue
        currency=snapshot.get('currency') or next((change.snapshot['quote']['base'] for change in changes if any(v['id']==eid and revision.version<=v['before'] for v in change.snapshot['expense_versions'])),group.currency)
        changed=[key for key in set(previous)|set(snapshot) if previous.get(key)!=snapshot.get(key)]
        conversion=None
        if snapshot.get('exchange_token'):
            from .exchange import read_quote
            target=next((c.snapshot['quote']['base'] for c in changes if any(v['id']==eid and revision.version<=v['before'] for v in c.snapshot['expense_versions'])),group.currency)
            try:conversion=read_quote(snapshot['exchange_token'],snapshot.get('currency'),target,stored=True)
            except ValueError:conversion=None
        elif snapshot.get('exchange_rate'):
            context=snapshot.get('exchange_context')
            conversion={**context,'source':'Importato (tasso dichiarato): '+context['source']} if context and context.get('rate')==snapshot['exchange_rate'] and context.get('base')==snapshot.get('currency') and context.get('quote')==next((c.snapshot['quote']['base'] for c in changes if any(v['id']==eid and revision.version<=v['before'] for v in c.snapshot['expense_versions'])),group.currency) else {'rate':snapshot['exchange_rate'],'source':'Manuale','date':snapshot['date']}
        versions.append({'conversion':conversion,'version':revision.version,'created':revision.created,'actor':actor_name(db,revision.actor_id),'currency':currency,'snapshot':snapshot,'changed':sorted(changed)})
        previous=snapshot
    disputes=[]
    for d in db.scalars(select(ExpenseDispute).where(ExpenseDispute.expense_id==eid).order_by(ExpenseDispute.created,ExpenseDispute.id)):
        revision=db.get(ExpenseRevision,(eid,d.version))
        if revision.snapshot.get('audience') is not None and actor.id not in revision.snapshot['audience']:continue
        disputes.append({'id':d.id,'participant':d.participant_id,'version':d.version,'reason':d.reason,'status':d.status,'resolution':d.resolution,'created':d.created,'resolved_at':d.resolved_at,'resolver':actor_name(db,d.resolver_id) if d.resolver_id else None,'can_resolve':actor.id!=d.participant_id and (actor.role in ('owner','admin') or row.author_id==user.id),'can_withdraw':actor.id==d.participant_id})
    entry=db.scalar(select(Entry).where(Entry.expense_id==eid,Entry.revision==row.version,Entry.participant_id==actor.id))
    return {'versions':versions,'disputes':disputes,'can_dispute':not any(d['status']=='open' and d['participant']==actor.id for d in disputes) and not row.deleted and bool(entry and (entry.paid or entry.owed)) and actor.role!='viewer' and group.state!='archived','version':row.version}


class ReasonIn(Strict):
    reason:str=Field(min_length=3,max_length=2000)


@router.post('/{gid}/expenses/{eid}/disputes',status_code=201)
def dispute(gid:str,eid:str,body:ReasonIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    group,actor,row=expense_access(db,gid,eid,user,True)
    if row.deleted or row.version!=if_match:raise HTTPException(409,'Spesa cambiata: aggiorna la cronologia')
    entry=db.scalar(select(Entry).where(Entry.expense_id==eid,Entry.revision==row.version,Entry.participant_id==actor.id))
    if not entry or not(entry.paid or entry.owed):raise HTTPException(403,'Puoi contestare soltanto una tua quota o un tuo anticipo')
    if len(body.reason.strip())<3:raise HTTPException(422,'Indica una motivazione')
    if db.scalar(select(ExpenseDispute).where(ExpenseDispute.expense_id==eid,ExpenseDispute.participant_id==actor.id,ExpenseDispute.status=='open')):raise HTTPException(409,'Hai già una contestazione aperta per questa spesa')
    d=ExpenseDispute(expense_id=eid,participant_id=actor.id,version=row.version,reason=body.reason.strip());db.add(d);db.commit()
    return {'id':d.id}


class ResolveIn(ReasonIn):
    status:Literal['resolved','rejected','withdrawn']


@router.put('/{gid}/expenses/{eid}/disputes/{did}')
def resolve(gid:str,eid:str,did:str,body:ResolveIn,user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    _,actor,row=expense_access(db,gid,eid,user,True)
    d=db.get(ExpenseDispute,did)
    if not d or d.expense_id!=eid:raise HTTPException(404,'Contestazione non trovata')
    rev=db.get(ExpenseRevision,(eid,d.version))
    if rev.snapshot.get('audience') is not None and actor.id not in rev.snapshot['audience']:raise HTTPException(404,'Contestazione non trovata')
    if body.status=='withdrawn':allowed=actor.id==d.participant_id
    else:allowed=actor.id!=d.participant_id and (actor.role in ('owner','admin') or row.author_id==user.id)
    if not allowed:raise HTTPException(403,'Non puoi risolvere questa contestazione')
    if d.status!='open':raise HTTPException(409,'Contestazione già conclusa')
    if len(body.reason.strip())<3:raise HTTPException(422,'Indica come è stata risolta')
    d.status=body.status;d.resolution=body.reason.strip();d.resolver_id=user.id;d.resolved_at=int(time.time());db.commit()
    return {'status':d.status}


@router.get('/{gid}/settlements/{sid}/history')
def settlement_history(gid:str,sid:str,user=Depends(current),db=Depends(get_db)):
    _,actor=membership(db,gid,user);row=db.get(Settlement,sid)
    if not row or row.group_id!=gid or not visible(row,actor):raise HTTPException(404,'Rimborso non trovato')
    events=[{'id':e.id,'actor':actor_name(db,e.actor_id),'status':e.status,'at':e.at,'reason':e.reason} for e in db.scalars(select(SettlementEvent).where(SettlementEvent.settlement_id==sid).order_by(SettlementEvent.at,SettlementEvent.ordinal,SettlementEvent.id))]
    conversions=[{'created':c.created,'quote':c.snapshot['quote'],'amount':v} for c in db.scalars(select(CurrencyChange).where(CurrencyChange.group_id==gid).order_by(CurrencyChange.created)) for v in c.snapshot['settlements'] if v['id']==sid]
    return {'events':events,'conversions':conversions}
