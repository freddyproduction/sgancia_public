import json
from fastapi import APIRouter,Depends,HTTPException,Header,Response
from pydantic import Field
from sqlalchemy import select,func
from .models import PaymentMethod,Participant
from .schemas import Strict
from .db import get_db
from .security import current,cipher,audit,throttle
from .group_settings import normalize_image
from .groups import membership
from .finance import finance_view
router=APIRouter(prefix='/api/v1',tags=['Metodi di pagamento account'])

class MethodIn(Strict):
    label:str=Field(min_length=1,max_length=100)
    instructions:str=Field(min_length=1,max_length=4000)
    shared:bool=False
    image:str|None=Field(default=None,max_length=2_800_000)


def output(row,base='/api/v1/account/payment-methods'):
    value=json.loads(cipher().decrypt(row.payload.encode()))
    return {'id':row.id,**value,'shared':row.shared,'version':row.version,'image_url':f'{base}/{row.id}/image?v={row.version}' if row.image else None}


def own(db,mid,user):
    row=db.get(PaymentMethod,mid)
    if not row or row.user_id!=user.id:raise HTTPException(404,'Metodo non disponibile')
    return row


def apply(row,body,user):
    if not body.label.strip() or not body.instructions.strip():raise HTTPException(422,'Compila nome e istruzioni')
    if body.shared and not user.email_verified:raise HTTPException(403,'Verifica la tua email prima di condividere i metodi di pagamento')
    row.payload=cipher().encrypt(json.dumps({'label':body.label.strip(),'instructions':body.instructions.strip()},ensure_ascii=False).encode()).decode();row.shared=body.shared
    if 'image' in body.model_fields_set:row.image=normalize_image(body.image) if body.image else None


@router.get('/account/payment-methods')
def methods(user=Depends(current),db=Depends(get_db)):
    return [output(row) for row in db.scalars(select(PaymentMethod).where(PaymentMethod.user_id==user.id).order_by(PaymentMethod.id))]


@router.post('/account/payment-methods',status_code=201)
def create(body:MethodIn,user=Depends(current),db=Depends(get_db)):
    throttle(db,'payment-method-write:'+user.id,30,60)
    from .account_security import locked_user
    user=locked_user(db,user.id)
    row=PaymentMethod(user_id=user.id);apply(row,body,user);check_image_quota(db,user,row); db.add(row);db.flush();audit(db,user.id,'payment_method.created',row.id);db.commit();return output(row)


@router.put('/account/payment-methods/{mid}')
def edit(mid:str,body:MethodIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    throttle(db,'payment-method-write:'+user.id,30,60)
    from .account_security import locked_user
    user=locked_user(db,user.id)
    row=db.scalar(select(PaymentMethod).where(PaymentMethod.id==mid,PaymentMethod.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Metodo non disponibile')
    if row.version!=if_match:raise HTTPException(409,'Metodo modificato: aggiorna prima di salvare')
    apply(row,body,user);check_image_quota(db,user,row);row.version+=1;audit(db,user.id,'payment_method.updated',row.id);db.commit();return output(row)


@router.delete('/account/payment-methods/{mid}',status_code=204)
def remove(mid:str,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    throttle(db,'payment-method-write:'+user.id,30,60)
    from .account_security import locked_user
    user=locked_user(db,user.id)
    row=db.scalar(select(PaymentMethod).where(PaymentMethod.id==mid,PaymentMethod.user_id==user.id).with_for_update())
    if not row:raise HTTPException(404,'Metodo non disponibile')
    if row.version!=if_match:raise HTTPException(409,'Metodo modificato: aggiorna prima di eliminarlo')
    db.delete(row);audit(db,user.id,'payment_method.deleted',mid);db.commit()


@router.get('/account/payment-methods/{mid}/image')
def own_image(mid:str,user=Depends(current),db=Depends(get_db)):
    row=own(db,mid,user)
    if not row.image:raise HTTPException(404)
    return Response(row.image,media_type='image/webp')


def creditor(db,gid,pid,user):
    _,actor=membership(db,gid,user);person=db.get(Participant,pid)
    if not person or person.group_id!=gid or not person.user_id or not any(t['from']==actor.id and t['to']==pid for t in finance_view(db,gid,user)['transfers']):raise HTTPException(404,'Recapiti non disponibili per questo saldo')
    from .models import User
    owner=db.get(User,person.user_id)
    if not owner.email_verified:raise HTTPException(404,'Recapiti non disponibili per questo saldo')
    return person


@router.get('/groups/{gid}/participants/{pid}/payment-methods')
def recipient_methods(gid:str,pid:str,user=Depends(current),db=Depends(get_db)):
    person=creditor(db,gid,pid,user)
    base=f'/api/v1/groups/{gid}/participants/{pid}/payment-methods'
    return [output(row,base) for row in db.scalars(select(PaymentMethod).where(PaymentMethod.user_id==person.user_id,PaymentMethod.shared.is_(True)))]


@router.get('/groups/{gid}/participants/{pid}/payment-methods/{mid}/image')
def recipient_image(gid:str,pid:str,mid:str,user=Depends(current),db=Depends(get_db)):
    person=creditor(db,gid,pid,user);row=db.get(PaymentMethod,mid)
    if not row or row.user_id!=person.user_id or not row.shared or not row.image:raise HTTPException(404,'Immagine non disponibile')
    return Response(row.image,media_type='image/webp')


def check_image_quota(db,user,row):
    with db.no_autoflush:
        total=sum(len(p.image or b'') for p in db.scalars(select(PaymentMethod).where(PaymentMethod.user_id==user.id)) if p.id!=row.id)+len(row.image or b'')
    if total>25*1024*1024:raise HTTPException(413,'Spazio immagini account esaurito: massimo 25 MiB')
