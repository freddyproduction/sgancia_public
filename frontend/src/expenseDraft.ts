import type { Item } from './api'
export type ExpenseDraft={allocation_order?:string[]|null;exchange_context?:{base:string;quote:string;rate:string;source:string;date:string}|null;tags?:string[];remember_expressions?:boolean;currency?:string;exchange_token?:string|null;exchange_rate?:string|null;title:string;description:string;date:string;category:string;items:Item[];audience:string[]|null;payers?:Record<string,string>}
export type LoadedExpense={id:string;version:number;draft:ExpenseDraft}
export function restrictDraft(draft:ExpenseDraft):ExpenseDraft{
 if(draft.audience===null)return draft
 const allowed=new Set(draft.audience)
 const clean=(values:Record<string,string>)=>Object.fromEntries(Object.entries(values).filter(([id])=>allowed.has(id)))
 return {...draft,payers:clean(draft.payers??{}),items:draft.items.map(item=>({...item,shares:clean(item.shares),payers:clean(item.payers??{})}))}
}
export function newItem(people:string[],payer:string):Item{return {title:'',amount:'',mode:'equal',shares:Object.fromEntries(people.map(id=>[id,'1'])),payers:{[payer]:''}}}

export function prepareDraft(draft:ExpenseDraft):ExpenseDraft{
 const clean={...restrictDraft(draft)}
 if(clean.allocation_order){const refs=new Set([...(clean.audience??[]),...Object.keys(clean.payers??{}),...clean.items.flatMap(i=>[...Object.keys(i.shares),...Object.keys(i.payers??{})])]);clean.allocation_order=[...clean.allocation_order.filter(id=>refs.has(id)),...[...refs].filter(id=>!clean.allocation_order!.includes(id)).sort()]}
 return {...clean,items:clean.items.map(item=>{const payers=item.payers??{};const keys=Object.keys(payers);return {...item,payers:keys.length===1?{[keys[0]]:''}:payers}})}
}

export function activeDraft(draft:ExpenseDraft,active:string[]):ExpenseDraft{
 const ids=new Set(active),filter=(values:Record<string,string>)=>Object.fromEntries(Object.entries(values).filter(([id])=>ids.has(id)))
 return {...draft,audience:draft.audience===null?null:draft.audience.filter(id=>ids.has(id)),payers:filter(draft.payers??{}),items:draft.items.map(i=>({...i,shares:filter(i.shares),payers:i.payers?filter(i.payers):i.payers}))}
}
