export const IDENTITY_REQUIRED='sgancia:identity-required'
export function requestIdentity(status:number,message:string){
 if(status===403&&message==='Conferma nuovamente la tua identità'&&typeof window!=='undefined')window.dispatchEvent(new Event(IDENTITY_REQUIRED))
}
