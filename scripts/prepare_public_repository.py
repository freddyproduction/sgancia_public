#!/usr/bin/env python3
"""Export committed source only into a NEW local public repository. Never pushes."""
import argparse,pathlib,subprocess
root=pathlib.Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('--output',default='.local/publication/sgancia-public');args=parser.parse_args()
target=(root/args.output).resolve()
if not target.is_relative_to(root/'.local/publication'):raise SystemExit('Destinazione consentita soltanto dentro .local/publication della cartella master')
if target.exists():raise SystemExit('La destinazione esiste già: scegliere una nuova cartella, nessun file viene sovrascritto')
def git(*args):return subprocess.check_output(['git',*args],cwd=root)
if git('status','--porcelain','--untracked-files=no').strip():raise SystemExit('Prima verificare e committare le modifiche: si esporta solo HEAD')
subprocess.run(['python3','scripts/check_git_secrets.py','--all'],cwd=root,check=True)
allowed_dirs={'backend','frontend','scripts','docs','.github','.githooks'}
allowed_files={'README.md','ROADMAP.md','CHANGELOG.md','AUTHORS.md','CONTRIBUTING.md','SECURITY.md','LICENSE','Dockerfile','docker-compose.yml','compose.qa.yml','.dockerignore','.gitignore','.env.example','.env.server.example'}
entries=[]
for item in git('ls-tree','-rz','--full-tree','HEAD').split(b'\0'):
 if not item:continue
 header,name=item.split(b'\t',1);mode,kind,oid=header.decode().split();path=pathlib.PurePosixPath(name.decode())
 if path.parts[0] not in allowed_dirs and str(path) not in allowed_files:continue
 if path.parts[:2]==('docs','screenshots') or str(path)=='docs/verifiche.md':continue
 if mode not in ('100644','100755') or kind!='blob':raise SystemExit('File non regolare: esportazione interrotta')
 entries.append((path,mode,oid))
target.mkdir(parents=True)
for path,mode,oid in entries:
 destination=target/str(path);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(git('cat-file','blob',oid));destination.chmod(0o755 if mode=='100755' else 0o644)
subprocess.run(['git','init','-b','main',str(target)],check=True,stdout=subprocess.DEVNULL)
print(f'Preparati {len(entries)} file in {target}. Nessun remoto, commit pubblico o invio effettuato. Configurare prima identità pubblica e destinazione.')
