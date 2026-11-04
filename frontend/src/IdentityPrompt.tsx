import {useEffect,useState} from 'react'
import {api,send,type User} from './api'
import {IDENTITY_REQUIRED} from './identityEvents'
import {Modal,ErrorMessage} from './ui'
export function IdentityPrompt(){
 const[open,setOpen]=useState(false)
 useEffect(()=>{const show=()=>setOpen(true);window.addEventListener(IDENTITY_REQUIRED,show);return()=>window.removeEventListener(IDENTITY_REQUIRED,show)},[])
 return open?<IdentityForm onClose={()=>setOpen(false)}/>:null
}
function IdentityForm({onClose}:{onClose:()=>void}){
 const[user,setUser]=useState<User|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[verified,setVerified]=useState(false)
 useEffect(()=>{let active=true;api<User>('/auth/me').then(u=>{if(active)setUser(u)}).catch(()=>{if(active)setError('Sessione non disponibile: chiudi e accedi nuovamente a Sgancia.')});return()=>{active=false}},[])
 return <Modal title={verified?'Identità confermata':'Conferma la tua identità'} onClose={onClose}>{verified?<><p className="success" role="status">Verifica completata. Torna al modulo e premi nuovamente il pulsante dell’operazione.</p><p className="small muted">L’operazione non viene ripetuta automaticamente.</p><button className="primary full" onClick={onClose}>Torna all’operazione</button></>:<><p>Per proteggere il tuo account, questa operazione richiede una nuova conferma. Inserisci la password del tuo account Sgancia{user?.totp?' e il codice MFA o di recupero':''}.</p><p className="small muted">Non serve la chiave globale dell’installazione. Dopo la verifica potrai riprovare l’operazione; i dati del modulo rimangono nella pagina.</p><ErrorMessage error={error}/>{user?<form onSubmit={async e=>{e.preventDefault();const form=e.currentTarget;const data=new FormData(form);setBusy(true);setError('');try{await api('/auth/reauth',send('POST',{email:user.email,password:String(data.get('password')??''),code:String(data.get('code')??'')}));form.reset();setVerified(true)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}><label>Email account<input type="email" value={user.email} readOnly autoComplete="username"/></label><label>Password account<input name="password" type="password" autoComplete="current-password" required disabled={busy}/></label>{user.totp&&<label>Codice MFA o recupero<input name="code" autoComplete="one-time-code" required disabled={busy}/></label>}<button className="primary full" disabled={busy}>{busy?'Verifica in corso…':'Conferma identità'}</button><button className="secondary full" type="button" onClick={onClose}>Annulla</button></form>:!error&&<p role="status">Caricamento account…</p>}</>}</Modal>
}
