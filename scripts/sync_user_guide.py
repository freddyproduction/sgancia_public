#!/usr/bin/env python3
"""Keep the repository user guide identical to the in-app guide."""
import json,pathlib,sys
root=pathlib.Path(__file__).resolve().parents[1]
sections=json.loads((root/'frontend/src/help-content.json').read_text())
output='# Guida utente di Sgancia\n\nGenerata dalla stessa fonte della guida nell’app: `frontend/src/help-content.json`.\n\n'
for section in sections:output+='## '+section['title']+'\n\n'+'\n\n'.join(section['paragraphs'])+'\n\n'
output=output.rstrip()+'\n'
path=root/'docs/guida-utente.md'
if '--check' in sys.argv:
 if path.read_text()!=output:raise SystemExit('Guida da aggiornare: python3 scripts/sync_user_guide.py')
else:path.write_text(output)
