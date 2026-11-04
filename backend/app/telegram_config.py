import json
from .models import Instance
from .security import cipher

def configuration(db):
    instance=db.get(Instance,1)
    saved=json.loads(cipher().decrypt(instance.telegram_config.encode())) if instance and instance.telegram_config else {}
    return {'enabled':False,'mode':'polling','username':'','generation':0,'max_messages_per_minute':10,**saved}

def seal(value):return cipher().encrypt(json.dumps(value,ensure_ascii=False).encode()).decode()
def unseal(value):return json.loads(cipher().decrypt(value.encode()))
