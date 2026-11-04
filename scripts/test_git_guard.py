#!/usr/bin/env python3
"""Exercise the Git guard in disposable repositories with synthetic secrets."""
from pathlib import Path
import subprocess
import tempfile

root=Path(__file__).resolve().parents[1]
private=root/'.local';private.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory(prefix='git-guard-qa-',dir=private) as folder:
    work=Path(folder)
    def git(*args):subprocess.run(['git',*args],cwd=work,check=True,capture_output=True)
    def check(ok):
        result=subprocess.run(['python3',str(root/'scripts/check_git_secrets.py')],cwd=work,capture_output=True,text=True)
        assert (result.returncode==0)==ok
        assert secret not in result.stdout+result.stderr
    git('init','-q')
    secret='synthetic-only-secret-'+'q'*30
    (work/'.env').write_text('SGANCIA_BACKUP_KEY='+secret+'\n')
    (work/'source.py').write_text('safe = True\n');git('add','source.py');check(True)
    (work/'source.py').write_text('value = '+repr(secret)+'\n');git('add','source.py');check(False)
    (work/'source.py').write_text('safe = True\n');git('add','source.py');check(True)
    (work/'.env.example').write_text('POSTGRES_PASSWORD=synthetic-example-password\n');git('add','.env.example');check(False)
    (work/'.env.example').write_text('POSTGRES_PASSWORD=\n');git('add','.env.example');check(True)
    git('add','.env');check(False)
print('Git guard QA: valid files accepted; private values, unsafe examples and .env blocked; no secret printed.')
