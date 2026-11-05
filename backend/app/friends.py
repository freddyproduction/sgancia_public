"""Consent-based account contacts. No email directory or implicit group privileges."""
import time
from fastapi import APIRouter,Depends,HTTPException,Response,Request
from pydantic import Field
from sqlalchemy import select,or_,delete
from .db import get_db
from .models import User,Friendship,FriendLink,Group,Participant
from .schemas import Strict
from .security import current,token,digest,cipher,audit,throttle
from .account_security import live_group_user
from .passkeys import ensure_live_session
from .groups import membership
router=APIRouter(prefix='/api/v1',tags=['Amici'])
class Target(Strict):user_id:str=Field(max_length=36)
class LinkIn(Strict):days:int=Field(default=30,ge=1,le=365)
class Join(Strict):token:str=Field(min_length=20,max_length=100)
class Add(Strict):user_id:str=Field(max_length=36);role:str=Field(default='member',pattern='^(member|viewer)$')

def pair(db,a,b,lock=False):
    first,second=sorted((a,b));q=select(Friendship).where(Friendship.first_id==first,Friendship.second_id==second)
    return db.scalar(q.with_for_update() if lock else q)

def profile(u):return {'id':u.id,'name':u.name,'avatar_icon':u.avatar_icon,'avatar_url':f'/api/v1/friends/{u.id}/avatar?v={u.avatar_version}' if u.avatar else None}

def contacts(db,uid):return db.scalars(select(Friendship).where(or_(Friendship.first_id==uid,Friendship.second_id==uid)))

@router.get('/friends')
def listing(q:str='',user=Depends(current),db=Depends(get_db)):
    result=[]
    for row in contacts(db,user.id):
        other=db.get(User,row.second_id if row.first_id==user.id else row.first_id)
        if not other or other.deleted or other.status!='active' or q.casefold() not in other.name.casefold():continue
        result.append({**profile(other),'friendship_id':row.id,'state':'accepted' if row.accepted else 'outgoing' if row.requested_by==user.id else 'incoming'})
    return sorted(result,key=lambda x:x['name'].casefold())

@router.get('/friends/search')
def search(q:str='',user=Depends(current),db=Depends(get_db)):
    throttle(db,'friend-search:'+user.id,40)
    # Existing friends can be filtered by name; strangers are found only by exact email.
    if len(q)<3 or '@' not in q:return []
    target=db.scalar(select(User).where(User.email==q.strip().lower(),User.status=='active',User.deleted.is_(False),User.id!=user.id))
    return [profile(target)] if target else []

@router.post('/friends/requests')
def request_friend(body:Target,request:Request,user=Depends(current),db=Depends(get_db)):
    throttle(db,'friend-request:'+user.id,20)
    accounts=list(db.scalars(select(User).where(User.id.in_([user.id,body.user_id])).order_by(User.id).with_for_update().execution_options(populate_existing=True)))
    if any(u.deleted or u.status!='active' for u in accounts):raise HTTPException(404,'Account non disponibile')
    ensure_live_session(db,request,next(u for u in accounts if u.id==user.id))
    target=next((u for u in accounts if u.id==body.user_id),None)
    if not target or target.id==user.id or target.status!='active' or target.deleted:raise HTTPException(404,'Account non disponibile')
    row=pair(db,user.id,target.id,True)
    if not row:
        a,b=sorted((user.id,target.id));row=Friendship(first_id=a,second_id=b,requested_by=user.id);db.add(row)
    # Crossed requests remain pending until explicit acceptance.
    audit(db,user.id,'friend.requested');db.commit();return {'saved':True}

@router.post('/friends/requests/{identity}/accept')
def accept(identity:str,user=Depends(current),db=Depends(get_db)):
    user=live_group_user(db,user);row=db.scalar(select(Friendship).where(Friendship.id==identity).with_for_update())
    if not row or user.id not in (row.first_id,row.second_id) or row.requested_by==user.id:raise HTTPException(404,'Richiesta non disponibile')
    other=db.get(User,row.requested_by)
    if not other or other.status!='active' or other.deleted:raise HTTPException(404,'Account non disponibile')
    row.accepted=True;audit(db,user.id,'friend.accepted');db.commit();return {'saved':True}

@router.delete('/friends/requests/{identity}')
def remove(identity:str,user=Depends(current),db=Depends(get_db)):
    row=db.scalar(select(Friendship).where(Friendship.id==identity).with_for_update())
    if not row or user.id not in (row.first_id,row.second_id):raise HTTPException(404,'Amicizia non disponibile')
    db.delete(row);audit(db,user.id,'friend.removed');db.commit();return {'saved':True}

