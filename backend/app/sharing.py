import time
import base64,json,hmac
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import Field
from sqlalchemy import select
from typing import Literal
from .schemas import Strict
from .db import get_db
from .security import recent,current,digest,token,passwords,verify,throttle,peer,audit
from .groups import membership
from .models import GuestLink,GroupInvite,Group,Participant,Expense,Invite,Instance,Attachment,ExpenseRevision
from .invitations import join_from_invitation,lock_invitation_group
from .config import settings
from .guest_policy import require_guest_links

router=APIRouter(prefix='/api/v1',tags=['Inviti e ospiti'])


class GuestIn(Strict):
    days:int=Field(default=7,ge=1,le=365)
    password:str=Field(default='',max_length=128)
    max_uses:int|None=Field(default=None,ge=1,le=100000)
    show_names:bool=True
    show_details:bool=True
    show_attachments:bool=False
    show_exports:bool=False


class GuestRead(Strict):
    token:str=Field(min_length=20,max_length=100)
    password:str=Field(default='',max_length=128)


class InviteIn(Strict):
    email:str|None=Field(default=None,max_length=254)
    role:Literal['admin','member','viewer']='member'
    registration:bool=False
    participant_id:str|None=Field(default=None,max_length=36)


class Accept(Strict):
    token:str=Field(min_length=20,max_length=100)


@router.post('/groups/{group_id}/guest-links',status_code=201)
def create_guest(group_id:str,body:GuestIn,request:Request,user=Depends(current),db=Depends(get_db)):
    membership(db,group_id,user,write=True,manage=True)
    require_guest_links(db)
    from .runtime_policy import policy
    limits=policy(db)
    if body.days>limits['guest_days'] or (body.max_uses is None and not limits['guest_allow_unlimited']) or (body.max_uses is not None and body.max_uses>limits['guest_max_uses']):raise HTTPException(422,'Il link supera i limiti ospiti dell’installazione')
    if body.show_attachments and not(body.show_names and body.show_details):raise HTTPException(422,'Per condividere allegati abilita anche nomi e dettagli: i file possono contenerli')
    clear=token()
    link=GuestLink(group_id=group_id,token_hash=digest(clear),password_hash=passwords.hash(body.password) if body.password else None,expires=int(time.time())+body.days*86400,max_uses=body.max_uses,show_names=body.show_names,show_details=body.show_details,show_attachments=body.show_attachments,show_exports=body.show_exports)
    db.add(link)
    db.flush()
    audit(db,user.id,'guest_link.created',link.id)
    db.commit()
    return {'id':link.id,'url':request.headers.get('origin',settings.public_origin)+'/guest#'+clear,'expires':link.expires}


@router.get('/groups/{group_id}/guest-links')
def list_links(group_id:str,user=Depends(current),db=Depends(get_db)):
    membership(db,group_id,user,manage=True)
    return [{'id':g.id,'expires':g.expires,'revoked':g.revoked,'uses':g.uses,'max_uses':g.max_uses,'show_attachments':g.show_attachments,'show_exports':g.show_exports} for g in db.scalars(select(GuestLink).where(GuestLink.group_id==group_id))]


@router.delete('/groups/{group_id}/guest-links/{link_id}',status_code=204)
def revoke(group_id:str,link_id:str,user=Depends(current),db=Depends(get_db)):
    membership(db,group_id,user,manage=True)
    link=db.scalar(select(GuestLink).where(GuestLink.id==link_id,GuestLink.group_id==group_id))
    if not link: raise HTTPException(404,'Link non trovato')
    link.revoked=True
    audit(db,user.id,'guest_link.revoked',link.id)
    db.commit()


@router.post('/guest/view')
def guest_view(body:GuestRead,request:Request,db=Depends(get_db)):
    # Body transport avoids leaking bearer tokens into URL/access/referrer logs.
    throttle(db,'guest:'+peer(request),30)
    return guest_projection(body,db)


def guest_projection(body,db,commit=True,require_exports=False):
    require_guest_links(db)
    initial=db.scalar(select(GuestLink).where(GuestLink.token_hash==digest(body.token)))
    if not initial:raise HTTPException(404,'Link scaduto, revocato o non valido')
    group=db.scalar(select(Group).where(Group.id==initial.group_id).with_for_update(read=True).execution_options(populate_existing=True))
    link=db.scalar(select(GuestLink).where(GuestLink.id==initial.id).with_for_update().execution_options(populate_existing=True))
    if not group or group.deleted or not link or link.revoked or link.expires<=time.time() or (link.max_uses is not None and link.uses>=link.max_uses) or (require_exports and not link.show_exports):
        raise HTTPException(404,'Link scaduto, revocato o non valido')
    if link.password_hash and not verify(link.password_hash,body.password):raise HTTPException(403,'Password ospite richiesta o non valida')
    link.uses+=1
    people=list(db.scalars(select(Participant).where(Participant.group_id==group.id).order_by(Participant.id)))
    names={p.id:p.name if link.show_names else f'Persona {i+1}' for i,p in enumerate(people)}
    # Secret records never enter guest projections, counts or amounts.
    rows=[e for e in db.scalars(select(Expense).where(Expense.group_id==group.id).order_by(Expense.date.desc())) if e.audience is None and not e.deleted]
    expenses=[]
    for e in rows:
        files=[]
        if link.show_attachments and link.show_names and link.show_details:
            from .attachments import output
            files=[output(a) for a in db.scalars(select(Attachment).where(Attachment.expense_id==e.id,Attachment.group_id==group.id,Attachment.deleted.is_(False))) if db.get(ExpenseRevision,(a.expense_id,a.expense_revision)).snapshot.get('audience') is None]
        expenses.append({'title':e.title if link.show_details else 'Spesa condivisa','date':e.date,'total':e.total,'category':e.category if link.show_details else None,'attachments':files})
    result={'name':group.name,'currency':group.currency,'read_only':True,'participants':list(names.values()),'expenses':expenses,'total':sum(e.total for e in rows),'can_export':link.show_exports,'file_access':guest_file_token(link) if link.show_attachments else None}
    if commit:db.commit()
    return result


