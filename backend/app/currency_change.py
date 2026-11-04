"""Explicit atomic redenomination; historical revisions are never relabelled."""
from decimal import Decimal
from fastapi import APIRouter,Depends,Header,HTTPException
from pydantic import Field
from sqlalchemy import select
from .schemas import Strict
from .db import get_db
from .security import current,audit
from .models import Group,Expense,ExpenseRevision,Entry,Settlement,CurrencyChange
from .groups import membership,group_out
from .exchange import valid_currency,read_quote,rate_value,rounded
from .money import allocate
router=APIRouter(prefix='/api/v1/groups',tags=['Valuta principale'])

class ChangeIn(Strict):
    currency:str=Field(min_length=3,max_length=3)
    exchange_token:str|None=Field(default=None,max_length=2000)
    exchange_rate:str|None=Field(default=None,max_length=40)

def decimal_amount(n):return format(Decimal(n)/100,'.2f')

def convert_map(values,total):
    if not total or not sum(values.values()):return {k:0 for k in values}
    return allocate(total,{k:str(v) for k,v in values.items()})

@router.put('/{group_id}/currency')
def change_currency(group_id:str,body:ChangeIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,_=membership(db,group_id,user,write=True,manage=True)
    if group.metadata_version!=if_match:raise HTTPException(409,'Il gruppo è cambiato: ricarica le impostazioni')
    try:
        valid_currency(body.currency)
        if body.currency==group.currency:raise ValueError('Il gruppo usa già questa valuta')
        quote=read_quote(body.exchange_token,group.currency,body.currency) if body.exchange_token else {'base':group.currency,'quote':body.currency,'rate':str(rate_value(body.exchange_rate)),'source':'Manuale'}
        rate=rate_value(quote['rate'])
        snapshot={'quote':quote,'settlements':[],'expense_versions':[]}
        for row in db.scalars(select(Expense).where(Expense.group_id==group_id).with_for_update()):
            # Convert the current resolved allocations, preserving every old revision.
            entries=list(db.scalars(select(Entry).where(Entry.expense_id==row.id,Entry.revision==row.version)))
            if not entries and row.deleted:
                prior=db.scalar(select(ExpenseRevision).where(ExpenseRevision.expense_id==row.id,ExpenseRevision.version<row.version).order_by(ExpenseRevision.version.desc()).limit(1))
                entries=list(db.scalars(select(Entry).where(Entry.expense_id==row.id,Entry.revision==prior.version)))
            paid={e.participant_id:e.paid for e in entries}
            resolved=[];owed={}
            for item in row.items:
                total=rounded(Decimal(item['amount_minor'])*rate)
                if total<=0:raise ValueError('Una voce diventerebbe inferiore a un centesimo: scegli un altro tasso')
                shares=convert_map(item['shares'],total)
                for k,v in shares.items():owed[k]=owed.get(k,0)+v
                resolved.append({**item,'amount_minor':total,'expression':decimal_amount(total),'shares':shares,'conversion':quote,'original_amount_minor':item['amount_minor']})
            total=sum(i['amount_minor'] for i in resolved)
            if total>10**12:raise ValueError('Spesa convertita fuori limite')
            per_item=all('payers' in item for item in row.items)
            paid=convert_map(paid,total)
            # Keep each item's actual payers. Only legacy aggregate advances need distribution.
            available=dict(paid);draft_items=[]
            if per_item:paid={}
            for item in resolved:
                left=item['amount_minor'];item_paid={}
                if per_item:
                    item_paid=convert_map(item['payers'],left)
                    for person,value in item_paid.items():paid[person]=paid.get(person,0)+value
                else:
                    for person in sorted(available):
                        value=min(left,available[person])
                        if value:item_paid[person]=value;available[person]-=value;left-=value
                item['payers']=item_paid
                draft_items.append({'title':item['title'],'amount':decimal_amount(item['amount_minor']),'mode':'exact','shares':{k:decimal_amount(v) for k,v in item['shares'].items()},'payers':{k:decimal_amount(v) for k,v in item_paid.items()}})
            snapshot['expense_versions'].append({'id':row.id,'before':row.version,'after':row.version+1})
            previous=db.get(ExpenseRevision,(row.id,row.version)).snapshot
            row.version+=1;row.total=total;row.items=resolved
            draft={'title':row.title,'description':row.description,'date':row.date,'category':row.category,'audience':row.audience,'payers':{},'currency':body.currency,'items':draft_items}
            draft['tags']=previous.get('tags',[]);draft['remember_expressions']=False
            if row.deleted:draft['deleted']=True
            db.add(ExpenseRevision(expense_id=row.id,version=row.version,actor_id=user.id,snapshot=draft))
            for person in set(paid)|set(owed):db.add(Entry(group_id=group_id,expense_id=row.id,revision=row.version,participant_id=person,paid=paid.get(person,0),owed=owed.get(person,0)))
        for payment in db.scalars(select(Settlement).where(Settlement.group_id==group_id).with_for_update()):
            amount=rounded(Decimal(payment.amount)*rate)
            if amount<=0:raise ValueError('Un rimborso diventerebbe inferiore a un centesimo')
            snapshot['settlements'].append({'id':payment.id,'before':payment.amount,'after':amount})
            payment.amount=amount
        db.add(CurrencyChange(group_id=group_id,actor_id=user.id,snapshot=snapshot))
        group.currency=body.currency;group.metadata_version+=1
        audit(db,user.id,'group.currency_changed',group.id)
        db.commit()
        return group_out(group)
    except ValueError as e:
        db.rollback();raise HTTPException(422,str(e)) from None
