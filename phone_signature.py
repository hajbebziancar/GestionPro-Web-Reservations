"""Signature client sur téléphone via le réseau local (QR code / navigateur)."""
from __future__ import annotations
import base64, html, io, json, os, secrets, socket, threading, time
from PIL import Image, ImageChops, ImageOps
_lock=threading.RLock()
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

APP_DIR=Path(__file__).resolve().parent
SIGN_DIR=APP_DIR/'signatures_clients'; SIGN_DIR.mkdir(exist_ok=True)
_sessions={}; _server=None; _thread=None

def _safe_contract(value):
    return ''.join(c for c in str(value) if c.isalnum() or c in '-_')[:80] or 'contrat'

def signature_path(contract_no): return SIGN_DIR/f"signature_{_safe_contract(contract_no)}.png"

def normalized_signature(payload):
    """Reject empty canvases; flatten transparency and crop to visible ink."""
    with Image.open(io.BytesIO(payload)) as source:
        if source.format != 'PNG' or source.width*source.height > 8_000_000:
            raise ValueError('Image de signature invalide ou trop grande.')
        rgba=source.convert('RGBA')
        white=Image.new('RGBA',rgba.size,'white')
        im=Image.alpha_composite(white,rgba).convert('RGB')
    gray=ImageOps.grayscale(im)
    ink=gray.point(lambda value:255 if value<220 else 0)
    box=ink.getbbox()
    count=sum(ink.histogram()[1:])
    if not box or count<12:
        raise ValueError('La signature est vide. Signez dans le cadre avant de valider.')
    im=ImageOps.colorize(ImageOps.grayscale(im.crop(box)),black='#000080',white='white')
    im=ImageOps.expand(im,border=12,fill='white')
    out=io.BytesIO();im.save(out,'PNG');return out.getvalue()

def saved_signature(contract_no):
    path=signature_path(str(contract_no).strip())
    try:return normalized_signature(path.read_bytes())
    except (OSError,ValueError):return None

def signature_data_uri(contract_no):
    payload=saved_signature(contract_no)
    return 'data:image/png;base64,'+base64.b64encode(payload).decode('ascii') if payload else ''

def signature_status(contract_no):
    with _lock:
        payload=saved_signature(contract_no)
        import hashlib
        return {'saved':bool(payload),'revision':hashlib.sha256(payload).hexdigest() if payload else ''}

def _lan_ip():
    s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
    try: s.connect(('8.8.8.8',80)); return s.getsockname()[0]
    except OSError: return '127.0.0.1'
    finally: s.close()

