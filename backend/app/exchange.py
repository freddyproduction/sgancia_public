"""Daily reference quotes: fixed provider, no amounts or user information sent."""
import base64
import hashlib
import hmac
import json
import time
import threading
from datetime import date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from urllib.request import urlopen
from fastapi import APIRouter, Depends, HTTPException
from .config import settings
from .security import current

CURRENCIES = ('EUR','USD','GBP','CHF','CAD','AUD','NZD','SEK','NOK','DKK','PLN','CZK','HUF','RON','TRY','BRL','MXN','SGD','HKD','ZAR')
router=APIRouter(prefix='/api/v1',tags=['Valute'])
_cache={}
_lock=threading.Lock()

def valid_currency(value):
    if value not in CURRENCIES:raise ValueError('Valuta non supportata')
    return value

def rounded(value):
    result=int(Decimal(value).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    if not 0 <= result <= 10**12:raise ValueError('Importo convertito fuori limite')
    return result

def rate_value(value):
    try: result=Decimal(value)
    except (InvalidOperation,ValueError,TypeError):raise ValueError('Tasso non valido') from None
    if not result.is_finite() or not Decimal('0.00000001')<=result<=Decimal('100000000') or result.as_tuple().exponent < -12:raise ValueError('Tasso non valido: usa al massimo 12 decimali')
    return result

def signature(raw):return hmac.new(settings.encryption_key.encode(),raw,hashlib.sha256).hexdigest()

def sign(payload):
    raw=json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
    return base64.urlsafe_b64encode(raw).decode()+'.'+signature(raw)

def read_quote(token,base,quote,stored=False):
    try:
        raw,mac=token.split('.')
        raw=base64.urlsafe_b64decode(raw)
        if not hmac.compare_digest(signature(raw),mac):raise ValueError()
        data=json.loads(raw)
        if data['base']!=base or data['quote']!=quote or (not stored and time.time()-data['issued']>86400):raise ValueError()
        rate_value(data['rate'])
        return data
    except Exception:raise ValueError('Cambio scaduto o non valido: aggiorna il tasso automatico') from None

def fetch_rate(base,quote):
    # Fixed HTTPS host, validated currency codes, bounded response and timeout.
    with urlopen(f'https://api.frankfurter.dev/v2/rate/{base}/{quote}?providers=ecb',timeout=8) as response:
        raw=response.read(16385)
    if len(raw)>16384:raise ValueError('Risposta troppo grande')
    data=json.loads(raw,parse_float=Decimal)
    if data['base'].upper()!=base or data['quote'].upper()!=quote:raise ValueError('Coppia errata')
    age=(date.today()-date.fromisoformat(data['date'])).days
    if age<0 or age>7:raise ValueError('Tasso non aggiornato')
    return {'base':base,'quote':quote,'date':data['date'],'rate':str(rate_value(str(data['rate']))),'source':'Frankfurter / BCE'}

@router.get('/currencies')
def currencies(user=Depends(current)):return list(CURRENCIES)

@router.get('/exchange-rate')
def exchange_rate(base:str,quote:str,user=Depends(current)):
    try:
        valid_currency(base);valid_currency(quote)
        if base==quote:raise ValueError('Scegli due valute differenti')
    except ValueError as e:raise HTTPException(422,str(e)) from None
    try:
        with _lock:
            cached=_cache.get((base,quote))
            if not cached or time.time()-cached[0]>3600:
                cached=(time.time(),fetch_rate(base,quote));_cache[(base,quote)]=cached
            data={**cached[1],'issued':int(time.time())}
        return {**data,'token':sign(data)}
    except Exception:raise HTTPException(503,'Cambio automatico non disponibile. Riprova oppure inserisci un tasso manuale.') from None


def expense_rate(body,group_currency,stored=False):
    base=body.currency or group_currency
    valid_currency(base)
    if base==group_currency:return Decimal(1),None
    if body.exchange_token:
        data=read_quote(body.exchange_token,base,group_currency,stored)
        return rate_value(data['rate']),data
    if body.exchange_rate:
        rate=rate_value(body.exchange_rate)
        context=getattr(body,'exchange_context',None)
        if context and context.base==base and context.quote==group_currency and rate_value(context.rate)==rate:
            return rate,{**context.model_dump(mode='json'),'source':'Importato (tasso dichiarato): '+context.source}
        return rate,{'base':base,'quote':group_currency,'rate':str(rate),'source':'Manuale','date':body.date.isoformat()}
    raise ValueError('Scegli il cambio automatico oppure inserisci il tasso manuale')


from pydantic import BaseModel,Field,ConfigDict
from .money import minor

class ConversionIn(BaseModel):
    model_config=ConfigDict(extra='forbid')
    amount:str=Field(min_length=1,max_length=300)
    base:str=Field(min_length=3,max_length=3)
    quote:str=Field(min_length=3,max_length=3)
    token:str|None=Field(default=None,max_length=2000)
    rate:str|None=Field(default=None,max_length=40)

@router.post('/currency-conversion')
def convert_amount(body:ConversionIn,user=Depends(current)):
    try:
        valid_currency(body.base);valid_currency(body.quote)
        # This read-only calculator accepts historic signed rates as a preview;
        # writing a new expense still requires a fresh quote.
        rate=rate_value(read_quote(body.token,body.base,body.quote,stored=True)['rate']) if body.token else rate_value(body.rate)
        source=minor(body.amount)
        if source<=0:raise ValueError('Inserisci un importo positivo')
        return {'original':source,'converted':rounded(Decimal(source)*rate),'currency':body.quote}
    except ValueError as e:raise HTTPException(422,str(e)) from None
