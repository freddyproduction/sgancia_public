"""Portable authorized snapshots and explicit, atomic imports. Never restore accounts."""
from copy import deepcopy
from datetime import date
from decimal import Decimal,InvalidOperation
from io import StringIO
import csv,hashlib,json,time,unicodedata
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request,Query
from fastapi.responses import Response
from pydantic import Field,ValidationError,field_validator
from sqlalchemy import select,delete,func
from .schemas import Strict,ExpenseIn
from .models import Group,Participant,Expense,ExpenseRevision,Entry,Settlement,ImportBatch,ImportedExpense,GuestLink
from .db import get_db
from .security import current,cipher,throttle,digest,peer
from .groups import membership,visible,build_expense,record_expense
from .insights import lock,records,filtered
from .finance import finance_view
from .expense_tools import expense_snapshot,reconcile_allocation_order
from .money import minor
from .pdf_reports import report_pdf
router=APIRouter(prefix='/api/v1',tags=['Importazione ed esportazione'])
MAX_BYTES=2*1024*1024
MAX_ROWS=500
SCHEMA='sgancia.exchange/1'
CSV_SCHEMA='sgancia.csv/1'
FIELDS=['schema','participants','source_group','source_id','date','title','description','category','currency','exchange_rate','exchange_context','allocation_order','payers','tags','audience','items','remember_expressions','total_minor','group_currency']
csv.field_size_limit(MAX_BYTES)


def sha(value):return hashlib.sha256(value.encode()).hexdigest()


def parse_json(value):
    def pairs(items):
        result={}
        for key,val in items:
            if key in result:raise ValueError('Campi JSON duplicati')
            result[key]=val
        return result
    def invalid(_):raise ValueError('Numeri JSON non validi')
    try:
        obj=json.loads(value,object_pairs_hook=pairs,parse_constant=invalid)
        def depth(item,level=0):
            if level>20:raise ValueError('JSON troppo annidato')
            if isinstance(item,dict):
                for val in item.values():depth(val,level+1)
            elif isinstance(item,list):
                for val in item:depth(val,level+1)
            elif isinstance(item,str):
                item.encode('utf-8')
                if '\x00' in item:raise ValueError('Carattere nullo non valido')
        depth(obj);return obj
    except (json.JSONDecodeError,RecursionError,ValueError,UnicodeError):raise HTTPException(422,'JSON non valido, duplicato o troppo annidato') from None


def safe_csv(value):
    value=str(value)
    probe=value
    while probe and (probe[0].isspace() or unicodedata.category(probe[0]) in ('Cf','Cc')):probe=probe[1:]
    if value.startswith("'") or (value and unicodedata.category(value[0])=='Cc') or probe.startswith(('=','+','-','@','＝','＋','－','＠')):return "'"+value
    return value


def csv_bytes(rows,fields):
    out=StringIO(newline='');writer=csv.DictWriter(out,fieldnames=fields,lineterminator='\r\n');writer.writeheader()
    for row in rows:writer.writerow({k:safe_csv(row.get(k,'')) for k in fields})
    return ('\ufeff'+out.getvalue()).encode('utf-8')


def snapshot_quote(draft,target):
    from .exchange import read_quote
    base=draft.get('currency') or target
    if base==target:return None
    if draft.get('exchange_token'):
        try:return read_quote(draft['exchange_token'],base,target,stored=True)
        except ValueError:raise HTTPException(409,'Cambio storico non leggibile: verifica la spesa prima di esportarla') from None
    if draft.get('exchange_rate'):
        context=draft.get('exchange_context')
        if context and context['base']==base and context['quote']==target and context['rate']==draft['exchange_rate']:return context
        return {'base':base,'quote':target,'rate':draft['exchange_rate'],'source':'Manuale','date':draft['date']}
    raise HTTPException(409,'Tasso storico mancante: verifica la spesa')


