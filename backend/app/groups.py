from collections import defaultdict
from decimal import Decimal, InvalidOperation
import hashlib
import json
from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from .db import get_db
from .models import Group, Participant, User, Expense, Entry, Idempotency, Settlement, ExpenseRevision
from .schemas import GroupIn, ParticipantIn, ExpenseIn, ExpressionIn
from .security import current, audit
from .money import allocate, minor, MAX_MINOR

from .expense_tools import expense_snapshot

router = APIRouter(prefix='/api/v1', tags=['Gruppi e spese'])


def membership(db, group_id, user, write=False, manage=False):
    participant = db.scalar(select(Participant).where(Participant.group_id == group_id, Participant.user_id == user.id))
    group = db.get(Group, group_id)
    if not participant or not participant.active or not group or group.deleted:
        raise HTTPException(404, 'Gruppo non trovato')
    if (write and participant.role == 'viewer') or (manage and participant.role not in ('owner', 'admin')):
        raise HTTPException(403, 'Operazione non consentita')
    if write and group.state != 'active':
        raise HTTPException(409, 'Gruppo non modificabile')
    return group, participant


def group_out(group):
    return {'id': group.id, 'name': group.name, 'currency': group.currency, 'state': group.state, 'description': group.description, 'icon': group.icon, 'metadata_version': group.metadata_version, 'smart_balances': group.smart_balances, 'image_url': f'/api/v1/groups/{group.id}/image?v={group.metadata_version}' if group.image else None}


def visible(expense, participant):
    return expense.audience is None or participant.id in expense.audience


@router.get('/groups')
def groups(user=Depends(current), db=Depends(get_db)):
    rows = db.scalars(select(Group).join(Participant, Participant.group_id == Group.id).where(Participant.user_id == user.id, Participant.active.is_(True), Group.deleted.is_(False)).order_by(Group.name))
    return [group_out(g) for g in rows]


@router.post('/groups', status_code=201)
def create_group(body: GroupIn, user=Depends(current), db=Depends(get_db)):
    if not body.name.strip():
        raise HTTPException(422, 'Nome obbligatorio')
    group = Group(name=body.name.strip(), currency=body.currency, owner_id=user.id)
    db.add(group)
    db.flush()
    db.add(Participant(group_id=group.id, name=user.name, user_id=user.id, role='owner'))
    audit(db, user.id, 'group.created', group.id)
    db.commit()
    return group_out(group)


@router.get('/groups/{group_id}')
def group_detail(group_id: str, user=Depends(current), db=Depends(get_db)):
    group, participant = membership(db, group_id, user)
    rows=db.execute(select(Participant,User.avatar_icon,User.avatar_version,User.avatar.is_not(None)).outerjoin(User,(Participant.user_id==User.id)&(User.status=='active')).where(Participant.group_id==group_id).order_by(Participant.name))
    people=[]
    for p,icon,version,has_image in rows:
        profile=p.active and not p.merged_into
        people.append({'id':p.id,'name':p.name,'virtual':p.user_id is None,'role':p.role,'active':p.active,'merged_into':p.merged_into,'avatar_icon':icon if profile else None,'avatar_url':f'/api/v1/groups/{group_id}/participants/{p.id}/avatar?v={version}' if profile and has_image else None})
    return {**group_out(group),'my_participant':participant.id,'role':participant.role,'participants':people}


@router.get('/groups/{group_id}/participants/{participant_id}/avatar')
def participant_avatar(group_id:str,participant_id:str,user=Depends(current),db=Depends(get_db)):
    from fastapi import Response
    membership(db,group_id,user)
    person=db.get(Participant,participant_id)
    if not person or person.group_id!=group_id or not person.active or person.merged_into or not person.user_id:raise HTTPException(404,'Immagine non disponibile')
    account=db.get(User,person.user_id)
    if not account or account.status!='active' or not account.avatar:raise HTTPException(404,'Immagine non disponibile')
    return Response(content=account.avatar,media_type='image/webp',headers={'Cache-Control':'private, no-store'})


