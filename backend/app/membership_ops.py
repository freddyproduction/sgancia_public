"""Group-locked, previewed operations; immutable expense revisions survive merges."""
import time,json,hashlib,copy
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,Header,Request
from pydantic import Field
from sqlalchemy import select,update
from .db import get_db
from .schemas import Strict
from .security import current,recent,audit
from .groups import membership,visible,group_out
from .models import Group,Participant,User,GroupOperation,VirtualDelegation,Expense,ExpenseRevision,Entry,Settlement,SettlementEvent,GroupInvite,Invite,ParticipantClaim,GuestLink
router=APIRouter(prefix='/api/v1/groups',tags=['Gestione avanzata gruppi'])


def locked(db,gid,user,manage=False):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    return membership(db,gid,user,write=True,manage=manage)


def person(db,gid,pid,active=True):
    p=db.get(Participant,pid)
    if not p or p.group_id!=gid or (active and (not p.active or p.merged_into)):raise HTTPException(404,'Partecipante non disponibile')
    return p


def revoke(db,gid,pid=None):
    # Revoke account+group invitations together, including pending virtual claims.
    invites=select(GroupInvite.token_hash).where(GroupInvite.group_id==gid)
    if pid:
        target=db.get(Participant,pid);account=db.get(User,target.user_id) if target and target.user_id else None
        condition=GroupInvite.participant_id==pid
        if account:condition=condition|(GroupInvite.email==account.email)
        invites=invites.where(condition)
    hashes=list(db.scalars(invites))
    if hashes:
        db.execute(update(Invite).where(Invite.token_hash.in_(hashes)).values(used=True));db.execute(update(GroupInvite).where(GroupInvite.token_hash.in_(hashes)).values(used=True))
    if pid:
        db.execute(update(ParticipantClaim).where(ParticipantClaim.participant_id==pid).values(used=True))
        db.execute(update(VirtualDelegation).where(VirtualDelegation.group_id==gid,((VirtualDelegation.virtual_id==pid)|(VirtualDelegation.delegate_id==pid))).values(revoked=True))


def delegated(db,gid,actor,pid,permission):
    p=db.get(Participant,pid)
    if not p or p.group_id!=gid or p.user_id is not None or p.merged_into or actor.role=='viewer' or not actor.active:return False
    return bool(db.scalar(select(VirtualDelegation.id).where(VirtualDelegation.group_id==gid,VirtualDelegation.virtual_id==pid,VirtualDelegation.delegate_id==actor.id,VirtualDelegation.revoked.is_(False),VirtualDelegation.expires>time.time(),getattr(VirtualDelegation,permission).is_(True))))


class TargetIn(Strict):
    target:str


