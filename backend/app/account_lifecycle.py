"""Root-only account suspension and irreversible profile anonymization; ledger retained."""
from typing import Literal
from fastapi import APIRouter,Depends,Request,HTTPException
from pydantic import Field
from sqlalchemy import select,delete,update,or_
from .db import get_db
from .models import User,Instance,Group,Participant,GroupJoinCode,GroupOperation,GuestLink,GroupInvite,ParticipantClaim,InstallationPasskey,PlatformInvitationLink,Invite,Notification,NotificationPreference,PaymentMethod,Passkey,RecoveryCode,AccountToken,MailMessage,WebChallenge,TelegramLink,TelegramGrant,TelegramAction,TelegramOutbox
from .security import admin,throttle,audit,passwords,token
from .schemas import Strict
from .account_security import Proof,require_password,revoke_access
from .global_roles import locked_admin
from .admin_permissions import require_superadmin
from .superadmin import is_superadmin
router=APIRouter(prefix='/api/v1/admin/users',tags=['Ciclo di vita account — superadmin'])

class LifecycleIn(Proof):
    action:Literal['suspend','activate','delete']
    expected_status:Literal['active','suspended','pending']
    expected_auth_version:int=Field(ge=1)
    confirmation:str=Field(default='',max_length=254)


def custody_anchor(db,target):
    if not is_superadmin(db,target.id):return
    instance=db.get(Instance,1)
    others=list(db.scalars(select(User).where(User.id!=target.id,or_(User.superadmin.is_(True),User.id==instance.superadmin_id),User.admin.is_(True),User.status=='active',User.deleted.is_(False)).order_by(User.id).with_for_update()))
    if not others:raise HTTPException(409,'Non puoi sospendere o eliminare l’ultimo superadmin attivo')
    if not target.superadmin:target.superadmin=True
    if instance.superadmin_id==target.id:instance.superadmin_id=others[0].id;db.flush()


def candidates(db,group,target_id):
    return list(db.scalars(select(Participant).join(User,Participant.user_id==User.id).where(Participant.group_id==group.id,Participant.user_id!=target_id,Participant.active.is_(True),Participant.merged_into.is_(None),User.status=='active',User.deleted.is_(False)).order_by(Participant.id)))

@router.get('/{identity}/deletion-preview')
def preview(identity:str,user=Depends(admin),db=Depends(get_db)):
    require_superadmin(db,user);target=db.get(User,identity)
    if not target or target.deleted:raise HTTPException(404,'Account non disponibile')
    groups=list(db.scalars(select(Group).where(Group.owner_id==identity)))
    transferable=sum(bool(candidates(db,g,identity)) for g in groups)
    return {'owned_groups':len(groups),'transferable_groups':transferable,'groups_to_trash':len(groups)-transferable,'memberships':len(list(db.scalars(select(Participant.id).where(Participant.user_id==identity))))}


def erase_profile(db,target,actor):
    from .models import Friendship,FriendLink
    db.execute(delete(FriendLink).where(FriendLink.user_id==target.id))
    db.execute(delete(Friendship).where((Friendship.first_id==target.id)|(Friendship.second_id==target.id)))
    from .membership_ops import revoke
    # Group locks serialize account deletion with membership, ownership and invitation acceptance.
    gids=list(db.scalars(select(Group.id).where((Group.owner_id==target.id)|(Group.id.in_(select(Participant.group_id).where(Participant.user_id==target.id)))).order_by(Group.id)))
    for gid in gids:
        group=db.scalar(select(Group).where(Group.id==gid).with_for_update())
        people=list(db.scalars(select(Participant).where(Participant.group_id==gid,Participant.user_id==target.id).with_for_update()))
        if group.owner_id==target.id:
            options=candidates(db,group,target.id)
            rank={'admin':0,'member':1,'viewer':2,'owner':0}
            replacement=min(options,key=lambda p:(rank.get(p.role,3),p.id)) if options else None
            if replacement:replacement.role='owner';group.owner_id=replacement.user_id
            else:group.deleted=True
            db.execute(delete(GroupJoinCode).where(GroupJoinCode.group_id==gid));revoke(db,gid)
            db.execute(update(GuestLink).where(GuestLink.group_id==gid).values(revoked=True))
            db.add(GroupOperation(group_id=gid,actor_id=actor.id,kind='account_owner_removed',snapshot={'transferred':bool(replacement)}))
        for p in people:
            revoke(db,gid,p.id);p.user_id=None;p.active=False;p.role='member';p.name='Utente eliminato'
        group.metadata_version+=1
    hashes=list(db.scalars(select(AccountToken.token_hash).where(AccountToken.user_id==target.id)))
    if hashes:db.execute(delete(MailMessage).where(MailMessage.token_hash.in_(hashes)))
    for model in (InstallationPasskey,TelegramOutbox,TelegramAction,TelegramGrant,TelegramLink,WebChallenge,Passkey,RecoveryCode,AccountToken,PaymentMethod,Notification,NotificationPreference):
        db.execute(delete(model).where(model.user_id==target.id))
    db.execute(update(GroupInvite).where((GroupInvite.email==target.email)|(GroupInvite.issuer_id==target.id)).values(used=True))
    db.execute(update(ParticipantClaim).where((ParticipantClaim.email==target.email)|(ParticipantClaim.issuer_id==target.id)).values(used=True))
    db.execute(update(PlatformInvitationLink).where(PlatformInvitationLink.issuer_id==target.id).values(revoked=True))
    db.execute(update(Invite).where((Invite.issuer_id==target.id)|(Invite.email==target.email)).values(revoked=True))
    target.email='deleted-'+target.id+'@deleted.invalid';target.name='Account eliminato';target.password_hash=passwords.hash(token())
    target.avatar=None;target.avatar_icon='';target.avatar_version+=1;target.email_verified=False
    target.totp_secret=None;target.totp_pending=None;target.totp_last_counter=-1
    target.superadmin=False;target.admin=False;target.admin_permissions=[];target.requested_role='user';target.deleted=True;target.status='suspended'

@router.post('/{identity}/lifecycle')
def lifecycle(identity:str,body:LifecycleIn,request:Request,user=Depends(admin),db=Depends(get_db)):
    throttle(db,'account-lifecycle-proof:'+user.id,10)
    actor,target=locked_admin(db,request,user,identity);require_superadmin(db,actor)
    require_password(db,actor,body.password,body.code)
    if actor.id==target.id:raise HTTPException(403,'Un altro superadmin deve gestire la sospensione o eliminazione del tuo account')
    if target.deleted:raise HTTPException(409,'L’account è già eliminato e non può essere riattivato')
    if target.auth_version!=body.expected_auth_version or target.status!=body.expected_status:raise HTTPException(409,'Account modificato: aggiorna la lista')
    if body.action=='activate' and target.status=='pending':raise HTTPException(409,'Approva la richiesta dalla gestione registrazioni')
    if body.action!='activate':custody_anchor(db,target)
    if body.action=='suspend' and target.status=='pending':target.requested_role='user'
    if body.action=='delete':
        if body.confirmation!=target.email:raise HTTPException(422,'Per eliminare scrivi l’email esatta dell’account')
        erase_profile(db,target,actor)
    else:target.status='active' if body.action=='activate' else 'suspended'
    revoke_access(db,target)
    audit(db,actor.id,'account.'+body.action,target.id);db.commit();return {'status':target.status,'deleted':target.deleted}
