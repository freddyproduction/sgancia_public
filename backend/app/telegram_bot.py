"""Private-chat command adapter. Financial services and update acknowledgements share a transaction."""
import json,time,uuid
from sqlalchemy import func
from datetime import datetime
from decimal import Decimal,InvalidOperation
from zoneinfo import ZoneInfo
from fastapi import HTTPException
from sqlalchemy import select,delete,case
from .models import (Instance,User,Group,Participant,Expense,ExpenseRevision,Settlement,Notification,NotificationPreference,RateBucket,
 TelegramState,TelegramLink,TelegramGrant,TelegramUpdate,TelegramAction,TelegramOutbox)
from .security import token,digest,audit
from .telegram_config import configuration,seal,unseal
from .telegram_account import link_live
from .groups import membership,visible,build_expense,record_expense
from .schemas import ExpenseIn
from .config import settings
from .money import minor
from . import telegram_api
from .db import SessionLocal

HELP='Comandi: /gruppi /saldi /spesa /spese /rimborsi /foto /notifiche /riepilogo /web /annulla /scollega. Per conoscere il tuo ID usa /id. Non inviare mai password o chiavi globali in chat.'


def enqueue_update(db,cfg,data):
    if not isinstance(data,dict) or type(data.get('update_id')) is not int or not 0<=data['update_id']<2**63:raise HTTPException(400,'Aggiornamento non valido')
    if len(json.dumps(data))>262144:raise HTTPException(413,'Aggiornamento troppo grande')
    if not any(k in data for k in ('message','callback_query')):return
    dialect=db.bind.dialect.name
    if dialect=='postgresql':from sqlalchemy.dialects.postgresql import insert
    else:from sqlalchemy.dialects.sqlite import insert
    db.execute(insert(TelegramUpdate).values(generation=cfg['generation'],update_id=data['update_id'],payload=seal(data),created=int(time.time()),status='pending',error='').on_conflict_do_nothing(index_elements=['generation','update_id']))