@router.post('/{gid}/ownership',status_code=201)
def offer_owner(gid:str,body:TargetIn,request:Request,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    group,actor=locked(db,gid,user,True);recent(request)
    if actor.role!='owner' or group.owner_id!=user.id:raise HTTPException(403,'Solo il proprietario può trasferire la proprietà')
    target=person(db,gid,body.target)
    account=db.get(User,target.user_id) if target.user_id else None
    if target.id==actor.id or not account or account.status!='active' or target.role=='viewer':raise HTTPException(422,'Scegli un altro membro con account attivo e permesso di scrittura')
    if group.metadata_version!=if_match:raise HTTPException(409,'Gruppo cambiato: aggiorna')
    group.metadata_version+=1
    op=GroupOperation(group_id=gid,actor_id=user.id,kind='ownership_offer',snapshot={'target':target.id,'owner':actor.id,'version':group.metadata_version,'expires':int(time.time())+86400})
    db.add(op);db.commit();return {'id':op.id}


@router.post('/{gid}/ownership/{oid}/accept')
def accept_owner(gid:str,oid:str,request:Request,user=Depends(current),db=Depends(get_db)):
    group,actor=locked(db,gid,user);recent(request);op=db.get(GroupOperation,oid)
    if not op or op.group_id!=gid or op.kind!='ownership_offer':raise HTTPException(404,'Trasferimento non disponibile')
    data=op.snapshot
    if data['target']!=actor.id:raise HTTPException(403,'Trasferimento destinato a un altro account')
    if data['expires']<=time.time() or data['version']!=group.metadata_version:raise HTTPException(409,'Trasferimento scaduto o gruppo modificato: richiedi una nuova proposta')
    old=person(db,gid,data['owner'])
    if old.role!='owner' or group.owner_id!=old.user_id or actor.role=='viewer':raise HTTPException(409,'Proprietà o ruolo cambiati')
    old.role='admin';actor.role='owner';group.owner_id=user.id;group.metadata_version+=1
    op.kind='ownership_accepted';revoke(db,gid)
    db.add(GroupOperation(group_id=gid,actor_id=user.id,kind='ownership_accepted_event',snapshot={'from':old.id,'to':actor.id}))
    audit(db,user.id,'group.owner_transferred',gid);db.commit();return group_out(group)


class DepartureIn(Strict):
    keep_balance:bool=False
    fingerprint:str=Field(min_length=64,max_length=64)


def departure_preview(db,gid,p,actor):
    from .groups import balances
    # Preserve every scope separately; a zero aggregate does not settle private debts.
    class Identity: id=p.user_id
    if p.user_id:
        scopes=balances(gid,Identity(),db)
    else:
        # Use a virtual identity only for server-side projection, never for access.
        # Calculate directly, without borrowing the administrator's narrower audience.
        scopes=[]
        for e in db.scalars(select(Expense).where(Expense.group_id==gid,Expense.deleted.is_(False))):
            if e.audience is not None and p.id not in e.audience:continue
            key=None if e.audience is None else tuple(sorted(e.audience));found=next((v for v in scopes if v['audience']==key),None)
            if not found:found={'audience':key,'balances':{p.id:0}};scopes.append(found)
            for entry in db.scalars(select(Entry).where(Entry.expense_id==e.id,Entry.revision==e.version,Entry.participant_id==p.id)):found['balances'][p.id]+=entry.paid-entry.owed
        for pay in db.scalars(select(Settlement).where(Settlement.group_id==gid,Settlement.status=='confirmed')):
            if p.id not in (pay.sender,pay.recipient):continue
            key=None if pay.audience is None else tuple(sorted(pay.audience));found=next((v for v in scopes if v['audience']==key),None)
            if not found:found={'audience':key,'balances':{p.id:0}};scopes.append(found)
            found['balances'][p.id]+=pay.amount if pay.sender==p.id else -pay.amount
    pending=bool(db.scalar(select(Settlement.id).where(Settlement.group_id==gid,Settlement.status.in_(['pending','disputed']),((Settlement.sender==p.id)|(Settlement.recipient==p.id)))))
    can_see=actor.id==p.id
    from .direct_debts import direct_scopes
    direct_open=not db.get(Group,gid).smart_balances and any(r['from']==p.id or r['to']==p.id for rows in direct_scopes(db,gid,p).values() for r in rows)
    zero=all(s['balances'].get(p.id,0)==0 for s in scopes) and not pending and not direct_open
    data={'id':p.id,'name':p.name,'keep_balance_required':not zero if can_see else True,'amounts':[{'private':s['audience'] is not None,'balance':s['balances'].get(p.id,0)} for s in scopes] if can_see else [],'limited':not can_see,'pending':pending if can_see else None}
    data['fingerprint']=hashlib.sha256(json.dumps({'state':fingerprint(db,gid),'person':p.id},sort_keys=True).encode()).hexdigest()
    return data


@router.get('/{gid}/participants/{pid}/departure-preview')
def preview_departure(gid:str,pid:str,user=Depends(current),db=Depends(get_db)):
    _,actor=membership(db,gid,user);p=person(db,gid,pid)
    if (actor.role=='viewer' and actor.id!=p.id) or (actor.id!=p.id and actor.role not in ('owner','admin')) or p.role=='owner' or (p.role=='admin' and actor.role!='owner' and actor.id!=p.id):raise HTTPException(403,'Trasferisci prima la proprietà oppure chiedi a un amministratore')
    return departure_preview(db,gid,p,actor)


@router.post('/{gid}/participants/{pid}/depart')
def depart(gid:str,pid:str,body:DepartureIn,user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    group,actor=membership(db,gid,user);p=person(db,gid,pid)
    if actor.id!=p.id:membership(db,gid,user,write=True,manage=True)
    if (actor.role=='viewer' and actor.id!=p.id) or (actor.id!=p.id and actor.role not in ('owner','admin')) or p.role=='owner' or (p.role=='admin' and actor.role!='owner' and actor.id!=p.id):raise HTTPException(403,'Rimozione non consentita: il proprietario deve prima trasferire la proprietà')
    preview=departure_preview(db,gid,p,actor)
    if body.fingerprint!=preview['fingerprint']:raise HTTPException(409,'Dati cambiati: aggiorna l’anteprima')
    if preview['keep_balance_required'] and not body.keep_balance:raise HTTPException(409,'Conserva esplicitamente i saldi aperti oppure saldali prima di uscire')
    op=GroupOperation(group_id=gid,actor_id=user.id,kind='departure',snapshot={'participant':p.id,'user':p.user_id,'role':p.role,'keep_balance':body.keep_balance})
    revoke(db,gid,p.id)
    # The historical participant becomes an inactive virtual; no account retains access.
    p.user_id=None;p.active=False;p.role='member';group.metadata_version+=1
    db.add(op);audit(db,user.id,'participant.departed',p.id);db.commit();return {'status':'departed'}


@router.post('/{gid}/participants/{pid}/reactivate')
def reactivate(gid:str,pid:str,user=Depends(current),db=Depends(get_db)):
    group,_=locked(db,gid,user,True);p=person(db,gid,pid,False)
    if p.merged_into:raise HTTPException(409,'Partecipante unito: usa il ripristino della fusione')
    p.active=True;group.metadata_version+=1
    db.add(GroupOperation(group_id=gid,actor_id=user.id,kind='reactivate',snapshot={'participant':p.id}));db.commit()
    return {'id':p.id}


class DelegationIn(Strict):
    virtual_id:str
    delegate_id:str
    pay:bool=False
    attest:bool=False
    days:int=Field(default=30,ge=1,le=90)


@router.get('/{gid}/delegations')
def delegations(gid:str,user=Depends(current),db=Depends(get_db)):
    _,actor=membership(db,gid,user)
    return [{'id':d.id,'virtual_id':d.virtual_id,'delegate_id':d.delegate_id,'pay':d.pay,'attest':d.attest,'expires':d.expires} for d in db.scalars(select(VirtualDelegation).where(VirtualDelegation.group_id==gid,VirtualDelegation.revoked.is_(False),VirtualDelegation.expires>time.time())) if actor.role in ('owner','admin') or actor.id==d.delegate_id]


@router.post('/{gid}/delegations',status_code=201)
def grant(gid:str,body:DelegationIn,user=Depends(current),db=Depends(get_db)):
    _,_=locked(db,gid,user,True);v=person(db,gid,body.virtual_id);d=person(db,gid,body.delegate_id)
    if v.user_id or not d.user_id or db.get(User,d.user_id).status!='active' or d.role=='viewer' or not(body.pay or body.attest):raise HTTPException(422,'Scegli un virtuale, un account con scrittura e almeno un permesso')
    db.execute(update(VirtualDelegation).where(VirtualDelegation.group_id==gid,VirtualDelegation.virtual_id==v.id,VirtualDelegation.delegate_id==d.id).values(revoked=True))
    row=VirtualDelegation(group_id=gid,virtual_id=v.id,delegate_id=d.id,pay=body.pay,attest=body.attest,expires=int(time.time())+body.days*86400,granted_by=user.id)
    db.add(row);audit(db,user.id,'delegation.granted',v.id);db.commit();return {'id':row.id}


@router.delete('/{gid}/delegations/{did}',status_code=204)
def revoke_delegation(gid:str,did:str,user=Depends(current),db=Depends(get_db)):
    locked(db,gid,user,True);d=db.get(VirtualDelegation,did)
    if not d or d.group_id!=gid:raise HTTPException(404,'Delega non trovata')
    d.revoked=True;audit(db,user.id,'delegation.revoked',did);db.commit()


def fingerprint(db,gid):
    data={'expenses':[(e.id,e.version,e.deleted) for e in db.scalars(select(Expense).where(Expense.group_id==gid).order_by(Expense.id))],'payments':[(s.id,s.sender,s.recipient,s.amount,s.status,s.audience) for s in db.scalars(select(Settlement).where(Settlement.group_id==gid).order_by(Settlement.id))],'participants':[(p.id,p.user_id,p.role,p.active,p.merged_into) for p in db.scalars(select(Participant).where(Participant.group_id==gid).order_by(Participant.id))],'group':db.get(Group,gid).metadata_version}
    return hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()


class MergeIn(Strict):
    source:str
    target:str
    fingerprint:str|None=Field(default=None,min_length=64,max_length=64)


def merge_plan(db,gid,body,actor):
    source=person(db,gid,body.source);target=person(db,gid,body.target)
    if source.id==target.id or source.user_id is not None:raise HTTPException(422,'La sorgente deve essere un duplicato senza account, distinto dalla destinazione')
    expenses=list(db.scalars(select(Expense).where(Expense.group_id==gid)))
    payments=list(db.scalars(select(Settlement).where(Settlement.group_id==gid)))
    # Check every historical audience as well: the merge must not disclose any old secret.
    audiences=[e.audience for e in expenses]+[s.audience for s in payments]+[v.snapshot.get('audience') for v in db.scalars(select(ExpenseRevision).join(Expense,Expense.id==ExpenseRevision.expense_id).where(Expense.group_id==gid))]
    if any(a is not None and ((source.id in a)!=(target.id in a)) for a in audiences):raise HTTPException(409,'Fusione non disponibile con i tuoi permessi o con le identità selezionate. Nessun dato è stato cambiato')
    if any(a is not None and source.id in a and actor.id not in a for a in audiences):raise HTTPException(409,'Fusione non disponibile con i tuoi permessi o con le identità selezionate. Nessun dato è stato cambiato')
    if any({s.sender,s.recipient}=={source.id,target.id} for s in payments):raise HTTPException(409,'Esistono rimborsi tra i duplicati: richiedono una riconciliazione dedicata prima della fusione')
    # An outstanding association must never silently redirect to another identity.
    return source,target,expenses,payments


@router.post('/{gid}/merge/preview')
def merge_preview(gid:str,body:MergeIn,user=Depends(current),db=Depends(get_db)):
    _,actor=locked(db,gid,user,True);source,target,expenses,payments=merge_plan(db,gid,body,actor)
    from .groups import balances
    scope_balances=[{'private':s['private'],'source':s['balances'].get(source.id,0),'target':s['balances'].get(target.id,0),'after':s['balances'].get(source.id,0)+s['balances'].get(target.id,0)} for s in balances(gid,user,db) if source.id in s['balances'] or target.id in s['balances']]
    return {'balances':scope_balances,'source':source.name,'target':target.name,'expenses':sum(any(entry.participant_id==source.id for entry in current_entries(db,e)) or (e.audience is not None and source.id in e.audience) for e in expenses),'payments':sum(source.id in (p.sender,p.recipient) for p in payments),'fingerprint':fingerprint(db,gid),'note':'Somma quote e anticipi senza cambiare i totali. Le vecchie versioni restano conservate. Nessun accesso riservato viene ampliato.'}


def current_entries(db,row):
    entries=list(db.scalars(select(Entry).where(Entry.expense_id==row.id,Entry.revision==row.version)))
    if not entries:
        prior=db.scalar(select(ExpenseRevision).where(ExpenseRevision.expense_id==row.id,ExpenseRevision.version<row.version).order_by(ExpenseRevision.version.desc()).limit(1))
        if prior:entries=list(db.scalars(select(Entry).where(Entry.expense_id==row.id,Entry.revision==prior.version)))
    return entries


def replace_map(values,source,target):
    out={}
    for k,v in values.items():out[target if k==source else k]=out.get(target if k==source else k,0)+v
    return out


def save_revision(db,row,items,audience,entries,user,snapshot=None):
    row.version+=1;row.items=copy.deepcopy(items);row.audience=audience
    if snapshot is None:
        amount=lambda n:format(Decimal(n)/100,'.2f')
        snapshot={'title':row.title,'description':row.description,'date':row.date,'category':row.category,'currency':db.get(Group,row.group_id).currency,'audience':audience,'payers':{},'items':[{'title':i['title'],'amount':amount(i['amount_minor']),'mode':'exact','shares':{k:amount(v) for k,v in i['shares'].items()},'payers':{k:amount(v) for k,v in i['payers'].items() if v}} for i in items]}
        if row.deleted:snapshot['deleted']=True
    previous=db.get(ExpenseRevision,(row.id,row.version-1))
    if previous:snapshot.setdefault('tags',previous.snapshot.get('tags',[]))
    db.add(ExpenseRevision(expense_id=row.id,version=row.version,actor_id=user.id,snapshot=snapshot))
    for k,v in entries.items():db.add(Entry(group_id=row.group_id,expense_id=row.id,revision=row.version,participant_id=k,paid=v[0],owed=v[1]))


@router.post('/{gid}/merge')
def merge(gid:str,body:MergeIn,user=Depends(current),db=Depends(get_db)):
    group,actor=locked(db,gid,user,True);source,target,expenses,payments=merge_plan(db,gid,body,actor)
    if not body.fingerprint or body.fingerprint!=fingerprint(db,gid):raise HTTPException(409,'Dati cambiati: ripeti l’anteprima')
    before={'source':source.id,'target':target.id,'expenses':[],'payments':[]}
    for row in expenses:
        old=db.get(ExpenseRevision,(row.id,row.version));entries=current_entries(db,row)
        if not any(e.participant_id==source.id for e in entries) and (row.audience is None or source.id not in row.audience):continue
        if not visible(row,actor):raise HTTPException(403,'Fusione non disponibile con i tuoi permessi')
        original={e.participant_id:[e.paid,e.owed] for e in entries}
        before['expenses'].append({'id':row.id,'items':row.items,'audience':row.audience,'entries':original,'snapshot':old.snapshot})
        totals={}
        for key,value in original.items():
            key=target.id if key==source.id else key
            current=totals.setdefault(key,[0,0]);current[0]+=value[0];current[1]+=value[1]
        items=copy.deepcopy(row.items)
        # Legacy aggregate payers are split deterministically into rows, preserving totals.
        available={e.participant_id:e.paid for e in entries}
        for item in items:
            if 'payers' not in item:
                left=item['amount_minor'];paid={}
                for k in sorted(available):
                    v=min(left,available[k]);left-=v;available[k]-=v
                    if v:paid[k]=v
                item['payers']=paid
            item['payers']=replace_map(item['payers'],source.id,target.id);item['shares']=replace_map(item['shares'],source.id,target.id)
        audience=sorted(set(target.id if k==source.id else k for k in row.audience)) if row.audience is not None else None
        save_revision(db,row,items,audience,totals,user)
    for payment in payments:
        if source.id not in (payment.sender,payment.recipient) and (payment.audience is None or source.id not in payment.audience):continue
        before['payments'].append({'id':payment.id,'sender':payment.sender,'recipient':payment.recipient,'audience':payment.audience})
        if payment.sender==source.id:payment.sender=target.id
        if payment.recipient==source.id:payment.recipient=target.id
        if payment.audience is not None:payment.audience=sorted(set(target.id if k==source.id else k for k in payment.audience))
        db.add(SettlementEvent(settlement_id=payment.id,actor_id=user.id,status=payment.status,reason='Fusione controllata dei partecipanti: identità aggiornata; importo e stato conservati'))
    source.active=False;source.merged_into=target.id;revoke(db,gid,source.id);revoke(db,gid,target.id);group.metadata_version+=1
    db.flush();before['after']=fingerprint(db,gid)
    op=GroupOperation(group_id=gid,actor_id=user.id,kind='merge',snapshot=before);db.add(op);db.commit();return {'id':op.id}


@router.post('/{gid}/operations/{oid}/undo-merge')
def undo_merge(gid:str,oid:str,user=Depends(current),db=Depends(get_db)):
    group,actor=locked(db,gid,user,True);op=db.get(GroupOperation,oid)
    if not op or op.group_id!=gid or op.kind!='merge':raise HTTPException(404,'Fusione non disponibile')
    data=op.snapshot
    if fingerprint(db,gid)!=data['after']:raise HTTPException(409,'Dopo la fusione ci sono altre modifiche: serve una rettifica esplicita, non un ripristino automatico')
    for saved in data['expenses']:
        row=db.get(Expense,saved['id'])
        if not visible(row,actor):raise HTTPException(404,'Fusione non disponibile')
        save_revision(db,row,saved['items'],saved['audience'],saved['entries'],user,copy.deepcopy(saved['snapshot']))
    for saved in data['payments']:
        payment=db.get(Settlement,saved['id'])
        if not visible(payment,actor):raise HTTPException(404,'Fusione non disponibile')
        payment.sender=saved['sender'];payment.recipient=saved['recipient'];payment.audience=saved['audience']
        db.add(SettlementEvent(settlement_id=payment.id,actor_id=user.id,status=payment.status,reason='Ripristino della fusione controllata'))
    source=db.get(Participant,data['source']);source.active=True;source.merged_into=None;group.metadata_version+=1;op.kind='merge_undone'
    db.add(GroupOperation(group_id=gid,actor_id=user.id,kind='merge_undo_event',snapshot={'operation':op.id}));db.commit();return {'status':'restored'}


@router.get('/{gid}/operations')
def operations(gid:str,user=Depends(current),db=Depends(get_db)):
    _,actor=membership(db,gid,user)
    result=[]
    for op in db.scalars(select(GroupOperation).where(GroupOperation.group_id==gid).order_by(GroupOperation.created.desc(),GroupOperation.id)):
        data=op.snapshot
        if op.kind=='ownership_offer':
            if actor.id not in (data['owner'],data['target']):continue
            if data['expires']<=time.time() or data['version']!=db.get(Group,gid).metadata_version:continue
        elif actor.role not in ('owner','admin'):continue
        if op.kind.startswith('merge') and 'expenses' in data:
            if any(not visible(db.get(Expense,e['id']),actor) for e in data['expenses']) or any(not visible(db.get(Settlement,p['id']),actor) for p in data['payments']):continue
        result.append({'id':op.id,'kind':op.kind,'created':op.created,'actor':db.get(User,op.actor_id).name,'target':data.get('target'),'source':data.get('source'),'can_accept':op.kind=='ownership_offer' and data.get('target')==actor.id,'can_undo':op.kind=='merge' and fingerprint(db,gid)==data.get('after')})
    return result
