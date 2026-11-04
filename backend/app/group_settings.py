import base64
import io
from fastapi import APIRouter,Depends,HTTPException,Header,Response
from pydantic import Field
from sqlalchemy import select
from PIL import Image,ImageOps,UnidentifiedImageError
from .db import get_db
from .schemas import Strict
from .models import Group,Expense,ExpenseRevision,Entry
from .security import current,audit
from .groups import membership,group_out,visible
router=APIRouter(prefix='/api/v1/groups',tags=['Impostazioni gruppo e cestino'])


class GroupUpdate(Strict):
    name:str=Field(min_length=1,max_length=100)
    description:str=Field(default='',max_length=2000)
    icon:str=Field(default='✳',min_length=1,max_length=16)
    image:str|None=Field(default=None,max_length=2_800_000)


def normalize_image(value):
    try:
        raw=base64.b64decode(value.split(',',1)[-1],validate=True)
        if len(raw)>2_000_000:raise ValueError()
        with Image.open(io.BytesIO(raw),formats=['PNG','JPEG','WEBP']) as image:
            if image.width*image.height>16_000_000:raise ValueError()
            image=ImageOps.exif_transpose(image)
            image.thumbnail((512,512))
            clean=Image.new('RGBA',image.size)
            clean.paste(image.convert('RGBA'))
            out=io.BytesIO();clean.save(out,format='WEBP',quality=85)
            return out.getvalue()
    except (ValueError,OSError,UnidentifiedImageError,Image.DecompressionBombError):
        raise HTTPException(422,'Scegli un’immagine PNG, JPG o WebP valida: massimo 2 MB e 16 megapixel') from None


@router.put('/{group_id}')
def update_group(group_id:str,body:GroupUpdate,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,_=membership(db,group_id,user,write=True,manage=True)
    if group.metadata_version!=if_match:raise HTTPException(409,'Il gruppo è stato aggiornato: ricarica le impostazioni')
    if not body.name.strip() or not body.icon.strip():raise HTTPException(422,'Titolo e icona sono obbligatori')
    group.name=body.name.strip();group.description=body.description;group.icon=body.icon.strip()
    if 'image' in body.model_fields_set:
        group.image=normalize_image(body.image) if body.image else None
    group.metadata_version+=1
    audit(db,user.id,'group.updated',group.id)
    db.commit()
    return group_out(group)


@router.get('/{group_id}/image')
def group_image(group_id:str,user=Depends(current),db=Depends(get_db)):
    group,_=membership(db,group_id,user)
    if not group.image:raise HTTPException(404,'Immagine non presente')
    return Response(content=group.image,media_type='image/webp')


@router.get('/{group_id}/trash')
def trash(group_id:str,user=Depends(current),db=Depends(get_db)):
    _,actor=membership(db,group_id,user)
    return [{'id':e.id,'title':e.title,'total':e.total,'version':e.version,'secret':e.audience is not None} for e in db.scalars(select(Expense).where(Expense.group_id==group_id,Expense.deleted.is_(True)).order_by(Expense.date.desc())) if visible(e,actor)]


@router.delete('/{group_id}/expenses/{expense_id}',status_code=204)
def remove_expense(group_id:str,expense_id:str,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    return delete_expense(db,group_id,expense_id,if_match,user)


def delete_expense(db,group_id,expense_id,if_match,user,commit=True):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    _,actor=membership(db,group_id,user,write=True)
    row=db.scalar(select(Expense).where(Expense.id==expense_id,Expense.group_id==group_id).with_for_update())
    if not row or not visible(row,actor):raise HTTPException(404,'Spesa non trovata')
    if row.deleted and if_match in (row.version,row.version-1):return
    if row.version!=if_match:raise HTTPException(409,'La spesa è cambiata: ricarica prima di eliminarla')
    snapshot=dict(db.get(ExpenseRevision,(row.id,row.version)).snapshot)
    row.deleted=True;row.version+=1
    snapshot['deleted']=True
    db.add(ExpenseRevision(expense_id=row.id,version=row.version,actor_id=user.id,snapshot=snapshot))
    audit(db,user.id,'expense.deleted')
    if commit:db.commit()
    else:db.flush()


@router.post('/{group_id}/expenses/{expense_id}/restore')
def restore_expense(group_id:str,expense_id:str,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    return restore_expense_data(db,group_id,expense_id,if_match,user)


def restore_expense_data(db,group_id,expense_id,if_match,user,commit=True):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    _,actor=membership(db,group_id,user,write=True)
    row=db.scalar(select(Expense).where(Expense.id==expense_id,Expense.group_id==group_id).with_for_update())
    if not row or not visible(row,actor):raise HTTPException(404,'Spesa non trovata')
    if row.version!=if_match or not row.deleted:raise HTTPException(409,'Spesa già ripristinata o modificata')
    previous=db.get(ExpenseRevision,(row.id,row.version))
    if not db.scalar(select(Entry.id).where(Entry.expense_id==row.id,Entry.revision==row.version).limit(1)):
        previous=db.scalar(select(ExpenseRevision).where(ExpenseRevision.expense_id==row.id,ExpenseRevision.version<row.version).order_by(ExpenseRevision.version.desc()).limit(1))
    entries=list(db.scalars(select(Entry).where(Entry.expense_id==row.id,Entry.revision==previous.version)))
    row.deleted=False;row.version+=1
    snapshot=dict(previous.snapshot);snapshot.pop('deleted',None)
    db.add(ExpenseRevision(expense_id=row.id,version=row.version,actor_id=user.id,snapshot=snapshot))
    for entry in entries:
        db.add(Entry(expense_id=row.id,group_id=group_id,participant_id=entry.participant_id,revision=row.version,paid=entry.paid,owed=entry.owed))
    audit(db,user.id,'expense.restored')
    if commit:db.commit()
    else:db.flush()
    return {'id':row.id,'version':row.version}


class SmartIn(Strict):
    enabled:bool

@router.put('/{group_id}/smart-balances')
def update_smart(group_id:str,body:SmartIn,if_match:int=Header(ge=1),user=Depends(current),db=Depends(get_db)):
    db.scalar(select(Group).where(Group.id==group_id).with_for_update())
    group,_=membership(db,group_id,user,write=True,manage=True)
    if group.metadata_version!=if_match:raise HTTPException(409,'Il gruppo è cambiato: aggiorna le impostazioni')
    group.smart_balances=body.enabled;group.metadata_version+=1
    audit(db,user.id,'group.smart_changed',group.id);db.commit()
    return group_out(group)
