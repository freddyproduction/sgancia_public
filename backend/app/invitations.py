"""Group invitation checks shared by registration and authenticated acceptance."""
import time
from fastapi import HTTPException
from sqlalchemy import select
from .models import Group, Participant, GroupInvite


def check_group_invitation(db, invitation, email,new_account=False):
    if not invitation or invitation.used or invitation.expires <= time.time() or (invitation.email and invitation.email != email):
        raise HTTPException(403, 'Invito scaduto, già usato o destinato a un’altra email')
    group = db.scalar(select(Group).where(Group.id == invitation.group_id).with_for_update().execution_options(populate_existing=True))
    if not group or group.deleted or group.state != 'active':
        raise HTTPException(409, 'Il gruppo dell’invito non è attivo')
    from .group_access import issuer_valid
    if not issuer_valid(db,invitation.issuer_id,group.id):raise HTTPException(403,'Invito non più autorizzato dal gestore')
    if new_account and invitation.issuer_id:
        from .models import User
        issuer=db.get(User,invitation.issuer_id)
        if not issuer or not issuer.admin:raise HTTPException(403,'Invito di registrazione non più autorizzato: chiedi un nuovo codice')
    if invitation.participant_id:
        person = db.scalar(select(Participant).where(Participant.id == invitation.participant_id, Participant.group_id == group.id).with_for_update())
        if not person or not person.active or person.merged_into or person.user_id is not None:
            raise HTTPException(409, 'La persona da collegare ha già un account: chiedi un nuovo invito')
    return group


def join_from_invitation(db, invitation, user):
    group = check_group_invitation(db, invitation, user.email)
    if db.scalar(select(Participant.id).where(Participant.group_id == group.id, Participant.user_id == user.id)):
        raise HTTPException(409, 'Sei già nel gruppo')
    if invitation.participant_id:
        person = db.get(Participant, invitation.participant_id)
        from .membership_ops import revoke
        revoke(db,group.id,person.id)
        person.user_id = user.id
        person.role = invitation.role
    else:
        person = Participant(group_id=group.id, name=user.name, user_id=user.id, role=invitation.role)
        db.add(person)
    invitation.used = True
    invitation.accepted_user_id=user.id
    return group


def lock_invitation_group(db,token_hash):
    invitation=db.get(GroupInvite,token_hash)
    if invitation:
        db.scalar(select(Group).where(Group.id==invitation.group_id).with_for_update())
