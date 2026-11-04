#!/usr/bin/env python3
"""Offline guard: inspect the staged index, never print secret values."""
from pathlib import Path
import re
import subprocess
import sys


def git(*args):return subprocess.check_output(['git',*args])
root=Path(git('rev-parse','--show-toplevel').decode().strip())
sensitive={'POSTGRES_PASSWORD','SGANCIA_ENCRYPTION_KEY','SGANCIA_BACKUP_KEY','SGANCIA_SMTP_PASSWORD'}
private_values=[]
# Include the preserved legacy example so obsolete private keys stay out of history too.
for path in (root/'.env',root/'.local/server-example-original-private.txt'):
    if path.is_file():
        for line in path.read_text().splitlines():
            key,separator,value=line.strip().partition('=')
            value=value.strip().strip('"\'')
            if separator and key in sensitive and len(value)>=12:private_values.append(value.encode())
paths=(git('ls-files','-z') if '--all' in sys.argv else git('diff','--cached','--name-only','--diff-filter=ACMR','-z')).decode().split('\0')
problems=[]
for name in filter(None,paths):
    path=Path(name)
    if any(part in ('.local','data','backups','node_modules','.venv','certs') for part in path.parts) or (path.name.startswith('.env') and path.name not in ('.env.example','.env.server.example')) or path.suffix in ('.sgb','.pem','.key','.p12','.pfx','.dump','.sqlite','.sqlite3'):
        problems.append((name,'file locale/privato non versionabile'));continue
    data=git('show',':'+name)
    if any(value in data for value in private_values):problems.append((name,'valore privato presente nell’indice'))
    if re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',data):problems.append((name,'chiave privata'))
    if re.search(rb'(?:ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk_live_[A-Za-z0-9]{20,})',data):problems.append((name,'possibile token di accesso'))
    if path.name in ('.env.example','.env.server.example'):
        for line in data.decode().splitlines():
            key,separator,value=line.strip().partition('=')
            if separator and key in sensitive and value.strip():problems.append((name,'gli esempi devono avere credenziali vuote'))
if problems:
    for name,reason in problems:print(f'BLOCCATO: {name}: {reason}',file=sys.stderr)
    print('Nessun valore segreto è stato stampato. Correggere i file nell’indice prima del commit.',file=sys.stderr)
    sys.exit(1)
print(f'Controllo Git superato: {sum(bool(p) for p in paths)} file nell’indice; nessun segreto locale noto rilevato.')