def _page(token, contract_no):
    c=html.escape(contract_no)
    return f'''<!doctype html><html lang="fr"><head><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no"><meta charset="utf-8"><title>Signature contrat {c}</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#eef4f8;color:#17324d}}.wrap{{max-width:850px;margin:auto;padding:18px}}h2{{margin:4px 0}}p{{color:#52687a}}canvas{{width:100%;height:52vh;min-height:330px;background:#fff;border:2px solid #1684d6;border-radius:14px;touch-action:none;box-sizing:border-box}}.bar{{display:flex;gap:12px;margin-top:14px}}button{{flex:1;border:0;border-radius:10px;padding:16px;font-size:18px;font-weight:700}}#clear{{background:#dfe8ef;color:#30495e}}#save{{background:#138c4b;color:#fff}}#msg{{font-weight:700;margin-top:12px}}</style></head><body><div class="wrap"><h2>HBZ Rent Car — Signature client</h2><p>Contrat <b>{c}</b> · Signez dans le cadre avec le S Pen ou le doigt.</p><canvas id="pad"></canvas><div class="bar"><button id="clear">Effacer</button><button id="save">Valider la signature</button></div><div id="msg"></div></div><script>
const token={json.dumps(token)};
const cv=document.getElementById('pad'),ctx=cv.getContext('2d');
const save=document.getElementById('save'),msg=document.getElementById('msg');
let drawing=false,dirty=false,revision='',saving=false,epoch=0,syncing=false;
function resize(){{
 const old=document.createElement('canvas');old.width=cv.width;old.height=cv.height;old.getContext('2d').drawImage(cv,0,0);
 const r=cv.getBoundingClientRect(),d=Math.min(window.devicePixelRatio||1,1.5);
 cv.width=Math.max(600,Math.floor(r.width*d));cv.height=Math.max(350,Math.floor(r.height*d));
 ctx.lineWidth=3*d;ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle='#000080';
 ctx.drawImage(old,0,0,cv.width,cv.height);
}}
resize();window.addEventListener('resize',resize);
function pt(e){{let r=cv.getBoundingClientRect();return [(e.clientX-r.left)*cv.width/r.width,(e.clientY-r.top)*cv.height/r.height]}}
cv.addEventListener('pointerdown',e=>{{if(saving)return;e.preventDefault();drawing=true;epoch++;dirty=true;save.disabled=false;save.textContent='Valider la signature';cv.setPointerCapture(e.pointerId);ctx.beginPath();ctx.moveTo(...pt(e))}});
cv.addEventListener('pointermove',e=>{{if(!drawing)return;e.preventDefault();ctx.lineTo(...pt(e));ctx.stroke()}});
cv.addEventListener('pointerup',()=>drawing=false);cv.addEventListener('pointercancel',()=>drawing=false);
document.getElementById('clear').onclick=()=>{{if(saving)return;epoch++;ctx.clearRect(0,0,cv.width,cv.height);dirty=false;save.disabled=false;save.textContent='Valider la signature';msg.textContent='Signez dans le cadre. La signature enregistrée est conservée tant qu’un nouveau tracé n’est pas validé.'}};
async function synchronize(force=false){{
 if(syncing||drawing||dirty||saving)return;syncing=true;const ticket=epoch;
 try{{
  const r=await fetch('/status/'+token,{{cache:'no-store'}});if(!r.ok)return;
  const state=await r.json();if(!state.saved||(!force&&state.revision===revision))return;
  const imageResponse=await fetch('/image/'+token+'?revision='+state.revision,{{cache:'no-store'}});if(!imageResponse.ok)return;
  const blob=await imageResponse.blob(),url=URL.createObjectURL(blob);
  try{{
   const im=new Image();await new Promise((resolve,reject)=>{{im.onload=resolve;im.onerror=reject;im.src=url}});
   if(ticket!==epoch||drawing||dirty||saving)return;
   ctx.clearRect(0,0,cv.width,cv.height);
   const scale=Math.min(cv.width/im.width,cv.height/im.height)*.86,w=im.width*scale,h=im.height*scale;
   ctx.drawImage(im,(cv.width-w)/2,(cv.height-h)/2,w,h);revision=state.revision;
   save.disabled=true;save.textContent='✓ Signature validée';msg.textContent='✓ Signature enregistrée et affichée. Vous pouvez fermer cette page.';
  }}finally{{URL.revokeObjectURL(url)}}
 }}catch(_e){{}}finally{{syncing=false}}
}}
save.onclick=async()=>{{
 if(saving)return;
 if(!dirty){{msg.textContent='Signez dans le cadre avant de valider.';return}}
 saving=true;save.disabled=true;drawing=false;epoch++;msg.textContent='Enregistrement en cours…';
 try{{
  const r=await fetch('/save/'+token,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{image:cv.toDataURL('image/png')}}),cache:'no-store'}});
  const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||('HTTP '+r.status));
  dirty=false;revision='';msg.textContent='✓ Signature enregistrée. Vous pouvez fermer cette page.';save.textContent='✓ Signature validée';
 }}catch(e){{save.disabled=false;msg.textContent='Échec de validation : '+e.message}}
 finally{{saving=false}}
 await synchronize(true);
}};
synchronize();setInterval(synchronize,900);
</script></body></html>'''

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a): pass
    def do_GET(self):
        token=urlparse(self.path).path.rsplit('/',1)[-1]; info=_sessions.get(token)
        if not info: return self._reply(404,b'Lien invalide')
        if self.path.startswith('/status/'):
            return self._reply(200,json.dumps(signature_status(info['contract'])).encode(),'application/json')
        if self.path.startswith('/image/'):
            payload=saved_signature(info['contract'])
            if not payload:return self._reply(404,b'Pas de signature')
            return self._reply(200,payload,'image/png')
        if not self.path.startswith('/sign/'):
            return self._reply(404,b'Lien invalide')
        self._reply(200,_page(token,info['contract']).encode(), 'text/html; charset=utf-8')
    def do_POST(self):
        token=urlparse(self.path).path.rsplit('/',1)[-1]; info=_sessions.get(token)
        if not self.path.startswith('/save/') or not info: return self._reply(404,b'Lien invalide')
        try:
            length=int(self.headers.get('Content-Length','0'))
            if length <= 0 or length > 20_000_000: raise ValueError('taille image invalide')
            raw=self.rfile.read(length)
            ctype=(self.headers.get('Content-Type') or '').lower()
            if 'image/png' in ctype:
                payload=raw
            else:
                data=json.loads(raw.decode('utf-8')); uri=data['image']; payload=base64.b64decode(uri.split(',',1)[1],validate=True)
            if not payload.startswith(b'\x89PNG') or len(payload)<100: raise ValueError('image invalide')
            payload=normalized_signature(payload)
            path=signature_path(info['contract'])
            with _lock:
                temp=path.with_name(path.name+'.'+secrets.token_hex(6)+'.tmp')
                previous=path.read_bytes() if path.is_file() else None
                try:
                    temp.write_bytes(payload);os.replace(temp,path)
                    if info.get('contract_html'):
                        from signed_contracts import archive_contract
                        archive_contract(info['contract'],info['client_codes'],info['contract_html'],payload)
                except Exception:
                    if previous is None:path.unlink(missing_ok=True)
                    else:
                        temp.write_bytes(previous);os.replace(temp,path)
                    raise
                finally:
                    temp.unlink(missing_ok=True)
                for session in _sessions.values():
                    if session['contract']==info['contract']:
                        session['saved']=True;session['saved_at']=time.time();session['event'].set()
            self._reply(200,b'{"ok":true}','application/json')
        except Exception as exc:
            body=json.dumps({'ok':False,'error':str(exc)},ensure_ascii=False).encode('utf-8')
            self._reply(400,body,'application/json; charset=utf-8')
    def _reply(self,status,data,ctype='text/plain; charset=utf-8'):
        self.send_response(status); self.send_header('Content-Type',ctype); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