def portable_draft(db,gid,eid,user,target):
    expense=db.get(Expense,eid)
    draft=deepcopy(db.get(ExpenseRevision,(eid,expense.version)).snapshot)
    draft.pop('deleted',None)
    quote=snapshot_quote(draft,target)
    draft['currency']=draft.get('currency') or target
    if quote:
        draft['exchange_rate']=quote['rate']
        draft['exchange_context']={k:quote[k] for k in ('base','quote','rate','source','date')}
    draft['exchange_token']=None
    refs=set(draft.get('audience') or [])|set(draft.get('payers',{}))
    for item in draft['items']:refs.update(item['shares']);refs.update(item.get('payers') or {})
    draft['allocation_order']=draft.get('allocation_order') or sorted(refs)
    reconcile_allocation_order(draft)
    if len(refs)>200:raise HTTPException(413,'Il formato di scambio supporta al massimo 200 riferimenti per spesa')
    # Honor the current consent, even for pre-feature numeric/legacy source snapshots.
    draft=expense_snapshot(ExpenseIn.model_validate(draft))
    return draft,quote


@router.get('/groups/{gid}/export')
def export_group(gid:str,format:Literal['json','csv','pdf']='json',q:str=Query(default='',max_length=200),start:date|None=None,end:date|None=None,category:str=Query(default='',max_length=60),tag:str=Query(default='',max_length=40),person:str=Query(default='',max_length=36),user=Depends(current),db=Depends(get_db)):
    throttle(db,'export:'+user.id,20,60)
    g,actor=lock(db,gid,user);rows=filtered(records(db,gid,actor),q,start,end,category,tag,person)
    if len(rows)>MAX_ROWS:raise HTTPException(413,'Esporta al massimo 500 spese: restringi i filtri')
    expenses=[];refs=set()
    for row in rows:
        draft,quote=portable_draft(db,gid,row['id'],user,g.currency)
        refs.update(draft.get('audience') or [])
        for item in draft['items']:refs.update(item['shares']);refs.update(item.get('payers') or {})
        expenses.append({'source_id':row['id'],'date':row['date'],'title':row['title'],'category':row['category'],'total':row['total'],'draft':draft,'conversion':quote})
    unfiltered=not any((q,start,end,category,tag,person))
    finance=finance_view(db,gid,user) if unfiltered else None
    if finance:
        for row in finance['transfers']:refs.update((row['from'],row['to']))
    people=[{'ref':p.id,'name':p.name} for p in db.scalars(select(Participant).where(Participant.group_id==gid).order_by(Participant.id)) if p.id in refs]
    # Payments are exported for consultation, never replayed as financial events on import.
    ps=[{'source_id':p.id,'sender':p.sender,'recipient':p.recipient,'amount_minor':p.amount,'audience':p.audience,'status':p.status,'kind':p.kind,'note':p.note} for p in db.scalars(select(Settlement).where(Settlement.group_id==gid)) if unfiltered and visible(p,actor)]
    extra={x for p in ps for x in (p['sender'],p['recipient'],*(p['audience'] or []))}-refs
    people.extend({'ref':p.id,'name':p.name} for p in db.scalars(select(Participant).where(Participant.group_id==gid,Participant.id.in_(extra))))
    data={'schema':SCHEMA,'group':{'source_id':gid,'name':g.name,'currency':g.currency},'participants':people,'expenses':expenses,'total':sum(r['total'] for r in rows),'finance':finance,'payments':ps,'notice':'Solo dati autorizzati del tuo account. Saldi e pagamenti sono consultivi e non vengono reimportati. Non include allegati, account, credenziali, inviti o cronologia completa.'}
    db.commit()
    return download(data,format)


