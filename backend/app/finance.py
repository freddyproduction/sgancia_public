"""Only permission-filtered values enter summaries and combined transfers."""
from collections import defaultdict
import hashlib
import json
from fastapi import APIRouter,Depends
from sqlalchemy import select
from .db import get_db
from .security import current
from .groups import membership,visible,balances
from .models import Expense,Entry,Settlement
router=APIRouter(prefix='/api/v1/groups',tags=['Riepiloghi economici'])


def transfer_fingerprint(components,currency=None):
    canonical=sorted([{'audience':sorted(c['audience']) if c['audience'] is not None else None,'amount':c['amount']} for c in components],key=lambda c:json.dumps(c,sort_keys=True))
    return hashlib.sha256(json.dumps({'components':canonical,'currency':currency},sort_keys=True).encode()).hexdigest()


def finance_view(db,group_id,user):
    group,actor=membership(db,group_id,user)
    scopes=balances(group_id,user,db)
    summary={'expenses_total':0,'paid':0,'owed':0,'sent':0,'received':0,'balance':0,'receivable':0,'payable':0}
    for expense,entry in db.execute(select(Expense,Entry).join(Entry,(Entry.expense_id==Expense.id)&(Entry.revision==Expense.version)).where(Expense.group_id==group_id,Expense.deleted.is_(False),Entry.participant_id==actor.id)):
        if visible(expense,actor):
            summary['paid']+=entry.paid
            summary['owed']+=entry.owed
    for payment in db.scalars(select(Settlement).where(Settlement.group_id==group_id,Settlement.status=='confirmed')):
        if visible(payment,actor):
            if payment.sender==actor.id:summary['sent']+=payment.amount
            if payment.recipient==actor.id:summary['received']+=payment.amount
    transfers={}
    for scope in scopes:
        summary['expenses_total']+=scope['total']
        net=scope['balances'].get(actor.id,0)
        summary['balance']+=net
        for transfer in scope['suggestions']:
            if transfer['to']==actor.id:summary['receivable']+=transfer['amount']
            if transfer['from']==actor.id:summary['payable']+=transfer['amount']
        for suggestion in scope['suggestions']:
            key=(suggestion['from'],suggestion['to'])
            if key not in transfers:
                transfers[key]={'from':key[0],'to':key[1],'amount':0,'private':False,'components':[]}
            row=transfers[key]
            row['amount']+=suggestion['amount']
            row['private']|=scope['private']
            row['components'].append({'audience':scope['audience'],'amount':suggestion['amount']})
    result=[]
    for row in transfers.values():
        row['fingerprint']=transfer_fingerprint(row['components'],group.currency)
        result.append(row)
    assert summary['balance']==summary['paid']-summary['owed']+summary['sent']-summary['received']
    return {'summary':summary,'transfers':sorted(result,key=lambda row:(row['from'],row['to']))}


@router.get('/{group_id}/finance')
def finance(group_id:str,user=Depends(current),db=Depends(get_db)):
    return finance_view(db,group_id,user)
