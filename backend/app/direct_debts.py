from collections import defaultdict
from sqlalchemy import select
from .models import Expense,Entry,Settlement
from .groups import visible


def route(paid,owed):
    creditors=[[p,max(paid.get(p,0)-owed.get(p,0),0)] for p in sorted(set(paid)|set(owed))]
    debtors=[[p,max(owed.get(p,0)-paid.get(p,0),0)] for p in sorted(set(paid)|set(owed))]
    creditors=[v for v in creditors if v[1]];debtors=[v for v in debtors if v[1]]
    i=j=0;rows=[]
    while i<len(debtors) and j<len(creditors):
        value=min(debtors[i][1],creditors[j][1]);rows.append((debtors[i][0],creditors[j][0],value))
        debtors[i][1]-=value;creditors[j][1]-=value
        if not debtors[i][1]:i+=1
        if not creditors[j][1]:j+=1
    return rows


def direct_scopes(db,group_id,actor):
    scopes={}
    def scope(audience):
        key=None if audience is None else tuple(sorted(audience))
        return scopes.setdefault(key,defaultdict(int))
    def add(ledger,sender,recipient,amount):
        left,right=sorted((sender,recipient));ledger[(left,right)]+=amount if sender==left else -amount
    for expense in db.scalars(select(Expense).where(Expense.group_id==group_id,Expense.deleted.is_(False))):
        if not visible(expense,actor):continue
        ledger=scope(expense.audience)
        if all('payers' in item for item in expense.items):
            items=[(item['payers'],item['shares']) for item in expense.items]
        else:
            entries=list(db.scalars(select(Entry).where(Entry.expense_id==expense.id,Entry.revision==expense.version)))
            items=[({e.participant_id:e.paid for e in entries},{e.participant_id:e.owed for e in entries})]
        for paid,owed in items:
            for sender,recipient,amount in route(paid,owed):add(ledger,sender,recipient,amount)
    for payment in db.scalars(select(Settlement).where(Settlement.group_id==group_id,Settlement.status=='confirmed')):
        if visible(payment,actor):add(scope(payment.audience),payment.sender,payment.recipient,-payment.amount)
    return {key:[{'from':a if value>0 else b,'to':b if value>0 else a,'amount':abs(value)} for (a,b),value in sorted(rows.items()) if value] for key,rows in scopes.items()}
