import json
from fastapi import APIRouter,Depends,HTTPException,Header
from sqlalchemy import select
from typing import Literal
from pydantic import Field
from .schemas import Strict
from .models import Settlement,SettlementEvent,Participant,Group,Idempotency
from .security import current,digest
from .db import get_db
from .groups import membership,visible
from .money import minor
from .membership_ops import delegated

router=APIRouter(prefix='/api/v1/groups',tags=['Rimborsi'])


class PaymentIn(Strict):
    kind:Literal['reimbursement','advance']='reimbursement'
    note:str=Field(default='',max_length=2000)
    sender:str
    recipient:str
    amount:str=Field(min_length=1,max_length=300)
    audience:list[str]|None=Field(default=None,min_length=1,max_length=200)


class Transition(Strict):
    status:Literal['confirmed','disputed','cancelled']
    reason:str=Field(default='',max_length=2000)


def output(s):
    return {'kind':s.kind,'note':s.note,'id':s.id,'sender':s.sender,'recipient':s.recipient,'amount':s.amount,'status':s.status,'private':s.audience is not None,'audience':s.audience,'created':s.created}


@router.get('/{group_id}/settlements')
def payments(group_id:str,user=Depends(current),db=Depends(get_db)):
    _,actor=membership(db,group_id,user)
    return [output(s) for s in db.scalars(select(Settlement).where(Settlement.group_id==group_id).order_by(Settlement.created.desc())) if visible(s,actor)]


@router.post('/{group_id}/settlements',status_code=201)
def create(group_id:str,body:PaymentIn,idempotency_key:str=Header(min_length=8,max_length=150),user=Depends(current),db=Depends(get_db)):
    return create_payment(db,group_id,body,idempotency_key,user)


def create_payment(db,group_id,body,idempotency_key,user,commit=True):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,actor=membership(db,group_id,user)
    if group.state=='archived' or actor.role=='viewer':
        raise HTTPException(403,'Rimborso non consentito')
    if body.kind=='advance' and group.state!='active':raise HTTPException(409,'Gli anticipi richiedono un gruppo attivo')
    key='pay:'+group_id+':'+idempotency_key
    body_hash=digest(json.dumps({'body':body.model_dump(),'currency':group.currency},sort_keys=True))
    prior=db.get(Idempotency,(key,user.id))
    if prior:
        if prior.request_hash!=body_hash: raise HTTPException(409,'Chiave già usata per dati differenti')
        return prior.response
    if body.sender!=actor.id and not delegated(db,group_id,actor,body.sender,'pay'):
        raise HTTPException(403,'Per pagare per un virtuale serve una delega esplicita al pagamento')
    people=set(db.scalars(select(Participant.id).where(Participant.group_id==group_id,Participant.merged_into.is_(None))))
    if body.kind=='advance':
        people=set(db.scalars(select(Participant.id).where(Participant.group_id==group_id,Participant.active.is_(True),Participant.merged_into.is_(None))))
    audience=sorted(set(body.audience)) if body.audience is not None else None
    allowed=set(audience) if audience is not None else people
    if actor.id not in allowed: raise HTTPException(422,'Devi essere incluso nel pubblico del rimborso')
    if not allowed<=people or body.sender not in allowed or body.recipient not in allowed or body.sender==body.recipient:
        raise HTTPException(422,'Partecipanti o pubblico non validi')
    try:
        value=minor(body.amount)
        if value<=0: raise ValueError()
    except ValueError:
        raise HTTPException(422,'Importo non valido') from None
    settlement=Settlement(kind=body.kind,note=body.note.strip(),group_id=group_id,sender=body.sender,recipient=body.recipient,amount=value,audience=audience,author_id=user.id)
    db.add(settlement)
    db.flush()
    db.add(SettlementEvent(settlement_id=settlement.id,actor_id=user.id,status='pending'))
    result=output(settlement)
    db.add(Idempotency(key=key,user_id=user.id,request_hash=body_hash,response=result))
    if commit:db.commit()
    else:db.flush()
    return result


@router.put('/{group_id}/settlements/{settlement_id}')
def transition(group_id:str,settlement_id:str,body:Transition,user=Depends(current),db=Depends(get_db)):
    return transition_payment(db,group_id,settlement_id,body,user)