def download(data,format,guest=False):
    if format=='json':content=json.dumps(data,ensure_ascii=False,allow_nan=False,indent=2).encode();media='application/json'
    elif format=='pdf':
        if len(json.dumps(data,ensure_ascii=False))>MAX_BYTES:raise HTTPException(413,'Report troppo esteso: restringi le spese esportate')
        content=report_pdf(data);media='application/pdf'
    elif guest:
        rows=[{'date':e['date'],'title':e['title'],'category':e.get('category') or '','amount':f"{Decimal(e['total'])/100:.2f}",'currency':data['group']['currency']} for e in data['expenses']]
        content=csv_bytes(rows,['date','title','category','amount','currency']);media='text/csv; charset=utf-8'
    else:
        rows=[]
        for e in data['expenses']:
            d=e['draft'];row={'schema':CSV_SCHEMA,'participants':json.dumps(data['participants'],ensure_ascii=False,separators=(',',':')),'source_group':data['group']['source_id'],'source_id':e['source_id'],'total_minor':e['total'],'group_currency':data['group']['currency']}
            for k in ('date','title','description','category','currency','exchange_rate'):row[k]=d.get(k) or ''
            for k in ('exchange_context','allocation_order','payers','tags','audience','items','remember_expressions'):row[k]=json.dumps(d.get(k),ensure_ascii=False,separators=(',',':'))
            rows.append(row)
        content=csv_bytes(rows,FIELDS);media='text/csv; charset=utf-8'
    if len(content)>20*1024*1024:raise HTTPException(413,'Esportazione troppo grande: restringi i filtri')
    return Response(content,media_type=media,headers={'Content-Disposition':f'attachment; filename="sgancia-{"ospite" if guest else "gruppo"}.{format}"','X-Content-Type-Options':'nosniff'})


class GuestExport(Strict):
    token:str=Field(min_length=20,max_length=100)
    password:str=Field(default='',max_length=128)
    format:Literal['csv','json','pdf']='pdf'


@router.post('/guest/export')
def export_guest(body:GuestExport,request:Request,db=Depends(get_db)):
    from .sharing import GuestRead,guest_projection
    throttle(db,'guest-export:'+peer(request),20,60)
    data=guest_projection(GuestRead(token=body.token,password=body.password),db,commit=False,require_exports=True)
    report={'schema':'sgancia.guest-report/1','group':{'name':data['name'],'currency':data['currency']},'participants':data['participants'],'expenses':[{k:v for k,v in row.items() if k!='attachments'} for row in data['expenses']],'total':data['total'],'notice':'Vista ospite: solo spese pubbliche e dettagli consentiti dal link. Riepilogo consultivo, non importabile.'}
    if len(report['expenses'])>MAX_ROWS:raise HTTPException(413,'Report ospite troppo esteso')
    response=download(report,body.format,guest=True)
    db.commit();return response


class PreviewIn(Strict):
    format:Literal['json','csv']
    content:str=Field(min_length=1,max_length=MAX_BYTES)
    mapping:dict[str,str]=Field(default_factory=dict,max_length=200)
    rates:dict[str,str]=Field(default_factory=dict,max_length=20)

    @field_validator('mapping')
    @classmethod
    def mapping_lengths(cls,values):
        if any(not k or len(k)>120 or len(v)>36 for k,v in values.items()):raise ValueError('Riferimenti non validi')
        return values

    @field_validator('rates')
    @classmethod
    def rates_lengths(cls,values):
        if any(len(k)!=3 or not v or len(v)>40 for k,v in values.items()):raise ValueError('Tassi non validi')
        return values


class ApplyIn(Strict):
    selected:list[int]=Field(min_length=1,max_length=MAX_ROWS)
    force_duplicates:list[int]=Field(default_factory=list,max_length=MAX_ROWS)
    confirm:bool=False


