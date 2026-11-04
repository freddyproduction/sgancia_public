"""Interactive local administration only; never exposed as an HTTP endpoint."""
import argparse,getpass
from sqlalchemy import select,delete
from .db import SessionLocal
from .models import User,RecoveryCode,Passkey,Instance,Session,GateGrant
from .account_security import locked_user,issue_token,revoke_access
from .security import audit

def main():
    parser=argparse.ArgumentParser(description='Recupero locale Sgancia dopo verifica manuale dell’identità da parte dell’operatore del server')
    parser.add_argument('--reset-mfa',action='store_true',help='Revoca anche MFA e passkey dopo conferma esplicita')
    parser.add_argument('--enable-gate',action='store_true',help='Riabilita il gate e revoca gli accessi senza cambiare la chiave')
    args=parser.parse_args()
    if input('Scrivi IDENTITA VERIFICATA per continuare: ')!='IDENTITA VERIFICATA':return
    with SessionLocal() as db:
        if args.enable_gate:
            instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update());instance.gate_enabled=True;instance.gate_version+=1
            db.execute(delete(Session));db.execute(delete(GateGrant));audit(db,None,'gate.local_reenabled');db.commit();print('Gate riabilitato; sessioni revocate.');return
        email=input('Email account da recuperare: ').strip().lower();user=db.scalar(select(User).where(User.email==email).with_for_update())
        if not user or user.status!='active':raise SystemExit('Account attivo non disponibile')
        if args.reset_mfa:
            if input('Scrivi REVOCA TUTTI I FATTORI per revocare MFA e passkey: ')!='REVOCA TUTTI I FATTORI':return
            user.totp_secret=None;user.totp_pending=None;user.totp_last_counter=-1
            db.execute(delete(RecoveryCode).where(RecoveryCode.user_id==user.id));db.execute(delete(Passkey).where(Passkey.user_id==user.id))
        revoke_access(db,user);url=issue_token(db,user,'reset',queue=False);audit(db,user.id,'account.local_recovery');db.commit()
        print('Link privato valido 30 minuti da consegnare solo al titolare verificato:\n'+url)
if __name__=='__main__':main()
