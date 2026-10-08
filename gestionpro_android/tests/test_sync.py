import base64,io,json,sqlite3,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'pc')]
from relay import Relay
from mobile_sync import apply_one,db,snapshot,sync_once,CLIENT_FIELDS,VEHICLE_FIELDS,clean
PNG=base64.b64encode((ROOT/'mobile/icon-192.png').read_bytes()).decode()
PDF=base64.b64encode((Path(__file__).with_name('fixture.pdf')).read_bytes()).decode()
class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.relay=Relay(self.root/'relay.sqlite','mobile-test','pc-test')
        self.path=self.root/'gestionpro_hbz.db'
        with sqlite3.connect(self.path) as c:
            c.executescript('''CREATE TABLE clients(code TEXT PRIMARY KEY,cin TEXT,nom TEXT,prenom TEXT,telephone TEXT,ville TEXT,adresse TEXT,permis TEXT,date_naissance TEXT,date_permis TEXT,categorie TEXT,validite_permis TEXT);
            CREATE TABLE vehicles(code TEXT PRIMARY KEY,modele TEXT,immatriculation TEXT UNIQUE,chassis TEXT,compteur INTEGER,prix REAL,service INTEGER,prochaine_vidange INTEGER DEFAULT 0,vidange_restant INTEGER DEFAULT 0);
            CREATE TABLE contracts(numero TEXT PRIMARY KEY,client_code TEXT,second_code TEXT,vehicle_code TEXT,date_depart TEXT,heure_depart TEXT,date_retour TEXT,heure_retour TEXT,duree INTEGER,prix REAL,montant REAL,reglement REAL,reste REAL,km_depart INTEGER,km_retour INTEGER,created_at TEXT,return_status TEXT DEFAULT '',actual_return_date TEXT DEFAULT '',actual_return_time TEXT DEFAULT '');
            CREATE TABLE module_records(module TEXT,record_id TEXT,payload TEXT,created_at TEXT,PRIMARY KEY(module,record_id));
            CREATE TABLE app_settings(setting_key TEXT,setting_value TEXT);
            CREATE TABLE audit_log(action TEXT,module TEXT,reference TEXT,details TEXT,created_at TEXT);''')
            c.execute('INSERT INTO vehicles(code,modele,immatriculation,chassis,compteur,prix,service) VALUES(?,?,?,?,?,?,?)',('V1','Peugeot 208','TEST-PLATE','TEST-CHASSIS',10000,300,1))
            c.execute('INSERT INTO vehicles(code,modele,immatriculation,chassis,compteur,prix,service) VALUES(?,?,?,?,?,?,?)',('V2','Hors service','OFF','OFF',0,0,0))
        (self.root/'mobile_sync_config.json').write_text('{}')
    def tearDown(self):self.temp.cleanup()
    def call(self,path,p,token='mobile-test'):
        raw=json.dumps(p).encode();capture={}
        result=self.relay({'PATH_INFO':path,'REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(raw)),'HTTP_AUTHORIZATION':'Bearer '+token,'wsgi.input':io.BytesIO(raw)},lambda status,headers:capture.update(status=int(status.split()[0])))
        return capture['status'],json.loads(b''.join(result))
    def send(self,p):
        status,result=self.call('/mobile/api/pc-exchange',p,'pc-test');self.assertEqual(status,200,result);return result
    def sync(self):return sync_once(self.root,self.send)
    def customer(self):
        r=clean({'code':'MCL-001','cin':'TEST-CIN','nom':'Client test','prenom':'Fictif','telephone':'0600000000'},CLIENT_FIELDS)
        return {'id':'op-client-001','kind':'client_create','record':r}
    def contract(self,signed=True):
        cl=self.customer()['record']
        with db(self.path) as c:v=clean(dict(c.execute('SELECT * FROM vehicles WHERE code="V1"').fetchone()),VEHICLE_FIELDS)
        r={'numero':'MCT-001','client_code':cl['code'],'vehicle_code':'V1','date_depart':'02/10/2026','heure_depart':'09:00','date_retour':'05/10/2026','heure_retour':'09:00','duree':3,'prix':300,'montant':900,'reglement':200,'reste':700,'km_depart':10000}
        return {'id':'op-contract-001','kind':'contract_create','record':r,'frozen':{'record':dict(r),'client':cl,'vehicle':v,'current_km':10000,'settings':{'general_conditions':'Conditions de test'},'created_at':'2026-10-02T09:00:00Z'},'signature':'data:image/png;base64,'+PNG if signed else '', 'pdf':PDF if signed else ''}
    def test_client_pdf_upload_retry_and_folder(self):
        op={'id':'op-document-001','kind':'document_upload','record':{'reference':'PDF-001','client_code':'MCL-001','filename':'identite.pdf'},'pdf':PDF}
        status,result=self.call('/mobile/api/sync',{'operations':[self.customer(),op]})
        self.assertEqual(status,200,result)
        self.sync();self.sync()
        with db(self.path) as c:
            rows=c.execute('SELECT * FROM client_documents').fetchall()
            self.assertEqual(len(rows),1)
            self.assertEqual(rows[0]['client_code'],'MCL-001')
            self.assertEqual(rows[0]['document_type'],'AUTRE')
            path=Path(rows[0]['file_path'])
            self.assertEqual(path.parent,self.root/'assets'/'client_documents'/'MCL-001')
            self.assertEqual(path.read_bytes(),base64.b64decode(PDF))
        status,result=self.call('/mobile/api/sync',{'operations':[op]})
        self.assertEqual(status,200)
        self.assertEqual(next(o for o in result['operations'] if o['id']==op['id'])['status'],'applied')

    def test_offline_creation_pc_off_retry_no_duplicate(self):
        ops=[self.customer(),self.contract()]
        status,result=self.call('/mobile/api/sync',{'operations':ops});self.assertEqual(status,200)
        self.assertEqual([o['status'] for o in result['operations']],['pending','pending'])
        self.sync();self.sync()
        with db(self.path) as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM clients').fetchone()[0],1)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],1)
        status,result=self.call('/mobile/api/sync',{'operations':ops})
        self.assertEqual(status,200);self.assertTrue(all(o['status']=='applied' for o in result['operations']))
        self.assertEqual(len(result['vehicles']),1)
        archives=list((self.root/'contrats_signes').glob('*/latest.json'));self.assertEqual(len(archives),1)
        self.assertTrue(list((self.root/'contrats_signes').glob('*/*.pdf')))
    def test_contract_counter_correction_preserves_contract(self):
        self.call('/mobile/api/sync',{'operations':[self.customer(),self.contract(False)]});self.sync()
        with db(self.path) as c:
            before=dict(c.execute('SELECT * FROM contracts').fetchone())
            v=clean(dict(c.execute('SELECT * FROM vehicles WHERE code="V1"').fetchone()),VEHICLE_FIELDS)
        op={'id':'op-correction','kind':'vehicle_update','record':{**v,'compteur':9500,'hbz_counter_correction':True},'original':v}
        self.call('/mobile/api/sync',{'operations':[op]});self.sync()
        with db(self.path) as c:
            self.assertEqual(c.execute('SELECT compteur FROM vehicles WHERE code="V1"').fetchone()[0],9500)
            self.assertEqual(dict(c.execute('SELECT * FROM contracts').fetchone()),before)

    def test_conflict_counter_does_not_overwrite_pc(self):
        with db(self.path) as c:v=clean(dict(c.execute('SELECT * FROM vehicles WHERE code="V1"').fetchone()),VEHICLE_FIELDS)
        op={'id':'op-counter-001','kind':'vehicle_update','record':{**v,'compteur':11000},'original':v}
        self.call('/mobile/api/sync',{'operations':[op]})
        with sqlite3.connect(self.path) as c:c.execute('UPDATE vehicles SET compteur=12000 WHERE code="V1"')
        self.sync()
        with db(self.path) as c:self.assertEqual(c.execute('SELECT compteur FROM vehicles WHERE code="V1"').fetchone()[0],12000)
        status,result=self.call('/mobile/api/sync',{'operations':[]});self.assertEqual(result['operations'][0]['status'],'rejected')
    def test_contract_collision_and_malformed_calculation_rollback(self):
        self.call('/mobile/api/sync',{'operations':[self.customer(),self.contract()]});self.sync()
        bad=self.contract();bad['id']='op-contract-002';bad['record']['numero']='MCT-002';bad['frozen']['record']=dict(bad['record'])
        self.call('/mobile/api/sync',{'operations':[bad]});self.sync()
        with db(self.path) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],1)
        status,result=self.call('/mobile/api/sync',{'operations':[]});self.assertEqual(result['operations'][-1]['status'],'rejected')
    def test_reservation_and_maintenance_add_update(self):
        self.call('/mobile/api/sync',{'operations':[self.customer()]});self.sync()
        r={'reference':'MRES-1','vehicle':'V1 | Peugeot 208','client':'MCL-001','start_date':'10/10/2026','start_time':'09:00','end_date':'12/10/2026','end_time':'09:00','daily_price':'300','total':'600','deposit':'100','balance':'500','status':'CONFIRMÉ'}
        m={'reference':'MENT-1','vehicle':'V1 | Peugeot 208','date':'01/10/2026','service':'Vidange','mileage':'9500','next_mileage':'20000','amount':'450','product_km':'10500','next_date':'01/10/2027'}
        self.call('/mobile/api/sync',{'operations':[{'id':'op-reservation-001','kind':'reservation_create','record':r},{'id':'op-maintenance-001','kind':'maintenance_create','record':m}]});self.sync()
        updated={**m,'next_mileage':'22000','amount':'500'}
        self.call('/mobile/api/sync',{'operations':[{'id':'op-maintenance-002','kind':'maintenance_update','record':updated,'original':m}]});self.sync()
        with db(self.path) as c:
            v=c.execute('SELECT prochaine_vidange,vidange_restant FROM vehicles WHERE code="V1"').fetchone();self.assertEqual(tuple(v),(22000,12000))
            saved=json.loads(c.execute('SELECT payload FROM module_records WHERE module="maintenance"').fetchone()[0]);self.assertEqual(saved['amount'],'500')
    def test_signature_remote_one_time_and_unsigned_wait(self):
        self.call('/mobile/api/sync',{'operations':[self.customer(),self.contract(False)]});self.sync()
        with db(self.path) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],1)
        self.sync() # Retry before signature must not duplicate or reject the draft.
        status,view=self.call('/mobile/api/sync',{'operations':[]})
        self.assertTrue(view['operations'][-1]['pc_received'])
        status,j=self.call('/mobile/api/invite',{'op_id':'op-contract-001'});self.assertEqual(status,200)
        raw=json.dumps({'signature':'data:image/png;base64,'+PNG,'pdf':PDF,'accepted':True}).encode();env={'PATH_INFO':'/mobile/signature/'+j['token']+'/save','REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)}
        result=self.relay.route(env);self.assertEqual(result[0],200)
        with self.assertRaises(ValueError):self.relay.route({**env,'wsgi.input':io.BytesIO(raw)})
        self.sync()
        with db(self.path) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],1)
    def test_auth_role_and_mutated_retry(self):
        self.assertEqual(self.call('/mobile/api/pc-exchange',{},'mobile-test')[0],401)
        self.assertEqual(self.call('/mobile/api/sync',{'operations':[]},'pc-test')[0],401)
        op=self.customer();self.assertEqual(self.call('/mobile/api/sync',{'operations':[op]})[0],200)
        op['record']['nom']='Autre';self.assertEqual(self.call('/mobile/api/sync',{'operations':[op]})[0],400)
    def test_duplicate_cin_and_changed_signed_record_rejected(self):
        self.call('/mobile/api/sync',{'operations':[self.customer()]});self.sync()
        duplicate=self.customer();duplicate['id']='op-client-002';duplicate['record']['code']='MCL-002'
        tampered=self.contract();tampered['record']['reglement']=0
        self.call('/mobile/api/sync',{'operations':[duplicate,tampered]});self.sync()
        with db(self.path) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM clients').fetchone()[0],1);self.assertEqual(c.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],0)

    def test_archive_from_pc_and_signed_whatsapp_link(self):
        self.call('/mobile/api/sync',{'operations':[self.customer(),self.contract()]});self.sync()
        status,req=self.call('/mobile/api/contract-document',{'numero':'MCT-001'})
        self.assertEqual(status,200);self.assertTrue(req['pending'])
        self.sync()
        status,doc=self.call('/mobile/api/contract-document',{'numero':'MCT-001'})
        self.assertEqual(status,200);self.assertTrue(base64.b64decode(doc['document']['pdf']).startswith(b'%PDF-'))
        status,link=self.call('/mobile/api/share-contract',{'numero':'MCT-001'})
        self.assertEqual(status,200)
        status,data=self.relay.route({'PATH_INFO':'/mobile/signature/'+link['token']+'/data','REQUEST_METHOD':'GET'})
        self.assertTrue(data['signed']);self.assertTrue(data['pdf'])
        raw=json.dumps({'signature':'data:image/png;base64,'+PNG}).encode()
        with self.assertRaises(ValueError):self.relay.route({'PATH_INFO':'/mobile/signature/'+link['token']+'/save','REQUEST_METHOD':'POST','CONTENT_LENGTH':str(len(raw)),'wsgi.input':io.BytesIO(raw)})

    def test_confirm_local_signature_pdf_both_pages_and_retry(self):
        from PIL import Image,ImageDraw
        from pypdf import PdfReader
        from remote_contract_common import normalize_png
        canvas=Image.new('RGBA',(900,300),(0,0,0,0));pen=ImageDraw.Draw(canvas)
        pen.line([(100,240),(450,40),(320,240),(600,90),(750,180)],fill='#133b67',width=7)
        png=io.BytesIO();canvas.save(png,'PNG');uri='data:image/png;base64,'+base64.b64encode(png.getvalue()).decode()
        unsigned=self.contract(False)
        self.call('/mobile/api/sync',{'operations':[self.customer(),unsigned]});self.sync()
        self.assertEqual(self.call('/mobile/api/sign-contract',{'op_id':unsigned['id'],'signature':uri,'accepted':False})[0],400)
        status,result=self.call('/mobile/api/sign-contract',{'op_id':unsigned['id'],'signature':uri,'accepted':True})
        self.assertEqual(status,200);self.assertEqual(result['document']['signature'],uri)
        pdf=base64.b64decode(result['document']['pdf']);reader=PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages),2)
        expected=Image.open(io.BytesIO(normalize_png(png.getvalue()))).size
        for page in reader.pages:self.assertTrue(any(image.image.size==expected for image in page.images),'Signature dessinée absente de la page')
        self.assertEqual(self.call('/mobile/api/sync',{'operations':[unsigned]})[0],200)
        self.sync();self.sync()
        with db(self.path) as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],1)
        Path('/workspace/scratch/66ebe2e2e65c/confirmation-signature-test.pdf').write_bytes(pdf)

if __name__=='__main__':unittest.main()
