"""Only authorized current revisions enter search, analytics and simulations."""
from collections import defaultdict
from datetime import date
from decimal import InvalidOperation
import hashlib,json
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Header,Query
from pydantic import Field
from sqlalchemy import select,func
from .schemas import Strict,ExpenseIn
from .models import Group,Participant,Expense,ExpenseRevision,Entry,Settlement,Budget,FinalReport,ExpensePlan,Idempotency
from .db import get_db
from .security import current,audit
from .groups import membership,visible,build_expense
from .finance import finance_view
from .direct_debts import route
from .money import minor,MAX_MINOR
router=APIRouter(prefix='/api/v1',tags=['Ricerca, statistiche e chiusura'])


def lock(db,gid,user,write=False):
    db.scalar(select(Group).where(Group.id==gid).with_for_update(read=not write))
    return membership(db,gid,user)


def records(db,gid,actor):
    result=[]
    for e in db.scalars(select(Expense).where(Expense.group_id==gid,Expense.deleted.is_(False)).order_by(Expense.date.desc(),Expense.id)):
        if not visible(e,actor):continue
        snap=db.get(ExpenseRevision,(e.id,e.version)).snapshot
        entries=list(db.scalars(select(Entry).where(Entry.expense_id==e.id,Entry.revision==e.version)))
        result.append({'id':e.id,'version':e.version,'title':e.title,'description':e.description,'date':e.date,'category':e.category,'tags':snap.get('tags',[]),'total':e.total,'secret':e.audience is not None,'audience':e.audience,'items':e.items,'paid':{x.participant_id:x.paid for x in entries},'owed':{x.participant_id:x.owed for x in entries}})
    return result


def filtered(rows,q='',start=None,end=None,category='',tag='',person=''):
    if start and end and start>end:raise HTTPException(422,'La data iniziale supera quella finale')
    return [r for r in rows if (not start or r['date']>=str(start)) and (not end or r['date']<=str(end)) and (not category or r['category']==category) and (not tag or tag.casefold() in [t.casefold() for t in r['tags']]) and (not person or r['paid'].get(person,0) or r['owed'].get(person,0)) and (not q.strip() or q.strip().casefold() in ' '.join([r['title'],r['description'],r['category'],*r['tags'],*[i['title'] for i in r['items']]]).casefold())]


def aggregate(rows,pid):
    categories=defaultdict(lambda:{'total':0,'personal':0});months=defaultdict(lambda:{'total':0,'personal':0})
    total=paid=owed=0;consistent=True
    for r in rows:
        total+=r['total'];paid+=r['paid'].get(pid,0);owed+=r['owed'].get(pid,0)
        consistent &= sum(r['paid'].values())==sum(r['owed'].values())==r['total']
        for bucket,key in ((categories,r['category']),(months,r['date'][:7])):
            bucket[key]['total']+=r['total'];bucket[key]['personal']+=r['owed'].get(pid,0)
    return {'count':len(rows),'total':total,'paid':paid,'owed':owed,'reconciled':bool(consistent),'categories':[{'name':k,**v} for k,v in sorted(categories.items())],'months':[{'name':k,**v} for k,v in sorted(months.items())]}


@router.get('/groups/{gid}/search')
def search(gid:str,q:str=Query(default='',max_length=200),start:date|None=None,end:date|None=None,category:str=Query(default='',max_length=60),tag:str=Query(default='',max_length=40),person:str=Query(default='',max_length=36),page:int=Query(default=1,ge=1),size:int=Query(default=50,ge=1,le=100),user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user);all_rows=records(db,gid,actor)
    rows=filtered(all_rows,q,start,end,category,tag,person)
    return {'currency':g.currency,'count':len(rows),'page':page,'size':size,'categories':sorted({r['category'] for r in all_rows}),'tags':sorted({t for r in all_rows for t in r['tags']}),'stats':aggregate(rows,actor.id),'expenses':[{k:v for k,v in r.items() if k not in ('paid','owed','audience','items')} for r in rows[(page-1)*size:page*size]]}


@router.get('/statistics')
def personal_stats(start:date|None=None,end:date|None=None,user=Depends(current),db=Depends(get_db)):
    from .overview import lock_groups
    filtered([],start=start,end=end)
    totals={}
    for g in lock_groups(db,user):
        _,actor=membership(db,g.id,user);rows=filtered(records(db,g.id,actor),start=start,end=end)
        # Personal statistics include only the account's own shares, not others' costs.
        own=[{**r,'total':r['owed'].get(actor.id,0),'paid':{'self':r['paid'].get(actor.id,0)},'owed':{'self':r['owed'].get(actor.id,0)}} for r in rows if r['paid'].get(actor.id,0) or r['owed'].get(actor.id,0)]
        bucket=totals.setdefault(g.currency,[]);bucket.extend(own)
    output=[]
    for currency,rows in sorted(totals.items()):
        data=aggregate(rows,'self');data.pop('reconciled');output.append({'currency':currency,**data})
    return output


