"""Transactional, permission-scoped inbox. Email is an opt-in, generic digest."""
import time
from datetime import datetime,date,time as clock,timedelta,timezone as utc
from zoneinfo import ZoneInfo,ZoneInfoNotFoundError,available_timezones
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException
from pydantic import Field,field_validator
from sqlalchemy import select,event,delete
from sqlalchemy.orm import Session
from .db import get_db,SessionLocal
from .models import Notification,NotificationPreference,Expense,ExpenseRevision,Settlement,SettlementEvent,GroupOperation,Group,Participant,User,uid
from .schemas import Strict
from .security import current
from .groups import membership,visible
router=APIRouter(prefix='/api/v1/notifications',tags=['Notifiche'])

class Preferences(Strict):
    enabled:bool=True
    events:bool=True
    email:bool=False
    frequency:Literal['daily','weekly','monthly']='daily'
    reminder:Literal['off','daily','weekly','monthly']='off'
    summary:Literal['off','daily','weekly','monthly']='off'
    threshold:int=Field(default=100,ge=1,le=100000000000)
    hour:int=Field(default=9,ge=0,le=23)
    timezone:str=Field(default='UTC',max_length=100)
    minute:int=Field(default=0,ge=0,le=59)
    week_day:int=Field(default=0,ge=0,le=6)
    month_day:int=Field(default=1,ge=1,le=28)
    days:list[int]=Field(default_factory=lambda:list(range(7)),min_length=1,max_length=7)
    retention_days:int=Field(default=90,ge=1,le=365)
    max_items:int=Field(default=100,ge=20,le=200)
    show_read:bool=True
    expense_events:bool=True
    payment_events:bool=True
    group_events:bool=True
    pause_until:int=Field(default=0,ge=0,le=4102444800)

    @field_validator('timezone')
    @classmethod
    def valid_zone(cls,value):
        try:ZoneInfo(value)
        except (ZoneInfoNotFoundError,ValueError):raise ValueError('Scegli un fuso orario IANA valido') from None
        return value

    @field_validator('days')
    @classmethod
    def valid_days(cls,value):
        if len(set(value))!=len(value) or any(d<0 or d>6 for d in value):raise ValueError('Giorni non validi')
        return sorted(value)


def preferences(db,user_id,gid=''):
    account=db.get(NotificationPreference,(user_id,''))
    base=Preferences.model_validate(account.config if account else {}).model_dump()
    if gid:
        group=db.get(NotificationPreference,(user_id,gid))
        if group:base.update(group.config)
    return base


def permitted(db,n,user):
    if n.user_id!=user.id or user.status!='active':return False
    g=db.get(Group,n.group_id)
    actor=db.get(Participant,n.participant_id)
    if not g or g.deleted or not actor or not actor.active or actor.user_id!=user.id or actor.group_id!=g.id or not visible(n,actor):return False
    pref=preferences(db,user.id,g.id)
    account=preferences(db,user.id)
    if not pref['enabled'] or not account['enabled'] or max(pref['pause_until'],account['pause_until'])>time.time():return False
    if n.created<int(time.time())-pref['retention_days']*86400:return False
    if n.kind in ('expense','payment','group') and (not pref['events'] or not pref[n.kind+'_events']):return False
    if n.kind in ('reminder','summary') and pref[n.kind]=='off':return False
    if n.kind=='reminder':
        from .finance import finance_view
        if finance_view(db,g.id,user)['summary']['payable']<pref['threshold']:return False
    if n.kind=='expense':
        row=db.get(Expense,n.resource)
        return bool(row and row.group_id==g.id and visible(row,actor))
    if n.kind=='payment':
        row=db.get(Settlement,n.resource)
        return bool(row and row.group_id==g.id and visible(row,actor))
    return True


@router.get('/preferences')
def get_preferences(group_id:str='',user=Depends(current),db=Depends(get_db)):
    if group_id:membership(db,group_id,user)
    return {'config':preferences(db,user.id,group_id),'override':bool(group_id and db.get(NotificationPreference,(user.id,group_id)))}


@router.put('/preferences')
def set_preferences(body:Preferences,group_id:str='',user=Depends(current),db=Depends(get_db)):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    if group_id:membership(db,group_id,user)
    row=db.get(NotificationPreference,(user.id,group_id))
    if not row:row=NotificationPreference(user_id=user.id,scope=group_id);db.add(row)
    row.config=body.model_dump();row.started_at=int(time.time());db.commit();return {'saved':True}


@router.delete('/preferences')
def reset_preferences(group_id:str,user=Depends(current),db=Depends(get_db)):
    membership(db,group_id,user)
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    row=db.get(NotificationPreference,(user.id,group_id))
    if row:db.delete(row)
    db.commit();return {'saved':True}


