import type {ButtonHTMLAttributes,ReactNode} from 'react'
export function ActionButton({label,help,children,className='',...props}:{label:string;help:string;children:ReactNode}&ButtonHTMLAttributes<HTMLButtonElement>){
 return <button {...props} type="button" className={'icon expense-action '+className} title={label+' — '+help} aria-description={help}>{children}<span className="expense-action-label">{label}</span></button>
}