def rate(db,key,limit,seconds=60):
    now=int(time.time());hashed=digest(key+':'+str(now//seconds))
    if db.bind.dialect.name=='postgresql':from sqlalchemy.dialects.postgresql import insert
    else:from sqlalchemy.dialects.sqlite import insert
    row=insert(RateBucket).values(key=hashed,hits=1,window=now)
    value=db.execute(row.on_conflict_do_update(index_elements=['key'],set_={'hits':RateBucket.hits+1}).returning(RateBucket.hits)).scalar_one()
    return value<=limit


def group_lock(db,gid):
    return db.scalar(select(Group).where(Group.id==gid).with_for_update().execution_options(populate_existing=True))


def money(value,currency):return f'{Decimal(value)/100:.2f} {currency}'


def draft(link):return unseal(link.draft) if link.draft and link.draft_expires>time.time() else {}


def save_draft(link,value):
    if len(json.dumps(value))>2000000:raise HTTPException(422,'Bozza troppo grande: completa questa spesa dal web')
    link.draft=seal(value);link.draft_expires=int(time.time())+1800


def button(db,link,label,kind,**values):
    clear=token();db.add(TelegramAction(token_hash=digest(clear),user_id=link.user_id,telegram_id=link.telegram_id,revision=link.action_version,payload=seal({'kind':kind,**values}),expires=int(time.time())+600))
    return {'text':label[:60],'callback_data':'t:'+clear}


def say(db,link,text,buttons=None,guard=None,chat_id=None,dedup=None,notification=None):
    uid=link.user_id if link else None;tid=link.telegram_id if link else chat_id;cfg=configuration(db)
    # Button is on the last chunk so the full financial preview arrives before confirmation.
    chunks=[text[i:i+3500] for i in range(0,len(text),3500)] or ['Sgancia']
    for i,chunk in enumerate(chunks[:20]):
        payload={'text':chunk,'protect_content':True}
        if buttons and i==len(chunks)-1:payload['reply_markup']={'inline_keyboard':[[b] for b in buttons]}
        db.add(TelegramOutbox(generation=cfg['generation'],telegram_id=tid,user_id=uid,auth_version=link.auth_version if link else None,gate_version=link.gate_version if link else None,link_revision=link.revision if link else None,payload=seal(payload),guard=seal(guard) if guard else None,expires=int(time.time())+600,notification_id=notification,dedup=dedup if len(chunks)==1 else None))


def menu(db,link):
    say(db,link,HELP,[button(db,link,label,'command',command=cmd) for label,cmd in [('Gruppi','/gruppi'),('Saldi','/saldi'),('Nuova spesa','/spesa'),('Spese e foto','/spese'),('Rimborsi','/rimborsi'),('Notifiche','/notifiche'),('Apri Sgancia','/web')]])


def scope_guard(db,gid,actor,link):
    rows=list(db.scalars(select(Expense).where(Expense.group_id==gid,Expense.deleted.is_(False))))
    return {'group':gid,'expenses':[{'id':e.id,'version':e.version,'audience':e.audience} for e in rows if visible(e,actor) and (link.allow_private or e.audience is None)],'payments':[{'id':p.id,'audience':p.audience,'status':p.status} for p in db.scalars(select(Settlement).where(Settlement.group_id==gid)) if visible(p,actor) and (link.allow_private or p.audience is None)]}


def notification_allowed(db,n,user,link):
    from .notifications import permitted,preferences
    if not permitted(db,n,user) or n.event_key.startswith('email:'):return False
    if link.allow_private:return True
    if n.audience is not None:return False
    if n.kind=='expense':
        e=db.get(Expense,n.resource)
        return bool(e and e.audience is None)
    if n.kind=='payment':
        p=db.get(Settlement,n.resource)
        return bool(p and p.audience is None)
    if n.kind=='reminder':return finance(db,n.group_id,user,link)['summary']['payable']>=preferences(db,user.id,n.group_id)['threshold']
    return True


def guard_valid(db,user,link,guard):
    if not guard:return True
    if guard.get('notifications'):
        for nid in guard['notifications']:
            n=db.get(Notification,nid)
            if not n or not notification_allowed(db,n,user,link):return False
    if 'groups' in guard:
        try:
            for gid in guard['groups']:membership(db,gid,user)
        except HTTPException:return False
        return True
    if guard.get('notification'):
        from .notifications import permitted
        n=db.get(Notification,guard['notification'])
        return bool(n and notification_allowed(db,n,user,link))
    try:_,actor=membership(db,guard['group'],user)
    except HTTPException:return False
    for e in guard.get('expenses',[]):
        row=db.get(Expense,e['id'])
        if not row or row.deleted!=e.get('deleted',False) or row.group_id!=guard['group'] or row.version!=e['version'] or row.audience!=e['audience'] or not visible(row,actor) or (row.audience is not None and not link.allow_private):return False
    for p in guard.get('payments',[]):
        row=db.get(Settlement,p['id'])
        if not row or row.group_id!=guard['group'] or row.audience!=p['audience'] or row.status!=p['status'] or not visible(row,actor) or (row.audience is not None and not link.allow_private):return False
    return True


def finance(db,gid,user,link):
    if link.allow_private:
        from .finance import finance_view
        return finance_view(db,gid,user)
    from .insights import records,payments,projection
    group,actor=membership(db,gid,user)
    rows=[r for r in records(db,gid,actor) if r['audience'] is None]
    pays=[{'sender':p.sender,'recipient':p.recipient,'amount':p.amount,'audience':None,'status':p.status} for p in payments(db,gid,actor) if p.audience is None]
    value=projection(rows,pays,actor.id,group.smart_balances)
    from .finance import transfer_fingerprint
    transfers=[{**t,'public_only':True,'components':[{'audience':None,'amount':t['amount']}],'fingerprint':transfer_fingerprint([{'audience':None,'amount':t['amount']}],group.currency)} for t in value['transfers']]
    return {'summary':value,'transfers':transfers}


def groups_menu(db,user,link,command):
    groups=list(db.scalars(select(Group).join(Participant,Participant.group_id==Group.id).where(Participant.user_id==user.id,Participant.active.is_(True),Group.deleted.is_(False)).order_by(Group.name,Group.id)))
    buttons=[button(db,link,g.name,'choose',group=g.id,command=command) for g in groups[:40]]
    say(db,link,'Scegli il gruppo. Gli archiviati sono in sola lettura.' if groups else 'Nessun gruppo disponibile. Gestisci inviti e associazioni dal web.',buttons+[{'text':'Gestione completa sul web','url':settings.public_origin}],{'groups':[g.id for g in groups[:40]]})


def selected(db,user,link,gid,command):
    group,actor=membership(db,gid,user)
    current=draft(link);save_draft(link,{'group':gid,'last_expense':current.get('last_expense')})
    web={'text':'Gestione completa sul web','url':settings.public_origin+'/groups/'+gid}
    if command in ('/gruppi','/web'):
        say(db,link,group.name+' · '+group.currency,[button(db,link,label,'choose',group=gid,command=cmd) for label,cmd in [('Saldi','/saldi'),('Nuova spesa','/spesa'),('Spese e foto','/spese'),('Rimborsi','/rimborsi')]]+[web],{'group':gid});return
    if command in ('/saldi','/riepilogo'):
        view=finance(db,gid,user,link);s=view['summary'];names={p.id:p.name for p in db.scalars(select(Participant).where(Participant.group_id==gid))}
        text=f"{group.name}\nTi devono: {money(s['receivable'],group.currency)}\nDevi restituire: {money(s['payable'],group.currency)}\nSaldo netto: {money(s['balance'],group.currency)}\n"+('Pubbliche e riservate autorizzate.' if link.allow_private else 'Solo spese pubbliche: i tuoi saldi completi possono essere diversi sul web.')
        for t in view['transfers']:
            if actor.id in (t['from'],t['to']):text+='\n'+names.get(t['from'],'Persona')+' → '+names.get(t['to'],'Persona')+': '+money(t['amount'],group.currency)
        say(db,link,text,[web],scope_guard(db,gid,actor,link));return
    if command=='/spesa':
        membership(db,gid,user,write=True);save_draft(link,{'group':gid,'step':'title','items':[],'audience':None,'currency':group.currency});say(db,link,'Come si chiama la spesa? Invia il titolo, oppure /annulla.');return
    if command in ('/spese','/foto','/cestino'):
        rows=[r for r in db.scalars(select(Expense).where(Expense.group_id==gid,Expense.deleted.is_(command=='/cestino')).order_by(Expense.date.desc(),Expense.id)) if visible(r,actor) and (link.allow_private or r.audience is None)]
        buttons=[button(db,link,r.title,'expense_view',group=gid,expense=r.id,version=r.version,audience=r.audience,deleted=r.deleted) for r in rows[:30]]
        say(db,link,'Scegli una spesa: modifica, duplica, allega uno scontrino o gestisci il cestino. Le prime 30 sono mostrate; l’elenco completo è sul web.',buttons+[web],{'group':gid,'expenses':[{'id':r.id,'version':r.version,'audience':r.audience,'deleted':r.deleted} for r in rows[:30]]});return
    if command=='/rimborsi':
        view=finance(db,gid,user,link);names={p.id:p.name for p in db.scalars(select(Participant).where(Participant.group_id==gid))};buttons=[]
        if actor.role!='viewer' and group.state!='archived':
            for t in view['transfers']:
                if actor.id not in (t['from'],t['to']):continue
                label=('Conferma incasso da ' if actor.id==t['to'] else 'Segnala pagamento a ')+names.get(t['from'] if actor.id==t['to'] else t['to'],'Persona')+' '+money(t['amount'],group.currency)
                buttons.append(button(db,link,label,'payment_preview',group=gid,transfer=t))
            for p in db.scalars(select(Settlement).where(Settlement.group_id==gid,Settlement.recipient==actor.id,Settlement.status.in_(['pending','confirmed'])).order_by(Settlement.created.desc()).limit(20)):
                if not visible(p,actor) or (p.audience is not None and not link.allow_private):continue
                buttons.append(button(db,link,('Conferma rimborso ' if p.status=='pending' else 'Ripristina debito ')+money(p.amount,group.currency),'transition_preview',group=gid,payment=p.id,status=p.status,audience=p.audience))
        say(db,link,'Solo il ricevente può confermare l’incasso. Il pagatore può segnalare un pagamento che resta in attesa. Ogni operazione richiede conferma.',buttons[:40]+[web],scope_guard(db,gid,actor,link));return


def people(db,gid,allowed=None):
    return [p for p in db.scalars(select(Participant).where(Participant.group_id==gid,Participant.active.is_(True)).order_by(Participant.name,Participant.id)) if not p.merged_into and (allowed is None or p.id in allowed)]


def selection(db,user,link,state,kind,page=0):
    group,actor=membership(db,state['group'],user,write=True)
    allowed=state.get('audience') if kind!='audience' else None;rows=people(db,group.id,allowed)
    chosen=state.get('selected',[]);buttons=[]
    for p in rows[page*20:page*20+20]:buttons.append(button(db,link,('✓ ' if p.id in chosen else '')+p.name,'toggle',selection=kind,person=p.id,page=page))
    if page:buttons.append(button(db,link,'Pagina precedente','selection',selection=kind,page=page-1))
    if (page+1)*20<len(rows):buttons.append(button(db,link,'Pagina seguente','selection',selection=kind,page=page+1))
    buttons.append(button(db,link,'Conferma selezione','selection_done',selection=kind))
    say(db,link,{'audience':'Chi può conoscere la spesa? Devi essere incluso.','shares':'Chi partecipa a questa voce?','payers':'Chi ha pagato questa voce? Puoi scegliere più persone.'}[kind],buttons,{'group':group.id})


def prompt_item(db,user,link,state):
    state['step']='item_title';state.pop('current',None);save_draft(link,state);say(db,link,'Descrizione della voce? Invia - per lasciarla vuota.')


def value_prompt(db,user,link,state):
    group,_=membership(db,state['group'],user);pid=state['values_left'][0];person=db.get(Participant,pid)
    say(db,link,('Quanto ha anticipato ' if state['step']=='payer_value' else 'Quota / percentuale / peso / quantità per ')+person.name+'?'+(' Invia auto per dividere il resto.' if state['step']=='payer_value' else '')+' Valuta: '+state['currency'],guard={'group':group.id})


def item_done(db,user,link,state):
    item=state.pop('current')
    if 'edit_index' in state:state['items'][state.pop('edit_index')]=item
    else:state['items'].append(item)
    state['step']='items';state.pop('values_left',None);save_draft(link,state)
    say(db,link,f"Voci inserite: {len(state['items'])}. Puoi aggiungerne altre o controllare il totale.",[button(db,link,'Aggiungi voce','add_item'),button(db,link,'Controlla e conferma','expense_preview'),button(db,link,'Modifica voci','edit_menu',page=0)],{'group':state['group']})


def expense_body(state):
    base=dict(state.get('base',{}));base.pop('deleted',None)
    base.update(title=state['title'],date=state['date'],category=state.get('category','Altro'),currency=state['currency'],exchange_rate=state.get('exchange_rate'),items=state['items'],audience=state.get('audience'))
    return ExpenseIn.model_validate(base)


def preview_expense(db,user,link,state):
    group,actor=membership(db,state['group'],user,write=True)
    body=expense_body(state);data=build_expense(db,group.id,body,actor)
    names={p.id:p.name for p in people(db,group.id)}
    text=state['title']+' · '+state['date']+'\nTotale: '+money(data['total'],group.currency)+'\n'+('Riservata: '+', '.join(names.get(p,'Persona') for p in state['audience']) if state.get('audience') else 'Pubblica nel gruppo')+'\nQuote:'
    for pid,value in data['owed'].items():text+='\n'+names.get(pid,'Persona')+': '+money(value,group.currency)
    text+='\nAnticipi:'
    for pid,value in data['paid'].items():text+='\n'+names.get(pid,'Persona')+': '+money(value,group.currency)
    state['step']='preview';state['metadata_version']=group.metadata_version;save_draft(link,state)
    say(db,link,text,[button(db,link,'Conferma e salva spesa','expense_confirm'),button(db,link,'Aggiungi voce','add_item'),button(db,link,'Annulla','command',command='/annulla')],{'group':group.id})


def handle_text(db,user,link,text):
    state=draft(link)
    if text.startswith('/'):
        command=text.split()[0].split('@')[0].lower()
        if command in ('/annulla','/cancel'):
            link.draft=None;say(db,link,'Bozza annullata.');menu(db,link);return
        if command=='/scollega':say(db,link,'Vuoi revocare il collegamento Telegram?',[button(db,link,'Conferma scollegamento','unlink')]);return
        if command=='/notifiche':
            from .notifications import permitted
            rows=[n for n in db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.read_at.is_(None)).order_by(Notification.created.desc())) if notification_allowed(db,n,user,link)]
            rows=rows[:30]
            say(db,link,'Aggiornamenti recenti non letti autorizzati: '+str(len(rows))+'\nConsulta dettagli e preferenze dal web.',[{'text':'Apri Sgancia','url':settings.public_origin}],{'notifications':[n.id for n in rows],'groups':sorted({n.group_id for n in rows})});return
        if command=='/valuta':
            args=text.split();from .exchange import CURRENCIES
            if len(args)!=3 or args[1].upper() not in CURRENCIES or state.get('step') not in ('items','preview'):raise HTTPException(422,'Durante una bozza con voci usa /valuta USD 0.92 (tasso verso la valuta del gruppo). Per cambio automatico usa il web.')
            if Decimal(args[2])<=0:raise HTTPException(422,'Tasso non valido')
            state.get('base',{}).pop('exchange_token',None);state.get('base',{}).pop('exchange_context',None)
            state['currency']=args[1].upper();state['exchange_rate']=args[2];state['step']='items';save_draft(link,state);preview_expense(db,user,link,state);return
        if command in ('/gruppi','/saldi','/riepilogo','/spesa','/spese','/rimborsi','/foto','/cestino'):
            groups_menu(db,user,link,command);return
        if command=='/web':say(db,link,'Tutte le funzioni sono disponibili sul web: impostazioni, inviti, categorie, modifica/cestino, allegati, import/export, sicurezza e amministrazione richiedono il normale accesso personale.',[{'text':'Apri Sgancia','url':settings.public_origin}]);return
        menu(db,link);return
    if not state.get('step'):menu(db,link);return
    group,actor=membership(db,state['group'],user,write=True)
    step=state['step'];text=text.strip()
    if step=='title':
        if not 1<=len(text)<=200:raise HTTPException(422,'Titolo da 1 a 200 caratteri')
        state.update(title=text,step='date');save_draft(link,state);say(db,link,'Data della spesa? Invia AAAA-MM-GG oppure oggi.');return
    if step=='date':
        from .notifications import preferences
        value=datetime.now(ZoneInfo(preferences(db,user.id,group.id)['timezone'])).date() if text.lower()=='oggi' else __import__('datetime').date.fromisoformat(text)
        state.update(date=value.isoformat(),step='category');save_draft(link,state);say(db,link,'Categoria? Invia Altro oppure il nome della categoria.');return
    if step=='category':
        if not 1<=len(text)<=60:raise HTTPException(422,'Categoria da 1 a 60 caratteri')
        state.update(category=text,step='visibility')
        if state.get('edit_expense'):
            state['step']='items';save_draft(link,state);preview_expense(db,user,link,state);return
        save_draft(link,state)
        buttons=[button(db,link,'Pubblica','visibility',private=False)]
        if link.allow_private:buttons.append(button(db,link,'Riservata','visibility',private=True))
        say(db,link,'Visibilità della spesa. Le spese riservate richiedono l’abilitazione dal tuo account web.',buttons);return
    if step=='item_title':
        if len(text)>200:raise HTTPException(422,'Descrizione troppo lunga')
        state['current']={'title':'' if text=='-' else text};state['step']='amount';save_draft(link,state);say(db,link,'Importo della voce in '+state['currency']+'? Sono ammesse anche espressioni come 12,50 + 8.');return
    if step=='amount':
        if minor(text)<=0:raise HTTPException(422,'Importo maggiore di zero richiesto')
        state['current']['amount']=text;state['step']='mode';save_draft(link,state)
        say(db,link,'Come si divide questa voce?',[button(db,link,label,'mode',mode=mode) for mode,label in [('equal','In parti uguali'),('exact','Importi esatti'),('percent','Percentuali'),('weight','Pesi'),('quantity','Quantità')]]);return
    if step in ('share_value','payer_value'):
        if not text or len(text)>300:raise HTTPException(422,'Valore non valido')
        pid=state['values_left'].pop(0);field='shares' if step=='share_value' else 'payers'
        if step=='payer_value':value='' if text.lower()=='auto' else text;minor(text) if value else None
        else:
            value=text
            if state['current']['mode']=='exact':minor(text)
            elif not Decimal(text.replace(',','.')).is_finite() or Decimal(text.replace(',','.'))<0:raise ValueError()
        state['current'].setdefault(field,{})[pid]=value
        if state['values_left']:save_draft(link,state);value_prompt(db,user,link,state)
        elif step=='share_value':state.update(step='select_payers',selected=[actor.id]);save_draft(link,state);selection(db,user,link,state,'payers')
        else:item_done(db,user,link,state)
        return
    say(db,link,'Usa i pulsanti del messaggio più recente oppure /annulla.')


