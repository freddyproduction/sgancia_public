"""Public project identity. Edit the three empty contacts here, then rebuild Sgancia."""
from fastapi import APIRouter
from urllib.parse import urlsplit
VERSION = '0.2.0-dev'
DEVELOPER = 'PjChaosEOW'
# INSERISCI QUI la tua email pubblica (nessuna email viene inviata automaticamente).
DEVELOPER_EMAIL = ''
# INSERISCI QUI il link HTTPS reale alla pagina Buy Me a Coffee.
DONATION_URL = ''
# INSERISCI QUI il link HTTPS reale al repository GitHub pubblico.
REPOSITORY_URL = ''
# Testo approvato dal titolare il 4 novembre 2026.
DONATION_DISCLAIMER_APPROVED = True
DONATION_DISCLAIMER = ('La donazione è interamente volontaria: non acquista funzionalità né comporta obblighi, '
    'priorità delle richieste, legami con lo sviluppo del codice o promesse su tempi e risultati.')
router = APIRouter(tags=['Informazioni pubbliche'])

def https_link(value,hosts):
    try:
        parsed=urlsplit(value)
        return value if parsed.scheme=='https' and parsed.hostname in hosts and not parsed.username and not parsed.password and parsed.port in (None,443) else None
    except ValueError:return None

@router.get('/api/v1/project')
def project():
    import re
    email=DEVELOPER_EMAIL.strip()
    return {'name':'Sgancia','version':VERSION,'developer':DEVELOPER,'license':'AGPL-3.0-only',
        'signature':'Ideato e sviluppato da PjChaosEOW, con vibecoding e ChatGPT.',
        'email':email if re.fullmatch(r'[A-Za-z0-9.!#$%&\x27*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+',email) else None,
        'donation_url':https_link(DONATION_URL,{'buymeacoffee.com','www.buymeacoffee.com'}) if DONATION_DISCLAIMER_APPROVED else None,
        'donation_disclaimer':DONATION_DISCLAIMER if DONATION_DISCLAIMER_APPROVED else None,
        'repository_url':https_link(REPOSITORY_URL,{'github.com','www.github.com'}),
        'release_status':'Sviluppo attivo · verifiche server e dispositivi ancora aperte'}
