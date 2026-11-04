from io import BytesIO
from pathlib import Path
import hashlib,json,tarfile
import pytest
from app.attachment_backup import pack,stage
from app.backup import encrypt,decrypt


def test_complete_bundle_encrypted_roundtrip_and_legacy(tmp_path):
    source=tmp_path/'source';source.mkdir();key='a'*32+'.blob';(source/key).write_bytes(b'receipt-file')
    dump=b'PGDMP-test-database-content';archive=BytesIO();pack(BytesIO(dump),archive,source)
    encrypted=BytesIO();secret=b'x'*32;encrypt(BytesIO(archive.getvalue()),encrypted,secret)
    restored=BytesIO();decrypt(BytesIO(encrypted.getvalue()),restored,secret)
    target=tmp_path/'target';out=BytesIO();result=stage(BytesIO(restored.getvalue()),out,target)
    assert result['files']==1 and out.getvalue()==dump and (target/key).read_bytes()==b'receipt-file'
    old=BytesIO();assert stage(BytesIO(dump),old,target)['legacy'];assert old.getvalue()==dump
    # Repeated restore reuses identical immutable blobs.
    again=BytesIO();stage(BytesIO(restored.getvalue()),again,target);assert again.getvalue()==dump


def test_bundle_missing_or_corrupt_file_aborts_before_database_output(tmp_path):
    source=tmp_path/'source';source.mkdir();key='b'*32+'.blob';(source/key).write_bytes(b'file')
    with pytest.raises(ValueError):pack(BytesIO(b'PGDMP-db'),BytesIO(),source,{key:'0'*64})
    archive=BytesIO();pack(BytesIO(b'PGDMP-db'),archive,source)
    raw=archive.getvalue().replace(b'PGDMP-db',b'PGDMP-xx',1)
    target=tmp_path/'target';out=BytesIO()
    with pytest.raises(ValueError):stage(BytesIO(raw),out,target)
    assert out.getvalue()==b'' and not (target/key).exists()


def test_backup_rejects_traversal_links_missing_and_duplicate_entries(tmp_path):
    def archive(name,kind=None):
        payload=b'PGDMP-db';files={'database.dump':{'size':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}}
        if name!='database.dump':files[name]={'size':1,'sha256':hashlib.sha256(b'x').hexdigest()}
        manifest=json.dumps({'format':'sgancia-files-1','files':files}).encode();out=BytesIO()
        with tarfile.open(fileobj=out,mode='w') as tar:
            info=tarfile.TarInfo('manifest.json');info.size=len(manifest);tar.addfile(info,BytesIO(manifest))
            info=tarfile.TarInfo('database.dump');info.size=len(payload);tar.addfile(info,BytesIO(payload))
            info=tarfile.TarInfo(name);info.size=1
            if kind:info.type=kind;info.linkname='/etc/passwd'
            tar.addfile(info,BytesIO(b'x'))
        return out.getvalue()
    for name,kind in (('../escape',None),('objects/'+'c'*32+'.blob',tarfile.SYMTYPE),('database.dump',None)):
        out=BytesIO()
        with pytest.raises(ValueError):stage(BytesIO(archive(name,kind)),out,tmp_path/'target')
        assert out.getvalue()==b''
