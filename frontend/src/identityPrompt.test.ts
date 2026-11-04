import {afterEach,expect,it,vi} from 'vitest'
import {api,apiBlob} from './api'
import {IDENTITY_REQUIRED} from './identityEvents'
afterEach(()=>vi.unstubAllGlobals())
function setup(status:number,detail:string){const events=new EventTarget(),listener=vi.fn();events.addEventListener(IDENTITY_REQUIRED,listener);vi.stubGlobal('window',events);vi.stubGlobal('document',{cookie:''});vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status,json:async()=>({detail})}));return listener}
it('opens the identity prompt on an explicit recent-identity refusal',async()=>{const listener=setup(403,'Conferma nuovamente la tua identità');await expect(api('/admin/operations/policy')).rejects.toThrow('Conferma nuovamente');expect(listener).toHaveBeenCalledOnce();expect(fetch).toHaveBeenCalledTimes(1)})
it('also handles protected downloads',async()=>{const listener=setup(403,'Conferma nuovamente la tua identità');await expect(apiBlob('/protected-file')).rejects.toThrow();expect(listener).toHaveBeenCalledOnce()})
it('does not turn permission or login failures into identity prompts',async()=>{for(const [status,message] of [[403,'Permesso negato'],[401,'Verifica identità fallita']] as const){const listener=setup(status,message);await expect(api('/auth/reauth')).rejects.toThrow(message);expect(listener).not.toHaveBeenCalled()}})
