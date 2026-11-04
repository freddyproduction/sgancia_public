"""Fixed Telegram hosts, bounded responses, TLS validation, no token-bearing logs."""
import json,re,urllib.request,urllib.error
class TelegramError(Exception):pass
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise TelegramError('redirect_refused')

def request(url,data=None,limit=1048576,timeout=30):
    try:
        req=urllib.request.Request(url,data=json.dumps(data).encode() if data is not None else None,headers={'Content-Type':'application/json'} if data is not None else {})
        with urllib.request.build_opener(NoRedirect()).open(req,timeout=timeout) as response:raw=response.read(limit+1)
        if len(raw)>limit:raise TelegramError('response_too_large')
        return raw
    except urllib.error.HTTPError as error:raise TelegramError('rate_limited' if error.code==429 else 'bot_not_authorized' if error.code==401 else 'chat_blocked' if error.code==403 else 'api_unavailable') from None
    except (OSError,ValueError):raise TelegramError('api_unavailable') from None

def call(cfg,method,data=None):
    if method not in {'getMe','getUpdates','setWebhook','deleteWebhook','sendMessage','answerCallbackQuery','getFile'}:raise TelegramError('method_refused')
    raw=request('https://api.telegram.org/bot'+cfg['bot_token']+'/'+method,data or {})
    try:
        result=json.loads(raw)
        if not result.get('ok'):raise TelegramError('api_unavailable')
        return result['result']
    except (ValueError,KeyError,TypeError):raise TelegramError('api_unavailable') from None

def download(cfg,file_id,maximum):
    info=call(cfg,'getFile',{'file_id':file_id});path=info.get('file_path','')
    if not re.fullmatch(r'[A-Za-z0-9_./-]{1,500}',path) or '..' in path.split('/') or info.get('file_size',0)>maximum:raise TelegramError('invalid_file')
    return request('https://api.telegram.org/file/bot'+cfg['bot_token']+'/'+path,limit=maximum,timeout=15)
