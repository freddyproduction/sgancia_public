import {useState} from 'react'
import {RotateCcw,Trash2} from 'lucide-react'
import {api,send} from './api'
import {Modal,ErrorMessage} from './ui'
import {useAutoRefresh} from './live'
type Removed={id:string;name:string;currency:string;state:string;metadata_version:number}
export function GroupTrash({onClose,onChanged}:{onClose:()=>void;onChanged:()=>Promise<void>}){
 const[rows,setRows]=useState<Removed[]>([]),[error,setError]=useState(''),[busy,setBusy]=useState('')
 async function load(){setRows(await api('/group-trash'))}
 useAutoRefresh(load,true,e=>setError(e.message))
 return <Modal title="Cestino dei gruppi" onClose={onClose}><p className="small muted">Qui trovi i gruppi eliminati che puoi gestire come proprietario o admin. Il ripristino recupera dati e stato precedente; gli inviti e link revocati restano disattivati.</p><ErrorMessage error={error}/>{!rows.length&&<p className="muted">Nessun gruppo nel cestino.</p>}{rows.map(g=><div className="session-row" key={g.id}><div><b>{g.name}</b><p>{g.currency} · {g.state==='archived'?'Archiviato':g.state==='frozen'?'Congelato':'Attivo'}</p></div><button type="button" className="secondary" disabled={!!busy} onClick={async()=>{setBusy(g.id);setError('');try{await api(`/groups/${g.id}/restore`,{...send('POST'),headers:{'If-Match':String(g.metadata_version)}});await load();await onChanged()}catch(e){setError((e as Error).message)}finally{setBusy('')}}}><RotateCcw size={16}/>Ripristina</button></div>)}<p className="small muted"><Trash2 size={14}/> I gruppi archiviati ripristinati restano nascosti nell’elenco finché non attivi “Mostra archiviati”.</p></Modal>
}
