from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from .config import settings,normalize_origin
from .db import engine
from .auth import router as auth
from .groups import router as groups
from .admin import router as admin
from .passkeys import router as passkeys
from .settlements import router as settlements
from .sharing import router as sharing
from .lifecycle import router as lifecycle
from .editing import router as editing
from .finance import router as finance
from .group_settings import router as group_settings

from fastapi.exceptions import RequestValidationError

from .project_info import VERSION, router as project_info

app = FastAPI(title='Sgancia', version=VERSION, docs_url='/api/docs', openapi_url='/api/openapi.json', redoc_url=None)


@app.exception_handler(RequestValidationError)
async def validation_error(request,exc):
    # Never echo credentials or a whole submitted configuration in validation errors.
    return JSONResponse({'detail':[{key:error[key] for key in ('loc','msg','type') if key in error} for error in exc.errors()]},status_code=422)


@app.middleware('http')
async def boundary(request: Request, call_next):
    # All entry points serve their own frontend and API. Never reflect arbitrary hosts.
    try:target_origin=normalize_origin(str(request.url.replace(path='',query='',fragment='')))
    except ValueError:return JSONResponse({'detail':'Indirizzo non autorizzato'},status_code=400)
    health=request.url.path in ('/health/live','/health/ready') and request.method in ('GET','HEAD')
    if not health and target_origin not in settings.origins:
        return JSONResponse({'detail':'Indirizzo non autorizzato: configura dominio o IP del server'},status_code=400)
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin=request.headers.get('origin')
        if origin is not None:
            try:source_origin=normalize_origin(origin)
            except ValueError:source_origin=None
            if source_origin!=target_origin or source_origin not in settings.origins:
                return JSONResponse({'detail':'Origine non autorizzata'},status_code=403)
        if request.headers.get('sec-fetch-site')=='cross-site':
            return JSONResponse({'detail':'Richiesta non autorizzata'},status_code=403)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['X-Frame-Options'] = 'DENY'
    if request.url.path != '/api/docs':
        response.headers.setdefault('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
    if request.url.scheme=='https':
        response.headers['Strict-Transport-Security'] = 'max-age=31536000'
    return response


from .registration_admin import router as registration_admin
app.include_router(registration_admin)
from .authority import router as authority
app.include_router(authority)
app.include_router(project_info)

@app.get('/health/live', include_in_schema=False)
def live():
    return {'status': 'ok'}


@app.get('/health/ready', include_in_schema=False)
def ready():
    try:
        with engine.connect() as connection:
            connection.execute(text('SELECT gate_version FROM instance WHERE id = 1')).scalar_one()
        return {'status': 'ready'}
    except Exception:
        return JSONResponse({'status': 'not_ready'}, status_code=503)


app.include_router(auth)
from .account_security import router as account_security
from .payment_methods import router as payment_methods
app.include_router(account_security)
from .smtp_admin import router as smtp_admin
app.include_router(smtp_admin)
app.include_router(payment_methods)
app.include_router(groups)
app.include_router(admin)
from .global_roles import router as global_roles
app.include_router(global_roles)
from .admin_recovery import router as admin_recovery
app.include_router(admin_recovery)

app.include_router(passkeys)
app.include_router(settlements)
app.include_router(sharing)
app.include_router(lifecycle)
app.include_router(editing)
app.include_router(finance)
app.include_router(group_settings)
from .membership_ops import router as membership_ops
app.include_router(membership_ops)
from .history import router as history
app.include_router(history)
from .group_trash import router as group_trash
app.include_router(group_trash)
from .attachments import router as attachments
app.include_router(attachments)
from .overview import router as overview
app.include_router(overview)
from .exchange import router as exchange
app.include_router(exchange)
from .currency_change import router as currency_change
app.include_router(currency_change)

from .automation import router as automation
app.include_router(automation)

from .insights import router as insights
app.include_router(insights)

from .data_exchange import router as data_exchange
app.include_router(data_exchange)

from .guest_policy import router as guest_policy
app.include_router(guest_policy)

from .reveals import router as reveals
app.include_router(reveals)

from .notifications import router as notifications
app.include_router(notifications)

from .gate_passkeys import router as gate_passkeys
app.include_router(gate_passkeys)

from .operations import router as operations
app.include_router(operations)

from .group_access import router as group_access
app.include_router(group_access)

from .telegram_account import router as telegram_account
app.include_router(telegram_account)

# A production image includes the React build. Never fall back to HTML for API errors.
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
static = Path(__file__).resolve().parent.parent / 'static'
if static.exists():
    app.mount('/assets', StaticFiles(directory=static / 'assets'), name='assets')

    @app.get('/{path:path}', include_in_schema=False)
    def web(path: str):
        if path.startswith(('api/', 'health/')):
            return JSONResponse({'detail': 'Not found'}, status_code=404)
        if path in ('icon.svg', 'manifest.webmanifest'):
            return FileResponse(static / path)
        return FileResponse(static / 'index.html')
