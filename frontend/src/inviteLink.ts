export type IncomingInvite={token:string;register:boolean}
export function readInvitation(url:string):IncomingInvite|null{
 const parsed=new URL(url)
 if(parsed.pathname!=='/invite')return null
 const token=parsed.hash.slice(1).trim()
 if(!/^[A-Za-z0-9_-]{20,100}$/.test(token))return null
 return {token,register:parsed.searchParams.get('register')==='1'}
}