def transition_payment(db,group_id,settlement_id,body,user,commit=True):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,actor=membership(db,group_id,user)
    row=db.scalar(select(Settlement).where(Settlement.id==settlement_id,Settlement.group_id==group_id).with_for_update())
    if not row or not visible(row,actor): raise HTTPException(404,'Rimborso non trovato')
    if group.state=='archived' or actor.role=='viewer': raise HTTPException(403,'Operazione non consentita')
    recipient=db.get(Participant,row.recipient)
    recipient_allowed=row.recipient==actor.id or (recipient.user_id is None and (actor.role in ('owner','admin') or delegated(db,group_id,actor,row.recipient,'attest')))
    if body.status in ('confirmed','disputed') and not recipient_allowed:
        raise HTTPException(403,'È richiesta la conferma del ricevente')
    if body.status=='cancelled' and actor.id not in (row.sender,row.recipient) and not recipient_allowed and not delegated(db,group_id,actor,row.sender,'pay'):
        raise HTTPException(403,'Operazione non consentita')
    if row.status==body.status: return output(row)
    if row.status!='pending' and not(row.status=='disputed' and body.status in ('cancelled','confirmed')):
        raise HTTPException(409,'Transizione non consentita: il rimborso è già concluso')
    if (body.status=='disputed' or row.status=='disputed') and len(body.reason.strip())<3:raise HTTPException(422,'Indica la motivazione della contestazione o della risoluzione')
    row.status=body.status
    db.add(SettlementEvent(settlement_id=row.id,actor_id=user.id,status=row.status,reason=body.reason.strip()))
    if commit:db.commit()
    else:db.flush()
    return output(row)


@router.post('/{group_id}/settlements/settle-suggestion')
def settle_suggestion(group_id:str,body:PaymentIn,idempotency_key:str=Header(min_length=8,max_length=150),user=Depends(current),db=Depends(get_db)):
    return record_suggestion(db,group_id,body,idempotency_key,user)


def record_suggestion(db,group_id,body,idempotency_key,user,commit=True):
    if body.kind!='reimbursement':raise HTTPException(422,'Per un anticipo usa Registra pagamento effettuato')
    from .groups import balances
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,actor=membership(db,group_id,user)
    if group.state=='archived' or actor.role=='viewer':
        raise HTTPException(403,'Non puoi registrare pagamenti in questo gruppo')
    manager=actor.role in ('owner','admin')
    if not manager and actor.id != body.recipient and not delegated(db,group_id,actor,body.recipient,'attest'):
        raise HTTPException(403,'Solo le persone coinvolte o gli amministratori possono registrare questo saldo')
    audience=sorted(set(body.audience)) if body.audience is not None else None
    people={p.id:p for p in db.scalars(select(Participant).where(Participant.group_id==group_id))}
    allowed=set(audience) if audience is not None else set(people)
    if not allowed<=set(people) or actor.id not in allowed or body.sender not in allowed or body.recipient not in allowed:
        raise HTTPException(404,'Saldo non disponibile')
    key='done:'+group_id+':'+idempotency_key
    body_hash=digest(json.dumps({'body':body.model_dump(),'currency':group.currency},sort_keys=True))
    prior=db.get(Idempotency,(key,user.id))
    if prior:
        if prior.request_hash!=body_hash:raise HTTPException(409,'Chiave già usata per altri dati')
        return prior.response
    try:value=minor(body.amount)
    except ValueError as error:raise HTTPException(422,str(error)) from None
    same_scope=lambda value:set(value or [])==set(audience or []) and (value is None)==(audience is None)
    scope=next((s for s in balances(group_id,user,db) if same_scope(s['audience'])),None)
    if not scope or not any(s['from']==body.sender and s['to']==body.recipient and s['amount']==value for s in scope['suggestions']):
        raise HTTPException(409,'Il saldo è cambiato: aggiorna il gruppo prima di segnarlo come saldato')
    recipient=people[body.recipient]
    # Registered recipients confirm themselves. Group managers can attest for
    # virtual recipients; the acting account is always retained in the events.
    may_confirm=recipient.user_id==user.id or (recipient.user_id is None and (manager or delegated(db,group_id,actor,recipient.id,'attest')))
    pending=[s for s in db.scalars(select(Settlement).where(Settlement.group_id==group_id,Settlement.sender==body.sender,Settlement.recipient==body.recipient,Settlement.amount==value,Settlement.status=='pending').with_for_update()) if same_scope(s.audience)]
    if pending:
        row=pending[0]
    else:
        row=Settlement(group_id=group_id,sender=body.sender,recipient=body.recipient,amount=value,audience=audience,author_id=user.id)
        db.add(row);db.flush()
        db.add(SettlementEvent(settlement_id=row.id,actor_id=user.id,status='pending'))
    if may_confirm:
        row.status='confirmed'
        db.add(SettlementEvent(settlement_id=row.id,actor_id=user.id,status='confirmed'))
    result=output(row)
    db.add(Idempotency(key=key,user_id=user.id,request_hash=body_hash,response=result))
    if commit:db.commit()
    else:db.flush()
    return result


class TransferComponent(Strict):
    audience:list[str]|None=Field(default=None,min_length=1,max_length=200)
    amount:int=Field(ge=1,le=10**12)


class TransferIn(Strict):
    sender:str
    recipient:str
    components:list[TransferComponent]=Field(min_length=1,max_length=200)
    fingerprint:str=Field(min_length=64,max_length=64)


