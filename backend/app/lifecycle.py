import time
from decimal import InvalidOperation
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Header
from pydantic import Field,field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .schemas import Strict,ExpenseIn,Credentials
from .db import get_db
from .models import Expense,ExpenseRevision,Entry,Participant,ParticipantClaim,Group,Settlement
from .security import current,digest,token,audit
from .groups import membership,visible,build_expense
from .expense_tools import expense_snapshot,reconcile_allocation_order

router=APIRouter(prefix='/api/v1',tags=['Cronologia e gestione gruppi'])


class StateIn(Strict):
    state:Literal['active','frozen','archived']


class ClaimIn(Strict):
    email:str=Field(min_length=3,max_length=254)
    @field_validator('email')
    @classmethod
    def valid_email(cls,value):return Credentials.email_valid(value)


class TokenIn(Strict):
    token:str=Field(min_length=20,max_length=100)


@router.put('/groups/{group_id}/state')
def state(group_id:str,body:StateIn,user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,actor=membership(db,group_id,user,manage=True)
    group.state=body.state;group.metadata_version+=1
    audit(db,user.id,'group.state_changed',group.id)
    db.commit()
    return {'state':group.state}


def editable(db,group_id,expense_id,user):
    group,actor=membership(db,group_id,user,write=True)
    row=db.scalar(select(Expense).where(Expense.id==expense_id,Expense.group_id==group_id).with_for_update())
    if not row or row.deleted or not visible(row,actor): raise HTTPException(404,'Spesa non trovata')
    return row,actor


@router.put('/groups/{group_id}/expenses/{expense_id}')
def edit(group_id:str,expense_id:str,body:ExpenseIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    return edit_expense(db,group_id,expense_id,body,if_match,user)


def edit_expense(db,group_id,expense_id,body,if_match,user,commit=True):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    row,actor=editable(db,group_id,expense_id,user)
    if row.version!=if_match: raise HTTPException(409,'La spesa è stata modificata: ricarica e confronta le versioni')
    if set(body.audience or [])!=set(row.audience or []) or (body.audience is None)!=(row.audience is None):
        raise HTTPException(422,'Per rivelare una spesa usa l’operazione dedicata; il pubblico non può essere cambiato durante una modifica')
    prior_snapshot=db.get(ExpenseRevision,(row.id,row.version)).snapshot
    try: data=build_expense(db,group_id,body,actor,stored_quote=bool(body.exchange_token and body.exchange_token==prior_snapshot.get('exchange_token')),existing_people=set(row.audience or [])|{e.participant_id for e in db.scalars(select(Entry).where(Entry.expense_id==row.id,Entry.revision==row.version))})
    except Exception as e:
        from decimal import InvalidOperation
        if isinstance(e,ValueError):
            raise HTTPException(422,str(e)) from None
        if isinstance(e,InvalidOperation):
            raise HTTPException(422,'Inserisci quote e percentuali come numeri validi') from None
        raise
    row.version+=1
    row.title=body.title.strip();row.description=body.description;row.category=body.category;row.date=body.date.isoformat()
    row.total=data['total'];row.items=data['items']
    for p in set(data['paid'])|set(data['owed']):
        db.add(Entry(group_id=group_id,expense_id=row.id,participant_id=p,revision=row.version,paid=data['paid'].get(p,0),owed=data['owed'].get(p,0)))
    db.add(ExpenseRevision(expense_id=row.id,version=row.version,actor_id=user.id,snapshot=expense_snapshot(body)))
    audit(db,user.id,'expense.revised')
    if commit:db.commit()
    else:db.flush()
    return {'id':row.id,'version':row.version,'total':row.total}


@router.get('/groups/{group_id}/expenses/{expense_id}/versions')
def history(group_id:str,expense_id:str,user=Depends(current),db=Depends(get_db)):
    from .history import expense_history
    return expense_history(group_id,expense_id,user,db)['versions']


@router.post('/groups/{group_id}/expenses/{expense_id}/reveal')
def reveal(group_id:str,expense_id:str,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    from .reveals import simple_reveal
    return simple_reveal(group_id,expense_id,if_match,user,db)


@router.post('/groups/{group_id}/participants/{participant_id}/claim',status_code=201)
def issue_claim(group_id:str,participant_id:str,body:ClaimIn,user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    membership(db,group_id,user,write=True,manage=True)
    participant=db.get(Participant,participant_id)
    if not participant or participant.group_id!=group_id or participant.user_id or not participant.active or participant.merged_into:
        raise HTTPException(404,'Partecipante virtuale non disponibile')
    clear=token()
    from .membership_ops import revoke
    revoke(db,group_id,participant_id)
    db.add(ParticipantClaim(token_hash=digest(clear),participant_id=participant_id,email=body.email.strip().lower(),issuer_id=user.id,expires=int(time.time())+86400))
    audit(db,user.id,'participant.claim_issued',participant_id)
    db.commit()
    return {'token':clear,'expires_in':86400}


@router.post('/participants/claim')
def claim(body:TokenIn,user=Depends(current),db=Depends(get_db)):
    from .account_security import live_group_user
    user=live_group_user(db,user)
    initial=db.get(ParticipantClaim,digest(body.token))
    if not initial:raise HTTPException(404,'Associazione non disponibile')
    initial_person=db.get(Participant,initial.participant_id)
    db.scalar(select(Group).where(Group.id==initial_person.group_id).with_for_update())
    invitation=db.scalar(select(ParticipantClaim).where(ParticipantClaim.token_hash==digest(body.token)).with_for_update().execution_options(populate_existing=True))
    if not invitation or invitation.used or invitation.expires<=time.time() or invitation.email!=user.email:
        raise HTTPException(404,'Associazione non disponibile')
    person=db.scalar(select(Participant).where(Participant.id==invitation.participant_id).with_for_update())
    group=db.get(Group,person.group_id)
    from .group_access import issuer_valid
    if not issuer_valid(db,invitation.issuer_id,group.id):raise HTTPException(404,'Associazione revocata')
    if person.user_id or not person.active or person.merged_into or group.deleted or group.state!='active': raise HTTPException(409,'Partecipante o gruppo non disponibile')
    existing=db.scalar(select(Participant).where(Participant.group_id==person.group_id,Participant.user_id==user.id))
    if existing: raise HTTPException(409,'Hai già un partecipante nel gruppo: è necessaria una fusione controllata')
    from .membership_ops import revoke
    revoke(db,group.id,person.id)
    person.user_id=user.id;invitation.used=True;group.metadata_version+=1
    audit(db,user.id,'participant.claimed',person.id)
    try: db.commit()
    except IntegrityError:
        db.rollback();raise HTTPException(409,'Associazione concorrente: ricarica il gruppo') from None
    return {'group_id':person.group_id,'participant_id':person.id}


@router.post('/groups/{group_id}/expenses/{expense_id}/preview')
def edit_preview(group_id:str,expense_id:str,body:ExpenseIn,user=Depends(current),db=Depends(get_db)):
    row,actor=editable(db,group_id,expense_id,user)
    existing=set(row.audience or [])|{e.participant_id for e in db.scalars(select(Entry).where(Entry.expense_id==row.id,Entry.revision==row.version))}
    prior=db.get(ExpenseRevision,(row.id,row.version)).snapshot
    try:
        return build_expense(db,group_id,body,actor,stored_quote=bool(body.exchange_token and body.exchange_token==prior.get('exchange_token')),existing_people=existing)
    except (ValueError,InvalidOperation) as error:raise HTTPException(422,str(error) or 'Quote non valide') from None