@router.get('')
def inbox(folder:Literal['inbox','unread','archived','trash']='inbox',user=Depends(current),db=Depends(get_db)):
    rows=[n for n in db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.created>=int(time.time())-365*86400).order_by(Notification.created.desc(),Notification.id)) if not n.event_key.startswith('email:') and permitted(db,n,user)]
    labels={'expense':'Spesa creata o aggiornata','payment':'Rimborso aggiornato','group':'Impostazioni o membri del gruppo aggiornati','reminder':'Hai importi da restituire: controlla i saldi attuali','summary':'Il riepilogo del gruppo è disponibile'}
    return {'unread':sum(n.read_at is None and n.folder=='inbox' for n in rows),'items':[{'id':n.id,'group_id':n.group_id,'group':db.get(Group,n.group_id).name,'kind':n.kind,'text':labels[n.kind],'created':n.created,'read_at':n.read_at,'email_status':n.email_status} for n in rows if n.folder==('inbox' if folder=='unread' else folder) and (folder!='unread' or n.read_at is None) and (folder not in ('inbox','unread') or preferences(db,user.id,n.group_id)['show_read'] or n.read_at is None)][:preferences(db,user.id)['max_items']]}


@router.post('/read-all')
def mark_all(user=Depends(current),db=Depends(get_db)):
    now=int(time.time())
    for n in db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.read_at.is_(None),Notification.folder=='inbox')):
        if permitted(db,n,user):n.read_at=now
    db.commit();return {'read':True}


@router.post('/{nid}/read')
def mark_read(nid:str,user=Depends(current),db=Depends(get_db)):
    n=db.get(Notification,nid)
    if not n or not permitted(db,n,user):raise HTTPException(404,'Notifica non disponibile')
    n.read_at=n.read_at or int(time.time());db.commit();return {'read':True}


class InboxAction(Strict):
    action:Literal['read','unread','archive','trash','restore']


@router.post('/{nid}/action')
def inbox_action(nid:str,body:InboxAction,user=Depends(current),db=Depends(get_db)):
    n=db.scalar(select(Notification).where(Notification.id==nid,Notification.user_id==user.id).with_for_update())
    if not n or not permitted(db,n,user):raise HTTPException(404,'Notifica non disponibile')
    if body.action=='read':n.read_at=n.read_at or int(time.time())
    elif body.action=='unread':n.read_at=None
    elif body.action=='archive':n.folder='archived'
    elif body.action=='trash':n.folder='trash'
    else:n.folder='inbox'
    db.commit();return {'folder':n.folder,'read':n.read_at is not None}


def add(db,user,actor,gid,key,kind,resource,audience=None,now=None):
    pref=preferences(db,user.id,gid)
    if not pref['enabled'] or not preferences(db,user.id)['enabled'] or max(pref['pause_until'],preferences(db,user.id)['pause_until'])>(now or time.time()):return
    if kind in ('expense','payment','group') and (not pref['events'] or not pref[kind+'_events']):return
    db.add(Notification(user_id=user.id,group_id=gid,participant_id=actor.id,event_key=key,kind=kind,resource=resource,audience=audience,created=now or int(time.time())))


@event.listens_for(Session,'before_flush')
def collect_events(db,context,instances):
    # Same transaction as the mutation, no historical backfill and no polling cursor.
    for row in list(db.new):
        if isinstance(row,ExpenseRevision):
            parent=db.get(Expense,row.expense_id) or next((e for e in db.new if isinstance(e,Expense) and e.id==row.expense_id),None)
            if not parent:continue
            gid=parent.group_id;kind='expense';resource=parent.id;audience=row.snapshot.get('audience');key=f'expense:{resource}:{row.version}'
        elif isinstance(row,SettlementEvent):
            parent=db.get(Settlement,row.settlement_id) or next((s for s in db.new if isinstance(s,Settlement) and s.id==row.settlement_id),None)
            if not parent:continue
            row.id=row.id or uid();gid=parent.group_id;kind='payment';resource=parent.id;audience=parent.audience;key='payment:'+row.id
        elif isinstance(row,GroupOperation):
            row.id=row.id or uid();gid=row.group_id;kind='group';resource=gid;audience=None;key='group:'+row.id
        else:continue
        for actor in db.scalars(select(Participant).where(Participant.group_id==gid,Participant.active.is_(True),Participant.user_id.is_not(None))):
            if not actor.active or not actor.user_id:continue
            if audience is not None and actor.id not in audience:continue
            user=db.get(User,actor.user_id)
            if user and user.status=='active':add(db,user,actor,gid,key,kind,resource,list(audience) if audience is not None else None)


def period(now,frequency,hour):
    shift=now-hour*3600-(4*86400 if frequency=='weekly' else 0)
    return shift//(86400 if frequency=='daily' else 7*86400)


def scheduled_slot(now,frequency,pref):
    zone=ZoneInfo(pref['timezone']);local=datetime.fromtimestamp(now,zone);day=local.date()
    if frequency=='weekly':day-=timedelta(days=(day.weekday()-pref['week_day'])%7)
    elif frequency=='monthly':day=day.replace(day=pref['month_day'])
    for _ in range(370):
        slot=datetime.combine(day,clock(pref['hour'],pref['minute']),zone)
        # A nonexistent DST time moves forward; an ambiguous time uses its first occurrence.
        if slot.timestamp()<=now and (frequency!='daily' or day.weekday() in pref['days']):break
        if frequency=='monthly':day=(day.replace(day=1)-timedelta(days=1)).replace(day=pref['month_day'])
        else:day-=timedelta(days=7 if frequency=='weekly' else 1)
    days=(day-date(1970,1,1)).days
    key=days if frequency=='daily' else (days-4)//7 if frequency=='weekly' else day.year*12+day.month
    return int(slot.timestamp()),key


