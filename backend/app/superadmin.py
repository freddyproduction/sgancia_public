"""The installation founder is an immutable identity, not a display name."""
from .models import Instance

def is_superadmin(db,user_id):
    instance=db.get(Instance,1)
    return bool(instance and instance.superadmin_id==user_id)