def handle_action(db,user,link,args,key):
    kind=args['kind'];state=draft(link)
    if kind=='command':handle_text(db,user,link,args['command']);return
    if kind=='unlink':
        from .telegram_account import revoke
        tid=link.telegram_id;revoke(db,user.id);audit(db,user.id,'telegram.unlinked');say(db,None,'Collegamento revocato. Per ricollegarti usa il tuo account web.',chat_id=tid);return
    if kind=='choose':selected(db,user,link,args['group'],args['command']);return
    if kind in ('expense_view','expense_edit','expense_clone','expense_delete','expense_restore','expense_delete_confirm','expense_restore_confirm'):
        group,actor=membership(db,args['group'],user);e=db.get(Expense,args['expense'])
        if not e or e.group_id!=group.id or e.version!=args['version'] or e.audience!=args['audience'] or e.deleted!=args.get('deleted',False) or not visible(e,actor) or (e.audience is not None and not link.allow_private):raise HTTPException(409,'Spesa modificata o non disponibile: aggiorna l’elenco')
        guard={'group':group.id,'expenses':[{'id':e.id,'version':e.version,'audience':e.audience,'deleted':e.deleted}]};values={k:v for k,v in args.items() if k!='kind'}
        if kind=='expense_view':
            buttons=[]
            if actor.role!='viewer' and group.state=='active':
                for k,label in ([('expense_restore','Ripristina spesa')] if e.deleted else [('expense_edit','Modifica voci'),('expense_clone','Duplica spesa'),('expense_delete','Elimina spesa'),('photo_target','Allega scontrino')]):buttons.append(button(db,link,label,k,**values))
            buttons.append({'text':'Cronologia e gestione web','url':settings.public_origin+'/groups/'+group.id})
            say(db,link,e.title+' · '+money(e.total,group.currency)+' · '+e.date+(' · Cestino' if e.deleted else ''),buttons,guard);return
        membership(db,group.id,user,write=True)
        if kind in ('expense_delete','expense_restore'):
            say(db,link,('Spostare questa spesa nel cestino?' if kind=='expense_delete' else 'Ripristinare questa spesa e i suoi effetti sui saldi?'),[button(db,link,'Conferma operazione',kind+'_confirm',**values)],guard);return
        if kind.endswith('_confirm'):
            from .group_settings import delete_expense,restore_expense_data
            if kind=='expense_delete_confirm':delete_expense(db,group.id,e.id,e.version,user,commit=False)
            else:restore_expense_data(db,group.id,e.id,e.version,user,commit=False)
            say(db,link,'Spesa aggiornata.',guard={'group':group.id});return
        base=dict(db.get(ExpenseRevision,(e.id,e.version)).snapshot);base.pop('deleted',None)
        state={'group':group.id,'step':'items','base':base,'title':base['title'],'date':base['date'],'category':base.get('category','Altro'),'currency':base.get('currency') or group.currency,'exchange_rate':base.get('exchange_rate'),'items':base['items'],'audience':e.audience}
        if kind=='expense_edit':state.update(edit_expense=e.id,edit_version=e.version)
        else:state['title']=(state['title']+' (copia)')[:200]
        save_draft(link,state);say(db,link,'Bozza pronta. Modifica le voci o i dati generali, poi controlla e conferma.',[button(db,link,'Modifica voci','edit_menu',page=0),button(db,link,'Titolo, data e categoria','edit_general'),button(db,link,'Aggiungi voce','add_item'),button(db,link,'Controlla','expense_preview')],guard);return
    if kind=='photo_target':
        group,actor=membership(db,args['group'],user,write=True);e=db.get(Expense,args['expense'])
        if not e or e.deleted or e.group_id!=group.id or e.version!=args['version'] or e.audience!=args['audience'] or not visible(e,actor) or (e.audience is not None and not link.allow_private):raise HTTPException(404,'Spesa non più disponibile')
        save_draft(link,{'step':'photo','group':group.id,'expense':e.id,'version':e.version,'audience':e.audience});say(db,link,'Invia una foto o un PDF dello scontrino. La foto viene salvata solo dopo la tua conferma.',guard={'group':group.id,'expenses':[{'id':e.id,'version':e.version,'audience':e.audience}]});return
    if kind in ('payment_preview','transition_preview'):
        group,actor=membership(db,args['group'],user);guard=scope_guard(db,group.id,actor,link)
        if kind=='payment_preview':
            t=args['transfer'];live=next((v for v in finance(db,group.id,user,link)['transfers'] if v['from']==t['from'] and v['to']==t['to'] and v['fingerprint']==t['fingerprint']),None)
            if not live:raise HTTPException(409,'Saldo cambiato: richiedi i rimborsi aggiornati')
            label='Confermi di aver ricevuto ' if actor.id==t['to'] else 'Vuoi segnalare di aver pagato '
            say(db,link,label+money(t['amount'],group.currency)+'? La conferma del ricevente è necessaria.',[button(db,link,'Conferma operazione','payment_confirm',**{k:v for k,v in args.items() if k!='kind'})],guard)
        else:
            row=db.get(Settlement,args['payment'])
            if not row or row.group_id!=group.id or row.status!=args['status'] or row.audience!=args['audience'] or not visible(row,actor) or (row.audience is not None and not link.allow_private):raise HTTPException(404,'Rimborso non disponibile')
            say(db,link,('Confermare l’incasso di ' if row.status=='pending' else 'Annullare la conferma e ripristinare il debito di ')+money(row.amount,group.currency)+'?',[button(db,link,'Conferma operazione','transition_confirm',**{k:v for k,v in args.items() if k!='kind'})],guard)
        return
    if kind=='payment_confirm':
        from .settlements import TransferIn,PaymentIn,record_transfer,record_suggestion,create_payment
        group,actor=membership(db,args['group'],user);t=args['transfer']
        current=next((v for v in finance(db,group.id,user,link)['transfers'] if v['from']==t['from'] and v['to']==t['to'] and v['fingerprint']==t['fingerprint']),None)
        if not current or actor.id not in (t['from'],t['to']):raise HTTPException(409,'Saldo cambiato o non autorizzato: aggiorna il gruppo')
        if actor.id==t['to']:
            if t.get('public_only'):result=record_suggestion(db,group.id,PaymentIn(sender=t['from'],recipient=t['to'],amount=str(Decimal(t['amount'])/100)),key,user,commit=False)
            else:result=record_transfer(db,group.id,TransferIn(sender=t['from'],recipient=t['to'],components=t['components'],fingerprint=t['fingerprint']),key,user,commit=False)
            say(db,link,'Incasso confermato. I saldi sono aggiornati.',guard={'group':group.id})
        else:
            for i,component in enumerate(t['components']):create_payment(db,group.id,PaymentIn(sender=t['from'],recipient=t['to'],amount=str(Decimal(component['amount'])/100),audience=component['audience']),key+':'+str(i),user,commit=False)
            say(db,link,'Pagamento segnalato, in attesa della conferma del ricevente.',guard={'group':group.id})
        return
    if kind=='transition_confirm':
        from .settlements import transition_payment,undo_payment,Transition
        group,actor=membership(db,args['group'],user);row=db.get(Settlement,args['payment'])
        if not row or row.group_id!=group.id or row.recipient!=actor.id or not visible(row,actor) or (row.audience is not None and not link.allow_private) or row.audience!=args['audience'] or row.status!=args['status']:raise HTTPException(409,'Rimborso cambiato o non autorizzato')
        if row.status=='pending':transition_payment(db,group.id,row.id,Transition(status='confirmed'),user,commit=False)
        else:undo_payment(db,group.id,row.id,user,commit=False)
        say(db,link,'Rimborso aggiornato.',guard={'group':group.id});return
    if kind=='photo_confirm':
        group,actor=membership(db,state['group'],user,write=True);e=db.get(Expense,state['expense'])
        if state.get('step')!='photo_preview' or not e or e.group_id!=group.id or e.version!=state['version'] or e.audience!=state['audience'] or e.deleted or not visible(e,actor) or (e.audience is not None and not link.allow_private):raise HTTPException(409,'Spesa modificata: selezionala di nuovo prima di inviare il file')
        from .runtime_policy import policy
        limits=policy(db)
        if not limits['uploads_enabled']:raise HTTPException(403,'Caricamenti disabilitati')
        raw=telegram_api.download(configuration(db),state['file_id'],limits['attachment_max_bytes'])
        from .attachments import validate_file,persist_attachment
        meta,data,preview=validate_file(raw,limits['attachment_max_bytes'])
        persist_attachment(db,group.id,'expenses',e.id,user,raw,state.get('filename','scontrino.jpg'),key,meta,data,preview,commit=False)
        save_draft(link,{'group':group.id,'last_expense':e.id});say(db,link,'Scontrino salvato con le autorizzazioni della spesa.',guard={'group':group.id,'expenses':[{'id':e.id,'version':e.version,'audience':e.audience}]});return
    if not state.get('group'):raise HTTPException(409,'Bozza scaduta: riparti con /spesa')
    group,actor=membership(db,state['group'],user,write=True)
    if kind=='edit_general':state['step']='title';save_draft(link,state);say(db,link,'Nuovo titolo della spesa?');return
    if kind=='visibility':
        if state.get('step')!='visibility':raise HTTPException(409,'Passaggio non aggiornato')
        if args['private']:
            if not link.allow_private:raise HTTPException(403,'Abilita prima le spese riservate dal web')
            state.update(step='select_audience',selected=[actor.id]);save_draft(link,state);selection(db,user,link,state,'audience')
        else:state['audience']=None;prompt_item(db,user,link,state)
    elif kind in ('selection','toggle'):
        name=args['selection']
        if state.get('step')!='select_'+name:raise HTTPException(409,'Selezione non più attiva')
        if kind=='toggle':
            pid=args['person'];allowed={p.id for p in people(db,group.id,state.get('audience') if name!='audience' else None)}
            if pid not in allowed:raise HTTPException(404,'Persona non disponibile')
            chosen=set(state['selected'])
            if name=='audience' and pid==actor.id:raise HTTPException(422,'Devi essere incluso nel pubblico')
            chosen.symmetric_difference_update({pid});state['selected']=sorted(chosen);save_draft(link,state)
        selection(db,user,link,state,name,args.get('page',0))
    elif kind=='selection_done':
        name=args['selection'];chosen=state.get('selected',[])
        if state.get('step')!='select_'+name or not chosen:raise HTTPException(422,'Seleziona almeno una persona')
        if name=='audience':
            if not link.allow_private or actor.id not in chosen:raise HTTPException(403,'Pubblico non autorizzato')
            state['audience']=sorted(chosen);prompt_item(db,user,link,state)
        elif name=='shares':
            state['current']['shares']={pid:'1' for pid in chosen}
            if state['current']['mode']=='equal':state.update(step='select_payers',selected=[actor.id]);save_draft(link,state);selection(db,user,link,state,'payers')
            else:state.update(step='share_value',values_left=list(chosen));save_draft(link,state);value_prompt(db,user,link,state)
        else:
            state['current']['payers']={pid:'' for pid in chosen}
            if len(chosen)==1:item_done(db,user,link,state)
            else:state.update(step='payer_value',values_left=list(chosen));save_draft(link,state);value_prompt(db,user,link,state)
    elif kind=='mode':
        if state.get('step')!='mode' or args['mode'] not in ('equal','exact','percent','weight','quantity'):raise HTTPException(409,'Modalità non valida')
        state['current']['mode']=args['mode'];state.update(step='select_shares',selected=[p.id for p in people(db,group.id,state.get('audience'))]);save_draft(link,state);selection(db,user,link,state,'shares')
    elif kind=='edit_menu':
        page=args.get('page',0);buttons=[button(db,link,'Voce '+str(i+1)+': '+item['title'],'edit_item',index=i) for i,item in list(enumerate(state['items']))[page*20:page*20+20]]
        if page:buttons.append(button(db,link,'Pagina precedente','edit_menu',page=page-1))
        if (page+1)*20<len(state['items']):buttons.append(button(db,link,'Pagina seguente','edit_menu',page=page+1))
        say(db,link,'Quale voce vuoi reinserire con i valori corretti?',buttons,{'group':group.id})
    elif kind=='edit_item':
        if not 0<=args['index']<len(state['items']):raise HTTPException(404,'Voce non disponibile')
        state['edit_index']=args['index'];prompt_item(db,user,link,state)
    elif kind=='add_item':
        if state.get('step') not in ('items','preview') or len(state.get('items',[]))>=100:raise HTTPException(422,'Numero massimo di voci raggiunto o passaggio non attivo')
        prompt_item(db,user,link,state)
    elif kind=='expense_preview':preview_expense(db,user,link,state)
    elif kind=='expense_confirm':
        if state.get('step')!='preview' or group.metadata_version!=state.get('metadata_version'):raise HTTPException(409,'Il gruppo è cambiato: controlla di nuovo l’anteprima')
        if state.get('audience') is not None and not link.allow_private:raise HTTPException(403,'Riservate non abilitate')
        if state.get('edit_expense'):
            from .lifecycle import edit_expense
            result=edit_expense(db,group.id,state['edit_expense'],expense_body(state),state['edit_version'],user,commit=False)
        else:result=record_expense(group.id,expense_body(state),key,user,db,commit=False)
        save_draft(link,{'group':group.id,'last_expense':result['id']});say(db,link,'Spesa salvata: '+money(result['total'],group.currency),[button(db,link,'Allega scontrino','photo_target',group=group.id,expense=result['id'],version=result['version'],audience=state.get('audience')),{'text':'Apri nel web','url':settings.public_origin+'/groups/'+group.id}],{'group':group.id,'expenses':[{'id':result['id'],'version':result['version'],'audience':state.get('audience')}]})
    else:raise HTTPException(409,'Pulsante non più disponibile')


