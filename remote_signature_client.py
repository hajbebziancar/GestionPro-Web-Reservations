"""Envoi au site et récupération persistante, même après fermeture du QR."""
from pathlib import Path
import json,threading,time,base64,os,secrets,urllib.parse
ROOT=Path(__file__).resolve().parent
PENDING=ROOT/'remote_signature_pending.json'
_lock=threading.RLock();_running=False

def state():
    try:return json.loads(PENDING.read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}

def persist(data):
    temp=PENDING.with_name(PENDING.name+'.'+secrets.token_hex(4)+'.tmp');temp.write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8');os.replace(temp,PENDING)

def start(number,clients,content):
    from web_sync import _request,load_config
    from remote_contract_common import freeze_html
    base,_=load_config()
    if not base.startswith('https://'):raise ValueError('La signature distante nécessite une adresse de site HTTPS dans sync_web_config.json.')
    reply=_request('POST','/api/sync/signatures',{'contract_no':number,'client_codes':clients,'html':freeze_html(content)})
    token=reply['token']
    with _lock:
        data=state();data[token]={'contract':number,'client_codes':clients,'base_url':base,'saved':False};persist(data)
    monitor()
    return base+reply['path'],token

def pull(token):
    from web_sync import _request,load_config
    from phone_signature import signature_path,normalized_signature
    from signed_contracts import archive_contract,signed_html
    with _lock:item=state().get(token)
    if not item or item.get('saved'):return bool(item and item.get('saved'))
    base,_=load_config()
    if base!=item['base_url']:raise ValueError('Le site configuré a changé : restaurez l’adresse utilisée pour cette signature.')
    reply=_request('GET','/api/sync/signatures/'+urllib.parse.quote(token,safe=''))
    if not reply.get('saved'):return False
    if reply.get('contract_no')!=item['contract'] or reply.get('client_codes')!=item['client_codes']:raise ValueError('Contrat distant incompatible.')
    image=normalized_signature(base64.b64decode(reply['image'],validate=True));pdf=base64.b64decode(reply['pdf'],validate=True)
    if not pdf.startswith(b'%PDF'):raise ValueError('PDF distant invalide.')
    with _lock:
        # Archive the server's immutable document and associated PDF together.
        archive_contract(item['contract'],item['client_codes'],reply['html'],image)
        path=signed_html(item['contract']);path.with_suffix('.pdf').write_bytes(pdf)
        target=signature_path(item['contract']);tmp=target.with_suffix('.tmp');tmp.write_bytes(image);os.replace(tmp,target)
        data=state();data[token]['saved']=True;data[token]['error']='';persist(data)
    return True

def saved(token):
    monitor()
    return bool(state().get(token,{}).get('saved'))

def error(token):return str(state().get(token,{}).get('error',''))

def monitor():
    global _running
    with _lock:
        if _running:return
        _running=True
    def worker():
        while True:
            for token,item in list(state().items()):
                if item.get('saved'):continue
                try:pull(token)
                except Exception as exc:
                    with _lock:
                        data=state()
                        if token in data:data[token]['error']=str(exc);persist(data)
            time.sleep(4)
    threading.Thread(target=worker,daemon=True).start()