@router.post('/groups/{group_id}/invitations',status_code=201)
def invite(group_id:str,body:InviteIn,request:Request,user=Depends(current),db=Depends(get_db)):
    membership(db,group_id,user,write=True,manage=True)
    email=body.email.strip().lower() if body.email and body.email.strip() else None
    if email:
        from .schemas import Credentials
        try:email=Credentials.email_valid(email)
        except ValueError:raise HTTPException(422,'Email destinatario non valida') from None
    if body.registration:
        from .admin_permissions import require_permission
        require_permission(db,user,'registrations')
        if not user.admin:
            raise HTTPException(403,'Solo l’amministratore dell’installazione può invitare nuovi account')
        recent(request)
        if db.get(Instance,1).registration=='disabled':
            raise HTTPException(403,'Le registrazioni sono disabilitate nelle impostazioni')
        if not email:raise HTTPException(422,'Per un nuovo account indica l’email del destinatario')
    if body.participant_id:
        if not email:raise HTTPException(422,'Per collegare una persona esistente è richiesta l’email destinatario')
        person=db.get(Participant,body.participant_id)
        if not person or person.group_id!=group_id or not person.active or person.merged_into or person.user_id is not None:
            raise HTTPException(409,'Partecipante senza account non disponibile')
    clear=token()
    from .runtime_policy import policy
    duration=policy(db)['invitation_days']*86400
    expires=int(time.time())+duration
    db.add(GroupInvite(token_hash=digest(clear),group_id=group_id,role=body.role,email=email,expires=expires,participant_id=body.participant_id,issuer_id=user.id))
    if body.registration:
        db.add(Invite(token_hash=digest(clear),email=email,expires=expires))
    audit(db,user.id,'group_invitation.created')
    db.commit()
    origin=request.headers.get('origin',settings.public_origin)
    return {'token':clear,'expires_in':duration,'kind':'account_and_group' if body.registration else 'group', 'url':origin+'/invite'+('?register=1' if body.registration else '')+'#'+clear}


@router.post('/invitations/accept')
def accept(body:Accept,user=Depends(current),db=Depends(get_db)):
    lock_invitation_group(db,digest(body.token.strip()))
    registration=db.scalar(select(Invite).where(Invite.token_hash==digest(body.token.strip())).with_for_update())
    invitation=db.scalar(select(GroupInvite).where(GroupInvite.token_hash==digest(body.token.strip())).with_for_update().execution_options(populate_existing=True))
    if not invitation or invitation.used or invitation.expires<=time.time() or (invitation.email and invitation.email!=user.email):
        raise HTTPException(404,'Questo codice non è un invito al gruppo: controlla il tipo di invito ricevuto')
    from .group_access import issuer_valid
    if not issuer_valid(db,invitation.issuer_id,invitation.group_id):raise HTTPException(404,'Invito revocato: chiedi un nuovo invito al gestore')
    group=join_from_invitation(db,invitation,user)
    invitation.accepted_user_id=user.id
    if registration:registration.used=True
    audit(db,user.id,'group_invitation.accepted',group.id)
    db.commit()
    return {'group_id':group.id}


def guest_file_token(link):
    from .exchange import sign
    return sign({'purpose':'guest-files','link':link.id,'expires':min(link.expires,int(time.time())+300),'nonce':token()})

class GuestFileIn(GuestRead):
    view_token:str=Field(min_length=20,max_length=2000)
    preview:bool=False

@router.post('/guest/attachments/{aid}')
def guest_attachment(aid:str,body:GuestFileIn,request:Request,db=Depends(get_db)):
    from .exchange import signature
    from .attachments import content
    throttle(db,'guest-files:'+peer(request),100)
    require_guest_links(db)
    link=db.scalar(select(GuestLink).where(GuestLink.token_hash==digest(body.token)).with_for_update())
    if not link or db.get(Group,link.group_id).deleted or link.revoked or link.expires<=time.time() or not(link.show_attachments and link.show_details and link.show_names):raise HTTPException(404,'Allegato non disponibile')
    if link.password_hash and not verify(link.password_hash,body.password):raise HTTPException(403,'Password ospite richiesta o non valida')
    try:
        encoded,mac=body.view_token.split('.')
        raw=base64.urlsafe_b64decode(encoded)
        if not hmac.compare_digest(signature(raw),mac):raise ValueError()
        grant=json.loads(raw)
        if grant['purpose']!='guest-files' or grant['link']!=link.id or grant['expires']<=time.time():raise ValueError()
    except Exception:raise HTTPException(404,'Apri nuovamente il link ospite per accedere ai file') from None
    row=db.get(Attachment,aid)
    expense=db.get(Expense,row.expense_id) if row and row.expense_id else None
    if not row or row.group_id!=link.group_id or row.deleted or not expense or expense.group_id!=link.group_id or expense.deleted or expense.audience is not None:raise HTTPException(404,'Allegato non disponibile')
    from .models import ExpenseRevision
    if db.get(ExpenseRevision,(row.expense_id,row.expense_revision)).snapshot.get('audience') is not None:raise HTTPException(404,'Allegato non disponibile')
    if body.preview and not row.preview_size:raise HTTPException(404,'Anteprima non disponibile')
    return content(row,body.preview)
