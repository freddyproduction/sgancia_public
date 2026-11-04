"""Discoverable, user-verifying passkeys unlock the gate, never an account session."""
import json,time
from fastapi import APIRouter,Depends,HTTPException,Request,Response
from sqlalchemy import select,delete
from sqlalchemy.exc import IntegrityError
from webauthn import generate_registration_options,generate_authentication_options,verify_registration_response,verify_authentication_response,options_to_json
from webauthn.helpers import bytes_to_base64url,base64url_to_bytes
from webauthn.helpers.structs import AuthenticatorSelectionCriteria,UserVerificationRequirement,ResidentKeyRequirement,PublicKeyCredentialDescriptor
from .db import get_db
from .models import InstallationPasskey as Key,InstallationChallenge as Challenge,Instance,User,GateGrant
from .security import current,recent,throttle,peer,token,digest,set_cookie,audit
from .passkeys import canonical_passkey_origin,rp,VerifyIn,ensure_live_session
from .config import settings
router=APIRouter(prefix='/api/v1/auth/installation-passkeys',tags=['Passkey installazione'])


def challenge(db,options,purpose,instance,user=None):
    clear=token();db.execute(delete(Challenge).where(Challenge.expires<time.time()))
    db.add(Challenge(id=digest(clear),user_id=user.id if user else None,purpose=purpose,challenge=bytes_to_base64url(options.challenge),gate_version=instance.gate_version,auth_version=user.auth_version if user else None,expires=int(time.time())+300));db.commit()
    return {'challenge_id':clear,'options':json.loads(options_to_json(options))}


def consume(db,clear,purpose):
    row=db.execute(delete(Challenge).where(Challenge.id==digest(clear)).returning(Challenge.user_id,Challenge.purpose,Challenge.challenge,Challenge.gate_version,Challenge.auth_version,Challenge.expires)).first();db.commit()
    if not row or row.purpose!=purpose or row.expires<=time.time():raise HTTPException(400,'Richiesta scaduta o già usata')
    return row


def instance_lock(db):
    instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update(read=True).execution_options(populate_existing=True))
    if not instance or not instance.gate_enabled:raise HTTPException(409,'La chiave di installazione non è attiva')
    return instance


def owner_lock(db,uid):
    user=db.scalar(select(User).where(User.id==uid).with_for_update().execution_options(populate_existing=True))
    if not user or user.status!='active':raise HTTPException(400,'Passkey non disponibile')
    return user


@router.get('')
def keys(user=Depends(current),db=Depends(get_db)):
    instance=db.get(Instance,1)
    return [{'id':k.credential_id,'name':k.name,'active':k.gate_version==instance.gate_version and k.auth_version==user.auth_version} for k in db.scalars(select(Key).where(Key.user_id==user.id))]


@router.post('/register/options')
def registration_options(request:Request,user=Depends(current),db=Depends(get_db)):
    recent(request);canonical_passkey_origin(request);instance=instance_lock(db);user=owner_lock(db,user.id);ensure_live_session(db,request,user)
    existing=list(db.scalars(select(Key).where(Key.user_id==user.id)))
    if len(existing)>=20:raise HTTPException(409,'Rimuovi una passkey prima di aggiungerne altre')
    options=generate_registration_options(rp_id=rp(),rp_name='Sgancia · accesso installazione',user_id=('installation:'+user.id).encode(),user_name='Installazione · '+user.email,user_display_name='Accesso installazione · '+user.name,
        authenticator_selection=AuthenticatorSelectionCriteria(resident_key=ResidentKeyRequirement.REQUIRED,require_resident_key=True,user_verification=UserVerificationRequirement.REQUIRED),exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(k.credential_id)) for k in existing])
    return challenge(db,options,'register',instance,user)