@router.post('/groups/{group_id}/participants', status_code=201)
def add_participant(group_id: str, body: ParticipantIn, user=Depends(current), db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    membership(db, group_id, user, write=True, manage=True)
    if not body.name.strip():
        raise HTTPException(422, 'Nome obbligatorio')
    target = None
    if body.email:
        target = db.scalar(select(User).where(User.email == body.email.strip().lower(), User.status == 'active'))
        if not target:
            raise HTTPException(400, 'Account non disponibile')
    p = Participant(group_id=group_id, name=body.name.strip(), user_id=target.id if target else None, role=body.role)
    db.add(p)
    try:
        db.flush()
        audit(db, user.id, 'participant.created', p.id)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, 'Account già presente nel gruppo') from None
    return {'id': p.id, 'name': p.name, 'virtual': p.user_id is None, 'role': p.role}


def build_expense(db, group_id, body, actor, stored_quote=False, existing_people=None):
    from .exchange import expense_rate,rounded
    group=db.get(Group,group_id)
    rate,conversion=expense_rate(body,group.currency,stored_quote)
    if not body.title.strip():
        raise ValueError('Titolo obbligatorio')
    people = set(db.scalars(select(Participant.id).where(Participant.group_id == group_id,Participant.active.is_(True),Participant.merged_into.is_(None)))) | set(existing_people or [])
    audience = sorted(set(body.audience)) if body.audience is not None else None
    if audience is not None and (not set(audience) <= people or actor.id not in audience):
        raise ValueError('Il pubblico deve appartenere al gruppo e includere l’autore')
    allowed = set(audience) if audience is not None else people
    refs=set(body.payers)|set(audience or [])
    for item in body.items:refs.update(item.shares);refs.update(item.payers or {})
    if body.allocation_order is not None and (len(body.allocation_order)!=len(set(body.allocation_order)) or set(body.allocation_order)!=refs):raise ValueError('Ordine di arrotondamento non coerente con i partecipanti')
    per_item = any(item.payers is not None for item in body.items)
    if per_item and (body.payers or any(item.payers is None for item in body.items)):
        raise ValueError('Specifica i pagatori per ogni voce, senza duplicarli a livello della spesa')
    paid = defaultdict(int) if per_item else {key: minor(value) for key, value in body.payers.items()}
    if not per_item and (not paid or not set(paid) <= allowed or any(value <= 0 for value in paid.values())):
        raise ValueError('Scegli almeno un pagatore incluso nel pubblico e indica quanto ha pagato')
    owed = defaultdict(int)
    items = []
    for item in body.items:
        total = minor(item.amount)
        if not set(item.shares) <= allowed:
            raise ValueError('Una quota appartiene a una persona esclusa dal pubblico: rimuovila dalla divisione')
        item_paid = None
        if per_item:
            if not item.payers or not set(item.payers) <= allowed:
                raise ValueError('Scegli con la stella almeno un pagatore visibile per ogni voce')
            fixed = {p: minor(value) for p, value in item.payers.items() if value.strip()}
            automatic = {p: '1' for p, value in item.payers.items() if not value.strip()}
            remainder = total - sum(fixed.values())
            if total <= 0 or any(value < 0 for value in fixed.values()) or remainder < 0:
                raise ValueError('Gli anticipi dei pagatori superano il costo della voce o non sono validi')
            if not automatic and remainder != 0:
                raise ValueError('La somma degli anticipi deve coincidere con il costo della voce')
            item_paid = dict(fixed)
            if automatic:
                item_paid.update(allocate(remainder, automatic, body.allocation_order) if remainder > 0 else {p: 0 for p in automatic})
            for person, value in item_paid.items():
                paid[person] += value
        if item.mode == 'exact':
            shares = {key: minor(value) for key, value in item.shares.items()}
            if total <= 0 or any(v < 0 for v in shares.values()) or sum(shares.values()) != total:
                raise ValueError('Le quote personalizzate non coincidono con il totale')
        else:
            weights = {key: '1' for key in item.shares} if item.mode == 'equal' else item.shares
            if item.mode == 'percent' and sum(Decimal(v) for v in weights.values()) != Decimal(100):
                raise ValueError('Le percentuali devono sommare a 100')
            shares = allocate(total, weights, body.allocation_order)
        for key, value in shares.items():
            owed[key] += value
        resolved = {'title': item.title, 'amount_minor': total, 'expression': item.amount if body.remember_expressions else f'{Decimal(total)/100:.2f}', 'mode': item.mode, 'shares': shares}
        if item_paid is not None:
            resolved['payers'] = item_paid
        items.append(resolved)
    total = sum(i['amount_minor'] for i in items)
    if not 0 < total <= MAX_MINOR or sum(paid.values()) != total:
        raise ValueError('La somma dei pagatori deve coincidere con il totale delle voci')
    if conversion:
        source_paid=dict(paid)
        paid=defaultdict(int);owed=defaultdict(int)
        for item in items:
            source_total=item['amount_minor']
            target=rounded(Decimal(source_total)*rate)
            if target<=0:raise ValueError('Una voce convertita è inferiore a un centesimo')
            item['original_amount_minor']=source_total;item['conversion']=conversion
            item['amount_minor']=target
            item['shares']=allocate(target,{k:str(v) for k,v in item['shares'].items()},body.allocation_order)
            for k,v in item['shares'].items():owed[k]+=v
            if 'payers' in item:
                item['payers']=allocate(target,{k:str(v) for k,v in item['payers'].items()},body.allocation_order)
                for k,v in item['payers'].items():paid[k]+=v
        total=sum(i['amount_minor'] for i in items)
        if not per_item:paid=allocate(total,{k:str(v) for k,v in source_paid.items()},body.allocation_order)
        if total>MAX_MINOR:raise ValueError('Totale convertito fuori limite')
    return {'total': total, 'paid': dict(paid), 'owed': dict(owed), 'items': items, 'audience': audience,'conversion':conversion}