def start_signature_session(contract_no, client_codes=None, contract_html=None, remote=True):
    if remote:
        from remote_signature_client import start
        return start(str(contract_no).strip(),client_codes or [],contract_html or "")
    global _server,_thread
    if _server is None:
        _server=ThreadingHTTPServer(('0.0.0.0',0),Handler); _thread=threading.Thread(target=_server.serve_forever,daemon=True); _thread.start()
    token=secrets.token_urlsafe(24)
    with _lock:
        _sessions[token]={'contract':str(contract_no).strip(),'client_codes':client_codes or [],'contract_html':contract_html or '', 'saved':False,'event':threading.Event(),'started_at':time.time()}
    return f"http://{_lan_ip()}:{_server.server_port}/sign/{token}", token

def session_saved(token):
    if token not in _sessions:
        from remote_signature_client import saved
        return saved(token)
    info=_sessions.get(token,{})
    if not info: return False
    ev=info.get('event')
    if ev is not None and ev.is_set(): return bool(saved_signature(info['contract']))
    if info.get('saved'): return bool(saved_signature(info['contract']))
    try:
        p=signature_path(info.get('contract',''))
        return p.is_file() and p.stat().st_mtime >= float(info.get('started_at',0)) and bool(saved_signature(info['contract']))
    except OSError:
        return False
