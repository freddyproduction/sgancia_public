import os
from pathlib import Path
if __name__=='__main__':
    path=Path(os.environ.get('SGANCIA_BACKUP_DIR','/app/backups'));path.mkdir(parents=True,exist_ok=True);os.chown(path,10001,10001);os.chmod(path,0o700)