def due(db,user_id,gid,frequency,hour,now):
    row=db.get(NotificationPreference,(user_id,gid)) or db.get(NotificationPreference,(user_id,''))
    if not row:return False
    if frequency=='daily' and datetime.fromtimestamp(now,ZoneInfo(preferences(db,user_id,gid)['timezone'])).weekday() not in preferences(db,user_id,gid)['days']:return False
    pref=preferences(db,user_id,gid);pref['hour']=hour
    return scheduled_slot(now,frequency,pref)[0]>=row.started_at


@router.get('/options')
def options(user=Depends(current)):
    return {'timezones':sorted(available_timezones())}


def cleanup(db,user_id,now):
    for n in db.scalars(select(Notification).where(Notification.user_id==user_id)):
        days=preferences(db,user_id,n.group_id)['retention_days']
        if n.event_key.startswith('email:'):days=max(35,days) # minimal delivery stamp prevents duplicate digests
        if n.created<now-days*86400:db.delete(n)


def run_user(db,uid_,now=None):
    from .finance import finance_view
    from .mail_delivery import enqueue,configured
    now=now or int(time.time())
    # Same Group -> User lock order as publication and financial mutations.
    gids=list(db.scalars(select(Participant.group_id).where(Participant.user_id==uid_,Participant.active.is_(True)).order_by(Participant.group_id)))
    groups=list(db.scalars(select(Group).where(Group.id.in_(gids),Group.deleted.is_(False)).order_by(Group.id).with_for_update(read=True)))
    user=db.scalar(select(User).where(User.id==uid_).with_for_update().execution_options(populate_existing=True))
    if not user:db.commit();return
    cleanup(db,user.id,now)
    if user.status!='active' or not preferences(db,user.id)['enabled'] or preferences(db,user.id)['pause_until']>now:db.commit();return
    for g in groups:
        actor=db.scalar(select(Participant).where(Participant.user_id==user.id,Participant.group_id==g.id,Participant.active.is_(True)))
        if not actor:continue
        pref=preferences(db,user.id,g.id)
        if not pref['enabled'] or pref['pause_until']>now or g.state=='archived':continue
        for kind in ('reminder','summary'):
            frequency=pref[kind]
            if frequency=='off' or not due(db,user.id,g.id,frequency,pref['hour'],now):continue
            key=f'{kind}:{g.id}:{actor.id}:{frequency}:{scheduled_slot(now,frequency,pref)[1]}'
            if db.scalar(select(Notification.id).where(Notification.user_id==user.id,Notification.event_key==key)):continue
            if kind=='reminder' and finance_view(db,g.id,user)['summary']['payable']<pref['threshold']:continue
            add(db,user,actor,g.id,key,kind,g.id,now=now);db.flush()
        # At most one generic email per group and cadence, regardless of event volume.
        if not pref['email'] or not user.email_verified or not configured(db) or not due(db,user.id,g.id,pref['frequency'],pref['hour'],now):continue
        email_key=f'email:{g.id}:{actor.id}:{pref["frequency"]}:{scheduled_slot(now,pref['frequency'],pref)[1]}'
        if db.scalar(select(Notification.id).where(Notification.user_id==user.id,Notification.event_key==email_key)):continue
        rows=list(db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.group_id==g.id,Notification.read_at.is_(None),Notification.email_status=='none',Notification.created>=now-7*86400)))
        rows=[n for n in rows if permitted(db,n,user)]
        if not rows:continue
        # A visible inbox item is the authorization anchor; no financial data leaves the app.
        anchor=rows[0]
        marker=Notification(user_id=user.id,group_id=g.id,participant_id=actor.id,event_key=email_key,kind=anchor.kind,resource=anchor.resource,audience=anchor.audience,created=now,read_at=now,email_status='queued')
        db.add(marker);db.flush()
        enqueue(db,user.email,'Sgancia: aggiornamenti disponibili','Accedi a Sgancia per consultare gli aggiornamenti e i saldi autorizzati del tuo account.',now+86400,notification_id=marker.id,notification_ids=[n.id for n in rows])
        for row in rows:row.email_status='queued'
    db.commit()


def email_allowed(db,nid):
    n=db.get(Notification,nid)
    if not n:return None
    db.scalar(select(Group).where(Group.id==n.group_id).with_for_update(read=True))
    user=db.scalar(select(User).where(User.id==n.user_id).with_for_update().execution_options(populate_existing=True))
    if not user or not permitted(db,n,user) or not user.email_verified or not preferences(db,user.id,n.group_id)['email']:return None
    return user


def tick():
    with SessionLocal() as db:ids=list(db.scalars(select(User.id).where(User.status=='active')))
    for user_id in ids:
        try:
            with SessionLocal() as db:run_user(db,user_id)
        except Exception:print('Notifiche temporaneamente non elaborate',flush=True)
