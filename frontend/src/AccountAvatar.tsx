import {useEffect,useState} from 'react'
import {api,send,type User} from './api'
import {ImagePicker} from './ImagePicker'
import {ErrorMessage} from './ui'
export function Avatar({user}:{user:{name:string;avatar_url?:string|null;avatar_icon?:string|null}}){const[failed,setFailed]=useState('');return <span className="avatar">{user.avatar_url&&user.avatar_url!==failed?<img src={user.avatar_url} alt="" onError={()=>setFailed(user.avatar_url||'')}/>:user.avatar_icon||user.name[0]}</span>}

export function AccountAvatar({user,onChanged}:{user:User;onChanged:(user:User)=>void}){
 const[icon,setIcon]=useState(user.avatar_icon||''),[image,setImage]=useState<string|null|undefined>(),[dirty,setDirty]=useState(false),[error,setError]=useState(''),[busy,setBusy]=useState(false),[version,setVersion]=useState(user.avatar_version||1)
 useEffect(()=>{if(!dirty){setIcon(user.avatar_icon||'');setImage(undefined);setVersion(user.avatar_version||1)}},[user,dirty])
 const preview=image===undefined?user.avatar_url:image
 return <section className="panel settings-panel"><h2>Immagine e icona account</h2><p className="small muted">Personalizza il tuo profilo. Se presente, l’immagine ha precedenza sull’icona; altrimenti viene mostrata l’iniziale del nome.</p><form onSubmit={async e=>{e.preventDefault();setBusy(true);setError('');try{onChanged(await api('/account/avatar',{...send('PUT',{icon,...(image!==undefined?{image}:{})}),headers:{'If-Match':String(version)}}));setDirty(false)}catch(e){setError((e as Error).message)}finally{setBusy(false)}}}><div className="account-avatar-preview">{preview?<img src={preview} alt="Anteprima del profilo"/>:icon||user.name[0]}</div><ImagePicker label="Scegli immagine account" onChange={v=>{setImage(v);setDirty(true)}}/>{preview&&<button className="text-btn danger" type="button" onClick={()=>{setImage(null);setDirty(true)}}>Rimuovi immagine account</button>}<label>Icona o emoji account<input value={icon} maxLength={16} onChange={e=>{setIcon(e.target.value);setDirty(true)}}/></label><div className="emoji-choices">{['🙂','😎','🌻','🐱','🎵','🚀','⭐','🏔️'].map(v=><button key={v} type="button" onClick={()=>{setIcon(v);setImage(null);setDirty(true)}} aria-label={'Icona account '+v}>{v}</button>)}</div><ErrorMessage error={error}/><button className="primary" disabled={!dirty||busy}>Salva immagine e icona</button></form></section>
}