class BudgetIn(Strict):
    name:str=Field(min_length=1,max_length=100)
    scope:Literal['personal','public']='personal'
    amount:str=Field(min_length=1,max_length=300)
    threshold:int=Field(default=80,ge=1,le=100)
    start:date
    end:date
    category:str=Field(default='',max_length=60)
    tag:str=Field(default='',max_length=40)


def budget_out(row,g,rows,actor):
    rows=filtered(rows,start=row.start,end=row.end,category=row.category,tag=row.tag)
    spent=sum(r['owed'].get(actor.id,0) if row.scope=='personal' else r['total'] for r in rows if row.scope=='personal' or not r['secret'])
    review=row.currency!=g.currency
    return {'id':row.id,'name':row.name,'scope':row.scope,'amount':row.amount,'currency':row.currency,'threshold':row.threshold,'start':row.start,'end':row.end,'category':row.category,'tag':row.tag,'version':row.version,'spent':None if review else spent,'remaining':None if review else row.amount-spent,'percent':None if review else spent*100//row.amount,'status':'currency_changed' if review else 'exceeded' if spent>=row.amount else 'threshold' if spent*100>=row.amount*row.threshold else 'ok'}


def budget_visible(row,actor):return row.scope=='public' or (row.user_id==actor.user_id and row.participant_id==actor.id)


@router.get('/groups/{gid}/budgets')
def budgets(gid:str,user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user);rows=records(db,gid,actor)
    return [budget_out(r,g,rows,actor) for r in db.scalars(select(Budget).where(Budget.group_id==gid).order_by(Budget.name)) if budget_visible(r,actor)]


def set_budget(row,body,g,actor):
    if body.scope=='public' and actor.role not in ('owner','admin'):raise HTTPException(403,'Solo gli amministratori gestiscono i budget pubblici')
    try:amount=minor(body.amount)
    except ValueError as e:raise HTTPException(422,str(e)) from None
    if not 0<amount<=MAX_MINOR or body.start>body.end or not body.name.strip():raise HTTPException(422,'Nome, importo o periodo non valido')
    row.name=body.name.strip();row.scope=body.scope;row.amount=amount;row.threshold=body.threshold;row.start=body.start.isoformat();row.end=body.end.isoformat();row.category=body.category.strip();row.tag=body.tag.strip();row.currency=g.currency


@router.post('/groups/{gid}/budgets',status_code=201)
def add_budget(gid:str,body:BudgetIn,user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user,True);membership(db,gid,user,write=True)
    if db.scalar(select(func.count()).select_from(Budget).where(Budget.group_id==gid,Budget.user_id==user.id))>=100:raise HTTPException(409,'Limite di 100 budget per account nel gruppo')
    row=Budget(group_id=gid,user_id=user.id,participant_id=actor.id);set_budget(row,body,g,actor);db.add(row);db.flush();result=budget_out(row,g,records(db,gid,actor),actor);db.commit();return result


@router.put('/groups/{gid}/budgets/{bid}')
def edit_budget(gid:str,bid:str,body:BudgetIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user,True);membership(db,gid,user,write=True)
    row=db.get(Budget,bid)
    if not row or row.group_id!=gid or not budget_visible(row,actor):raise HTTPException(404,'Budget non trovato')
    if row.scope!=body.scope:raise HTTPException(422,'La visibilità del budget non può cambiare')
    if row.version!=if_match:raise HTTPException(409,'Budget modificato: ricarica')
    set_budget(row,body,g,actor);row.version+=1;db.commit();return budget_out(row,g,records(db,gid,actor),actor)


@router.delete('/groups/{gid}/budgets/{bid}')
def delete_budget(gid:str,bid:str,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user,True);membership(db,gid,user,write=True);row=db.get(Budget,bid)
    if not row or row.group_id!=gid or not budget_visible(row,actor):raise HTTPException(404,'Budget non trovato')
    if row.scope=='public' and actor.role not in ('owner','admin'):raise HTTPException(403,'Operazione non consentita')
    if row.version!=if_match:raise HTTPException(409,'Budget modificato: ricarica')
    db.delete(row);db.commit();return {'deleted':True}


def payments(db,gid,actor):return [p for p in db.scalars(select(Settlement).where(Settlement.group_id==gid)) if visible(p,actor)]


def projection(rows,payments,actor,smart):
    scopes={};direct={}
    def scope(aud):
        key=None if aud is None else tuple(sorted(aud));return key,scopes.setdefault(key,defaultdict(int)),direct.setdefault(key,defaultdict(int))
    def add(ledger,a,b,value):
        left,right=sorted((a,b));ledger[(left,right)]+=value if a==left else -value
    for r in rows:
        key,net,ledger=scope(r['audience'])
        for p in set(r['paid'])|set(r['owed']):net[p]+=r['paid'].get(p,0)-r['owed'].get(p,0)
        items=[(i['payers'],i['shares']) for i in r['items']] if all('payers' in i for i in r['items']) else [(r['paid'],r['owed'])]
        for paid,owed in items:
            for a,b,value in route(paid,owed):add(ledger,a,b,value)
    for p in payments:
        if p['status']!='confirmed':continue
        key,net,ledger=scope(p['audience']);net[p['sender']]+=p['amount'];net[p['recipient']]-=p['amount'];add(ledger,p['sender'],p['recipient'],-p['amount'])
    balances=defaultdict(int);transfers=defaultdict(int);receive=pay=0
    for key,net in scopes.items():
        for p,value in net.items():balances[p]+=value
        suggestions=route({p:max(value,0) for p,value in net.items()},{p:max(-value,0) for p,value in net.items()}) if smart else [(a if v>0 else b,b if v>0 else a,abs(v)) for (a,b),v in sorted(direct[key].items()) if v]
        for sender,recipient,amount in suggestions:
            transfers[(sender,recipient)]+=amount
            if recipient==actor:receive+=amount
            if sender==actor:pay+=amount
    return {'balance':balances.get(actor,0),'receivable':receive,'payable':pay,'expenses_total':sum(r['total'] for r in rows),'balances':dict(balances),'transfers':[{'from':a,'to':b,'amount':v} for (a,b),v in sorted(transfers.items())]}


class SimulationIn(Strict):
    action:Literal['add','edit','delete','payment','smart']
    expense_id:str|None=Field(default=None,max_length=36)
    version:int|None=Field(default=None,ge=1)
    draft:ExpenseIn|None=None
    sender:str|None=Field(default=None,max_length=36)
    recipient:str|None=Field(default=None,max_length=36)
    amount:str|None=Field(default=None,max_length=300)
    audience:list[str]|None=Field(default=None,min_length=1,max_length=200)
    smart:bool|None=None


@router.post('/groups/{gid}/simulate')
def simulate(gid:str,body:SimulationIn,user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user)
    if body.action=='payment':
        if actor.role=='viewer' or g.state=='archived':raise HTTPException(403,'Operazione non consentita')
    else:membership(db,gid,user,write=True)
    rows=records(db,gid,actor);ps=[{'sender':p.sender,'recipient':p.recipient,'amount':p.amount,'audience':p.audience,'status':p.status} for p in payments(db,gid,actor)]
    before=projection(rows,ps,actor.id,g.smart_balances)
    old=None
    if body.action in ('edit','delete'):
        old=next((r for r in rows if r['id']==body.expense_id),None)
        if old is None:raise HTTPException(404,'Spesa non trovata')
        if old['version']!=body.version:raise HTTPException(409,'Spesa modificata: ricarica')
        rows=[r for r in rows if r['id']!=old['id']]
    if body.action in ('add','edit'):
        if body.draft is None:raise HTTPException(422,'Inserisci la bozza')
        draft=body.draft
        if old and (set(old['audience'] or [])!=set(draft.audience or []) or (old['audience'] is None)!=(draft.audience is None)):raise HTTPException(422,'Il pubblico della spesa non può cambiare')
        stored=False
        if old:stored=bool(draft.exchange_token and draft.exchange_token==db.get(ExpenseRevision,(old['id'],old['version'])).snapshot.get('exchange_token'))
        try:data=build_expense(db,gid,draft,actor,stored_quote=stored,existing_people=set(old['paid'])|set(old['owed']) if old else None)
        except (ValueError,InvalidOperation) as e:raise HTTPException(422,str(e)) from None
        rows.append({'total':data['total'],'audience':data['audience'],'paid':data['paid'],'owed':data['owed'],'items':data['items']})
    if body.action=='payment':
        people=set(db.scalars(select(Participant.id).where(Participant.group_id==gid,Participant.merged_into.is_(None))))
        allowed=set(body.audience) if body.audience is not None else people
        if not allowed<=people or actor.id not in allowed or body.sender not in allowed or body.recipient not in allowed or body.sender==body.recipient:raise HTTPException(422,'Partecipanti o pubblico non validi')
        try:value=minor(body.amount or '')
        except ValueError as e:raise HTTPException(422,str(e)) from None
        if value<=0:raise HTTPException(422,'Importo non valido')
        ps.append({'sender':body.sender,'recipient':body.recipient,'amount':value,'audience':body.audience,'status':'confirmed'})
    if body.action=='smart' and body.smart is None:raise HTTPException(422,'Scegli lo stato Smart')
    after=projection(rows,ps,actor.id,body.smart if body.action=='smart' else g.smart_balances)
    return {'currency':g.currency,'before':before,'after':after,'applied':False}


def final_view(db,g,user,actor):
    rows=records(db,g.id,actor);ps=payments(db,g.id,actor);finance=finance_view(db,g.id,user)
    summary=aggregate(rows,actor.id)
    source={'currency':g.currency,'state':g.state,'expenses':[(r['id'],r['version']) for r in rows],'payments':sorted((p.id,p.status,p.amount) for p in ps),'smart':g.smart_balances}
    fingerprint=hashlib.sha256(json.dumps(source,sort_keys=True).encode()).hexdigest()
    names={p.id:p.name for p in db.scalars(select(Participant).where(Participant.group_id==g.id))}
    return {'group':g.name,'currency':g.currency,'state':g.state,'stats':summary,'finance':finance['summary'],'transfers':[{'from':names[r['from']],'to':names[r['to']],'amount':r['amount']} for r in finance['transfers']],'pending':sum(p.status in ('pending','disputed') for p in ps),'fingerprint':fingerprint,'visibility':'Solo dati visibili al tuo account; nessuna verifica dei saldi riservati agli altri.'}


@router.get('/groups/{gid}/closing')
def closing(gid:str,user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user);return final_view(db,g,user,actor)


class CloseIn(Strict):
    fingerprint:str=Field(min_length=64,max_length=64)
    retain_balances:bool=False


@router.post('/groups/{gid}/close')
def close(gid:str,body:CloseIn,idempotency_key:str=Header(min_length=8,max_length=150),user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user,True)
    if actor.role!='owner':raise HTTPException(403,'Solo il proprietario può chiudere il gruppo')
    key='close:'+gid+':'+idempotency_key;hashed=hashlib.sha256(json.dumps(body.model_dump(),sort_keys=True).encode()).hexdigest();prior=db.get(Idempotency,(key,user.id))
    if prior:
        if prior.request_hash!=hashed:raise HTTPException(409,'Chiave già usata')
        report=db.get(FinalReport,prior.response['id'])
        if report.participant_id!=actor.id:raise HTTPException(404,'Riepilogo non disponibile')
        return prior.response
    if g.state!='frozen':raise HTTPException(409,'Congela prima le spese per completare i rimborsi')
    view=final_view(db,g,user,actor)
    if view['fingerprint']!=body.fingerprint:raise HTTPException(409,'I dati visibili sono cambiati: ricarica il riepilogo')
    if not body.retain_balances:raise HTTPException(422,'Conferma la conservazione di eventuali saldi aperti, anche non visibili')
    if not view['stats']['reconciled']:raise HTTPException(409,'I totali visibili richiedono una riconciliazione')
    g.state='archived';g.metadata_version+=1
    for plan in db.scalars(select(ExpensePlan).where(ExpensePlan.group_id==gid,ExpensePlan.kind=='recurring')):plan.enabled=False;plan.error='group_closed'
    view['state']='archived';view['balances_retained']=True
    report=FinalReport(group_id=gid,user_id=user.id,participant_id=actor.id,snapshot=view);db.add(report);db.flush()
    response={'id':report.id,'state':'archived'};db.add(Idempotency(key=key,user_id=user.id,request_hash=hashed,response=response));audit(db,user.id,'group.closed',gid);db.commit();return response


@router.post('/groups/{gid}/reports',status_code=201)
def save_report(gid:str,user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user,True)
    if g.state=='active':raise HTTPException(409,'Congela il gruppo prima di salvare il riepilogo finale')
    if db.scalar(select(func.count()).select_from(FinalReport).where(FinalReport.group_id==gid,FinalReport.user_id==user.id))>=50:raise HTTPException(409,'Limite di 50 riepiloghi per account nel gruppo')
    report=FinalReport(group_id=gid,user_id=user.id,participant_id=actor.id,snapshot=final_view(db,g,user,actor));db.add(report);db.flush();result={'id':report.id};db.commit();return result


@router.get('/groups/{gid}/reports')
def reports(gid:str,user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user)
    return [{'id':r.id,'created':r.created,'snapshot':r.snapshot} for r in db.scalars(select(FinalReport).where(FinalReport.group_id==gid,FinalReport.user_id==user.id,FinalReport.participant_id==actor.id).order_by(FinalReport.created.desc()))]