def read_file(body):
    try:size=len(body.content.encode('utf-8'))
    except UnicodeError:raise HTTPException(422,'Il file deve essere UTF-8 valido') from None
    if '\x00' in body.content:raise HTTPException(422,'Caratteri nulli non consentiti')
    if size>MAX_BYTES:raise HTTPException(413,'File massimo 2 MB')
    source_group='';names={};rows=[]
    if body.format=='json':
        data=parse_json(body.content.lstrip('\ufeff'))
        if not isinstance(data,dict) or data.get('schema')!=SCHEMA or not isinstance(data.get('group'),dict) or not isinstance(data.get('expenses'),list):raise HTTPException(422,'Formato JSON Sgancia non riconosciuto: usa un’esportazione del gruppo')
        source_group=str(data['group'].get('source_id',''))[:120]
        if not isinstance(data.get('participants',[]),list):raise HTTPException(422,'Partecipanti JSON non validi')
        for p in data.get('participants',[]):
            if not isinstance(p,dict) or not isinstance(p.get('ref'),str) or not isinstance(p.get('name'),str) or len(p['ref'])>120 or len(p['name'])>100:raise HTTPException(422,'Riferimento partecipante non valido')
            if p['ref'] in names:raise HTTPException(422,'Partecipanti duplicati')
            names[p['ref']]=p['name']
        for i,e in enumerate(data['expenses']):
            if not isinstance(e,dict):rows.append({'draft':None,'source':str(i)});continue
            rows.append({'draft':e.get('draft'),'source':str(e.get('source_id',i))[:120]})
    else:
        try:
            stream=StringIO(body.content.lstrip('\ufeff'),newline='')
            reader=csv.DictReader(stream)
            headers=reader.fieldnames or []
            if len(headers)!=len(set(headers)) or len(headers)>30:raise ValueError()
            extended='schema' in headers
            required=set(FIELDS)-{'allocation_order'} if extended else {'date','title','amount','paid_by','split_between'}
            if not required<=set(headers):raise HTTPException(422,'Colonne mancanti. Usa il modello CSV scaricabile nel pannello')
            if extended and not set(headers)<=set(FIELDS):raise HTTPException(422,'Colonne CSV Sgancia non riconosciute')
            for i,row in enumerate(reader):
                if i>=MAX_ROWS:raise HTTPException(413,'Massimo 500 righe per importazione')
                if None in row or any(v is None for v in row.values()):raise HTTPException(422,'Numero di colonne CSV non valido')
                try:
                    if extended:
                        row={k:v[1:] if v.startswith("'") else v for k,v in row.items()}
                        if row['schema']!=CSV_SCHEMA:raise HTTPException(422,'Versione CSV Sgancia non supportata')
                        if source_group and source_group!=row['source_group']:raise HTTPException(422,'Il CSV contiene gruppi differenti')
                        source_group=row['source_group'][:120]
                        participants=parse_json(row['participants'])
                        if not isinstance(participants,list):raise ValueError()
                        for p in participants:
                            if not isinstance(p,dict) or not isinstance(p.get('ref'),str) or not isinstance(p.get('name'),str) or len(p['name'])>100:raise ValueError()
                            if p['ref'] in names and names[p['ref']]!=p['name']:raise ValueError()
                            names[p['ref']]=p['name']
                        draft={k:row[k] for k in ('date','title','description','category','currency')}
                        draft['exchange_rate']=row['exchange_rate'] or None
                        for k in ('exchange_context','allocation_order','payers','tags','audience','items','remember_expressions'):draft[k]=parse_json(row.get(k,'null'))
                        rows.append({'draft':draft,'source':row['source_id'][:120]})
                    else:
                        people=[p.strip() for p in row['split_between'].split('|') if p.strip()];payer=row['paid_by'].strip()
                        if len(people)!=len(set(people)):raise ValueError()
                        refs=set(people)|{payer};names.update({r:r for r in refs})
                        audience=None if not row.get('audience','').strip() else [p.strip() for p in row['audience'].split('|') if p.strip()]
                        draft={'title':row['title'],'date':row['date'],'description':row.get('description',''),'category':row.get('category') or 'Altro','currency':row.get('currency') or None,'exchange_rate':row.get('exchange_rate') or None,'tags':[t.strip() for t in row.get('tags','').split('|') if t.strip()],'audience':audience,'items':[{'title':row.get('item') or row['title'],'amount':row['amount'],'mode':'equal','shares':{p:'1' for p in people},'payers':{payer:''}}]}
                        rows.append({'draft':draft,'source':row.get('source_id') or str(i)})
                except (HTTPException,ValueError,TypeError):rows.append({'draft':None,'source':str(i)})
        except (csv.Error,UnicodeError,ValueError):raise HTTPException(422,'CSV non valido: usa UTF-8 e separatori virgola') from None
    if not rows or len(rows)>MAX_ROWS:raise HTTPException(422,'Il file deve contenere da 1 a 500 spese')
    return source_group,names,rows


