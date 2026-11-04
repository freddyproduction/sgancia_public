"""Streaming DB+immutable-file bundle inside the authenticated backup envelope.

Files are atomically published before metadata commits and never physically
removed by the product. Thus metadata in a completed pg_dump always references
files still present when this bundle is collected. Extra newer files are safe.
Restore validates the entire archive, then publishes immutable blobs BEFORE the
single-transaction pg_restore. A failed DB restore leaves only unreferenced blobs.
"""
import hashlib,io,json,os,shutil,sys,tarfile,tempfile
from pathlib import Path
from .attachment_storage import root,KEY,storage_lock,path_for
MAX_MANIFEST=16*1024*1024


def file_hash(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()


def pack(source,target,storage,expected=None,temporary_dir=None):
    storage=Path(storage);storage.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryFile(dir=temporary_dir or storage) as dump:
        shutil.copyfileobj(source,dump,1024*1024);size=dump.tell();dump.seek(0)
        if dump.read(5)!=b'PGDMP':raise ValueError('Dump PostgreSQL non valido')
        dump.seek(0);dbhash=hashlib.sha256()
        while chunk:=dump.read(1024*1024):dbhash.update(chunk)
        files={'database.dump':{'size':size,'sha256':dbhash.hexdigest()}}
        keys=sorted(expected) if expected is not None else sorted(f.name for f in storage.iterdir() if KEY.fullmatch(f.name) and f.is_file())
        for key in keys:
            if not KEY.fullmatch(key):raise ValueError('Chiave file non valida')
            path=storage/key
            if not path.is_file() or path.is_symlink():raise ValueError('File allegato mancante')
            digest=file_hash(path)
            if expected is not None and expected[key] and digest!=expected[key]:raise ValueError('Allegato danneggiato: backup interrotto')
            files['objects/'+key]={'size':path.stat().st_size,'sha256':digest}
        manifest=json.dumps({'format':'sgancia-files-1','files':files},sort_keys=True).encode()
        if len(manifest)>MAX_MANIFEST:raise ValueError('Troppi file nel backup')
        with tarfile.open(fileobj=target,mode='w|') as archive:
            info=tarfile.TarInfo('manifest.json');info.size=len(manifest);info.mode=0o600;archive.addfile(info,io.BytesIO(manifest))
            info=tarfile.TarInfo('database.dump');info.size=size;info.mode=0o600;dump.seek(0);archive.addfile(info,dump)
            for key in keys:
                info=tarfile.TarInfo('objects/'+key);info.size=files['objects/'+key]['size'];info.mode=0o600
                with (storage/key).open('rb') as file:archive.addfile(info,file)


def stage(source,target,storage):
    storage=Path(storage);storage.mkdir(parents=True,exist_ok=True)
    buffered=source if hasattr(source,'peek') else io.BufferedReader(source)
    if buffered.peek(5)[:5]==b'PGDMP':
        shutil.copyfileobj(buffered,target,1024*1024);return {'legacy':True,'files':0}
    with tempfile.TemporaryDirectory(prefix='.restore-',dir=storage) as temporary:
        temporary=Path(temporary);seen=set()
        with tarfile.open(fileobj=buffered,mode='r|') as archive:
            first=archive.next()
            if not first or first.name!='manifest.json' or not first.isfile() or first.size>MAX_MANIFEST:raise ValueError('Manifest mancante')
            manifest=json.loads(archive.extractfile(first).read())
            if manifest.get('format')!='sgancia-files-1':raise ValueError('Formato non supportato')
            expected=manifest.get('files',{})
            if 'database.dump' not in expected or len(expected)>100000:raise ValueError('Contenuto backup non valido')
            for name,meta in expected.items():
                if name!='database.dump' and (not name.startswith('objects/') or not KEY.fullmatch(name[8:])):raise ValueError('Percorso non consentito')
                if not isinstance(meta['size'],int) or not 0<=meta['size']<=1024**4 or len(meta['sha256'])!=64:raise ValueError('Metadati non validi')
            while info:=archive.next():
                if info.name not in expected or info.name in seen or not info.isfile() or info.size!=expected[info.name]['size']:raise ValueError('File inatteso o duplicato')
                seen.add(info.name);local=temporary/('database.dump' if info.name=='database.dump' else info.name[8:])
                h=hashlib.sha256();size=0
                with local.open('xb') as out:
                    os.chmod(local,0o600)
                    stream=archive.extractfile(info)
                    while chunk:=stream.read(1024*1024):out.write(chunk);h.update(chunk);size+=len(chunk)
                if size!=info.size or h.hexdigest()!=expected[info.name]['sha256']:raise ValueError('File alterato o incompleto')
            if seen!=set(expected):raise ValueError('File mancanti')
        dump=temporary/'database.dump'
        with dump.open('rb') as file:
            if file.read(5)!=b'PGDMP':raise ValueError('Dump non valido')
        # Verify every collision before publishing any blob.
        for name,meta in expected.items():
            if name=='database.dump':continue
            final=storage/name[8:]
            if final.exists() and (final.is_symlink() or file_hash(final)!=meta['sha256']):raise ValueError('Conflitto con file esistente: ripristino interrotto')
        for name in expected:
            if name=='database.dump':continue
            final=storage/name[8:]
            if not final.exists():os.replace(temporary/name[8:],final)
        with dump.open('rb') as file:shutil.copyfileobj(file,target,1024*1024)
        return {'legacy':False,'files':len(expected)-1}


def referenced_files():
    from sqlalchemy import select,inspect
    from .db import engine
    from .models import Attachment
    if not inspect(engine).has_table('attachments'):return {}
    files={}
    with engine.connect() as db:
        for row in db.execute(select(Attachment.storage_key,Attachment.sha256,Attachment.preview_size)):
            files[row.storage_key+'.blob']=row.sha256
            if row.preview_size:files[row.storage_key+'.preview']=None
    return files

if __name__=='__main__':
    try:
        if sys.argv[1]=='pack':
            with storage_lock():pack(sys.stdin.buffer,sys.stdout.buffer,root(),referenced_files())
        elif sys.argv[1]=='stage':
            with storage_lock(exclusive=True):stage(sys.stdin.buffer,sys.stdout.buffer,root())
        else:raise ValueError()
    except Exception:
        print('Backup allegati non valido, incompleto o non coerente; operazione interrotta.',file=sys.stderr)
        raise SystemExit(1) from None