@router.post('/{group_id}/settlements/settle-transfer')
def settle_transfer(group_id:str,body:TransferIn,idempotency_key:str=Header(min_length=8,max_length=150),user=Depends(current),db=Depends(get_db)):
    return record_transfer(db,group_id,body,idempotency_key,user)


def record_transfer(db,group_id,body,idempotency_key,user,commit=True):
    from .finance import finance_view,transfer_fingerprint
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,actor=membership(db,group_id,user)
    if actor.role=='viewer' or group.state=='archived':raise HTTPException(403,'Pagamento non consentito')
    manager=actor.role in ('owner','admin')
    if not manager and actor.id != body.recipient and not delegated(db,group_id,actor,body.recipient,'attest'):raise HTTPException(403,'Solo il ricevente può segnare questo pagamento come saldato')
    key='batch:'+group_id+':'+idempotency_key
    request_hash=digest(json.dumps({'body':body.model_dump(),'currency':group.currency},sort_keys=True))
    prior=db.get(Idempotency,(key,user.id))
    if prior:
        if prior.request_hash!=request_hash:raise HTTPException(409,'Chiave già usata per dati diversi')
        if any(db.get(Settlement,sid).status!=prior.response['status'] for sid in prior.response['ids']):raise HTTPException(409,'Il rimborso è stato ripristinato: aggiorna e riprova')
        return prior.response
    components=[c.model_dump() for c in body.components]
    transfer=next((row for row in finance_view(db,group_id,user)['transfers'] if row['from']==body.sender and row['to']==body.recipient),None)
    if not transfer or body.fingerprint!=transfer['fingerprint'] or transfer_fingerprint(components,group.currency)!=transfer['fingerprint']:
        raise HTTPException(409,'Gli importi sono cambiati: aggiorna il gruppo e riprova')
    recipient=db.get(Participant,body.recipient)
    may_confirm=recipient.user_id==user.id or (recipient.user_id is None and (manager or delegated(db,group_id,actor,recipient.id,'attest')))
    recorded=[]
    for component in components:
        audience=sorted(component['audience']) if component['audience'] is not None else None
        same_scope=lambda value:(value is None)==(audience is None) and set(value or [])==set(audience or [])
        pending=[s for s in db.scalars(select(Settlement).where(Settlement.group_id==group_id,Settlement.sender==body.sender,Settlement.recipient==body.recipient,Settlement.status=='pending').with_for_update()) if same_scope(s.audience)]
        remaining=component['amount']-sum(s.amount for s in pending)
        if remaining<0:raise HTTPException(409,'I pagamenti in attesa superano il saldo: controlla la cronologia dei rimborsi')
        if remaining:
            row=Settlement(group_id=group_id,sender=body.sender,recipient=body.recipient,author_id=user.id,amount=remaining,audience=audience)
            db.add(row);db.flush()
            db.add(SettlementEvent(settlement_id=row.id,actor_id=user.id,status='pending'))
            pending.append(row)
        for row in pending:
            if may_confirm:
                row.status='confirmed'
                db.add(SettlementEvent(settlement_id=row.id,actor_id=user.id,status='confirmed'))
            recorded.append(row.id)
    result={'status':'confirmed' if may_confirm else 'pending','ids':recorded,'amount':transfer['amount']}
    db.add(Idempotency(key=key,user_id=user.id,request_hash=request_hash,response=result))
    if commit:db.commit()
    else:db.flush()
    return result


@router.post('/{group_id}/settlements/{settlement_id}/undo')
def undo_receipt(group_id:str,settlement_id:str,user=Depends(current),db=Depends(get_db)):
    return undo_payment(db,group_id,settlement_id,user)


def undo_payment(db,group_id,settlement_id,user,commit=True):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,actor=membership(db,group_id,user)
    row=db.scalar(select(Settlement).where(Settlement.group_id==group_id,Settlement.id==settlement_id).with_for_update())
    if not row or not visible(row,actor):raise HTTPException(404,'Rimborso non trovato')
    recipient=db.get(Participant,row.recipient)
    allowed=actor.id==row.recipient or (recipient.user_id is None and (actor.role in ('owner','admin') or delegated(db,group_id,actor,recipient.id,'attest')))
    if actor.role=='viewer' or group.state=='archived' or not allowed:raise HTTPException(403,'Solo il ricevente può ripristinare il debito; gli amministratori possono farlo per persone senza account')
    if row.status=='cancelled':return output(row)
    if row.status!='confirmed':raise HTTPException(409,'Puoi ripristinare soltanto un rimborso confermato')
    row.status='cancelled'
    db.add(SettlementEvent(settlement_id=row.id,actor_id=user.id,status='cancelled'))
    if commit:db.commit()
    else:db.flush()
    return output(row)