def private_sender(update):
    callback=update.get('callback_query')
    if callback is not None and not isinstance(callback,dict):return None
    message=callback.get('message') if callback else update.get('message')
    sender=callback.get('from') if callback else message.get('from') if isinstance(message,dict) else None
    if not isinstance(message,dict) or not isinstance(sender,dict):return None
    chat=message.get('chat',{})
    if chat.get('type')!='private' or type(sender.get('id')) is not int or sender.get('is_bot') or chat.get('id')!=sender['id'] or message.get('forward_origin') or message.get('via_bot') or message.get('business_connection_id'):return None
    if not 0<sender['id']<2**52 or message.get('forward_from') or message.get('forward_date') or message.get('sender_chat'):return None
    return sender['id'],message,callback


def start_link(db,user,tid,clear,cfg):
    grant=db.scalar(select(TelegramGrant).where(TelegramGrant.token_hash==digest(clear)).with_for_update().execution_options(populate_existing=True));instance=db.get(Instance,1)
    if not grant or not user or grant.user_id!=user.id or grant.telegram_id!=tid or grant.expires<=time.time() or grant.auth_version!=user.auth_version or grant.gate_version!=instance.gate_version or grant.generation!=cfg['generation'] or user.status!='active':return None
    other=db.scalar(select(TelegramLink).where(TelegramLink.telegram_id==tid,TelegramLink.user_id!=user.id))
    if other:return None
    link=db.get(TelegramLink,user.id);revision=link.revision+1 if link else 1
    if link:
        db.execute(delete(TelegramAction).where(TelegramAction.user_id==user.id));db.execute(delete(TelegramOutbox).where(TelegramOutbox.user_id==user.id))
    else:link=TelegramLink(user_id=user.id);db.add(link)
    link.telegram_id=tid;link.auth_version=user.auth_version;link.gate_version=instance.gate_version;link.generation=cfg['generation'];link.allow_private=grant.allow_private;link.notifications=grant.notifications;link.revision=revision;link.action_version=1;link.draft=None;link.created=int(time.time());link.draft_expires=0
    db.delete(grant);audit(db,user.id,'telegram.linked');return link


