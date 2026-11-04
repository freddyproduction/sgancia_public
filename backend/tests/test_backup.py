from io import BytesIO
import os
import pytest
from app.backup import encrypt,decrypt,CHUNK


@pytest.mark.parametrize('size',[0,1,10000,CHUNK,CHUNK*2+17])
def test_encrypted_roundtrip(size):
    data=os.urandom(size);key=os.urandom(32);out=BytesIO()
    encrypt(BytesIO(data),out,key)
    assert data[:min(100,len(data))] not in out.getvalue() if size>=100 else True
    restored=BytesIO();decrypt(BytesIO(out.getvalue()),restored,key)
    assert restored.getvalue()==data


def test_rejects_tampering_wrong_key_truncation_and_extra_data():
    key=os.urandom(32);out=BytesIO();encrypt(BytesIO(b'financial data'*100),out,key)
    encrypted=out.getvalue()
    broken=[encrypted[:-1],encrypted[:30],encrypted+b'junk',encrypted[:40]+bytes([encrypted[40]^1])+encrypted[41:]]
    for value in broken:
        with pytest.raises(Exception):decrypt(BytesIO(value),BytesIO(),key)
    with pytest.raises(Exception):decrypt(BytesIO(encrypted),BytesIO(),os.urandom(32))
