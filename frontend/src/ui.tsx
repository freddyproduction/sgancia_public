import {useLayoutEffect,useRef,useId,type ReactNode} from 'react'
import {createPortal} from 'react-dom'
import { X } from 'lucide-react'
export function Modal({title,children,onClose}:{title:string;children:ReactNode;onClose:()=>void}){
 const ref=useRef<HTMLDialogElement>(null),heading=useRef<HTMLHeadingElement>(null),titleId=useId(),pointer=useRef(false)
 useLayoutEffect(()=>{
  const dialog=ref.current,previous=document.activeElement as HTMLElement|null
  if(!dialog)return
  dialog.showModal()
  // A static heading keeps long forms at the top; native dialog isolates the background.
  heading.current?.focus({preventScroll:true});dialog.scrollTop=0
  return()=>{dialog.close();if(previous?.isConnected&&!previous.closest('[inert]'))previous.focus({preventScroll:true})}
 },[])
 return createPortal(<dialog ref={ref} className="overlay" aria-modal="true" aria-labelledby={titleId} onCancel={e=>{e.preventDefault();e.stopPropagation();onClose()}} onPointerDown={e=>{pointer.current=e.target===e.currentTarget}} onClick={e=>{if(pointer.current&&e.target===e.currentTarget)onClose();pointer.current=false}}><section className="modal"><header><h2 ref={heading} tabIndex={-1} id={titleId}>{title}</h2><button type="button" className="icon" aria-label="Chiudi" onClick={onClose}><X size={20}/></button></header>{children}</section></dialog>,document.body)
}
export function ErrorMessage({error}:{error:string}){return error?<p className="error" role="alert">{error}</p>:null}
