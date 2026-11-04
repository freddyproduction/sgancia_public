"""Multiple superadmins; the instance pointer anchors an active superadmin."""
from .models import Instance,User

def is_superadmin(db,user_id):
    instance=db.get(Instance,1);user=db.get(User,user_id)
    return bool(user and (user.superadmin or (instance and instance.superadmin_id==user_id)))

def role(db,user):return 'superadmin' if is_superadmin(db,user.id) else 'admin' if user.admin else 'user'
