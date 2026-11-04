"""Reusable group capabilities. Never grant installation or owner privileges."""
from fastapi import HTTPException
from sqlalchemy import select
from .models import GroupJoinCode,Group,Participant
from .security import token,digest,cipher,audit


def codes(db,gid,user,rotate=None):
    from .groups import membership
    db.scalar(select(Group).where(Group.id==gid).with_for_update())
    group,actor=membership(db,gid,user)
    manager=actor.role in ('owner','admin')
    if group.state!='active':raise HTTPException(409,'Gruppo non attivo')
    if rotate and (not manager or rotate not in ('admin','member','viewer')):raise HTTPException(403,'Solo gli admin del gruppo possono rigenerare i codici')
    roles=('member','viewer','admin') if manager else ('member','viewer') if actor.role=='member' else ('viewer',)
    rows={r.role:r for r in db.scalars(select(GroupJoinCode).where(GroupJoinCode.group_id==gid))}
    for role in ('member','viewer','admin'):
        if role not in rows:
            clear=token();row=GroupJoinCode(group_id=gid,role=role,token_hash=digest(clear),secret=cipher().encrypt(clear.encode()));db.add(row);rows[role]=row
        elif role==rotate:
            clear=token();rows[role].token_hash=digest(clear);rows[role].secret=cipher().encrypt(clear.encode())
    if rotate:audit(db,user.id,'group.code_rotated',gid)
    result=[{'role':role,'token':cipher().decrypt(rows[role].secret).decode()} for role in roles]
    db.commit();return result


def preview(db,clear,user):
    row=db.get(GroupJoinCode,digest(clear.strip()))
    if not row:return None
    group=db.get(Group,row.group_id)
    if not group or group.deleted or group.state!='active':raise HTTPException(404,'Codice gruppo non disponibile')
    existing=db.scalar(select(Participant).where(Participant.group_id==group.id,Participant.user_id==user.id))
    if existing and (not existing.active or existing.merged_into):raise HTTPException(403,'Partecipazione disattivata: contatta un admin del gruppo')
    people=[] if existing else [{'id':p.id,'name':p.name} for p in db.scalars(select(Participant).where(Participant.group_id==group.id,Participant.user_id.is_(None),Participant.active.is_(True),Participant.merged_into.is_(None)).order_by(Participant.name,Participant.id))]
    return {'kind':'group_code','group_id':group.id,'group':group.name,'role':existing.role if existing else row.role,'person':None,'already_member':bool(existing),'expires':None,'virtuals':people,'message':'Sei già nel gruppo: il tuo ruolo non cambia.' if existing else 'Entra come nuova persona oppure collega una persona senza account. Collegandola acquisisci i suoi saldi, le spese e il pubblico riservato: scegli solo la tua persona.'}


def join(db,body,user,data):
    if data['already_member']:return {'group_id':data['group_id'],'already_member':True}
    gid=data['group_id']
    name=body.name.strip() if body.name else None
    if body.name is not None and not name:raise HTTPException(422,'Inserisci un nome valido')
    if body.participant_id:
        person=db.scalar(select(Participant).where(Participant.id==body.participant_id,Participant.group_id==gid).with_for_update())
        if not person or person.user_id or not person.active or person.merged_into:raise HTTPException(409,'Persona non più disponibile: aggiorna l’anteprima')
        from .membership_ops import revoke
        revoke(db,gid,person.id)
        person.user_id=user.id;person.role=data['role']
        if name:person.name=name
    else:
        person=Participant(group_id=gid,user_id=user.id,role=data['role'],name=name or user.name);db.add(person)
    audit(db,user.id,'group.code_joined',gid);db.commit();return {'group_id':gid}
