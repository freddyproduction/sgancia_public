"""Interactive bootstrap: no default passwords or secrets in argv/history."""
import argparse
from getpass import getpass
from sqlalchemy import select
from cryptography.fernet import Fernet
from .db import SessionLocal
from .models import Instance, User
from .security import passwords


def main():
    parser = argparse.ArgumentParser(description='Amministrazione locale Sgancia')
    parser.add_argument('command', choices=['init', 'encryption-key'])
    args = parser.parse_args()
    if args.command == 'encryption-key':
        print(Fernet.generate_key().decode())
        return
    with SessionLocal() as db:
        if db.get(Instance, 1):
            raise SystemExit('Installazione già inizializzata: nessuna modifica effettuata.')
        email = input('Email amministratore: ').strip().lower()
        name = input('Nome: ').strip()
        password = getpass('Password amministratore (minimo 12 caratteri): ')
        if password != getpass('Conferma password: '):
            raise SystemExit('Password differenti')
        gate = getpass('Chiave globale (minimo 16 caratteri): ')
        if gate != getpass('Conferma chiave globale: '):
            raise SystemExit('Chiavi differenti')
        if '@' not in email or not name or len(password) < 12 or len(gate) < 16:
            raise SystemExit('Dati non validi')
        from .portable_backup import empty_lock
        empty_lock(db)
        founder=User(email=email,name=name,password_hash=passwords.hash(password),admin=True,superadmin=True)
        db.add(founder);db.flush()
        db.add(Instance(id=1,gate_hash=passwords.hash(gate),superadmin_id=founder.id))
        from .security import audit
        audit(db,founder.id,'installation.initialized',founder.id)
        db.commit()
        print('Installazione inizializzata: primo account superadmin protetto. Registrazione tramite invito attiva.')


if __name__ == '__main__':
    main()