@router.get('/friends/link')
def my_link(user=Depends(current),db=Depends(get_db)):
    row=db.get(FriendLink,user.id)
    if not row or row.expires<=time.time():return None
    return {'token':cipher().decrypt(row.secret).decode(),'expires':row.expires}

@router.post('/friends/link')
def make_link(body:LinkIn,user=Depends(current),db=Depends(get_db)):
    user=live_group_user(db,user);row=db.get(FriendLink,user.id);clear=token()
    if not row:row=FriendLink(user_id=user.id);db.add(row)
    row.token_hash=digest(clear);row.secret=cipher().encrypt(clear.encode());row.expires=int(time.time())+body.days*86400
    audit(db,user.id,'friend.link_rotated');db.commit();return {'token':clear,'expires':row.expires}

@router.delete('/friends/link')
def revoke_link(user=Depends(current),db=Depends(get_db)):
    user=live_group_user(db,user);db.execute(delete(FriendLink).where(FriendLink.user_id==user.id));db.commit();return {'saved':True}

@router.post('/friends/link/preview')
def preview(body:Join,user=Depends(current),db=Depends(get_db)):
    throttle(db,'friend-link:'+user.id,40)
    row=db.scalar(select(FriendLink).where(FriendLink.token_hash==digest(body.token),FriendLink.expires>int(time.time())))
    target=db.get(User,row.user_id) if row else None
    if not target or target.deleted or target.status!='active':raise HTTPException(404,'Link amicizia scaduto o revocato')
    return {'id':target.id,'name':target.name,'self':target.id==user.id}

@router.post('/friends/link/accept')
def accept_link(body:Join,request:Request,user=Depends(current),db=Depends(get_db)):
    hint=preview(body,user,db)
    # Consistent account ordering avoids mutual invitation deadlocks.
    accounts=list(db.scalars(select(User).where(User.id.in_([user.id,hint['id']])).order_by(User.id).with_for_update().execution_options(populate_existing=True)))
    if any(u.deleted or u.status!='active' for u in accounts):raise HTTPException(409,'Account non disponibile')
    ensure_live_session(db,request,next(u for u in accounts if u.id==user.id))
    row=db.scalar(select(FriendLink).where(FriendLink.user_id==hint['id'],FriendLink.token_hash==digest(body.token),FriendLink.expires>int(time.time())).with_for_update())
    if not row or hint['self']:raise HTTPException(409,'Non puoi aggiungere te stesso o usare un link revocato')
    relation=pair(db,user.id,hint['id'],True)
    if not relation:
        a,b=sorted((user.id,hint['id']));relation=Friendship(first_id=a,second_id=b,requested_by=hint['id']);db.add(relation)
    relation.accepted=True;audit(db,user.id,'friend.accepted');db.commit();return {'saved':True}

@router.get('/friends/{identity}/avatar')
def avatar(identity:str,user=Depends(current),db=Depends(get_db)):
    relation=pair(db,user.id,identity);target=db.get(User,identity)
    if not relation or not relation.accepted or not target or target.deleted or target.status!='active' or not target.avatar:raise HTTPException(404,'Immagine non disponibile')
    return Response(target.avatar,media_type='image/webp')

@router.post('/groups/{gid}/friends')
def add_group(gid:str,body:Add,request:Request,user=Depends(current),db=Depends(get_db)):
    membership(db,gid,user,write=True,manage=True)
    accounts=list(db.scalars(select(User).where(User.id.in_([user.id,body.user_id])).order_by(User.id).with_for_update().execution_options(populate_existing=True)))
    if len(accounts)!=2 or any(u.status!='active' or u.deleted for u in accounts):raise HTTPException(404,'Amico non disponibile')
    ensure_live_session(db,request,next(u for u in accounts if u.id==user.id))
    target=next(u for u in accounts if u.id==body.user_id)
    relation=pair(db,user.id,target.id,True)
    if not relation or not relation.accepted:raise HTTPException(403,'Prima confermate l’amicizia')
    db.scalar(select(Group).where(Group.id==gid).with_for_update());membership(db,gid,user,write=True,manage=True)
    if db.scalar(select(Participant.id).where(Participant.group_id==gid,Participant.user_id==target.id)):raise HTTPException(409,'Account già presente: gestiscilo dalla lista membri')
    person=Participant(group_id=gid,user_id=target.id,name=target.name,role=body.role);db.add(person);audit(db,user.id,'friend.added_to_group',gid);db.commit();return {'saved':True}
