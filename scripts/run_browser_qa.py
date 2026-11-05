#!/usr/bin/env python3
"""Fresh port-18088 QA with generated installation keys; removes only its own project."""
import os,pathlib,secrets,subprocess,time,urllib.request
root=pathlib.Path(__file__).resolve().parents[1]
env=os.environ.copy()
import base64
env.update(QA_DB_PASSWORD=secrets.token_hex(32),QA_ENCRYPTION_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),QA_BACKUP_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())
base=['docker','compose','-p','sgancia-release-qa','-f','compose.qa.yml']
def run(args,**kwargs):return subprocess.run(args,cwd=root,env=env,check=True,**kwargs)
seed="""from app.db import SessionLocal
from app.models import User,Instance,Group,Participant
from app.security import passwords
with SessionLocal() as db:
 u=User(id='qa-owner',email='qa@example.org',name='Sgancia QA',password_hash=passwords.hash('qa-password-long'),admin=True);db.add(u);db.flush()
 db.add(Instance(id=1,gate_hash=passwords.hash('qa-installation-gate'),superadmin_id=u.id))
 g=Group(id='qa-group',name='Prova rilascio',currency='EUR',owner_id=u.id);db.add(g);db.flush()
 db.add_all([Participant(id='qa-one',group_id=g.id,user_id=u.id,name='Sgancia QA',role='owner'),Participant(id='qa-two',group_id=g.id,name='Compagno QA',role='member')]);db.commit()
"""
try:
 # An existing project is not reset: fail rather than deleting someone else's QA session.
 existing=subprocess.check_output(base+['ps','-a','-q'],cwd=root,env=env,text=True)
 if existing.strip():raise SystemExit('QA release già presente: non viene sovrascritta')
 run(base+['up','-d','api','worker'])
 run(base+['exec','-T','api','python','-c',seed])
 for attempt in range(30):
  try:
   if urllib.request.urlopen('http://localhost:18088/health/ready',timeout=2).status==200:break
  except (OSError,ValueError):time.sleep(1)
 else:raise SystemExit('QA non pronta')
 run(['node','frontend/e2e/release.mjs'])
 run(['node','frontend/e2e/friends-backup.mjs'])
 migration_env={**env,'QA_PORT':'18089','QA_DB_PASSWORD':secrets.token_hex(32),'QA_ENCRYPTION_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),'QA_BACKUP_KEY':base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}
 migration_base=['docker','compose','-p','sgancia-portable-qa','-f','compose.qa.yml']
 migration_existing=subprocess.check_output(migration_base+['ps','-a','-q'],cwd=root,env=migration_env,text=True)
 if migration_existing.strip():raise SystemExit('QA migrazione già presente: nessuna modifica')
 try:
  subprocess.run(migration_base+['up','-d','api'],cwd=root,env=migration_env,check=True)
  for attempt in range(30):
   try:
    if urllib.request.urlopen('http://localhost:18089/health/ready',timeout=2).status==200:break
   except (OSError,ValueError):time.sleep(1)
  else:raise SystemExit('QA migrazione non pronta')
  subprocess.run(['node','frontend/e2e/restore-setup.mjs'],cwd=root,env=migration_env,check=True)
 finally:subprocess.run(migration_base+['down','-v','--remove-orphans'],cwd=root,env=migration_env,check=False)

 # Restart both processes, preserve volumes/database, then repeat authenticated read smoke.
 run(base+['restart','api','worker'])
 for attempt in range(30):
  try:
   if urllib.request.urlopen('http://localhost:18088/health/ready',timeout=2).status==200:break
  except (OSError,ValueError):time.sleep(1)
 else:raise SystemExit('QA non pronta dopo riavvio')
 env['QA_RESTART_ONLY']='1';run(['node','frontend/e2e/release.mjs'])
finally:
 # Never touch the ordinary installation project or its volumes.
 if 'existing' in locals() and not existing.strip():subprocess.run(base+['down','-v','--remove-orphans'],cwd=root,env=env,check=False)
