import { describe,it,expect } from 'vitest'
import { decodeBase64url,encodeBase64url,convertOptions } from './passkeys'
describe('WebAuthn binary protocol',()=>{
 it('preserves zero, high-bit and URL-special bytes without padding',()=>{
   const binary=new Uint8Array([0,1,127,128,254,255]).buffer
   expect(encodeBase64url(binary)).toBe('AAF_gP7_')
   expect([...new Uint8Array(decodeBase64url('AAF_gP7_'))]).toEqual([0,1,127,128,254,255])
 })
 it('converts opaque challenge and credential IDs without mutating server options',()=>{
   const source={challenge:'AAF_gP7_',user:{id:'AAE'},allowCredentials:[{id:'_w'}],excludeCredentials:[{id:'gA'}]}
   const result=convertOptions(source)
   expect([...new Uint8Array(result.challenge)]).toEqual([0,1,127,128,254,255])
   expect([...new Uint8Array(result.user!.id as ArrayBuffer)]).toEqual([0,1])
   expect([...new Uint8Array(result.allowCredentials![0].id as ArrayBuffer)]).toEqual([255])
   expect([...new Uint8Array(result.excludeCredentials![0].id as ArrayBuffer)]).toEqual([128])
   expect(source.challenge).toBe('AAF_gP7_')
   expect(source.user.id).toBe('AAE')
 })
 it('rejects malformed binary values instead of producing an authenticator request',()=>{
   expect(()=>decodeBase64url('@@not-valid')).toThrow()
 })
})

describe('installation key password manager',()=>{
 it('offers storage only through a supported secure browser, never app storage',async()=>{
  const {vi}=await import('vitest');const {offerInstallationPassword}=await import('./passkeys');const store=vi.fn().mockResolvedValue(undefined)
  class PasswordCredential {constructor(public data:{id:string;password:string;name:string}){}}
  vi.stubGlobal('window',{isSecureContext:true,PasswordCredential});vi.stubGlobal('navigator',{credentials:{store}})
  try{await offerInstallationPassword('synthetic-test-key');expect(store).toHaveBeenCalledOnce();expect(store.mock.calls[0][0].data).toEqual({id:'Sgancia · accesso installazione',password:'synthetic-test-key',name:'Chiave di accesso installazione Sgancia'})}finally{vi.unstubAllGlobals()}
 })
 it('does not block access if a browser declines saving',async()=>{
  const {vi}=await import('vitest');const {offerInstallationPassword}=await import('./passkeys')
  vi.stubGlobal('window',{isSecureContext:true,PasswordCredential:class{}});vi.stubGlobal('navigator',{credentials:{store:vi.fn().mockRejectedValue(Error('declined'))}})
  try{await expect(offerInstallationPassword('synthetic-test-key')).resolves.toBeUndefined()}finally{vi.unstubAllGlobals()}
 })
})