@router.post('/calculator')
def calculator(body: ExpressionIn, user=Depends(current)):
    try:
        value = minor(body.expression)
        return {'minor': value, 'formatted': f'{Decimal(value) / 100:.2f}'}
    except ValueError as e:
        raise HTTPException(422, str(e)) from None


@router.post('/groups/{group_id}/expenses/preview')
def preview(group_id: str, body: ExpenseIn, user=Depends(current), db=Depends(get_db)):
    _, actor = membership(db, group_id, user, write=True)
    try:
        stored=False
        if body.exchange_token:
            stored=any(r.snapshot.get('exchange_token')==body.exchange_token for r in db.scalars(select(ExpenseRevision).join(Expense,Expense.id==ExpenseRevision.expense_id).where(Expense.group_id==group_id)) if visible(db.get(Expense,r.expense_id),actor))
        return build_expense(db, group_id, body, actor,stored_quote=stored)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except InvalidOperation:
        raise HTTPException(422, 'Inserisci quote e percentuali come numeri validi') from None


@router.post('/groups/{group_id}/expenses', status_code=201)
def create_expense(group_id: str, body: ExpenseIn, idempotency_key: str = Header(min_length=8, max_length=150), user=Depends(current), db=Depends(get_db)):
    return record_expense(group_id,body,idempotency_key,user,db)


