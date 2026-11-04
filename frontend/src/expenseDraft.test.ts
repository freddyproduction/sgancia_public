import {describe,it,expect} from 'vitest'
import {restrictDraft,prepareDraft,activeDraft,type ExpenseDraft} from './expenseDraft'
import {minorToDecimal} from './api'

describe('spesa riservata',()=>{
 it('removes excluded shares AND advances from every item without mutating the original',()=>{
  const draft:ExpenseDraft={title:'Regalo',description:'',date:'2026-11-02',category:'Regali',audience:['alice','bob'],payers:{alice:'60',excluded:'20'},items:[{title:'Prima voce',amount:'60',mode:'equal',shares:{alice:'1',bob:'1',excluded:'1'},payers:{alice:'',excluded:''}},{title:'Seconda voce',amount:'20',mode:'percent',shares:{bob:'100',excluded:'0'},payers:{excluded:''}}]}
  const clean=restrictDraft(draft)
  expect(clean.items[0].shares).toEqual({alice:'1',bob:'1'})
  expect(clean.items[0].payers).toEqual({alice:''})
  expect(clean.items[1].payers).toEqual({})
  expect(clean.payers).toEqual({alice:'60'})
  expect(draft.items[0].shares).toHaveProperty('excluded')
 })
 it('keeps a payer who is visible even when they owe no share',()=>{
  const draft:ExpenseDraft={title:'Anticipo',description:'',date:'2026-11-02',category:'Altro',audience:['payer','debtor'],items:[{title:'',amount:'60',mode:'equal',shares:{debtor:'1'},payers:{payer:''}}]}
  expect(restrictDraft(draft).items[0].payers).toEqual({payer:''})
 })
})
describe('payment payload amounts',()=>{
 it('serializes minor units exactly at cent and maximum supported values',()=>{
  expect(minorToDecimal(1)).toBe('0.01')
  expect(minorToDecimal(12345)).toBe('123.45')
  expect(minorToDecimal(1_000_000_000_000)).toBe('10000000000.00')
 })
})

it('keeps a sole payer automatic when editing a legacy amount or removing the other payer',()=>{
 const original:ExpenseDraft={title:'Cena',description:'',date:'2026-11-02',category:'Altro',audience:['alice'],items:[{title:'',amount:'40',mode:'equal',shares:{alice:'1'},payers:{alice:'20',excluded:'20'}}]}
 const draft=prepareDraft(original)
 expect(draft.items[0].payers).toEqual({alice:''})
 expect(original.items[0].payers).toEqual({alice:'20',excluded:'20'})
})

it('copies only active references without reallocating missing exact amounts or mutating source',()=>{
 const source:ExpenseDraft={title:'QA',description:'',date:'2026-11-03',category:'Altro',tags:['QA'],remember_expressions:true,audience:['a','b'],items:[{title:'',amount:'10',mode:'exact',shares:{a:'4',b:'6'},payers:{b:''}}]}
 const copy=activeDraft(source,['a'])
 expect(copy.audience).toEqual(['a']);expect(copy.items[0].shares).toEqual({a:'4'});expect(copy.items[0].payers).toEqual({})
 expect(copy.items[0].amount).toBe('10');expect(source.items[0].shares).toHaveProperty('b');expect(copy.tags).toEqual(['QA']);expect(copy.remember_expressions).toBe(true)
})

it('preserves imported rounding order while reconciling changed participants without mutating source',()=>{
 const draft:ExpenseDraft={title:'Imported',description:'',date:'2026-11-03',category:'Altro',audience:null,allocation_order:['b','a','gone'],items:[{title:'',amount:'0.01',mode:'equal',shares:{a:'1',b:'1',c:'1'},payers:{a:''}}]}
 const result=prepareDraft(draft)
 expect(result.allocation_order).toEqual(['b','a','c'])
 expect(draft.allocation_order).toEqual(['b','a','gone'])
})