def process_update(db,generation,update_id):
    first=db.get(TelegramUpdate,(generation,update_id))
    if not first or first.status!='pending':return
    cfg=configuration(db)
    if not cfg['enabled'] or cfg['generation']!=generation or first.created<time.time()-3600:first.status='discarded';first.payload='';db.commit();return
    data=unseal(first.payload);sender=private_sender(data)
    if not sender:first.status='ignored';first.payload='';db.commit();return
    tid,message,callback=sender;text=message.get('text','') if not callback and isinstance(message.get('text',''),str) else ''
    clear=text.split(maxsplit=1)[1].strip() if text.startswith('/start ') else None
    preliminary=db.scalar(select(TelegramLink).where(TelegramLink.telegram_id==tid))
    grant=db.get(TelegramGrant,digest(clear)) if clear else None
    uid=grant.user_id if grant and grant.telegram_id==tid else preliminary.user_id if preliminary else None
    # Group -> User ordering matches all web financial services and credential revocations.
    db.scalar(select(Instance).where(Instance.id==1).with_for_update(read=True).execution_options(populate_existing=True));cfg=configuration(db)
    gids=list(db.scalars(select(Participant.group_id).where(Participant.user_id==uid,Participant.active.is_(True)).order_by(Participant.group_id))) if uid else []
    list(db.scalars(select(Group).where(Group.id.in_(gids)).order_by(Group.id).with_for_update().execution_options(populate_existing=True)))
    user=db.scalar(select(User).where(User.id==uid).with_for_update().execution_options(populate_existing=True)) if uid else None
    link=db.scalar(select(TelegramLink).where(TelegramLink.telegram_id==tid).with_for_update().execution_options(populate_existing=True))
    row=db.scalar(select(TelegramUpdate).where(TelegramUpdate.generation==generation,TelegramUpdate.update_id==update_id).with_for_update().execution_options(populate_existing=True))
    if row.status!='pending':return
    if not cfg['enabled'] or cfg['generation']!=generation:row.status='discarded';row.payload='';db.commit();return
    if not rate(db,'tg-in:'+str(tid),60):row.status='rate_limited';row.payload='';db.commit();return
    if text.strip()=='/id':say(db,None,'Il tuo ID Telegram è '+str(tid)+'. Inseriscilo nel tuo account web, poi apri il link monouso generato lì.',chat_id=tid)
    elif clear:
        linked=start_link(db,user,tid,clear,cfg)
        if linked:say(db,linked,'Account collegato. '+('Riservate abilitate solo qui in chat privata.' if linked.allow_private else 'Riservate non abilitate: i saldi mostrati dal bot sono solo pubblici.'));menu(db,linked)
        else:say(db,None,'Collegamento non disponibile: genera dal web un codice nuovo per il tuo ID Telegram.',chat_id=tid)
    elif not link_live(db,link,cfg,user):say(db,None,'Collega il tuo account dal web. '+HELP,chat_id=tid)
    else:
        link.action_version+=1;db.flush()
        try:
            with db.begin_nested():
                if callback:
                    value=callback.get('data','');action=db.get(TelegramAction,digest(value[2:])) if value.startswith('t:') else None
                    if not action or action.user_id!=user.id or action.telegram_id!=tid or action.expires<=time.time() or action.revision!=link.action_version-1:raise HTTPException(409,'Pulsanti scaduti: usa /menu o richiedi il passaggio aggiornato')
                    args=unseal(action.payload);db.delete(action);db.flush()
                    if args.get('group') and args['group'] not in gids:raise HTTPException(404,'Gruppo non più disponibile')
                    current=draft(link)
                    if current.get('group') and current['group'] not in gids:link.draft=None
                    handle_action(db,user,link,args,'telegram:'+str(generation)+':'+str(update_id))
                elif message.get('photo') or message.get('document'):
                    state=draft(link)
                    if state.get('step')!='photo' or state.get('group') not in gids:raise HTTPException(409,'Prima usa /foto e scegli una spesa')
                    media=message['photo'][-1] if isinstance(message.get('photo'),list) and message['photo'] else message.get('document')
                    if not isinstance(media,dict) or not isinstance(media.get('file_id'),str):raise HTTPException(422,'File non valido')
                    from .runtime_policy import policy
                    if media.get('file_size',0)>policy(db)['attachment_max_bytes']:raise HTTPException(413,'File troppo grande')
                    state.update(step='photo_preview',file_id=media['file_id'],filename=media.get('file_name','scontrino.jpg'))
                    save_draft(link,state);say(db,link,'Confermi di salvare questo scontrino sulla spesa selezionata?',[button(db,link,'Conferma allegato','photo_confirm')],{'group':state['group'],'expenses':[{'id':state['expense'],'version':state['version'],'audience':state['audience']}]})
                else:
                    current=draft(link)
                    if current.get('group') and current['group'] not in gids:link.draft=None
                    handle_text(db,user,link,text[:4096])
        except (HTTPException,ValueError,InvalidOperation,KeyError,TypeError,telegram_api.TelegramError) as error:
            # No stack, URLs, incoming payloads or configuration in logs or replies.
            db.refresh(link)
            message=error.detail if isinstance(error,HTTPException) and isinstance(error.detail,str) else 'Valore non valido: controlla importi, data e selezioni, oppure /annulla.'
            say(db,link,message[:500])
            state=draft(link)
            if state.get('step','').startswith('select_') and state.get('group') in gids:selection(db,user,link,state,state['step'][7:])
            elif state.get('step') in ('items','preview'):say(db,link,'Puoi correggere le voci o riprovare l’anteprima.',[button(db,link,'Modifica voci','edit_menu',page=0),button(db,link,'Controlla di nuovo','expense_preview')],{'group':state['group']})
    if callback and isinstance(callback.get('id'),str) and len(callback['id'])<=256 and link and link not in db.deleted and link_live(db,link,cfg,user):
        db.add(TelegramOutbox(method='answerCallbackQuery',generation=cfg['generation'],telegram_id=tid,user_id=user.id,auth_version=link.auth_version,gate_version=link.gate_version,link_revision=link.revision,payload=seal({'callback_query_id':callback['id']}),expires=int(time.time())+30))
    row.status='done';row.payload='';db.commit()