@router.post('/register/verify')
def registration_verify(body:VerifyIn,request:Request,user=Depends(current),db=Depends(get_db)):
    recent(request);canonical_passkey_origin(request);row=consume(db,body.challenge_id,'register');instance=instance_lock(db);user=owner_lock(db,user.id);ensure_live_session(db,request,user)
    if row.user_id!=user.id or row.auth_version!=user.auth_version or row.gate_version!=instance.gate_version:raise HTTPException(400,'Autorizzazione modificata: ripeti la registrazione')
    if len(list(db.scalars(select(Key).where(Key.user_id==user.id))))>=20:raise HTTPException(409,'Troppe passkey')
    try:result=verify_registration_response(credential=body.credential,expected_challenge=base64url_to_bytes(row.challenge),expected_rp_id=rp(),expected_origin=settings.public_origin,require_user_verification=True)
    except Exception:raise HTTPException(400,'Verifica passkey fallita') from None
    # WebAuthn verification enforces the requested UV; resident credentials are requested at creation.
    db.add(Key(credential_id=bytes_to_base64url(result.credential_id),public_key=bytes_to_base64url(result.credential_public_key),sign_count=result.sign_count,user_id=user.id,name=body.name or 'Accesso installazione',gate_version=instance.gate_version,auth_version=user.auth_version));audit(db,user.id,'installation_passkey.added')
    try:db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'Passkey già registrata') from None
    return {'ok':True}


@router.post('/unlock/options')
def unlock_options(request:Request,db=Depends(get_db)):
    canonical_passkey_origin(request);throttle(db,'gate-passkey:'+peer(request),20);instance=instance_lock(db)
    return challenge(db,generate_authentication_options(rp_id=rp(),user_verification=UserVerificationRequirement.REQUIRED),'unlock',instance)


@router.post('/unlock/verify')
def unlock_verify(body:VerifyIn,request:Request,response:Response,db=Depends(get_db)):
    canonical_passkey_origin(request);throttle(db,'gate-passkey-verify:'+peer(request),20);row=consume(db,body.challenge_id,'unlock');instance=instance_lock(db)
    first=db.get(Key,body.credential.get('id',''))
    if not first:raise HTTPException(400,'Verifica passkey fallita')
    user=owner_lock(db,first.user_id)
    key=db.scalar(select(Key).where(Key.credential_id==first.credential_id).with_for_update().execution_options(populate_existing=True))
    if not key or row.gate_version!=instance.gate_version or key.gate_version!=instance.gate_version or key.auth_version!=user.auth_version:raise HTTPException(400,'Passkey revocata: usa la chiave di installazione')
    try:
        result=verify_authentication_response(credential=body.credential,expected_challenge=base64url_to_bytes(row.challenge),expected_rp_id=rp(),expected_origin=settings.public_origin,credential_public_key=base64url_to_bytes(key.public_key),credential_current_sign_count=key.sign_count,require_user_verification=True)
        handle=body.credential.get('response',{}).get('userHandle')
        if handle and base64url_to_bytes(handle)!=('installation:'+user.id).encode():raise ValueError()
    except Exception:raise HTTPException(400,'Verifica passkey fallita') from None
    from .runtime_policy import access_lifetime
    duration,cookie_age=access_lifetime(db,'gate')
    key.sign_count=result.new_sign_count;clear=token();db.add(GateGrant(token_hash=digest(clear),expires=int(time.time())+duration,version=instance.gate_version,credential_id=key.credential_id));audit(db,user.id,'installation_passkey.unlocked');db.commit();set_cookie(response,'sg_gate',clear,cookie_age,request)
    return {'registration':instance.registration}


@router.delete('/{credential_id}',status_code=204)
def remove(credential_id:str,request:Request,user=Depends(current),db=Depends(get_db)):
    recent(request);user=owner_lock(db,user.id);ensure_live_session(db,request,user)
    key=db.get(Key,credential_id)
    if not key or key.user_id!=user.id:raise HTTPException(404,'Passkey non disponibile')
    db.execute(delete(GateGrant).where(GateGrant.credential_id==credential_id));db.delete(key);audit(db,user.id,'installation_passkey.removed');db.commit()
