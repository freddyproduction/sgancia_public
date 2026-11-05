"""Dedicated backup process: filesystem capability is never given to the web API."""
import base64,fcntl,os,re,shutil,subprocess,tempfile,time,uuid
from pathlib import Path
from contextlib import contextmanager
from sqlalchemy import select,delete
from sqlalchemy.engine import make_url
from .config import settings
from .db import SessionLocal
from .models import Instance,MaintenanceJob,Audit
from .operations import BackupPolicy,heartbeat
from .runtime_policy import policy
from .backup import encrypt,decrypt
from .attachment_backup import pack,stage,referenced_files,file_hash

class BackupError(Exception):pass


def directory():return Path(os.environ.get('SGANCIA_BACKUP_DIR','/app/backups'))

def workspace(prefix):
    folder=directory()/'.scratch'
    if folder.is_symlink():raise BackupError('unsafe_backup_path')
    folder.mkdir(parents=True,exist_ok=True,mode=0o700)
    return tempfile.TemporaryDirectory(prefix=prefix,dir=folder)

def key():
    try:
        result=base64.b64decode(os.environ.get('SGANCIA_BACKUP_KEY',''),altchars=b'-_',validate=True)
        if len(result)!=32:raise ValueError()
        return result
    except Exception:raise BackupError('backup_key_missing') from None


def connection(database=None):
    url=make_url(settings.database_url)
    return {'host':url.host or 'db','port':url.port or 5432,'user':url.username,'password':url.password,'dbname':database or url.database}


def command(program,database=None):
    cfg=connection(database);env=os.environ.copy();env['PGPASSWORD']=cfg['password'] or ''
    return [program,'--host',cfg['host'],'--port',str(cfg['port']),'--username',cfg['user'],'--dbname',cfg['dbname']],env


def execute(args,env=None,stdout=None,timeout=1800):
    try:
        result=subprocess.run(args,env=env,stdout=stdout or subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
        if result.returncode:raise BackupError('database_command_failed')
        return result
    except (OSError,subprocess.TimeoutExpired):raise BackupError('database_command_failed') from None


def verified_dump(backup,target,storage):
    storage=Path(storage);storage.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tempfile.TemporaryFile(dir=storage) as plain:
        with Path(backup).open('rb') as source:decrypt(source,plain,key())
        plain.seek(0);meta=stage(plain,target,storage);target.flush();target.seek(0)
    return meta


def restore_probe(backup):
    import psycopg
    from psycopg import sql
    name='sgancia_probe_'+uuid.uuid4().hex
    if name==connection()['dbname']:raise BackupError('unsafe_probe_target')
    created=False
    with workspace('sgancia-probe-') as tmp:
        tmp=Path(tmp);dump=tmp/'database.dump';objects=tmp/'objects'
        with dump.open('w+b') as stream:meta=verified_dump(backup,stream,objects)
        try:
            with psycopg.connect(**connection('postgres'),autocommit=True) as admin:
                admin.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)));created=True
            args,env=command('pg_restore',name);execute(args+['--clean','--if-exists','--no-owner','--no-acl','--single-transaction','--exit-on-error',str(dump)],env,timeout=1800)
            with psycopg.connect(**connection(name)) as check:
                bad=check.execute('SELECT 1 FROM ledger_entries GROUP BY expense_id,revision HAVING SUM(paid)<>SUM(owed) LIMIT 1').fetchone()
                if bad:raise BackupError('ledger_verification_failed')
                for storage_key,sha,preview in check.execute('SELECT storage_key,sha256,preview_size FROM attachments'):
                    if not re.fullmatch('[0-9a-f]{32}',storage_key) or not (objects/(storage_key+'.blob')).is_file() or file_hash(objects/(storage_key+'.blob'))!=sha:raise BackupError('attachment_verification_failed')
                    if preview and not (objects/(storage_key+'.preview')).is_file():raise BackupError('attachment_verification_failed')
                schema=check.execute('SELECT version_num FROM alembic_version').fetchone()[0]
            return {'restore':'verified','files':meta['files'],'schema':schema}
        finally:
            if created:
                with psycopg.connect(**connection('postgres'),autocommit=True) as admin:admin.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))