def deliver_one(db):
    preliminary=db.scalar(select(TelegramOutbox).where(TelegramOutbox.status=='pending',TelegramOutbox.next_attempt<=time.time()).order_by(case((TelegramOutbox.method=='answerCallbackQuery',0),else_=1),TelegramOutbox.sequence).limit(1))
    if not preliminary:return False
    db.scalar(select(Instance).where(Instance.id==1).with_for_update(read=True).execution_options(populate_existing=True));cfg=configuration(db)
    guard=unseal(preliminary.guard) if preliminary.guard else None
    if guard:
        gids=([guard['group']] if guard.get('group') else [])+guard.get('groups',[])
        for gid in sorted(set(gids)):group_lock(db,gid)
    user=db.scalar(select(User).where(User.id==preliminary.user_id).with_for_update().execution_options(populate_existing=True)) if preliminary.user_id else None
    link=db.scalar(select(TelegramLink).where(TelegramLink.user_id==preliminary.user_id).with_for_update().execution_options(populate_existing=True)) if user else None
    row=db.scalar(select(TelegramOutbox).where(TelegramOutbox.id==preliminary.id).with_for_update(skip_locked=True).execution_options(populate_existing=True))
    if not row or row.status!='pending':return False
    allowed=cfg['enabled'] and cfg['generation']==row.generation and row.expires>time.time()
    if row.user_id:allowed=allowed and link_live(db,link,cfg,user) and link.telegram_id==row.telegram_id and link.revision==row.link_revision and row.auth_version==user.auth_version and row.gate_version==link.gate_version and guard_valid(db,user,link,guard)
    if not allowed:row.status='cancelled';row.payload='';row.guard=None;db.commit();return True
    if row.method=='sendMessage' and not rate(db,'tg-out:'+str(row.telegram_id),cfg['max_messages_per_minute']):row.next_attempt=int(time.time())+15;db.commit();return False
    try:
        payload=unseal(row.payload)
        telegram_api.call(cfg,'answerCallbackQuery',payload) if row.method=='answerCallbackQuery' else telegram_api.call(cfg,'sendMessage',{'chat_id':row.telegram_id,**payload})
    except telegram_api.TelegramError as error:
        state=db.get(TelegramState,1)
        if state and str(error)=='bot_not_authorized':state.error='bot_not_authorized';state.username=''
        row.attempts+=1;row.next_attempt=int(time.time())+min(600,15*2**row.attempts)
        if row.attempts>=6 or row.method=='answerCallbackQuery' or str(error) in ('bot_not_authorized','chat_blocked'):row.status='failed';row.payload='';row.guard=None
    else:row.status='sent';row.payload='';row.guard=None
    db.commit();return True


