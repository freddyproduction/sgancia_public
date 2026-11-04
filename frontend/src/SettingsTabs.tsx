import {type ComponentType,type KeyboardEvent} from 'react'
export type SettingsTab={id:string;label:string;description:string;scope:'personal'|'admin'|'root';icon:ComponentType<{size?:number}>}
export function SettingsTabs({tabs,active,onChange}:{tabs:SettingsTab[];active:string;onChange:(id:string)=>void}){
 function keyboard(event:KeyboardEvent<HTMLButtonElement>,index:number){
  const offset=event.key==='ArrowRight'?1:event.key==='ArrowLeft'?-1:0
  const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:offset?(index+offset+tabs.length)%tabs.length:-1
  if(next<0)return;event.preventDefault();onChange(tabs[next].id)
  event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus()
 }
 return <div className="settings-tabs" role="tablist" aria-label="Sezioni delle impostazioni">{tabs.map((tab,index)=><button key={tab.id} id={'settings-tab-'+tab.id} role="tab" type="button" aria-selected={active===tab.id} aria-controls={'settings-panel-'+tab.id} tabIndex={active===tab.id?0:-1} onClick={()=>onChange(tab.id)} onKeyDown={event=>keyboard(event,index)}><tab.icon size={19}/><span>{tab.label}</span>{tab.scope!=='personal'&&<small>{tab.scope==='root'?'Superadmin':'Globale'}</small>}</button>)}</div>
}
