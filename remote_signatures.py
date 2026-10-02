"""Signature publique par lien secret, création et récupération protégées par API."""
from flask import Blueprint,request,jsonify,abort,Response,send_file
from pathlib import Path
import re, os,sqlite3,secrets,time,json,base64,subprocess,shutil,tempfile,threading,hashlib
from remote_contract_common import normalize_png,insert_signature,ensure_verso
bp=Blueprint('remote_signatures',__name__)
DATA=Path(os.environ.get('HBZ_SIGNATURE_DATA_DIR',str(Path(os.environ.get('GESTIONPRO_DATA_DIR',str(Path(__file__).resolve().parent))) / 'signature_data')))
_lock=threading.Lock()

def db():
    DATA.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DATA/'sessions.sqlite',timeout=25);c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS signatures(token TEXT PRIMARY KEY,contract_no TEXT,clients TEXT,expires REAL,original TEXT,signed TEXT,png BLOB,pdf BLOB,signed_at TEXT)')
    c.execute('CREATE TABLE IF NOT EXISTS signature_audit(token TEXT PRIMARY KEY, accepted_at TEXT NOT NULL, document_sha256 TEXT NOT NULL, ip TEXT, user_agent TEXT)')
    return c

def authorized():
    secret=(os.environ.get('GESTIONPRO_API_TOKEN') or os.environ.get('HBZ_WEB_SYNC_TOKEN','')).strip()
    if not secret or not secrets.compare_digest(request.headers.get('Authorization',''),'Bearer '+secret):abort(401)

def get(token):
    with db() as c:r=c.execute('SELECT * FROM signatures WHERE token=?',(token,)).fetchone()
    if not r:abort(404)
    if r['expires']<time.time():abort(410,'Ce lien a expiré. Demandez un nouveau lien à l’agence.')
    return r

def render_pdf(content):
    browser=os.environ.get('HBZ_CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
    if not browser:raise RuntimeError('La conversion PDF nécessite Chromium sur le serveur.')
    # The PDF renderer has no permission to load network or local resources.
    policy="default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; base-uri 'none'; form-action 'none'"
    import html
    meta='<meta http-equiv="Content-Security-Policy" content="'+html.escape(policy,quote=True)+'">'
    content=re.sub(r'<head\b[^>]*>',lambda m:m[0]+meta,content,count=1,flags=re.I) if re.search(r'<head\b',content,re.I) else '<head>'+meta+'</head>'+content
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        source=Path(td)/'contrat.html';pdf=Path(td)/'contrat.pdf';source.write_text(content,encoding='utf-8')
        try:
            command=[browser,'--headless','--no-sandbox','--disable-gpu','--disable-dev-shm-usage','--disable-background-networking','--no-first-run','--no-pdf-header-footer','--user-data-dir='+str(Path(td)/'profile'),'--print-to-pdf='+str(pdf),source.as_uri()]
            process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=(os.name=='posix'))
            try:
                stdout,stderr=process.communicate(timeout=45)
                result=subprocess.CompletedProcess(command,process.returncode,stdout,stderr)
            finally:
                # Chromium peut laisser un sous-processus écrire dans son profil
                # après création du PDF : l'arrêter avant le nettoyage.
                if os.name=='posix':
                    import signal
                    try:os.killpg(process.pid,signal.SIGKILL)
                    except ProcessLookupError:pass
                elif process.poll() is None:process.kill()
                if process.poll() is None:process.communicate()
        except subprocess.TimeoutExpired:raise RuntimeError('La conversion PDF a dépassé le délai. Réessayez.')
        if result.returncode or not pdf.is_file():raise RuntimeError('Le PDF signé n’a pas pu être créé.')
        from pypdf import PdfReader
        payload=pdf.read_bytes()
        if not PdfReader(__import__('io').BytesIO(payload)).pages:raise RuntimeError('Le PDF est vide.')
        return payload