def record_expense(group_id,body,idempotency_key,user,db,commit=True):
    # Serialize mutations in a group on PostgreSQL. This also serializes idempotent retries.
    db.scalar(select(Group).where(Group.id == group_id).with_for_update())
    _, actor = membership(db, group_id, user, write=True)
    key = group_id + ':' + idempotency_key
    request_hash = hashlib.sha256(json.dumps(body.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
    prior = db.get(Idempotency, (key, user.id))
    if prior:
        if prior.request_hash != request_hash:
            raise HTTPException(409, 'Chiave già usata per dati differenti')
        return prior.response
    try:
        data = build_expense(db, group_id, body, actor)
    except ValueError as error:
        raise HTTPException(422, str(error)) from None
    except InvalidOperation:
        raise HTTPException(422, 'Inserisci quote e percentuali come numeri validi') from None
    expense = Expense(group_id=group_id, author_id=user.id, title=body.title.strip(), description=body.description,
                      date=body.date.isoformat(), category=body.category, total=data['total'], audience=data['audience'], items=data['items'])
    db.add(expense)
    db.flush()
    for person in set(data['paid']) | set(data['owed']):
        db.add(Entry(group_id=group_id, expense_id=expense.id, participant_id=person, paid=data['paid'].get(person, 0), owed=data['owed'].get(person, 0)))
    db.add(ExpenseRevision(expense_id=expense.id, version=1, actor_id=user.id, snapshot=expense_snapshot(body)))
    result = {'id': expense.id, 'total': expense.total, 'version': expense.version}
    db.add(Idempotency(key=key, user_id=user.id, request_hash=request_hash, response=result))
    # No secret expense identifiers/titles in the generic audit feed.
    audit(db, user.id, 'expense.created', None)
    if commit: db.commit()
    return result


@router.get('/groups/{group_id}/expenses')
def list_expenses(group_id: str, user=Depends(current), db=Depends(get_db)):
    _, actor = membership(db, group_id, user)
    expenses = db.scalars(select(Expense).where(Expense.group_id == group_id, Expense.deleted.is_(False)).order_by(Expense.date.desc(), Expense.id))
    return [{'id': e.id, 'title': e.title, 'date': e.date, 'category': e.category, 'description': e.description, 'total': e.total, 'version': e.version, 'secret': e.audience is not None, 'items': e.items, 'tags': db.get(ExpenseRevision,(e.id,e.version)).snapshot.get('tags',[])} for e in expenses if visible(e, actor)]


@router.get('/groups/{group_id}/balances')
def balances(group_id: str, user=Depends(current), db=Depends(get_db)):
    _, actor = membership(db, group_id, user)
    # Keep every query in this monetary projection coherent with group-locked writes.
    group=db.scalar(select(Group).where(Group.id == group_id).with_for_update(read=True).execution_options(populate_existing=True))
    if group.deleted:raise HTTPException(404,'Gruppo non trovato')
    # Scope identity is the exact audience; never net distinct private audiences together.
    scopes = {}
    for expense in db.scalars(select(Expense).where(Expense.group_id == group_id, Expense.deleted.is_(False))):
        if not visible(expense, actor):
            continue
        key = 'public' if expense.audience is None else ','.join(sorted(expense.audience))
        if key not in scopes:
            scopes[key] = {'private': expense.audience is not None, 'audience': expense.audience, 'total': 0, 'balances': defaultdict(int)}
        scope = scopes[key]
        scope['total'] += expense.total
        for entry in db.scalars(select(Entry).where(Entry.expense_id == expense.id, Entry.revision == expense.version)):
            scope['balances'][entry.participant_id] += entry.paid - entry.owed
    for settlement in db.scalars(select(Settlement).where(Settlement.group_id == group_id, Settlement.status == 'confirmed')):
        if not visible(settlement, actor):
            continue
        key = 'public' if settlement.audience is None else ','.join(sorted(settlement.audience))
        if key not in scopes:
            scopes[key] = {'private': settlement.audience is not None, 'audience': settlement.audience, 'total': 0, 'balances': defaultdict(int)}
        scopes[key]['balances'][settlement.sender] += settlement.amount
        scopes[key]['balances'][settlement.recipient] -= settlement.amount
    direct={}
    if not group.smart_balances:
        from .direct_debts import direct_scopes
        direct=direct_scopes(db,group_id,actor)
    output = []
    for scope in scopes.values():
        net = dict(scope['balances'])
        creditors = [[p, v] for p, v in sorted(net.items()) if v > 0]
        debtors = [[p, -v] for p, v in sorted(net.items()) if v < 0]
        suggestions = []
        i = j = 0
        while i < len(debtors) and j < len(creditors):
            value = min(debtors[i][1], creditors[j][1])
            suggestions.append({'from': debtors[i][0], 'to': creditors[j][0], 'amount': value})
            debtors[i][1] -= value
            creditors[j][1] -= value
            if debtors[i][1] == 0: i += 1
            if creditors[j][1] == 0: j += 1
        if not group.smart_balances:suggestions=direct.get(None if scope['audience'] is None else tuple(sorted(scope['audience'])),[])
        output.append({**scope, 'balances': net, 'suggestions': suggestions})
    return output