def notification_digest(db):
    from .notifications import permitted,preferences,scheduled_slot
    now=int(time.time());cfg=configuration(db)
    if not cfg['enabled']:return
    for original in db.scalars(select(TelegramLink).where(TelegramLink.notifications.is_(True))):
        gids=list(db.scalars(select(Participant.group_id).where(Participant.user_id==original.user_id,Participant.active.is_(True)).order_by(Participant.group_id)))
        list(db.scalars(select(Group).where(Group.id.in_(gids)).order_by(Group.id).with_for_update(read=True)))
        user=db.scalar(select(User).where(User.id==original.user_id).with_for_update().execution_options(populate_existing=True));link=db.scalar(select(TelegramLink).where(TelegramLink.user_id==original.user_id).with_for_update().execution_options(populate_existing=True))
        if not link_live(db,link,cfg,user):continue
        for gid in gids:
            group=db.get(Group,gid);pref=preferences(db,user.id,gid)
            if group.deleted or group.state=='archived' or not pref['enabled'] or not preferences(db,user.id)['enabled']:continue
            if pref['frequency']=='daily' and datetime.fromtimestamp(now,ZoneInfo(pref['timezone'])).weekday() not in pref['days']:continue
            slot,period=scheduled_slot(now,pref['frequency'],pref)
            account_pref=db.get(NotificationPreference,(user.id,gid)) or db.get(NotificationPreference,(user.id,''))
            if slot<max(link.created,account_pref.started_at if account_pref else 0):continue
            key='tg:'+user.id+':'+str(link.revision)+':'+gid+':'+pref['frequency']+':'+str(period)
            if db.scalar(select(TelegramOutbox.id).where(TelegramOutbox.dedup==key)):continue
            rows=db.scalars(select(Notification).where(Notification.user_id==user.id,Notification.group_id==gid,Notification.read_at.is_(None),Notification.created>=max(link.created,now-7*86400)).order_by(Notification.created.desc()))
            n=next((n for n in rows if notification_allowed(db,n,user,link)),None)
            if n:say(db,link,'Hai aggiornamenti Sgancia autorizzati: consulta notifiche e riepiloghi dal web oppure usa /notifiche e /riepilogo.',[{'text':'Apri Sgancia','url':settings.public_origin}],{'notification':n.id,'group':gid},dedup=key,notification=n.id)
        db.commit()


