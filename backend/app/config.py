from urllib.parse import urlsplit
from ipaddress import ip_address,ip_network
from pydantic import model_validator,Field
from pydantic_settings import BaseSettings, SettingsConfigDict


LOOPBACK_HOSTS={'localhost','127.0.0.1','::1'}
LAN_NETWORKS=tuple(ip_network(n) for n in ('10.0.0.0/8','172.16.0.0/12','192.168.0.0/16','fc00::/7'))

def origin_parts(value):
    parsed=urlsplit(value)
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError('Origine esatta HTTP/HTTPS richiesta, senza percorsi o credenziali')
    host=parsed.hostname.lower()
    if '*' in host or host.endswith('.') or any(c.isspace() for c in host) or '%' in host:raise ValueError('Hostname non valido')
    port=parsed.port
    if port is not None and not 1<=port<=65535:raise ValueError('Porta non valida')
    display='['+host+']' if ':' in host else host
    suffix=':'+str(port) if port is not None and port!=(443 if parsed.scheme=='https' else 80) else ''
    return parsed,parsed.scheme+'://'+display+suffix

def normalize_origin(value):return origin_parts(value)[1]

def private_lan_origin(value):
    parsed,canonical=origin_parts(value)
    try:address=ip_address(parsed.hostname)
    except ValueError:raise ValueError('Per HTTP LAN indica un IP privato esatto, non un dominio') from None
    if parsed.scheme!='http' or not any(address.version==net.version and address in net for net in LAN_NETWORKS):raise ValueError('HTTP LAN consentito solo per IP privati RFC1918 o IPv6 ULA esplicitamente dichiarati')
    return canonical

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='SGANCIA_', env_file='.env', extra='ignore')
    database_url: str = 'postgresql+psycopg://localhost/sgancia'
    public_origin: str = 'http://localhost:5173'
    secure_cookies: bool = True
    allowed_origins: list[str] = []
    http_lan_origins: list[str] = []
    session_hours: int = 24
    encryption_key: str = ''
    smtp_host:str=''
    smtp_port:int=Field(default=587,ge=1,le=65535)
    smtp_mode:str='starttls'
    smtp_username:str=''
    smtp_password:str=''
    smtp_sender:str=''
    attachment_dir:str='/app/storage'
    attachment_max_bytes:int=Field(default=10*1024*1024,ge=1024,le=20*1024*1024)
    attachment_group_bytes:int=Field(default=100*1024*1024,ge=1024,le=10*1024*1024*1024)
    attachment_max_count:int=Field(default=20,ge=1,le=100)


    @model_validator(mode='after')
    def validate_origins(self):
        if self.smtp_mode not in ('starttls','ssl'):raise ValueError('SMTP richiede starttls o ssl')
        if any('\r' in v or '\n' in v for v in (self.smtp_host,self.smtp_sender,self.smtp_username)):raise ValueError('Configurazione SMTP non valida')
        self.http_lan_origins=list(dict.fromkeys(private_lan_origin(o) for o in self.http_lan_origins))
        self.public_origin=normalize_origin(self.public_origin)
        self.allowed_origins=list(dict.fromkeys(normalize_origin(o) for o in self.allowed_origins))
        for origin in [self.public_origin,*self.allowed_origins]:
            parsed=urlsplit(origin)
            if parsed.scheme=='http' and parsed.hostname not in LOOPBACK_HOSTS and origin not in self.http_lan_origins:
                raise ValueError('Per HTTP LAN dichiara espressamente l’IP in SGANCIA_HTTP_LAN_ORIGINS; domini pubblici solo HTTPS')
        if not self.secure_cookies and urlsplit(self.public_origin).hostname not in LOOPBACK_HOSTS:
            raise ValueError('Non disabilitare Secure globalmente sul server: usa SGANCIA_HTTP_LAN_ORIGINS per la sola LAN')
        return self

    @property
    def origins(self):return set([self.public_origin,*self.allowed_origins,*self.http_lan_origins])

settings=Settings()
