"""One explicit preview for membership invitations and existing-person associations."""
import time
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from .db import get_db
from .models import GroupInvite,ParticipantClaim,Participant,Group,Invite
from .security import current,recent,audit,digest,throttle
from .sharing import Accept
from pydantic import Field

class JoinAccept(Accept):
    participant_id:str|None=Field(default=None,max_length=36)
    name:str|None=Field(default=None,max_length=100)

from .invitations import check_group_invitation
router=APIRouter(prefix='/api/v1',tags=['Accesso ai gruppi'])


def issuer_valid(db,uid,gid):
    if not uid:return True # legacy invitations remain explicitly revocable by their managers
    person=db.scalar(select(Participant).where(Participant.user_id==uid,Participant.group_id==gid,Participant.active.is_(True)))
    from .models import User
    account=db.scalar(select(User).where(User.id==uid).execution_options(populate_existing=True))
    return bool(account and account.status=='active' and person and person.role in ('owner','admin'))


def preview_access(db,clear,user):
    from .group_codes import preview as code_preview
    data=code_preview(db,clear,user)
    if data:return data
    hashed=digest(clear.strip());inv=db.get(GroupInvite,hashed)
    if inv:
        group=db.get(Group,inv.group_id)
        if not group or group.deleted or group.state!='active' or inv.expires<=time.time() or (inv.email and inv.email!=user.email) or not issuer_valid(db,inv.issuer_id,group.id):raise HTTPException(404,'Invito non disponibile per questo account: controlla email, scadenza o chiedi un nuovo invito')
        existing=db.scalar(select(Participant).where(Participant.group_id==group.id,Participant.user_id==user.id,Participant.active.is_(True)))
        if inv.used and not (inv.accepted_user_id==user.id and existing):raise HTTPException(404,'Invito già usato o revocato')
        if not existing:check_group_invitation(db,inv,user.email)
        person=db.get(Participant,inv.participant_id) if inv.participant_id else None
        return {'kind':'invitation','group_id':group.id,'group':group.name,'role':existing.role if existing else inv.role,'person':person.name if person else None,'already_member':bool(existing),'expires':inv.expires,'message':'Sei già membro: apri il gruppo senza creare duplicati.' if existing else 'Collegherai il tuo account alla persona esistente, conservando saldi e cronologia.' if person else 'Diventerai un nuovo membro del gruppo con il tuo account.'}
    from .models import PlatformInvitationLink
    platform=db.scalar(select(PlatformInvitationLink).where(PlatformInvitationLink.token_hash==hashed))
    single=db.get(Invite,hashed)
    if platform or single:
        return {'kind':'platform_registration','group_id':'','group':'Invito alla piattaforma','role':'user','person':None,'already_member':True,'expires':(platform or single).expires,'message':'Questo link serve a creare un nuovo account Sgancia, non a entrare in un gruppo o cambiare il ruolo di un account esistente. Hai già effettuato l’accesso: puoi continuare con il tuo account.'}
    claim=db.get(ParticipantClaim,hashed)
    if claim:
        person=db.get(Participant,claim.participant_id);group=db.get(Group,person.group_id) if person else None
        if claim.used or claim.expires<=time.time() or claim.email!=user.email or not person or not person.active or person.user_id or person.merged_into or not group or group.deleted or group.state!='active' or not issuer_valid(db,claim.issuer_id,group.id):raise HTTPException(404,'Associazione non disponibile per questo account')
        if db.scalar(select(Participant.id).where(Participant.group_id==group.id,Participant.user_id==user.id)):raise HTTPException(409,'Hai già una persona nel gruppo: chiedi al gestore una fusione controllata, senza sostituire altri account')
        return {'kind':'association','group_id':group.id,'group':group.name,'role':person.role,'person':person.name,'already_member':False,'expires':claim.expires,'message':'Collegherai il tuo account a questa persona senza account. ID, saldi, spese e pubblico restano conservati.'}
    raise HTTPException(404,'Codice non valido: usa un invito per membri o un codice di associazione. I link ospiti si aprono separatamente in sola lettura.')


@router.post('/group-access/preview')
def preview(body:Accept,user=Depends(current),db=Depends(get_db)):
    throttle(db,'group-access:'+user.id,30)
    return preview_access(db,body.token,user)


@router.post('/group-access/accept')
def accept(body:JoinAccept,user=Depends(current),db=Depends(get_db)):
    throttle(db,'group-access:'+user.id,30)
    from .account_security import live_group_user
    user=live_group_user(db,user)
    data=preview_access(db,body.token,user)
    if data['kind']=='platform_registration':raise HTTPException(422,'Questo invito serve solo a registrarsi alla piattaforma')
    db.scalar(select(Group).where(Group.id==data['group_id']).with_for_update())
    db.expire_all()
    data=preview_access(db,body.token,user)
    if data['kind']=='group_code':
        from .group_codes import join
        return join(db,body,user,data)
    if body.participant_id or body.name is not None:raise HTTPException(422,'Questo invito non permette di scegliere una persona')
    if data['already_member']:return {'group_id':data['group_id'],'already_member':True}
    if data['kind']=='association':
        from .lifecycle import claim,TokenIn
        return claim(TokenIn(token=body.token.strip()),user,db)
    from .sharing import accept as accept_invitation
    return accept_invitation(Accept(token=body.token.strip()),user,db)


@router.get('/groups/{gid}/access-invitations')
def list_invitations(gid:str,user=Depends(current),db=Depends(get_db)):
    from .groups import membership
    membership(db,gid,user,manage=True)
    now=time.time()
    return [{'id':i.id,'role':i.role,'expires':i.expires,'used':i.used,'expired':i.expires<=now,'association':bool(i.participant_id)} for i in db.scalars(select(GroupInvite).where(GroupInvite.group_id==gid).order_by(GroupInvite.expires.desc()).limit(100))]


@router.delete('/groups/{gid}/access-invitations/{iid}',status_code=204)
def revoke_invitation(gid:str,iid:str,user=Depends(current),db=Depends(get_db)):
    from .groups import membership
    db.scalar(select(Group).where(Group.id==gid).with_for_update());membership(db,gid,user,manage=True)
    row=db.scalar(select(GroupInvite).where(GroupInvite.group_id==gid,GroupInvite.id==iid))
    if not row:raise HTTPException(404,'Invito non trovato')
    row.used=True;row.accepted_user_id=None
    registration=db.get(Invite,row.token_hash)
    if registration:registration.used=True
    audit(db,user.id,'group_invitation.revoked');db.commit()


@router.get('/groups/{gid}/join-codes')
def group_codes(gid:str,user=Depends(current),db=Depends(get_db)):
    from .group_codes import codes
    return codes(db,gid,user)

@router.post('/groups/{gid}/join-codes/{role}/rotate')
def rotate_code(gid:str,role:str,user=Depends(current),db=Depends(get_db)):
    from .group_codes import codes
    return codes(db,gid,user,role)
