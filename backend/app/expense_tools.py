"""Safe, versioned source values shared by manual entry and automation."""
from decimal import Decimal
from .money import minor


def expense_snapshot(body):
    draft=body.model_dump(mode='json')
    if not body.remember_expressions:
        numeric=lambda value:f'{Decimal(minor(value))/100:.2f}'
        draft['payers']={p:numeric(v) for p,v in draft['payers'].items()}
        for item in draft['items']:
            item['amount']=numeric(item['amount'])
            if item.get('payers') is not None:
                item['payers']={p:numeric(v) if v.strip() else '' for p,v in item['payers'].items()}
            if item['mode']=='exact': item['shares']={p:numeric(v) for p,v in item['shares'].items()}
    return draft


def reconcile_allocation_order(draft):
    if draft.get('allocation_order') is None:return draft
    refs=set(draft.get('payers',{}))|set(draft.get('audience') or [])
    for item in draft['items']:refs.update(item['shares']);refs.update(item.get('payers') or {})
    old=draft['allocation_order']
    draft['allocation_order']=[ref for ref in old if ref in refs]+sorted(refs-set(old))
    return draft
