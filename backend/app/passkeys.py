import json
import time
from urllib.parse import urlsplit
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import Field
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from webauthn import generate_registration_options, verify_registration_response, generate_authentication_options, verify_authentication_response, options_to_json
from webauthn.helpers import bytes_to_base64url, base64url_to_bytes
from webauthn.helpers.structs import AuthenticatorSelectionCriteria, UserVerificationRequirement, PublicKeyCredentialDescriptor
from .schemas import Strict
from .db import get_db
from .models import User, Passkey, WebChallenge, Session
from .security import current, gate, recent, audit, token, digest, set_cookie, throttle, peer
from .config import settings,normalize_origin
from .auth import user_out

router=APIRouter(prefix='/api/v1/auth/passkeys',tags=['Passkey'])


class EmailIn(Strict):
    email: str = Field(min_length=3, max_length=254)


class VerifyIn(Strict):
    challenge_id: str = Field(min_length=20, max_length=100)
    credential: dict
    name: str = Field(default='Passkey', max_length=100)


def canonical_passkey_origin(request):
    if normalize_origin(str(request.url.replace(path='',query='',fragment='')))!=settings.public_origin:
        raise HTTPException(400,'Per usare le passkey accedi dall’indirizzo principale: '+settings.public_origin)


def rp():
    return urlsplit(settings.public_origin).hostname


def save_challenge(db,user,purpose,options):
    clear=token()
    db.execute(delete(WebChallenge).where(WebChallenge.expires < time.time()))
    db.add(WebChallenge(id=digest(clear),user_id=user.id,purpose=purpose,challenge=bytes_to_base64url(options.challenge),expires=int(time.time())+300))
    db.commit()
    return {'challenge_id':clear,'options':json.loads(options_to_json(options))}


def consume(db,clear,purpose,user_id=None):
    row=db.execute(delete(WebChallenge).where(WebChallenge.id==digest(clear)).returning(WebChallenge.user_id,WebChallenge.purpose,WebChallenge.challenge,WebChallenge.expires)).first()
    # Commit consumption even when cryptographic verification fails.
    db.commit()
    if not row or row.purpose!=purpose or row.expires<=time.time() or (user_id and row.user_id!=user_id):
        raise HTTPException(400,'Richiesta passkey scaduta o già usata')
    return row


@router.post('/register/options')
def registration_options(request:Request,user=Depends(current),db=Depends(get_db)):
    recent(request)
    canonical_passkey_origin(request)
    from .account_security import locked_user
    user=locked_user(db,user.id)
    ensure_live_session(db,request,user)
    keys=list(db.scalars(select(Passkey).where(Passkey.user_id==user.id)))
    options=generate_registration_options(rp_id=rp(),rp_name='Sgancia',user_id=user.id.encode(),user_name=user.email,user_display_name=user.name,
        authenticator_selection=AuthenticatorSelectionCriteria(user_verification=UserVerificationRequirement.REQUIRED),
        exclude_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(k.credential_id)) for k in keys])
    return save_challenge(db,user,'register',options)


@router.post('/register/verify')
def registration_verify(body:VerifyIn,request:Request,user=Depends(current),db=Depends(get_db)):
    recent(request)
    canonical_passkey_origin(request)
    from .account_security import locked_user
    user=locked_user(db,user.id)
    ensure_live_session(db,request,user)
    row=consume(db,body.challenge_id,'register',user.id)
    user=locked_user(db,user.id)
    ensure_live_session(db,request,user)
    try:
        result=verify_registration_response(credential=body.credential,expected_challenge=base64url_to_bytes(row.challenge),expected_rp_id=rp(),expected_origin=settings.public_origin,require_user_verification=True)
    except Exception:
        raise HTTPException(400,'Verifica passkey fallita') from None
    db.add(Passkey(credential_id=bytes_to_base64url(result.credential_id),public_key=bytes_to_base64url(result.credential_public_key),sign_count=result.sign_count,user_id=user.id,name=body.name))
    audit(db,user.id,'passkey.added')
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Passkey già registrata') from None
    return {'ok':True}


