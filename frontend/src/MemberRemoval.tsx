import {useState} from 'react'
import {api,send,type Detail,type Person} from './api'
import {Modal,ErrorMessage} from './ui'
export function MemberRemoval({detail,person,onChanged}:{detail:Detail;person:Person;onChanged:()=>Promise<void>}){
 const[preview,setPreview]=useState<{fingerprint:string}|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState('')
 const base=`/groups/${detail.id}/participants/${person.id}`
 return <><button className="text-btn danger" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{setPreview(await api(base+'/departure-preview'))}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}>Rimuovi</button>{!preview&&<ErrorMessage error={error}/>} {preview&&<Modal title="Rimuovi membro" onClose={()=>setPreview(null)}><p>Rimuovere <b>{person.name}</b> dal gruppo?</p><p>L’accesso viene revocato; spese, storico e tutti i saldi restano conservati sulla persona senza account. Il proprietario non può essere rimosso.</p><ErrorMessage error={error}/><button className="primary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{await api(base+'/depart',send('POST',{keep_balance:true,fingerprint:preview.fingerprint}));setPreview(null);await onChanged()}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}>Conferma rimozione</button></Modal>}</>
}
