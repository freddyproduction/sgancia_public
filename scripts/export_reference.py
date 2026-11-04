#!/usr/bin/env python3
"""Generate public route/table inventories from code without connecting to a database."""
import os,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1]
os.environ['SGANCIA_DATABASE_URL']='sqlite://';os.environ['SGANCIA_PUBLIC_ORIGIN']='http://localhost:8088'
sys.path.insert(0,str(root/'backend'))
from app.main import app
from app.db import Base
schema=app.openapi()
api='# Catalogo API generato\n\nVersione '+schema['info']['version']+'. Fonte autorevole: `/api/openapi.json`; interfaccia `/api/docs`.\n\n| Metodo | Percorso | Operazione |\n|---|---|---|\n'
for path,methods in sorted(schema['paths'].items()):
 for method,op in methods.items():
  if method in ('get','post','put','patch','delete'):api+=f"| {method.upper()} | `{path}` | {op.get('summary','')} |\n"
db='# Catalogo database generato\n\nGenerato dai modelli SQLAlchemy; le migrazioni restano la fonte per vincoli SQL aggiuntivi. Nessun dato di installazione incluso.\n\n'
for name,table in sorted(Base.metadata.tables.items()):
 db+='## '+name+'\n\n| Colonna | Tipo | Nullable | Riferimenti |\n|---|---|---|---|\n'
 for c in table.columns:db+=f"| {c.name} | {c.type} | {'sì' if c.nullable else 'no'} | {', '.join(sorted(f.target_fullname for f in c.foreign_keys))} |\n"
 db+='\n'
for name,content in [('api-reference.md',api),('database-reference.md',db)]:
 content=content.rstrip()+'\n'
 p=root/'docs'/name
 if '--check' in sys.argv:
  if not p.exists() or p.read_text()!=content:raise SystemExit('Rigenerare i cataloghi con scripts/export_reference.py')
 else:p.write_text(content)