def cleanup(db):
    now=int(time.time())
    db.execute(delete(TelegramGrant).where(TelegramGrant.expires<now));db.execute(delete(TelegramAction).where(TelegramAction.expires<now))
    db.execute(delete(TelegramUpdate).where(TelegramUpdate.created<now-7*86400))
    # Keep minimal delivery stamps longer than the monthly cadence, never content after delivery.
    db.execute(delete(TelegramOutbox).where(TelegramOutbox.expires<now-35*86400))
    for row in db.scalars(select(TelegramOutbox).where(TelegramOutbox.expires<now,TelegramOutbox.status=='pending')):row.status='expired';row.payload='';row.guard=None
    for row in db.scalars(select(TelegramLink).where(TelegramLink.draft_expires<now,TelegramLink.draft.is_not(None))):row.draft=None
    db.commit()


def setup_remote(db):
    cfg=configuration(db)
    if not cfg['enabled'] or not cfg.get('bot_token'):return False
    state=db.get(TelegramState,1)
    if not state:state=TelegramState(id=1);db.add(state);db.flush()
    if state.generation==cfg['generation'] and state.username and not state.error and state.verified_at>time.time()-300:return True
    needs_setup=state.generation!=cfg['generation'] or not state.username
    try:
        info=telegram_api.call(cfg,'getMe');username=info.get('username','')
        import re
        if not info.get('is_bot') or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]{4,31}',username) or (cfg['username'] and username.lower()!=cfg['username'].lower()):raise telegram_api.TelegramError('bot_identity_mismatch')
        if needs_setup and cfg['mode']=='webhook':telegram_api.call(cfg,'setWebhook',{'url':settings.public_origin+'/api/v1/telegram/webhook','secret_token':cfg['webhook_secret'],'allowed_updates':['message','callback_query'],'drop_pending_updates':True})
        elif needs_setup:telegram_api.call(cfg,'deleteWebhook',{'drop_pending_updates':True})
        # Ignore the result if an administrator changed the token/configuration during the network call.
        db.expire_all();current=configuration(db)
        if current['generation']!=cfg['generation']:return False
        state=db.get(TelegramState,1);state.generation=cfg['generation'];state.username=username;state.verified_at=int(time.time());state.offset=0 if needs_setup else state.offset;state.error='';db.commit();return True
    except telegram_api.TelegramError as error:
        state.error=str(error) if str(error) in ('bot_identity_mismatch','bot_not_authorized','rate_limited') else 'api_unavailable';db.commit();return False


def tick(poll=True):
    with SessionLocal() as db:
        cfg=configuration(db)
        if not cfg['enabled']:return
        if not setup_remote(db):return
        state=db.get(TelegramState,1);offset=state.offset
        newest=db.scalar(select(func.max(TelegramUpdate.created))) or 0
        if newest<time.time()-6*86400:state.offset=0;offset=0;db.commit()
    if poll and cfg['mode']=='polling':
        try:updates=telegram_api.call(cfg,'getUpdates',{'offset':offset,'timeout':10,'limit':20,'allowed_updates':['message','callback_query']})
        except telegram_api.TelegramError as error:
            with SessionLocal() as db:
                state=db.get(TelegramState,1);state.error=str(error) if str(error) in ('bot_not_authorized','rate_limited') else 'api_unavailable'
                if str(error)=='bot_not_authorized':state.username=''
                db.commit()
            return
        with SessionLocal() as db:
            current=configuration(db)
            if current['generation']!=cfg['generation']:return
            state=db.scalar(select(TelegramState).where(TelegramState.id==1).with_for_update());state.error=''
            for update in updates:
                enqueue_update(db,cfg,update);state.offset=max(state.offset,update['update_id']+1)
            db.commit()
    with SessionLocal() as db:ids=list(db.scalars(select(TelegramUpdate.update_id).where(TelegramUpdate.generation==cfg['generation'],TelegramUpdate.status=='pending').order_by(TelegramUpdate.update_id).limit(30)))
    for update_id in ids:
        with SessionLocal() as db:process_update(db,cfg['generation'],update_id)
    with SessionLocal() as db:notification_digest(db);cleanup(db)
    for _ in range(20):
        with SessionLocal() as db:
            if not deliver_one(db):break