@router.post('/login/options')
def login_options(body:EmailIn,request:Request,db=Depends(get_db),instance=Depends(gate)):
    canonical_passkey_origin(request)
    throttle(db,'passkey:'+peer(request),20)
    user=db.scalar(select(User).where(User.email==body.email.strip().lower(),User.status=='active'))
    if not user:
        raise HTTPException(400,'Passkey non disponibile per questo account')
    from .account_security import locked_user
    user=locked_user(db,user.id)
    keys=list(db.scalars(select(Passkey).where(Passkey.user_id==user.id)))
    if not keys:
        raise HTTPException(400,'Passkey non disponibile per questo account')
    options=generate_authentication_options(rp_id=rp(),user_verification=UserVerificationRequirement.REQUIRED,
        allow_credentials=[PublicKeyCredentialDescriptor(id=base64url_to_bytes(k.credential_id)) for k in keys])
    return save_challenge(db,user,'login',options)


@router.post('/login/verify')
def login_verify(body:VerifyIn,request:Request,response:Response,db=Depends(get_db),instance=Depends(gate)):
    canonical_passkey_origin(request)
    throttle(db,'passkey-verify:'+peer(request),20)
    from .account_security import locked_user
    preliminary=db.get(WebChallenge,digest(body.challenge_id))
    if not preliminary:raise HTTPException(400,'Verifica passkey fallita')
    user=locked_user(db,preliminary.user_id)
    row=consume(db,body.challenge_id,'login')
    user=locked_user(db,row.user_id)
    credential_id=body.credential.get('id','')
    key=db.scalar(select(Passkey).where(Passkey.credential_id==credential_id,Passkey.user_id==row.user_id).with_for_update())
    user=db.get(User,row.user_id)
    if not key or not user or user.status!='active':
        raise HTTPException(400,'Verifica passkey fallita')
    try:
        result=verify_authentication_response(credential=body.credential,expected_challenge=base64url_to_bytes(row.challenge),expected_rp_id=rp(),expected_origin=settings.public_origin,
            credential_public_key=base64url_to_bytes(key.public_key),credential_current_sign_count=key.sign_count,require_user_verification=True)
    except Exception:
        raise HTTPException(400,'Verifica passkey fallita') from None
    key.sign_count=result.new_sign_count
    clear,csrf=token(),token()
    old=db.get(Session,digest(request.cookies.get('sg_session','')))
    if old: db.delete(old)
    from .runtime_policy import policy,check_verified
    check_verified(db,user)
    from .runtime_policy import access_lifetime
    duration,cookie_age=access_lifetime(db,'session')
    db.add(Session(token_hash=digest(clear),csrf_hash=digest(csrf),user_id=user.id,expires=int(time.time())+duration,gate_version=instance.gate_version,auth_version=user.auth_version))
    audit(db,user.id,'session.passkey_created')
    db.commit()
    set_cookie(response,'sg_session',clear,cookie_age,request)
    set_cookie(response,'sg_csrf',csrf,cookie_age,request)
    return user_out(user,db)


@router.get('')
def list_keys(user=Depends(current),db=Depends(get_db)):
    return [{'id':k.credential_id,'name':k.name} for k in db.scalars(select(Passkey).where(Passkey.user_id==user.id))]


@router.delete('/{credential_id}',status_code=204)
def delete_key(credential_id:str,request:Request,user=Depends(current),db=Depends(get_db)):
    recent(request)
    from .account_security import locked_user,revoke_access
    user=locked_user(db,user.id)
    removed=db.execute(delete(Passkey).where(Passkey.credential_id==credential_id,Passkey.user_id==user.id)).rowcount
    if not removed:raise HTTPException(404,'Passkey non disponibile')
    revoke_access(db,user,request.state.session)
    audit(db,user.id,'passkey.removed')
    db.commit()


def ensure_live_session(db,request,user):
    row=db.scalar(select(Session).where(Session.token_hash==request.state.session.token_hash,Session.auth_version==user.auth_version,Session.expires>time.time()))
    if not row:raise HTTPException(401,'Sessione revocata: accedi nuovamente')
