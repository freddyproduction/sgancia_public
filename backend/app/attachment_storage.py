import contextlib,fcntl,hashlib,os,re,uuid
from pathlib import Path
from .config import settings
KEY=re.compile(r'^[0-9a-f]{32}\.(blob|preview)$')

def root():
    path=Path(settings.attachment_dir);path.mkdir(parents=True,exist_ok=True)
    return path

@contextlib.contextmanager
def storage_lock(exclusive=False):
    with (root()/'.lock').open('a+b') as file:
        fcntl.flock(file,fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
        try:yield
        finally:fcntl.flock(file,fcntl.LOCK_UN)

def path_for(key):
    if not KEY.fullmatch(key):raise ValueError('Chiave storage non valida')
    return root()/key

def write_blob(key,data):
    final=path_for(key);temporary=root()/('.upload-'+uuid.uuid4().hex)
    try:
        with temporary.open('xb') as file:
            os.chmod(temporary,0o600);file.write(data);file.flush();os.fsync(file.fileno())
        if final.exists():raise ValueError('Chiave già presente')
        os.replace(temporary,final)
    finally:temporary.unlink(missing_ok=True)

def read_blob(key,expected_hash=None):
    data=path_for(key).read_bytes()
    if expected_hash and hashlib.sha256(data).hexdigest()!=expected_hash:raise ValueError('Allegato danneggiato')
    return data

if __name__=='__main__':
    path=root();os.chown(path,10001,10001);os.chmod(path,0o700)
    lock=path/'.lock'
    if lock.is_symlink():raise ValueError('Lock storage non valido')
    lock.touch(exist_ok=True);os.chown(lock,10001,10001);os.chmod(lock,0o600)