@bp.post('/api/sync/signatures')
def create():
    authorized();body=request.get_json(silent=True)
    if not isinstance(body,dict):return jsonify(error='Requête invalide'),400
    content=body.get('html','');number=str(body.get('contract_no','')).strip();clients=body.get('client_codes',[])
    if not number or len(number)>100 or not isinstance(clients,list) or not clients or len(clients)>10 or not all(isinstance(c,str) and c for c in clients) or not isinstance(content,str) or len(content)>12_000_000:return jsonify(error='Contrat incomplet ou trop volumineux'),400
    try:
        validate_contract(content)
        content=ensure_verso(content)
        insert_signature(content, b'') # Reject unsupported signature frames before creating the link.
    except ValueError as exc:return jsonify(error=str(exc)),400
    # Check that the site can actually supply the promised signed PDF before issuing a link.
    if not (os.environ.get('HBZ_CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')):return jsonify(error='Le site doit être déployé avec Chromium : Dockerfile.'),503
    token=secrets.token_urlsafe(32);expires=time.time()+7*86400
    with db() as c:c.execute('INSERT INTO signatures(token,contract_no,clients,expires,original) VALUES(?,?,?,?,?)',(token,number,json.dumps(clients),expires,content))
    return jsonify(token=token,path='/signature/'+token,expires_at=expires)

@bp.get('/signature/<token>')
def page(token):
    r=get(token)
    from signature_page import _page
    page=_page(token,r['contract_no'])
    introduction=f'''<div style="margin:16px 0"><a href="/signature/{token}/contract" target="_blank" rel="noopener">Ouvrir le contrat complet</a><a href="/signature/{token}/original.pdf">Télécharger le contrat avant signature (PDF)</a><iframe id="contract-preview" title="Contrat à lire avant signature" sandbox src="/signature/{token}/contract" style="width:100%;height:65vh;background:white;border:1px solid #c9d9e8"></iframe><label><input type="checkbox" id="accepted"> J’ai lu le recto et le verso de ce contrat et j’accepte de les signer.</label><p><a id="download" href="/signature/{token}/pdf" style="display:{'inline' if r['pdf'] else 'none'}">Télécharger mon contrat signé (PDF)</a></p></div>'''
    page=page.replace('<canvas id="pad">',introduction+'<canvas id="pad">',1)
    for name in ('status','image','save'):page=page.replace("'/"+name+"/'+token","'/signature/'+token+'/"+name+"'")
    page=page.replace("if(!dirty){", "if(!document.getElementById('accepted').checked){msg.textContent='Lisez le contrat et cochez votre accord avant de valider.';return}if(!dirty){",1)
    page=page.replace('image:cv.toDataURL(\'image/png\')','image:cv.toDataURL(\'image/png\'),accepted:document.getElementById(\'accepted\').checked')
    page=page.replace("dirty=false;revision='';", "document.getElementById('download').style.display='inline';dirty=false;revision='';",1)
    page=page.replace("saving=true;save.disabled=true;","if(!window.confirm('Confirmez-vous votre signature sur le recto et le verso de ce contrat ?'))return; saving=true;save.disabled=true;",1)
    page=page.replace("Vous pouvez fermer cette page.","Téléchargez votre contrat signé ci-dessus.")
    page=page.replace("save.disabled=true;save.textContent='✓ Signature validée';","document.getElementById('download').style.display='inline';document.getElementById('clear').disabled=true;cv.style.pointerEvents='none';document.getElementById('accepted').checked=true;document.getElementById('accepted').disabled=true;document.getElementById('contract-preview').src='/signature/'+token+'/contract';save.disabled=true;save.textContent='✓ Signature validée';")
    return Response(page,mimetype='text/html')

@bp.get('/signature/<token>/contract')
def contract(token):
    r=get(token);return Response(r['signed'] or r['original'],mimetype='text/html',headers={'Content-Security-Policy':"default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; base-uri 'none'"})

@bp.get('/signature/<token>/status')
def status(token):
    r=get(token);return jsonify(saved=bool(r['pdf']),revision=hashlib.sha256(r['png']).hexdigest() if r['png'] else '')