def remap_draft(raw,mapping,active,g,actor,rates,source_group):
    draft=deepcopy(raw)
    if not isinstance(draft,dict):raise ValueError('Riga o dati strutturati non validi')
    body=ExpenseIn.model_validate(draft)
    draft=body.model_dump(mode='json');draft['exchange_token']=None
    used=set(draft['audience'] or [])|set(draft['payers'])
    for item in draft['items']:used.update(item['shares']);used.update(item.get('payers') or {})
    order=draft.get('allocation_order')
    if order is None and source_group:order=sorted(used)
    if order is not None and (len(order)!=len(set(order)) or set(order)!=used):raise ValueError('Ordine di arrotondamento non coerente con i riferimenti')
    mapped={}
    for ref in used:
        target=mapping.get(ref) or (ref if source_group==g.id and ref in active else '')
        if target not in active:raise ValueError('Associa tutti i partecipanti a persone attive del gruppo')
        mapped[ref]=target
    if len(set(mapped.values()))!=len(mapped):raise ValueError('Due partecipanti della stessa spesa non possono essere uniti durante l’importazione')
    def convert(values):return {mapped[k]:v for k,v in values.items()}
    if order is not None:draft['allocation_order']=[mapped[ref] for ref in order]
    draft['payers']=convert(draft['payers'])
    if draft['audience'] is not None:draft['audience']=sorted(mapped[k] for k in draft['audience'])
    for item in draft['items']:
        item['shares']=convert(item['shares'])
        if item['payers'] is not None:item['payers']=convert(item['payers'])
    base=draft['currency'] or g.currency;draft['currency']=base
    if base in rates:
        draft['exchange_rate']=rates[base];draft['exchange_context']=None
    context=draft.get('exchange_context')
    if base!=g.currency and context and context.get('quote')!=g.currency and base not in rates:raise ValueError('La valuta del gruppo è diversa: indica un nuovo tasso di cambio')
    if base==g.currency:draft['exchange_rate']=None;draft['exchange_context']=None
    return ExpenseIn.model_validate(draft)


def normalized(body,data,currency):
    # Compare economic allocations, labels and visibility, not FX signature timestamps or input formatting.
    payload={'title':body.title.strip(),'description':body.description,'date':body.date.isoformat(),'category':body.category,'currency':currency,'audience':sorted(data['audience']) if data['audience'] is not None else None,'paid':{k:v for k,v in data['paid'].items() if v},'owed':{k:v for k,v in data['owed'].items() if v},'items':[{k:i[k] for k in ('title','amount_minor','shares','payers') if k in i} for i in data['items']],'tags':sorted(t.casefold() for t in body.tags)}
    return sha(json.dumps(payload,sort_keys=True,ensure_ascii=False))


def visible_fingerprints(db,g,actor):
    result=set()
    for e in db.scalars(select(Expense).where(Expense.group_id==g.id,Expense.deleted.is_(False))):
        if not visible(e,actor):continue
        snap=db.get(ExpenseRevision,(e.id,e.version)).snapshot
        entries=list(db.scalars(select(Entry).where(Entry.expense_id==e.id,Entry.revision==e.version)))
        data={'audience':e.audience,'paid':{x.participant_id:x.paid for x in entries if x.paid},'owed':{x.participant_id:x.owed for x in entries if x.owed},'items':e.items}
        try:
            body=ExpenseIn.model_validate({k:v for k,v in snap.items() if k!='deleted'});result.add(normalized(body,data,g.currency))
        except ValidationError:continue
    return result


