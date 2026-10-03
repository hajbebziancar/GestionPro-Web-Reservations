"""Relais autonome WSGI (stdlib). Montage sous /mobile/ sur le site existant."""
import base64, hashlib, hmac, json, mimetypes, os, secrets, sqlite3, time
from pathlib import Path
from contextlib import contextmanager
from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn
ROOT=Path(__file__).resolve().parent
class Relay:
    def __init__(self, database=None, mobile_token=None, pc_token=None):
        self.path=Path(database or os.environ.get('GP_RELAY_DB',ROOT/'data'/'mobile.sqlite3'))
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.mobile=mobile_token or os.environ.get('GP_MOBILE_TOKEN','')
        self.pc=pc_token or os.environ.get('GP_PC_TOKEN','')
        if not self.mobile or not self.pc or self.mobile==self.pc:
            raise RuntimeError('Définir GP_MOBILE_TOKEN et GP_PC_TOKEN, deux secrets différents.')
        with self.connect() as c:
            c.executescript('''CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1),payload TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS ops(id TEXT PRIMARY KEY,payload TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'pending',message TEXT NOT NULL DEFAULT '',created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS invites(token TEXT PRIMARY KEY,op_id TEXT NOT NULL,expires REAL NOT NULL,used INTEGER NOT NULL DEFAULT 0);''')
            c.execute('INSERT OR IGNORE INTO state VALUES(1,?)',(json.dumps({'clients':[],'vehicles':[],'contracts':[],'reservations':[],'maintenance':[],'expenses':[],'checks':[],'finance':[],'settings':{},'pc_at':None}),))
    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=20);c.row_factory=sqlite3.Row
        try:
            with c:
                yield c
        finally:
            c.close()
    def auth(self,e,role):
        token=e.get('HTTP_AUTHORIZATION','').removeprefix('Bearer ')
        if not hmac.compare_digest(token,self.mobile if role=='mobile' else self.pc):raise PermissionError('Accès refusé. Vérifiez votre clé de connexion.')
    def view(self,c):
        snapshot=json.loads(c.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
        ops=[{**json.loads(r['payload']),'status':r['status'],'message':r['message']} for r in c.execute('SELECT * FROM ops ORDER BY created,id')]
        # Only pending records are overlaid; rejected edits never hide the PC version.
        for op in ops:
            if op['status']!='pending':continue
            if op['kind'] in ('client_create','client_update'):
                key='clients';identity='code';record=op['record']
            elif op['kind']=='contract_create':
                key='contracts';identity='numero';record={**op['record'],'signature':op.get('signature',''),'frozen':op.get('frozen'), 'pdf':op.get('pdf','')}
            elif op['kind']=='vehicle_update':
                key='vehicles';identity='code';record=op['record']
            elif op['kind'].startswith('reservation_'):
                key='reservations';identity='reference';record=op['record']
            elif op['kind'].startswith('maintenance_'):
                key='maintenance';identity='reference';record=op['record']
            else:continue
            snapshot[key]=[r for r in snapshot[key] if r[identity]!=record[identity]]+[record]
        snapshot['operations']=ops
        return snapshot
    def validate(self,op):
        if not isinstance(op,dict) or op.get('kind') not in ('client_create','client_update','contract_create','reservation_create','reservation_update','maintenance_create','maintenance_update','vehicle_update'):raise ValueError('Opération inconnue.')
        if not isinstance(op.get('id'),str) or not 8<=len(op['id'])<=80:raise ValueError('Identifiant invalide.')
        r=op.get('record')
        if not isinstance(r,dict):raise ValueError('Fiche invalide.')
        if op['kind'].startswith('client'):
            if not r.get('code') or not r.get('cin') or not r.get('nom'):raise ValueError('Code, CIN et nom obligatoires.')
            if op['kind']=='client_update' and not isinstance(op.get('original'),dict):raise ValueError('Version d’origine absente.')
        elif op['kind']=='vehicle_update':
            if not r.get('code') or not isinstance(op.get('original'),dict):raise ValueError('Compteur incomplet.')
        elif op['kind'].startswith(('reservation_','maintenance_')):
            if not r.get('reference') or not r.get('vehicle'):raise ValueError('Référence et véhicule obligatoires.')
            if op['kind'].endswith('_update') and not isinstance(op.get('original'),dict):raise ValueError('Version d’origine absente.')
        else:
            if not all(r.get(k) for k in ('numero','client_code','vehicle_code','date_depart','date_retour')):raise ValueError('Contrat incomplet.')
            if not isinstance(op.get('frozen'),dict):raise ValueError('Copie figée absente.')
        if len(json.dumps(op))>3_000_000:raise ValueError('Document trop volumineux.')
        if op.get('signature'):
            signature=op['signature']
            if not isinstance(signature,str) or not signature.startswith('data:image/png;base64,'):raise ValueError('Signature invalide.')
            raw=base64.b64decode(signature.split(',',1)[1],validate=True)
            if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw)>700000:raise ValueError('Signature PNG invalide.')
        if op.get('pdf'):
            raw=base64.b64decode(op['pdf'],validate=True)
            if not raw.startswith(b'%PDF-') or len(raw)>2_000_000:raise ValueError('PDF invalide.')
    def route(self,e):
        path=e.get('PATH_INFO','/');method=e.get('REQUEST_METHOD','GET')
        if path.startswith('/mobile'):path=path[len('/mobile'): ] or '/'
        if path.startswith('/api/'):
            if method!='POST':raise ValueError('Requête POST requise.')
            length=int(e.get('CONTENT_LENGTH') or 0)
            if length<1 or length>20_000_000:raise ValueError('Taille invalide.')
            role='pc' if path=='/api/pc-exchange' else 'mobile'
            self.auth(e,role);p=json.loads(e['wsgi.input'].read(length))
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                if path=='/api/sync':
                    incoming=p.get('operations',[])
                    if not isinstance(incoming,list) or len(incoming)>50:raise ValueError('Maximum 50 opérations par échange.')
                    for op in incoming:
                        self.validate(op)
                        old=c.execute('SELECT payload FROM ops WHERE id=?',(op['id'],)).fetchone()
                        serial=json.dumps(op,sort_keys=True,ensure_ascii=False)
                        if old:
                            if json.loads(old[0])!=op:raise ValueError('Identifiant réutilisé avec un contenu différent.')
                        else:c.execute('INSERT INTO ops(id,payload,created) VALUES(?,?,?)',(op['id'],serial,time.time()))
                    return 200,self.view(c)
                if path=='/api/pc-exchange':
                    for item in p.get('results',[]):
                        if item.get('status') not in ('applied','rejected'):raise ValueError('Statut PC invalide.')
                        c.execute("UPDATE ops SET status=?,message=? WHERE id=? AND status='pending'",(item['status'],str(item.get('message',''))[:1000],item['id']))
                    if 'snapshot' in p:
                        s=p['snapshot']
                        if not all(isinstance(s.get(k),list) for k in ('clients','vehicles','contracts','reservations')):raise ValueError('Données PC invalides.')
                        s['vehicles']=[r for r in s['vehicles'] if r.get('service')==1]
                        s['pc_at']=time.time();c.execute('UPDATE state SET payload=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
                    return 200,{'pending':[json.loads(r[0]) for r in c.execute("SELECT payload FROM ops WHERE status='pending' ORDER BY created,id") ]}
                if path=='/api/invite':
                    row=c.execute('SELECT * FROM ops WHERE id=?',(p.get('op_id'),)).fetchone()
                    if not row or row['status']!='pending':raise ValueError('Le contrat doit être en attente de signature avant son transfert au PC.')
                    op=json.loads(row['payload'])
                    if op['kind']!='contract_create' or op.get('signature'):raise ValueError('Contrat déjà signé ou invalide.')
                    token=secrets.token_urlsafe(32);c.execute('INSERT INTO invites VALUES(?,?,?,0)',(token,op['id'],time.time()+172800))
                    return 200,{'token':token}
                raise FileNotFoundError()
        if path.startswith('/signature/'):
            token=path.split('/')[2]
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                invite=c.execute('SELECT * FROM invites WHERE token=?',(token,)).fetchone()
                if not invite or invite['expires']<time.time() or invite['used']:raise ValueError('Lien expiré ou déjà utilisé.')
                row=c.execute('SELECT * FROM ops WHERE id=?',(invite['op_id'],)).fetchone();op=json.loads(row['payload'])
                if row['status']!='pending' or op.get('signature'):raise ValueError('Ce contrat ne peut plus être signé.')
                if method=='GET' and path.endswith('/data'):return 200,{'frozen':op['frozen'],'record':op['record']}
                if method=='POST' and path.endswith('/save'):
                    n=int(e.get('CONTENT_LENGTH') or 0)
                    if n<1 or n>3_000_000:raise ValueError('Taille invalide.')
                    p=json.loads(e['wsgi.input'].read(n));op['signature']=p.get('signature','');op['pdf']=p.get('pdf','')
                    if not op['signature'] or not op['pdf']:raise ValueError('Signature et PDF obligatoires.')
                    self.validate(op);c.execute('UPDATE ops SET payload=? WHERE id=?',(json.dumps(op,ensure_ascii=False),op['id']))
                    c.execute('UPDATE invites SET used=1 WHERE token=?',(token,));return 200,{'ok':True}
                path='/sign.html'
        if method!='GET':raise FileNotFoundError()
        if path in ('/',''):path='/index.html'
        file=(ROOT/'mobile'/path.lstrip('/')).resolve()
        if not file.is_relative_to((ROOT/'mobile').resolve()) or not file.is_file():raise FileNotFoundError()
        return 200,file
    def __call__(self,e,start):
        try:status,data=self.route(e)
        except PermissionError as x:status,data=401,{'error':str(x)}
        except (ValueError,KeyError,TypeError,OverflowError) as x:status,data=400,{'error':str(x)}
        except FileNotFoundError:status,data=404,{'error':'Introuvable'}
        except Exception:status,data=503,{'error':'Relais temporairement indisponible.'}
        if isinstance(data,Path):body=data.read_bytes();mime=mimetypes.guess_type(data.name)[0] or 'application/octet-stream'
        else:body=json.dumps(data,ensure_ascii=False).encode();mime='application/json'
        headers=[('Content-Type',mime),('Content-Length',str(len(body))),('X-Content-Type-Options','nosniff'),('Referrer-Policy','no-referrer'),('Cache-Control','no-store' if mime=='application/json' else 'no-cache'),('X-Frame-Options','DENY')]
        start(str(status)+' '+{200:'OK',400:'Bad Request',401:'Unauthorized',404:'Not Found',503:'Service Unavailable'}[status],headers);return [body]
class ThreadedServer(ThreadingMixIn,WSGIServer):daemon_threads=True
if __name__=='__main__':
    app=Relay();port=int(os.environ.get('PORT','8766'))
    print('Gestion Pro Android : http://localhost:'+str(port)+'/mobile/')
    make_server('0.0.0.0',port,app,server_class=ThreadedServer).serve_forever()
