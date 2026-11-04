from fastapi import APIRouter,Depends,HTTPException,Header
from sqlalchemy import select,update,delete
from .db import get_db
from .security import current,audit
from .models import Group,Participant,GuestLink,GroupInvite,Invite,ParticipantClaim,GroupJoinCode
from .groups import group_out
router=APIRouter(prefix='/api/v1',tags=['Cestino gruppi'])


def owned(db,gid,user):
    group=db.scalar(select(Group).where(Group.id==gid).with_for_update())
    actor=db.scalar(select(Participant).where(Participant.group_id==gid,Participant.user_id==user.id))
    if not group or not actor:raise HTTPException(404,'Gruppo non trovato')
    if group.owner_id!=user.id or actor.role!='owner':raise HTTPException(403,'Solo il proprietario può eliminare o ripristinare il gruppo')
    return group

@router.get('/group-trash')
def group_trash(user=Depends(current),db=Depends(get_db)):
    rows=db.scalars(select(Group).join(Participant,Participant.group_id==Group.id).where(Participant.user_id==user.id,Participant.role.in_(['owner','admin']),((Participant.active.is_(True))|((Group.owner_id==user.id)&(Participant.role=='owner'))),Group.deleted.is_(True)).order_by(Group.name))
    return [{'id':g.id,'name':g.name,'currency':g.currency,'state':g.state,'metadata_version':g.metadata_version} for g in rows]

@router.delete('/groups/{gid}',status_code=204)
def remove_group(gid:str,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    group=owned(db,gid,user)
    if group.deleted and if_match in (group.metadata_version,group.metadata_version-1):return
    if group.deleted or group.metadata_version!=if_match:raise HTTPException(409,'Il gruppo è cambiato: aggiorna prima di eliminarlo')
    group.deleted=True;group.metadata_version+=1
    db.execute(delete(GroupJoinCode).where(GroupJoinCode.group_id==gid))
    db.execute(update(GuestLink).where(GuestLink.group_id==gid).values(revoked=True))
    hashes=select(GroupInvite.token_hash).where(GroupInvite.group_id==gid)
    db.execute(update(Invite).where(Invite.token_hash.in_(hashes)).values(used=True))
    db.execute(update(GroupInvite).where(GroupInvite.group_id==gid).values(used=True))
    people=select(Participant.id).where(Participant.group_id==gid)
    db.execute(update(ParticipantClaim).where(ParticipantClaim.participant_id.in_(people)).values(used=True))
    audit(db,user.id,'group.deleted',group.id);db.commit()

@router.post('/groups/{gid}/restore')
def restore_group(gid:str,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    group=db.scalar(select(Group).where(Group.id==gid).with_for_update())
    actor=db.scalar(select(Participant).where(Participant.group_id==gid,Participant.user_id==user.id))
    custody=bool(group and actor and group.owner_id==user.id and actor.role=='owner')
    if not group or not actor or actor.role not in ('owner','admin') or (not actor.active and not custody):raise HTTPException(403,'Solo i gestori del gruppo possono ripristinarlo')
    if not group.deleted:
        if if_match==group.metadata_version-1:return group_out(group)
        raise HTTPException(409,'Il gruppo non è nel cestino')
    if group.metadata_version!=if_match:raise HTTPException(409,'Il gruppo è cambiato: aggiorna il cestino')
    group.deleted=False;group.metadata_version+=1
    if custody:actor.active=True
    audit(db,user.id,'group.restored',group.id);db.commit()
    return group_out(group)