@router.post('/groups/{gid}/imports/preview')
def preview_import(gid:str,body:PreviewIn,user=Depends(current),db=Depends(get_db)):
    throttle(db,'import-preview:'+user.id,20,60)
    g,actor=lock(db,gid,user,True);membership(db,gid,user,write=True)
    source_group,names,source_rows=read_file(body)
    active=set(db.scalars(select(Participant.id).where(Participant.group_id==gid,Participant.active.is_(True),Participant.merged_into.is_(None))))
    known=visible_fingerprints(db,g,actor);seen=set();origins=set();rows=[];currencies=set();refs=set(names)
    file_hash=sha(body.content)
    for index,item in enumerate(source_rows):
        raw=item['draft'];origin=sha(json.dumps([source_group or file_hash,item['source']],separators=(',',':')))
        title=raw.get('title','')[:200] if isinstance(raw,dict) and isinstance(raw.get('title',''),str) else ''
        if isinstance(raw,dict):
            try:
                schema=ExpenseIn.model_validate(raw);refs.update(schema.payers);refs.update(schema.audience or [])
                currencies.add(schema.currency or g.currency)
                for line in schema.items:refs.update(line.shares);refs.update(line.payers or {})
            except ValidationError:pass
        row={'index':index,'line':index+1,'title':title,'origin':origin,'status':'error','message':'Riga non valida','draft':None,'total':None}
        try:
            if origin in origins:raise ValueError('Riferimento di origine ripetuto nel file: correggi source_id')
            origins.add(origin)
            draft=remap_draft(raw,body.mapping,active,g,actor,body.rates,source_group)
            data=build_expense(db,gid,draft,actor);fingerprint=normalized(draft,data,g.currency)
            row.update(draft=expense_snapshot(draft),total=data['total'],paid=data['paid'],owed=data['owed'],source_currency=draft.currency,rate=draft.exchange_rate,fingerprint=fingerprint,private=draft.audience is not None,status='ready',message='Pronta')
            prior=db.scalar(select(ImportedExpense).where(ImportedExpense.group_id==gid,ImportedExpense.participant_id==actor.id,ImportedExpense.origin==origin))
            if prior:row.update(status='imported',message='Origine già importata da questo partecipante')
            elif fingerprint in known or fingerprint in seen:row.update(status='duplicate',message='Spesa identica visibile o ripetuta nel file: verifica prima di includerla')
            seen.add(fingerprint)
        except ValidationError:row['message']='Campi, date, quote o riferimenti non validi'
        except (ValueError,InvalidOperation) as exc:row['message']=str(exc)[:300]
        rows.append(row)
    if len(refs)>200 or any(not isinstance(ref,str) or not ref or len(ref)>120 for ref in refs):raise HTTPException(422,'Massimo 200 riferimenti partecipante, ciascuno entro 120 caratteri')
    # Only staging is written. Expired previews and old unused previews for this account/group are discarded.
    db.execute(delete(ImportBatch).where(ImportBatch.group_id==gid,ImportBatch.user_id==user.id,ImportBatch.applied.is_(False)))
    payload={'rows':rows,'source_hash':file_hash}
    batch=ImportBatch(group_id=gid,user_id=user.id,participant_id=actor.id,currency=g.currency,payload=cipher().encrypt(json.dumps(payload,ensure_ascii=False).encode()).decode(),expires=int(time.time())+3600)
    db.add(batch);db.flush();result={'id':batch.id,'expires':batch.expires,'currency':g.currency,'participants':[{'ref':r,'name':names.get(r,r),'suggested':r if source_group==gid and r in active else None} for r in sorted(refs)],'currencies':sorted(currencies),'rows':[{k:v for k,v in r.items() if k not in ('draft','origin','fingerprint')} for r in rows]};db.commit();return result


