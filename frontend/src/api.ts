import { notifyChange } from './live'
export class ApiError extends Error { status:number; constructor(status:number,message:string){super(message);this.status=status} }
export async function api<T=unknown>(path:string, options:RequestInit={}):Promise<T>{
  const csrf=document.cookie.split('; ').find(v=>v.startsWith('sg_csrf='))?.split('=')[1]??''
  const res=await fetch('/api/v1'+path,{...options,credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRF-Token':decodeURIComponent(csrf),...options.headers}})
  if(!res.ok){const body=await res.json().catch(()=>({}));throw new ApiError(res.status,typeof body.detail==='string'?body.detail:'Controlla i dati inseriti e riprova.')}
  const result=res.status===204?undefined as T:await res.json()
  const method=(options.method??'GET').toUpperCase()
  if(!['GET','HEAD','OPTIONS'].includes(method)&&(!path.startsWith('/auth/')||path==='/auth/preferences')&&path!=='/calculator'&&path!=='/currency-conversion'&&!path.endsWith('/preview')&&path!=='/guest/view')notifyChange()
  return result
}
export const send=(method:string,body?:unknown):RequestInit=>({method,body:body===undefined?undefined:JSON.stringify(body)})
export type User={id:string;name:string;email:string;admin:boolean;superadmin?:boolean;totp:boolean;email_verified?:boolean;theme:'light'|'dark'}
export type Group={id:string;name:string;currency:string;state:string;description:string;icon:string;image_url:string|null;metadata_version:number;smart_balances:boolean}
export type Person={id:string;name:string;virtual:boolean;role:string;active?:boolean;merged_into?:string|null}
export type Detail=Group&{participants:Person[];my_participant:string;role:string}
export type Expense={tags?:string[];id:string;title:string;date:string;category:string;description:string;total:number;secret:boolean;version:number}
export type Scope={private:boolean;audience:string[]|null;total:number;balances:Record<string,number>;suggestions:{from:string;to:string;amount:number}[]}
export type Item={title:string;amount:string;mode:string;shares:Record<string,string>;payers?:Record<string,string>}
export const money=(n:number,currency='EUR')=>new Intl.NumberFormat('it-IT',{style:'currency',currency}).format(n/100)

export const minorToDecimal=(value:number)=>{const cents=BigInt(value);return `${cents/100n}.${String(cents%100n).padStart(2,'0')}`}

export type Transfer={from:string;to:string;amount:number;private:boolean;fingerprint:string;components:{audience:string[]|null;amount:number}[]}
export type Finance={summary:{expenses_total:number;paid:number;owed:number;sent:number;received:number;balance:number;receivable:number;payable:number};transfers:Transfer[]}


export async function apiBlob(path:string,options:RequestInit={}):Promise<Blob>{
 const res=await fetch('/api/v1'+path,{...options,credentials:'same-origin',headers:{'Content-Type':'application/json',...options.headers}})
 if(!res.ok){const body=await res.json().catch(()=>({}));throw new ApiError(res.status,typeof body.detail==='string'?body.detail:'File non disponibile.')}
 return res.blob()
}
export function saveBlob(blob:Blob,filename:string){const url=URL.createObjectURL(blob);const link=document.createElement('a');link.href=url;link.download=filename;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),30000)}
