"""Create random LOCAL-ONLY demo access. Never use on the production server."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import urllib.request

root=Path(__file__).resolve().parents[1]
os.chdir(root)
env=(root/'.env').read_text()
if 'SGANCIA_PUBLIC_ORIGIN=http://localhost:8088' not in env:
    raise SystemExit('Demo consentita soltanto su localhost:8088')
p=root/'.local/demo-access.json'
if p.exists():
    raise SystemExit('Credenziali demo già presenti: nessuna modifica effettuata.')
credentials={'url':'http://localhost:8088','email':'demo@example.invalid','name':'Freddy (test)','password':secrets.token_urlsafe(24),'gate':secrets.token_urlsafe(24)}
values='\n'.join([credentials['email'],credentials['name'],credentials['password'],credentials['password'],credentials['gate'],credentials['gate']])+'\n'
result=subprocess.run(['docker','compose','exec','-T','api','python','-m','app.cli','init'],input=values,text=True,capture_output=True)
if result.returncode:
    raise SystemExit('Installazione demo non effettuata: database già inizializzato o container non disponibile.')
p.parent.mkdir(exist_ok=True)
p.write_text(json.dumps(credentials,indent=2)+'\n');os.chmod(p,0o600)
print('Accesso locale creato. Credenziali casuali in .local/demo-access.json (non versionate).')
