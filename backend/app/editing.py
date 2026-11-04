from decimal import Decimal
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field, field_validator
from sqlalchemy import select, delete, update
from sqlalchemy.exc import IntegrityError
from .schemas import Strict, Credentials
from .db import get_db
from .models import Category, Participant, User, Session, Expense, ExpenseRevision, Entry, Group
from .groups import membership, visible
from .security import current, admin, recent, audit

router = APIRouter(prefix='/api/v1', tags=['Modifiche e categorie'])
DEFAULT_CATEGORIES = ['Altro', 'Cibo e bevande', 'Viaggi', 'Casa', 'Spesa', 'Regali', 'Tempo libero']


class CategoryIn(Strict):
    name: str = Field(min_length=1, max_length=60)

    @field_validator('name')
    @classmethod
    def clean(cls, value):
        value = ' '.join(value.split())
        if not value:
            raise ValueError('Nome obbligatorio')
        return value


class PersonUpdate(Strict):
    name: str = Field(min_length=1, max_length=100)
    role: Literal['owner', 'admin', 'member', 'viewer']


class UserUpdate(Strict):
    name: str = Field(min_length=1, max_length=100)
    email: str = Field(min_length=3, max_length=254)
    status: Literal['active', 'pending', 'suspended']

    @field_validator('email')
    @classmethod
    def email_valid(cls, value):
        return Credentials.email_valid(value)


@router.get('/groups/{group_id}/categories')
def categories(group_id: str, user=Depends(current), db=Depends(get_db)):
    membership(db, group_id, user)
    # Do not discover category names from secret expenses.
    custom = list(db.scalars(select(Category.name).where(Category.group_id == group_id).order_by(Category.name)))
    return list(dict.fromkeys(DEFAULT_CATEGORIES + custom))


@router.post('/groups/{group_id}/categories', status_code=201)
def create_category(group_id: str, body: CategoryIn, user=Depends(current), db=Depends(get_db)):
    membership(db, group_id, user, write=True)
    key = body.name.casefold()
    if key in {c.casefold() for c in DEFAULT_CATEGORIES}:
        raise HTTPException(409, 'Questa categoria esiste già')
    row = Category(group_id=group_id, name=body.name, name_key=key)
    db.add(row)
    try:
        db.flush()
        audit(db, user.id, 'category.created', row.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Questa categoria esiste già') from None
    return {'id': row.id, 'name': row.name}


@router.put('/groups/{group_id}/participants/{participant_id}')
def edit_person(group_id: str, participant_id: str, body: PersonUpdate, user=Depends(current), db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    _, actor = membership(db, group_id, user, write=True)
    person = db.scalar(select(Participant).where(Participant.id == participant_id, Participant.group_id == group_id).with_for_update())
    if not person or not person.active or person.merged_into:
        raise HTTPException(404, 'Partecipante non trovato')
    manager = actor.role in ('owner', 'admin')
    if not manager and person.user_id != user.id:
        raise HTTPException(403, 'Puoi modificare solo il tuo nome nel gruppo')
    if not body.name.strip():
        raise HTTPException(422, 'Nome obbligatorio')
    if body.role != person.role:
        if not manager or body.role == 'owner' or person.role == 'owner':
            raise HTTPException(403, 'Ruolo non modificabile: la proprietà richiede un trasferimento dedicato')
        if actor.id == person.id:
            raise HTTPException(403, 'Non puoi modificare il tuo ruolo da questa schermata')
    person.name, person.role = body.name.strip(), body.role
    audit(db, user.id, 'participant.updated', person.id)
    db.commit()
    return {'id': person.id, 'name': person.name, 'role': person.role, 'virtual': person.user_id is None}


@router.put('/admin/users/{user_id}')
def edit_user(user_id: str, body: UserUpdate, request: Request, user=Depends(admin), db=Depends(get_db)):
    from .global_roles import locked_admin
    user,person=locked_admin(db,request,user,user_id)
    from .superadmin import is_superadmin
    if person.admin and not is_superadmin(db,user.id) and person.id!=user.id:raise HTTPException(403,'Solo un superadmin può modificare altri amministratori')
    if person.requested_role!='user' and not is_superadmin(db,user.id):raise HTTPException(403,'Richiesta con ruolo riservata ai superadmin')
    if is_superadmin(db,person.id):
        if person.id!=user.id:raise HTTPException(403,'Solo il superadmin può modificare il proprio account')
        if body.status!='active' or body.email!=person.email:raise HTTPException(403,'Superadmin protetto: cambia la tua email dalle impostazioni personali con password e MFA')
    if not body.name.strip():
        raise HTTPException(422, 'Nome obbligatorio')
    if person.admin and person.status != body.status:
        raise HTTPException(403, 'Lo stato degli amministratori non può essere cambiato da questa schermata')
    email_changed = person.email != body.email
    person.name, person.email, person.status = body.name.strip(), body.email, body.status
    if email_changed:
        person.email_verified=False
        from .models import AccountToken
        with db.no_autoflush:db.execute(update(AccountToken).where(AccountToken.user_id==person.id).values(used=True))
    if email_changed or body.status != 'active':
        # Keep the current administrator session only when editing their own email.
        condition = [Session.user_id == person.id]
        if person.id == user.id and body.status == 'active':
            condition.append(Session.token_hash != request.state.session.token_hash)
        with db.no_autoflush:
            db.execute(delete(Session).where(*condition))
    try:
        audit(db, user.id, 'user.updated', person.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Email già associata a un altro account') from None
    return {'id': person.id, 'name': person.name, 'email': person.email, 'status': person.status, 'admin': person.admin,'superadmin':is_superadmin(db,person.id)}


@router.get('/groups/{group_id}/expenses/{expense_id}')
def expense_draft(group_id: str, expense_id: str, user=Depends(current), db=Depends(get_db)):
    _, actor = membership(db, group_id, user)
    expense = db.get(Expense, expense_id)
    if not expense or expense.deleted or expense.group_id != group_id or not visible(expense, actor):
        raise HTTPException(404, 'Spesa non trovata')
    revision = db.get(ExpenseRevision, (expense.id, expense.version))
    draft = dict(revision.snapshot)
    draft.pop('deleted',None)
    # Legacy expenses have only an aggregate payer distribution. Allocate those
    # advances to item rows without changing ANY person's paid total.
    if not all(i.get('payers') is not None for i in draft['items']):
        available = {e.participant_id: e.paid for e in db.scalars(select(Entry).where(Entry.expense_id == expense.id, Entry.revision == expense.version)) if e.paid > 0}
        if draft.get('currency') and draft['currency']!=db.get(Group,group_id).currency:
            from .money import minor
            available={k:minor(v) for k,v in draft['payers'].items()}
        new_items = []
        for original, resolved in zip(draft['items'], expense.items):
            from .money import minor
            left = minor(original['amount'])
            paid = {}
            for person in sorted(available):
                amount = min(left, available[person])
                if amount:
                    paid[person] = format(Decimal(amount) / 100, '.2f')
                    available[person] -= amount
                    left -= amount
            if left:
                raise HTTPException(409, 'La spesa richiede una riconciliazione prima della modifica')
            new_items.append({**original, 'payers': paid})
        draft['items'] = new_items
    draft['payers'] = {}
    return {'id': expense.id, 'version': expense.version, 'draft': draft}
