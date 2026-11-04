import {useEffect,useRef,type DependencyList} from 'react'
const EVENT='sgancia:changed'
let channel:BroadcastChannel|null=null
function changesChannel(){if(typeof window!=='undefined'&&typeof BroadcastChannel!=='undefined'&&!channel)channel=new BroadcastChannel('sgancia-changes');return channel}
export function notifyChange(){if(typeof window==='undefined')return;window.dispatchEvent(new Event(EVENT));changesChannel()?.postMessage('changed')}
export function useAutoRefresh(refresh:()=>Promise<void>,enabled=true,onError?:(error:Error)=>void,dependencies:DependencyList=[]){
 const current=useRef(refresh),errorHandler=useRef(onError);current.current=refresh;errorHandler.current=onError
 useEffect(()=>{
  if(!enabled)return
  let active=true,running=false,queued=false
  async function reload(){if(!active||document.hidden)return;if(running){queued=true;return}running=true;try{await current.current()}catch(error){if(active)errorHandler.current?.(error as Error)}finally{running=false;if(active&&queued){queued=false;void reload()}}}
  const external=()=>{void reload()}
  const shared=changesChannel();shared?.addEventListener('message',external)
  window.addEventListener(EVENT,external);window.addEventListener('focus',external);window.addEventListener('online',external);document.addEventListener('visibilitychange',external)
  const timer=setInterval(external,2000);void reload()
  return()=>{active=false;clearInterval(timer);shared?.removeEventListener('message',external);window.removeEventListener(EVENT,external);window.removeEventListener('focus',external);window.removeEventListener('online',external);document.removeEventListener('visibilitychange',external)}
 },[enabled,...dependencies])
}