@bp.get('/signature/<token>/image')
def image(token):
    r=get(token)
    if not r['png']:abort(404)
    return Response(r['png'],mimetype='image/png')

@bp.post('/signature/<token>/save')
def save(token):
    body=request.get_json(silent=True)
    if not isinstance(body,dict):return jsonify(ok=False,error='Requête invalide'),400
    if body.get('accepted') is not True:return jsonify(ok=False,error='Confirmez la lecture du contrat.'),400
    try:
        with _lock:
            r=get(token)
            if r['pdf']:return jsonify(ok=True)
            uri=body.get('image','')
            if not isinstance(uri,str) or not uri.startswith('data:image/png;base64,'):raise ValueError('Image PNG requise.')
            payload=normalize_png(base64.b64decode(uri.split(',',1)[1],validate=True))
            content=insert_signature(r['original'],payload);pdf=render_pdf(content)
            from datetime import datetime,timezone
            now=datetime.now(timezone.utc).isoformat()
            with db() as c:
                c.execute('INSERT OR IGNORE INTO signature_audit VALUES(?,?,?,?,?)',(token,now,hashlib.sha256(content.encode()).hexdigest(),request.remote_addr,(request.headers.get('User-Agent') or '')[:1000]))
                c.execute('UPDATE signatures SET signed=?,png=?,pdf=?,signed_at=? WHERE token=? AND pdf IS NULL',(content,payload,pdf,now,token))
        return jsonify(ok=True)
    except (ValueError,IndexError,OSError) as e:return jsonify(ok=False,error=str(e)),400
    except RuntimeError as e:return jsonify(ok=False,error=str(e)),503

@bp.get('/signature/<token>/original.pdf')
def original_download(token):
    r=get(token)
    try:payload=render_pdf(r['original'])
    except RuntimeError as exc:return jsonify(error=str(exc)),503
    import io
    return send_file(io.BytesIO(payload),mimetype='application/pdf',as_attachment=True,download_name='Contrat_AVANT_SIGNATURE.pdf')

@bp.get('/signature/<token>/pdf')
def download(token):
    r=get(token)
    if not r['pdf']:abort(409,'Le contrat n’est pas encore signé.')
    import io
    safe=''.join(c for c in r['contract_no'] if c.isalnum() or c in '-_')
    return send_file(io.BytesIO(r['pdf']),mimetype='application/pdf',as_attachment=True,download_name='Contrat_'+safe+'_SIGNE.pdf')

@bp.get('/api/sync/signatures/<token>')
def retrieve(token):
    authorized();r=get(token)
    return jsonify(saved=bool(r['pdf']),contract_no=r['contract_no'],client_codes=json.loads(r['clients']),signed_at=r['signed_at'],html=r['signed'] or '',image=base64.b64encode(r['png']).decode() if r['png'] else '',pdf=base64.b64encode(r['pdf']).decode() if r['pdf'] else '')

@bp.after_request
def private(response):
    response.headers['Cache-Control']='no-store';response.headers['Referrer-Policy']='no-referrer';response.headers['X-Content-Type-Options']='nosniff';return response


def validate_contract(content):
    from html.parser import HTMLParser
    class Checker(HTMLParser):
        def handle_starttag(self,tag,attrs):
            if tag.lower() in {'script','iframe','object','embed','base','meta','form','link','math','foreignobject','animate','set'}:
                # Allow ordinary charset / viewport metadata only.
                if tag.lower()=='meta' and not any(k.lower()=='http-equiv' for k,v in attrs):return
                raise ValueError('Le contrat contient un élément actif ou une ressource non autonome.')
            for key,value in attrs:
                if key.lower().startswith('on') or key.lower() in {'srcdoc','srcset'}:raise ValueError('Le contrat contient du code actif.')
                if key.lower() in {'src','background','poster'} and not (value or '').startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,')):
                    raise ValueError('Les images du contrat doivent être intégrées au document.')
                if key.lower() in {'href','xlink:href'} and (value or '').lower().startswith(('file:','javascript:')):raise ValueError('Lien interdit dans le contrat.')
    Checker().feed(content)