def create_backup(job_id,probe=False):
    uuid.UUID(job_id);key();folder=directory();folder.mkdir(parents=True,exist_ok=True)

    with SessionLocal() as db:
        instance=db.get(Instance,1);raw=instance.backup_policy or {};prefix=raw.get('filename_prefix','auto');sub=raw.get('subdirectory','')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,40}',prefix) or not re.fullmatch(r'[A-Za-z0-9_-]{0,40}',sub):raise BackupError('unsafe_backup_path')
    folder=folder/sub
    if folder.is_symlink():raise BackupError('unsafe_backup_path')
    folder.mkdir(parents=True,exist_ok=True)
    final=folder/(prefix+'-'+job_id+'.sgb');partial=folder/(prefix+'-'+job_id+'.partial')
    if final.is_symlink() or partial.is_symlink():raise BackupError('unsafe_backup_path')
    partial.unlink(missing_ok=True)
    if not final.exists():
        try:
            with workspace('sgancia-backup-') as tmp:
                tmp=Path(tmp);dump=tmp/'database.dump';bundle=tmp/'bundle.tar'
                # Immutable referenced files cannot disappear; lock also excludes an operator restore.
                with (Path(settings.attachment_dir)/'.lock').open('rb') as lock:
                    fcntl.flock(lock,fcntl.LOCK_SH)
                    args,env=command('pg_dump')
                    with dump.open('wb') as out:execute(args+['-Fc','--no-owner','--no-acl'],env,out)
                    with dump.open('rb') as source,bundle.open('wb') as out:pack(source,out,settings.attachment_dir,referenced_files(),temporary_dir=tmp)
                with bundle.open('rb') as source,partial.open('xb') as out:
                    os.chmod(partial,0o600);encrypt(source,out,key());out.flush();os.fsync(out.fileno())
                with tempfile.TemporaryFile(dir=tmp) as out:verified_dump(partial,out,tmp/'verified')
                execute(['pg_restore','--list',str(dump)])
                os.replace(partial,final)
        finally:partial.unlink(missing_ok=True)
    with workspace('sgancia-verify-') as tmp:
        with (Path(tmp)/'database.dump').open('w+b') as out:verified_dump(final,out,Path(tmp)/'objects')
        execute(['pg_restore','--list',str(Path(tmp)/'database.dump')])
    result={'filename':str(final.relative_to(directory())),'bytes':final.stat().st_size,'sha256':file_hash(final),'integrity':'verified'}
    if probe:result.update(restore_probe(final))
    return result


def prune(keep):
    # Only this service's encrypted completed archives; manual backups are in another directory.
    files=sorted((p for p in directory().rglob('*.sgb') if not p.is_symlink() and not p.parent.is_symlink() and re.fullmatch(r'[A-Za-z0-9_-]{1,40}-[0-9a-f-]{36}\.sgb',p.name)),key=lambda p:p.stat().st_mtime,reverse=True)
    for path in files[keep:]:path.unlink()


def schedule(db,now):
    instance=db.scalar(select(Instance).where(Instance.id==1).with_for_update())
    if not instance:return
    raw=instance.backup_policy or {};cfg=BackupPolicy.model_validate({k:v for k,v in raw.items() if k not in ('started_at','portable')})
    days=policy(db)['audit_retention_days']
    if days:db.execute(delete(Audit).where(Audit.at<now-max(7,days)*86400))
    if not cfg.enabled:return
    period=cfg.interval_hours*3600;slot=now//period
    if slot*period<raw.get('started_at',now):return
    name='scheduled:'+str(period)+':'+str(slot)
    if not db.scalar(select(MaintenanceJob.id).where(MaintenanceJob.slot==name)):db.add(MaintenanceJob(slot=name,kind='backup'))


def tick():
    folder=directory();folder.mkdir(parents=True,exist_ok=True)
    path=folder/'.service.lock'
    if path.is_symlink():raise BackupError('unsafe_backup_path')
    with path.open('a+b') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:return
        scratch=folder/'.scratch'
        if scratch.exists() and not scratch.is_symlink():
            for old in scratch.iterdir():
                if old.is_dir() and not old.is_symlink() and old.name.startswith(('sgancia-backup-','sgancia-probe-','sgancia-verify-')) and old.stat().st_mtime<time.time()-86400:shutil.rmtree(old)
        with SessionLocal() as db:
            schedule(db,int(time.time()));db.commit()
            # With the process lock held, a prior running job belongs to a crashed worker.
            job=db.scalar(select(MaintenanceJob).where(MaintenanceJob.status.in_(['pending','running'])).order_by(MaintenanceJob.created).with_for_update(skip_locked=True).limit(1))
            if not job:return
            instance=db.get(Instance,1);cfg=BackupPolicy.model_validate({k:v for k,v in (instance.backup_policy or {}).items() if k not in ('started_at','portable')})
            completed=db.query(MaintenanceJob).filter(MaintenanceJob.status=='done').count()
            probe=cfg.restore_checks and completed%cfg.restore_check_every==0
            job.status='running';job.started=int(time.time());db.commit()
            try:
                job.result=create_backup(job.id,probe);prune(cfg.keep_count);job.status='done';job.error=''
            except BackupError as error:job.status='failed';job.error=str(error) if re.fullmatch('[a-z_]{1,40}',str(error)) else 'backup_failed'
            except Exception:job.status='failed';job.error='backup_failed'
            job.finished=int(time.time());db.add(Audit(event='backup.'+job.status));db.commit()


if __name__=='__main__':
    import threading
    def pulse():
        while True:
            try:heartbeat('backup')
            except Exception:pass
            time.sleep(30)
    threading.Thread(target=pulse,daemon=True).start()
    while True:
        try:tick()
        except Exception:print('Servizio backup temporaneamente non disponibile',flush=True)
        time.sleep(60)
