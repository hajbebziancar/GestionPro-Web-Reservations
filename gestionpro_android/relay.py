"""Relais autonome WSGI (stdlib). Montage sous /mobile/ sur le site existant."""
import base64, hashlib, hmac, json, mimetypes, os, secrets, sqlite3, time
from pathlib import Path
from contextlib import contextmanager
from wsgiref.simple_server import make_server, WSGIServer
from socketserver import ThreadingMixIn
ROOT=Path(__file__).resolve().parent
import sys
sys.path.insert(0,str(ROOT.parent))
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
            CREATE TABLE IF NOT EXISTS document_requests(numero TEXT PRIMARY KEY,payload TEXT,status TEXT NOT NULL DEFAULT 'pending');
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
        from gestionpro_android.web_bookings import bookings
        web=bookings()
        existing={r['reference'] for r in snapshot['reservations']}
        snapshot['reservations'] += [r for r in web if r['reference'] not in existing]
        drafts={r['op_id'] for r in snapshot.get('mobile_contract_drafts',[])}
        for op in ops:
            if op['id'] in drafts:op['pc_received']=True
        snapshot['operations']=ops
        return snapshot
    def validate(self,op):
        if not isinstance(op,dict) or op.get('kind') not in ('client_create','client_update','contract_create','reservation_create','reservation_update','maintenance_create','maintenance_update','vehicle_update','document_upload'):raise ValueError('Opération inconnue.')
        if not isinstance(op.get('id'),str) or not 8<=len(op['id'])<=80:raise ValueError('Identifiant invalide.')
        if op.get('trusted_web'):raise ValueError('Réservation web importée uniquement par le serveur.')
        r=op.get('record')
        if not isinstance(r,dict):raise ValueError('Fiche invalide.')
        if op['kind']=='document_upload':
            if not all(r.get(k) for k in ('client_code','reference','filename')) or not op.get('pdf'):raise ValueError('Document PDF incomplet.')
        elif op['kind'].startswith('client'):
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
        if len(json.dumps(op))>6_000_000:raise ValueError('Document trop volumineux.')
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
            if path=='/api/contract-pdf':
                from gestionpro_android.contract_document import document_pdf
                pdf,content=document_pdf(p['frozen'],p.get('signature',''))
                return 200,{'pdf':base64.b64encode(pdf).decode()}
            if path=='/api/finance':
                from gestionpro_android.financial_rules import summary
                with self.connect() as c:data=json.loads(c.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
                return 200,{**summary(data,p.get('start'),p.get('end'),True),'pc_at':data.get('pc_at')}
            with self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                if path=='/api/contract-document':
                    number=str(p.get('numero',''))
                    snapshot=json.loads(c.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
                    if not any(r['numero']==number for r in snapshot['contracts']):raise ValueError('Contrat absent du PC.')
                    row=c.execute('SELECT * FROM document_requests WHERE numero=?',(number,)).fetchone()
                    if not row:
                        c.execute('INSERT INTO document_requests(numero) VALUES(?)',(number,))
                        return 200,{'pending':True,'message':'Demande envoyée. Laissez Gestion Pro ouvert sur le PC, puis synchronisez le téléphone et réessayez dans une minute.'}
                    if row['status']=='pending':return 200,{'pending':True,'message':'Archive en attente du PC. Vérifiez sa connexion et sa synchronisation.'}
                    doc=json.loads(row['payload'])
                    if doc.get('error'):raise ValueError(doc['error'])
                    number=doc['numero'];record=next(r for r in snapshot['contracts'] if r['numero']==number)
                    frozen={'record':record,'client':next(r for r in snapshot['clients'] if r['code']==record['client_code']),'vehicle':next((r for r in snapshot['vehicles']+snapshot.get('contract_vehicles',[]) if r['code']==record['vehicle_code']),{'modele':record['vehicle_code']}),'settings':snapshot['settings'],'created_at':record.get('created_at')}
                    if not doc.get('pdf'):
                        from remote_signatures import render_pdf
                        from remote_contract_common import ensure_verso
                        doc['pdf']=base64.b64encode(render_pdf(ensure_verso(doc['html']))).decode()
                        c.execute('UPDATE document_requests SET payload=? WHERE numero=?',(json.dumps(doc,ensure_ascii=False),number))
                    op={'id':'pc-archive-'+hashlib.sha256(number.encode()).hexdigest()[:32],'kind':'contract_create','record':record,'frozen':frozen,'signature':doc['signature'],'pdf':doc['pdf'],'document_html':doc['html']}
                    c.execute("INSERT INTO ops(id,payload,status,message,created) VALUES(?,?,'applied','Archive signée récupérée du PC',?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",(op['id'],json.dumps(op,ensure_ascii=False),time.time()))
                    return 200,{'document':op}
                if path=='/api/sync':
                    incoming=p.get('operations',[])
                    if not isinstance(incoming,list) or len(incoming)>50:raise ValueError('Maximum 50 opérations par échange.')
                    for op in incoming:
                        self.validate(op)
                        if op.get('kind')=='contract_create' and op.get('signature'):
                            from gestionpro_android.contract_document import document_html
                            op['document_html']=document_html(op['frozen'],op['signature'])
                        self.validate(op)
                        if op['kind']=='contract_create' and op['frozen'].get('record')!=op['record']:raise ValueError('Le document et le contrat ne correspondent pas.')
                        old=c.execute('SELECT payload FROM ops WHERE id=?',(op['id'],)).fetchone()
                        serial=json.dumps(op,sort_keys=True,ensure_ascii=False)
                        if old:
                            saved=json.loads(old[0])
                            late_unsigned=saved.get('kind')=='contract_create' and saved.get('signature') and not op.get('signature') and saved.get('record')==op.get('record') and saved.get('frozen')==op.get('frozen')
                            if saved!=op and not late_unsigned:raise ValueError('Identifiant réutilisé avec un contenu différent.')
                        else:c.execute('INSERT INTO ops(id,payload,created) VALUES(?,?,?)',(op['id'],serial,time.time()))
                    return 200,self.view(c)
                if path=='/api/pc-exchange':
                    for doc in p.get('documents',[]):
                        if not isinstance(doc,dict) or len(json.dumps(doc))>8_000_000:raise ValueError('Archive invalide ou trop volumineuse.')
                        number=doc.get('numero')
                        if not c.execute('SELECT 1 FROM document_requests WHERE numero=?',(number,)).fetchone():raise ValueError('Archive non demandée.')
                        if not doc.get('error') and (not doc.get('html') or not str(doc.get('signature','')).startswith('data:image/png;base64,')):raise ValueError('Archive signée incomplète.')
                        c.execute("UPDATE document_requests SET payload=?,status='received' WHERE numero=?",(json.dumps(doc,ensure_ascii=False),number))
                    for item in p.get('results',[]):
                        if item.get('status') not in ('applied','rejected'):raise ValueError('Statut PC invalide.')
                        c.execute("UPDATE ops SET status=?,message=? WHERE id=? AND status='pending'",(item['status'],str(item.get('message',''))[:1000],item['id']))
                    if 'snapshot' in p:
                        s=p['snapshot']
                        if not all(isinstance(s.get(k),list) for k in ('clients','vehicles','contracts','reservations')):raise ValueError('Données PC invalides.')
                        s['vehicles']=[r for r in s['vehicles'] if r.get('service')==1]
                        from gestionpro_android.web_bookings import update_statuses,bookings,sync_fleet
                        previous=json.loads(c.execute('SELECT payload FROM state WHERE id=1').fetchone()[0])
                        update_statuses(s.get('reservations',[]),previous.get('reservations',[]))
                        sync_fleet(s)
                        s['pc_at']=time.time();c.execute('UPDATE state SET payload=? WHERE id=1',(json.dumps(s,ensure_ascii=False),))
                    pending=[json.loads(r[0]) for r in c.execute("SELECT payload FROM ops WHERE status='pending' ORDER BY created,id")]
                    from gestionpro_android.web_bookings import bookings
                    s=json.loads(c.execute('SELECT payload FROM state WHERE id=1').fetchone()[0]);existing={r['reference']:r for r in s.get('reservations',[])}
                    for r in bookings():
                        if r['reference'] not in existing:pending.append({'id':'web-import-'+r['reference'],'kind':'reservation_create','record':r,'trusted_web':True})
                        elif existing[r['reference']].get('source')=='SITE WEB':
                            old=existing[r['reference']]
                            from gestionpro_android.web_bookings import canonical
                            if canonical(old.get('status'))!=r['status']:
                                updated={**old,'status':r['status']}
                                change_id='web-status-'+hashlib.sha256(json.dumps([r['reference'],old,r['status'],s.get('pc_at')],sort_keys=True).encode()).hexdigest()[:40]
                                pending.append({'id':change_id,'kind':'reservation_update','original':old,'record':updated,'trusted_web':True})
                    return 200,{'pending':pending,'document_requests':[r[0] for r in c.execute("SELECT numero FROM document_requests WHERE status='pending' ORDER BY rowid LIMIT 1")]}
                if path=='/api/sign-contract':
                    row=c.execute('SELECT * FROM ops WHERE id=?',(p.get('op_id'),)).fetchone()
                    if not row or row['status']=='rejected':raise ValueError('Contrat absent ou rejeté : consultez la synchronisation.')
                    op=json.loads(row['payload'])
                    if op['kind']!='contract_create':raise ValueError('Contrat invalide.')
                    if op.get('signature'):return 200,{'document':op}
                    if p.get('accepted') is not True:raise ValueError('Acceptation du recto et du verso requise.')
                    op['signature']=p.get('signature','');self.validate(op)
                    if not op['signature']:raise ValueError('Tracez une signature avant de valider.')
                    from gestionpro_android.contract_document import document_pdf
                    pdf,content=document_pdf(op['frozen'],op['signature']);op['pdf']=base64.b64encode(pdf).decode();op['document_html']=content
                    self.validate(op)
                    c.execute('UPDATE ops SET payload=? WHERE id=?',(json.dumps(op,ensure_ascii=False),op['id']))
                    return 200,{'document':op}
                if path=='/api/share-contract':
                    row=next((r for r in c.execute('SELECT * FROM ops ORDER BY created DESC,id DESC') if json.loads(r['payload']).get('record',{}).get('numero')==p.get('numero') and json.loads(r['payload']).get('signature')),None)
                    if not row:raise ValueError('Synchronisez le contrat signé avant de le partager.')
                    token=secrets.token_urlsafe(32);c.execute('INSERT INTO invites VALUES(?,?,?,1)',(token,row['id'],time.time()+172800))
                    return 200,{'token':token}
                if path=='/api/invite':
                    row=c.execute('SELECT * FROM ops WHERE id=?',(p.get('op_id'),)).fetchone()
                    if not row or row['status']!='pending':raise ValueError('Le contrat doit être en attente de signature.')
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
                if not invite or invite['expires']<time.time() :raise ValueError('Lien expiré.')
                row=c.execute('SELECT * FROM ops WHERE id=?',(invite['op_id'],)).fetchone();op=json.loads(row['payload'])
                if method=='GET' and path.endswith('/data'):
                    return 200,{'frozen':op['frozen'],'record':op['record'],'signed':bool(op.get('signature')),'pdf':op.get('pdf','')}
                if method=='POST' and path.endswith('/pdf'):
                    if invite['used']:return 200,{'pdf':op['pdf']}
                    from gestionpro_android.contract_document import document_pdf
                    pdf,content=document_pdf(op['frozen'])
                    return 200,{'pdf':base64.b64encode(pdf).decode()}
                if method=='POST' and path.endswith('/save') and (row['status']!='pending' or op.get('signature') or invite['used']):raise ValueError('Ce contrat est déjà signé.')
                if method=='POST' and path.endswith('/save'):
                    n=int(e.get('CONTENT_LENGTH') or 0)
                    if n<1 or n>3_000_000:raise ValueError('Taille invalide.')
                    p=json.loads(e['wsgi.input'].read(n))
                    if p.get('accepted') is not True:raise ValueError('Confirmez l’acceptation du recto et du verso avant de signer.')
                    op['signature']=p.get('signature','')
                    from gestionpro_android.contract_document import document_pdf
                    pdf,content=document_pdf(op['frozen'],op['signature']);op['pdf']=base64.b64encode(pdf).decode();op['document_html']=content
                    if not op['signature'] or not op['pdf']:raise ValueError('Signature et PDF obligatoires.')
                    self.validate(op);c.execute('UPDATE ops SET payload=? WHERE id=?',(json.dumps(op,ensure_ascii=False),op['id']))
                    c.execute('UPDATE invites SET used=1 WHERE token=?',(token,));return 200,{'ok':True,'pdf':op['pdf']}
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
