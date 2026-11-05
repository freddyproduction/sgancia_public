from fastapi import HTTPException
from .superadmin import is_superadmin
PERMISSIONS={'users':'Gestione account ordinari e recupero fattori','registrations':'Registrazioni, inviti ordinari e approvazioni','smtp':'Configurazione email','access':'Chiave e cancello installazione','policy':'Politiche e limiti','guests':'Abilitazione link ospiti','telegram':'Configurazione Telegram','backups':'Backup e recupero','audit':'Consultazione audit','sessions':'Revoca sessioni utenti'}

def permissions(db,user):
    if not user.admin:return []
    if is_superadmin(db,user.id):return list(PERMISSIONS)
    return list(PERMISSIONS) if user.admin_permissions is None else [p for p in user.admin_permissions if p in PERMISSIONS]

def require_permission(db,user,*names):
    if is_superadmin(db,user.id):return
    if not user.admin or not set(names).intersection(permissions(db,user)):raise HTTPException(403,'Permesso non concesso dal superadmin per questa operazione')

def require_superadmin(db,user):
    if not is_superadmin(db,user.id):raise HTTPException(403,'Operazione riservata ai superadmin')

def check_request(db,user,request):
    path=request.url.path
    if path.endswith(('/lifecycle','/deletion-preview')):require_superadmin(db,user);return
    if path.endswith(('/authority','/global-role','/authority-options')):require_superadmin(db,user);return
    if path.endswith('/admin/users') or (path.startswith('/api/v1/admin/users/') and path.endswith('/status')):require_permission(db,user,'users','registrations');return
    if '/admin/users/' in path:require_permission(db,user,'users');return
    if '/admin/invitations' in path or path.endswith('/admin/registration'):require_permission(db,user,'registrations');return
    if '/smtp' in path:require_permission(db,user,'smtp');return
    if path.endswith('/guest-links'):require_permission(db,user,'guests');return
    if path.endswith(('/access-policy','/admin/gate')):require_permission(db,user,'access');return
    if '/admin/operations/' in path:
        action=path.split('/admin/operations/')[1].split('/')[0]
        if action=='status':return
        require_permission(db,user,{'policy':'policy','backups':'backups','backup':'backups','portable':'backups','telegram':'telegram','audit':'audit','revoke-sessions':'sessions'}.get(action,'__denied'));return
    raise HTTPException(403,'Operazione amministrativa non autorizzata')