@router.post('/groups/{gid}/imports/{batch_id}/apply')
def apply_import(gid:str,batch_id:str,body:ApplyIn,user=Depends(current),db=Depends(get_db)):
    g,actor=lock(db,gid,user,True);membership(db,gid,user,write=True)
    batch=db.get(ImportBatch,batch_id)
    if not batch or batch.group_id!=gid or batch.user_id!=user.id or batch.participant_id!=actor.id:raise HTTPException(404,'Anteprima non disponibile')
    request_hash=sha(json.dumps(body.model_dump(),sort_keys=True))
    if batch.applied:
        if batch.response['request_hash']!=request_hash:raise HTTPException(409,'Questa anteprima è già stata confermata con una selezione differente')
        if any(not (e:=db.get(Expense,eid)) or not visible(e,actor) for eid in batch.response['ids']):raise HTTPException(404,'Importazione non disponibile')
        return {k:v for k,v in batch.response.items() if k!='request_hash'}
    if not body.confirm:raise HTTPException(422,'Conferma esplicitamente l’importazione')
    if batch.expires<=time.time():raise HTTPException(409,'Anteprima scaduta: ripeti il controllo')
    if batch.currency!=g.currency:raise HTTPException(409,'Valuta del gruppo cambiata: ripeti l’anteprima')
    selected=set(body.selected);forced=set(body.force_duplicates)
    if len(selected)!=len(body.selected) or not forced<=selected:raise HTTPException(422,'Selezione non valida')
    payload=json.loads(cipher().decrypt(batch.payload.encode()))
    if not selected<=set(range(len(payload['rows']))):raise HTTPException(422,'Riga non valida')
    fingerprints=visible_fingerprints(db,g,actor);prepared=[]
    for index in sorted(selected):
        row=payload['rows'][index]
        if row['status'] in ('error','imported') or not row['draft']:raise HTTPException(422,'Seleziona soltanto righe pronte o duplicati verificati')
        if db.scalar(select(ImportedExpense.id).where(ImportedExpense.group_id==gid,ImportedExpense.participant_id==actor.id,ImportedExpense.origin==row['origin'])):raise HTTPException(409,'Un’origine selezionata è già stata importata: ripeti l’anteprima')
        draft=ExpenseIn.model_validate(row['draft'])
        try:data=build_expense(db,gid,draft,actor)
        except (ValueError,InvalidOperation) as exc:raise HTTPException(409,'Partecipanti, pubblico o quote cambiati: ripeti l’anteprima') from None
        fp=normalized(draft,data,g.currency)
        if (fp in fingerprints or row['status']=='duplicate') and index not in forced:raise HTTPException(409,'Una spesa selezionata è duplicata: verifica e conferma esplicitamente la riga')
        fingerprints.add(fp);prepared.append((row,draft))
    ids=[]
    for row,draft in prepared:
        result=record_expense(gid,draft,'import:'+batch.id+':'+str(row['index']),user,db,commit=False)
        db.add(ImportedExpense(group_id=gid,participant_id=actor.id,origin=row['origin'],expense_id=result['id']));ids.append(result['id'])
    response={'ids':ids,'count':len(ids),'currency':g.currency,'total':sum(r['total'] for r,d in prepared)}
    batch.applied=True;batch.response={**response,'request_hash':request_hash};batch.payload=cipher().encrypt(b'{}').decode();db.commit();return response


@router.get('/imports/csv-template')
def csv_template(user=Depends(current)):
    fields=['date','title','amount','paid_by','split_between','currency','exchange_rate','category','tags','audience','description','source_id']
    content=csv_bytes([{'date':date.today().isoformat(),'title':'Cena di esempio','amount':'40.00','paid_by':'persona_a','split_between':'persona_a|persona_b','currency':'EUR','category':'Cibo','tags':'cena|weekend','source_id':'esempio-1'}],fields)
    return Response(content,media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="sgancia-modello.csv"'})
