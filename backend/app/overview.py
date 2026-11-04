"""Cross-group dashboard: identities, currencies and audiences stay explicit."""
import hashlib,json
from fastapi import APIRouter,Depends,HTTPException,Header
from pydantic import Field
from sqlalchemy import select
from .schemas import Strict
from .models import Group,Participant,User,Idempotency,Settlement
from .db import get_db
from .security import current,digest
from .finance import finance_view
from .settlements import TransferIn,record_transfer
router=APIRouter(prefix='/api/v1',tags=['Panoramica generale'])


def lock_groups(db,user,write=False):
    ids=list(db.scalars(select(Participant.group_id).where(Participant.user_id==user.id,Participant.active.is_(True)).order_by(Participant.group_id)))
    return list(db.scalars(select(Group).where(Group.id.in_(ids),Group.deleted.is_(False)).order_by(Group.id).with_for_update(read=not write)))


def overview_view(db,user,groups):
    rows={};totals={}
    for group in groups:
        actor=db.scalar(select(Participant).where(Participant.group_id==group.id,Participant.user_id==user.id))
        if not actor:continue
        people={p.id:p for p in db.scalars(select(Participant).where(Participant.group_id==group.id))}
        view=finance_view(db,group.id,user)
        for transfer in view['transfers']:
            if actor.id not in (transfer['from'],transfer['to']):continue
            direction='receive' if transfer['to']==actor.id else 'pay'
            person=people[transfer['from'] if direction=='receive' else transfer['to']]
            identity='user:'+person.user_id if person.user_id else 'participant:'+person.id
            key=direction+':'+group.currency+':'+identity
            name=db.get(User,person.user_id).name if person.user_id else person.name
            if key not in rows:rows[key]={'key':key,'direction':direction,'currency':group.currency,'name':name,'virtual':person.user_id is None,'amount':0,'private':False,'can_settle':True,'groups':[]}
            row=rows[key];row['amount']+=transfer['amount'];row['private']|=transfer['private']
            allowed=actor.role!='viewer' and group.state!='archived'
            row['can_settle']&=allowed
            row['groups'].append({'id':group.id,'name':group.name,'amount':transfer['amount'],'can_settle':allowed,'sender':transfer['from'],'recipient':transfer['to'],'components':transfer['components'],'fingerprint':transfer['fingerprint']})
            total=totals.setdefault(group.currency,{'currency':group.currency,'receive':0,'pay':0})
            total[direction]+=transfer['amount']
    for row in rows.values():
        row['groups'].sort(key=lambda g:g['id'])
        row['fingerprint']=hashlib.sha256(json.dumps(row['groups'],sort_keys=True).encode()).hexdigest()
    return {'totals':sorted(totals.values(),key=lambda t:t['currency']),'people':sorted(rows.values(),key=lambda r:(r['name'].casefold(),r['currency'],r['key']))}

@router.get('/overview')
def overview(user=Depends(current),db=Depends(get_db)):
    return overview_view(db,user,lock_groups(db,user))

class ReceiveIn(Strict):
    key:str=Field(min_length=1,max_length=150)
    fingerprint:str=Field(min_length=64,max_length=64)

@router.post('/overview/settle')
def settle_overview(body:ReceiveIn,idempotency_key:str=Header(min_length=8,max_length=150),user=Depends(current),db=Depends(get_db)):
    groups=lock_groups(db,user,write=True)
    key='overview:'+idempotency_key;request_hash=digest(json.dumps(body.model_dump(),sort_keys=True))
    prior=db.get(Idempotency,(key,user.id))
    if prior:
        if prior.request_hash!=request_hash:raise HTTPException(409,'Chiave già usata per un altro rimborso')
        if any(not (row:=db.get(Settlement,sid)) or row.status!='confirmed' for sid in prior.response['ids']):raise HTTPException(409,'Un rimborso è stato ripristinato: aggiorna la panoramica')
        return prior.response
    row=next((r for r in overview_view(db,user,groups)['people'] if r['key']==body.key),None)
    if not row or row['fingerprint']!=body.fingerprint:raise HTTPException(409,'I saldi sono cambiati: aggiorna la panoramica')
    if row['direction']!='receive' or not row['can_settle']:raise HTTPException(403,'Può saldare soltanto il ricevente con permessi in tutti i gruppi coinvolti')
    ids=[]
    for index,entry in enumerate(row['groups']):
        result=record_transfer(db,entry['id'],TransferIn(sender=entry['sender'],recipient=entry['recipient'],components=entry['components'],fingerprint=entry['fingerprint']),digest(idempotency_key+':'+str(index)),user,commit=False)
        if result['status']!='confirmed':raise HTTPException(409,'Ricezione non confermabile in uno dei gruppi')
        ids.extend(result['ids'])
    result={'status':'confirmed','ids':ids,'amount':row['amount'],'currency':row['currency'],'group_count':len(row['groups'])}
    db.add(Idempotency(key=key,user_id=user.id,request_hash=request_hash,response=result));db.commit()
    return result
