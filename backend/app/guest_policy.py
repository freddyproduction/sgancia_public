"""Installation-wide guest access switch. Existing links remain subject to this gate."""
from fastapi import APIRouter,Depends,HTTPException,Request
from sqlalchemy import select
from .models import Instance
from .schemas import Strict
from .db import get_db
from .security import admin,current,audit
from .smtp_admin import require_admin_session
router=APIRouter(prefix='/api/v1',tags=['Impostazioni installazione'])


def enabled(db):return bool(db.scalar(select(Instance.guest_links_enabled).where(Instance.id==1)))


def require_guest_links(db):
    if not enabled(db):raise HTTPException(403,'Link ospiti disabilitati dall’amministratore globale')


class PolicyIn(Strict):enabled:bool


@router.get('/guest-policy')
def read_policy(user=Depends(current),db=Depends(get_db)):return {'enabled':enabled(db)}


@router.get('/admin/installation/guest-links')
def admin_policy(user=Depends(admin),db=Depends(get_db)):return {'enabled':enabled(db)}


@router.put('/admin/installation/guest-links')
def change_policy(body:PolicyIn,request:Request,user=Depends(admin),db=Depends(get_db)):
    instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update().execution_options(populate_existing=True))
    require_admin_session(db,request,user)
    if instance.guest_links_enabled!=body.enabled:
        instance.guest_links_enabled=body.enabled;audit(db,user.id,'installation.guest_links_changed')
    db.commit();return {'enabled':body.enabled}
