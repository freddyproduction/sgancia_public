import {useState} from 'react'
import {api,send} from './api'
import {ErrorMessage} from './ui'
import {useAutoRefresh} from './live'
export function GuestPolicySettings(){
 const[enabled,setEnabled]=useState(false),[loaded,setLoaded]=useState(false),[dirty,setDirty]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
 useAutoRefresh(async()=>{const policy=await api<{enabled:boolean}>('/admin/installation/guest-links');if(!dirty)setEnabled(policy.enabled);setLoaded(true)},true,e=>setError(e.message))
 return <section className="panel settings-panel"><h2>Installazione · link ospiti</h2><p className="small muted">Interruttore globale per tutti i gruppi, disattivato di default. Se spento, blocca creazione, visualizzazione, esportazioni e download degli allegati anche sui link già creati. Riattivandolo, i link tornano utilizzabili se ancora validi e non revocati.</p><ErrorMessage error={error}/>{notice&&<p className="success" role="status">{notice}</p>}<form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');setNotice('');try{await api('/admin/installation/guest-links',send('PUT',{enabled}));setDirty(false);setNotice(enabled?'Link ospiti abilitati per tutti i gruppi.':'Link ospiti disabilitati per tutti i gruppi.')}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}><label className="check"><input type="checkbox" checked={enabled} disabled={!loaded||busy} onChange={e=>{setEnabled(e.target.checked);setDirty(true);setNotice('')}}/>Abilita link ospiti di visualizzazione</label><button className="secondary" disabled={!loaded||busy||!dirty}>Salva impostazione globale</button></form></section>
}
