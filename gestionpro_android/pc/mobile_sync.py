"""Synchronisation PC en arrière-plan; une connexion SQLite propre par passage."""
import base64, hashlib, html, json, math, os, sqlite3, threading, time, urllib.request
from datetime import datetime, timedelta
from pathlib import Path
ROOT=Path(__file__).resolve().parent
CLIENT_FIELDS=('code','cin','nom','prenom','telephone','ville','adresse','permis','date_naissance','date_permis','categorie','validite_permis')
VEHICLE_FIELDS=('code','modele','immatriculation','chassis','compteur','prix','service')
def date(value,hour='00:00'):
    for fmt in ('%Y-%m-%d','%d/%m/%Y','%d-%m-%Y'):
        try:return datetime.strptime(str(value)[:10],fmt).replace(hour=int(hour[:2]),minute=int(hour[3:5]))
        except (ValueError,TypeError):pass
    raise ValueError('Date ou heure invalide.')
def money(v):
    n=float(str(v or 0).replace(',','.'))
    if not math.isfinite(n) or n<0:raise ValueError('Montant invalide.')
    return round(n,2)
def clean(r,fields):return {k:r.get(k) if r.get(k) is not None else '' for k in fields}
def db(path):
    c=sqlite3.connect(path,timeout=20);c.row_factory=sqlite3.Row
    c.execute('CREATE TABLE IF NOT EXISTS gp_mobile_receipts(id TEXT PRIMARY KEY,status TEXT,message TEXT,payload TEXT)')
    return c
def module(c,name):
    return [json.loads(r[0]) for r in c.execute('SELECT payload FROM module_records WHERE module=?',(name,))]
def snapshot(c):
    return {'clients':[clean(dict(r),CLIENT_FIELDS) for r in c.execute('SELECT * FROM clients')],
      'vehicles':[clean(dict(r),VEHICLE_FIELDS) for r in c.execute('SELECT * FROM vehicles WHERE service=1')],
      'contracts':[dict(r) for r in c.execute('SELECT * FROM contracts')],
      **{name:module(c,name) for name in ('reservations','maintenance','expenses','checks','finance')},
      'settings':dict(c.execute("SELECT setting_key,setting_value FROM app_settings WHERE setting_key IN ('company_name','company_address','company_phone','company_ice','general_conditions')"))}
def available(c,code,start,end,ignore=''):
    vehicle=c.execute('SELECT * FROM vehicles WHERE code=?',(code,)).fetchone()
    if not vehicle or vehicle['service']!=1:raise ValueError('Véhicule absent ou hors service sur le PC.')
    for raw in c.execute('SELECT * FROM contracts WHERE vehicle_code=?',(code,)):
        r=dict(raw);status=str(r.get('return_status','')).upper()
        if any(x in status for x in ('RETOUR CONFIRM','ANTICIP','ANNUL')):continue
        a=date(r['date_depart'],r.get('heure_depart') or '00:00')
        b=datetime.max if 'RETARD CONFIRM' in status else date(r.get('actual_return_date') or r['date_retour'],r.get('actual_return_time') or r.get('heure_retour') or '23:59')
        if start<b and end>a:raise ValueError('Véhicule occupé : contrat '+r['numero'])
    for r in module(c,'reservations'):
        if r.get('reference')==ignore or str(r.get('vehicle','')).split('|')[0].strip()!=code:continue
        if any(x in str(r.get('status','')).upper() for x in ('ANNUL','TERMIN','CONVERT','SUPPR')):continue
        a=date(r.get('start_date'),r.get('start_time') or '00:00');b=date(r.get('end_date'),r.get('end_time') or '23:59')
        if start<b and end>a:raise ValueError('Véhicule réservé : '+str(r.get('reference','')))
    return dict(vehicle)
def archive(c,op,root):
    """Archive immutable compatible avec les historiques signed_contracts du PC."""
    r=op['record'];number=r['numero'];f=op['frozen'];folder=root/'contrats_signes'/hashlib.sha256(number.encode()).hexdigest()[:24]
    folder.mkdir(parents=True,exist_ok=True);prefix='mobile_'+op['id']
    png=base64.b64decode(op['signature'].split(',',1)[1],validate=True)
    if not png.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Signature invalide.')
    pdf=base64.b64decode(op.get('pdf',''),validate=True)
    if not pdf.startswith(b'%PDF-'):raise ValueError('Copie PDF signée absente.')
    document='<html lang="fr"><meta charset="utf-8"><title>Contrat '+html.escape(number)+'</title><style>body{font:16px sans-serif;margin:40px}pre{white-space:pre-wrap}img{max-width:400px}</style><h1>Contrat de location '+html.escape(number)+'</h1><pre>'+html.escape(json.dumps(f,ensure_ascii=False,indent=2))+'</pre><img alt="Signature du client" src="'+op['signature']+'"></html>'
    (folder/(prefix+'.html')).write_text(document,encoding='utf-8');(folder/(prefix+'.png')).write_bytes(png);(folder/(prefix+'.pdf')).write_bytes(pdf)
    record={'contract_no':number,'client_codes':[r['client_code']],'signed_at':datetime.now().isoformat(timespec='seconds'),'html':prefix+'.html','signature':prefix+'.png','pdf':prefix+'.pdf','sha256':hashlib.sha256(png).hexdigest(),'source':'Android autonome'}
    temp=folder/(prefix+'.tmp');temp.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8');os.replace(temp,folder/'latest.json')
def resync_maintenance(c,code):
    columns={r[1] for r in c.execute('PRAGMA table_info(vehicles)')}
    v=c.execute('SELECT compteur FROM vehicles WHERE code=?',(code,)).fetchone()
    jobs=[r for r in module(c,'maintenance') if str(r.get('vehicle','')).split('|')[0].strip()==code]
    jobs.sort(key=lambda r:(date(r['date']),int(r.get('mileage') or 0)),reverse=True)
    km=int(v[0] or 0);latest=jobs[0] if jobs else {};by={}
    for item in jobs:by.setdefault(str(item.get('service','')).casefold().replace('î','i'),item)
    values={'entretien_date':latest.get('date',''),'entretien_type':latest.get('service',''),
      'entretien_km_intervention':int(latest.get('mileage') or 0),'entretien_km_produit':int(latest.get('product_km') or 0),
      'entretien_prochaine':int(latest.get('next_mileage') or 0),'entretien_km_restant':max(0,int(latest.get('next_mileage') or 0)-km)}
    for name in ('vidange','chaine','adblue'):
        target=int(by.get(name,{}).get('next_mileage') or 0)
        values['prochaine_'+name]=target;values[name+'_restant']=max(0,target-km) if target else 0
    keys=[k for k in values if k in columns]
    if keys:c.execute('UPDATE vehicles SET '+','.join(k+'=?' for k in keys)+' WHERE code=?',[values[k] for k in keys]+[code])

def apply_one(c,op,root):
    old=c.execute('SELECT status,message FROM gp_mobile_receipts WHERE id=?',(op['id'],)).fetchone()
    if old:return {'id':op['id'],**dict(old)}
    if op['kind']=='contract_create' and not op.get('signature'):return None # Wait for remote or local signature.
    status='applied';message='Enregistré sur le PC.'
    c.execute('SAVEPOINT mobile_op')
    try:
        r=op['record'];kind=op['kind'];now=datetime.now().isoformat(timespec='seconds')
        if kind.startswith('client_'):
            r=clean(r,CLIENT_FIELDS)
            if not r['code'] or not str(r['nom']).strip() or not str(r['cin']).strip():raise ValueError('Nom et CIN obligatoires.')
            duplicate=c.execute('SELECT code FROM clients WHERE UPPER(TRIM(cin))=UPPER(TRIM(?)) AND code<>?',(r['cin'],r['code'])).fetchone()
            if duplicate:raise ValueError('CIN déjà enregistré sous le code '+duplicate['code'])
            old=c.execute('SELECT * FROM clients WHERE code=?',(r['code'],)).fetchone()
            if kind=='client_create':
                if old:raise ValueError('Code client déjà utilisé.')
                c.execute('INSERT INTO clients('+','.join(CLIENT_FIELDS)+') VALUES('+','.join('?' for _ in CLIENT_FIELDS)+')',list(r.values()))
            else:
                if not old or clean(dict(old),CLIENT_FIELDS)!=op['original']:raise ValueError('Fiche client modifiée sur le PC. Réactualisez avant de recommencer.')
                c.execute('UPDATE clients SET '+','.join(k+'=?' for k in CLIENT_FIELDS[1:])+' WHERE code=?',[r[k] for k in CLIENT_FIELDS[1:]]+[r['code']])
        elif kind=='vehicle_update':
            old=c.execute('SELECT * FROM vehicles WHERE code=?',(r['code'],)).fetchone()
            if not old or clean(dict(old),VEHICLE_FIELDS)!=op['original']:raise ValueError('Le véhicule a changé sur le PC. Réactualisez son compteur.')
            km=int(r['compteur'])
            if km<int(old['compteur'] or 0):raise ValueError('Le compteur ne peut pas diminuer.')
            c.execute('UPDATE vehicles SET compteur=? WHERE code=?',(km,r['code']))
            resync_maintenance(c,r['code'])
        elif kind=='contract_create':
            if c.execute('SELECT 1 FROM contracts WHERE numero=?',(r['numero'],)).fetchone():raise ValueError('Numéro de contrat déjà utilisé.')
            client=c.execute('SELECT * FROM clients WHERE code=?',(r['client_code'],)).fetchone()
            if not client:raise ValueError('Client absent sur le PC. Synchronisez sa fiche.')
            frozen=op['frozen']
            if frozen.get('record')!=r:raise ValueError('Le contenu signé ne correspond pas au contrat envoyé.')
            if clean(dict(client),CLIENT_FIELDS)!=clean(frozen['client'],CLIENT_FIELDS):raise ValueError('Identité du client modifiée : refaire le contrat et sa signature.')
            start=date(r['date_depart'],r['heure_depart']);end=date(r['date_retour'],r['heure_retour'])
            if end<=start:raise ValueError('Retour antérieur au départ.')
            vehicle=available(c,r['vehicle_code'],start,end)
            if any(str(vehicle.get(k,''))!=str(frozen['vehicle'].get(k,'')) for k in ('code','modele','immatriculation','chassis')):raise ValueError('Identité du véhicule modifiée : refaire le contrat et sa signature.')
            days=max(1,(end.date()-start.date()).days);price=money(r['prix']);paid=money(r['reglement']);total=round(days*price,2)
            if int(r['duree'])!=days or abs(money(r['montant'])-total)>.005 or paid>total or abs(money(r['reste'])-(total-paid))>.005:raise ValueError('Calcul du contrat invalide.')
            if int(r['km_depart'])<int(vehicle.get('compteur') or 0):raise ValueError('Kilométrage de départ inférieur au compteur PC.')
            cols=('numero','client_code','second_code','vehicle_code','date_depart','heure_depart','date_retour','heure_retour','duree','prix','montant','reglement','reste','km_depart','km_retour','created_at')
            values={**r,'second_code':'','km_retour':0,'created_at':now}
            c.execute('INSERT INTO contracts('+','.join(cols)+') VALUES('+','.join('?' for _ in cols)+')',[values[k] for k in cols])
            archive(c,op,root)
        elif kind.startswith(('reservation_','maintenance_')):
            name='reservations' if kind.startswith('reservation') else 'maintenance';reference=r['reference']
            prior=c.execute('SELECT payload FROM module_records WHERE module=? AND record_id=?',(name,reference)).fetchone()
            if kind.endswith('_update'):
                if not prior or json.loads(prior[0])!=op['original']:raise ValueError('Cette fiche a changé sur le PC. Réactualisez-la.')
            elif prior:raise ValueError('Référence déjà utilisée.')
            code=str(r['vehicle']).split('|')[0].strip()
            v=c.execute('SELECT * FROM vehicles WHERE code=? AND service=1',(code,)).fetchone()
            if not v:raise ValueError('Véhicule hors service ou absent.')
            if name=='reservations':
                if not c.execute('SELECT 1 FROM clients WHERE code=?',(str(r['client']).split('|')[0].strip(),)).fetchone():raise ValueError('Client absent.')
                a=date(r['start_date'],r['start_time']);b=date(r['end_date'],r['end_time'])
                if b<=a:raise ValueError('Dates de réservation invalides.')
                if r['status'] not in ('EN ATTENTE','CONFIRMÉ','PAYÉ','ANNULÉ','TERMINÉ'):raise ValueError('Statut invalide.')
                if r['status'] not in ('ANNULÉ','TERMINÉ'):available(c,code,a,b,reference)
                total=round(max(1,(b.date()-a.date()).days)*money(r['daily_price']),2)
                if abs(money(r['total'])-total)>.005 or money(r['deposit'])>total or abs(money(r['balance'])-(total-money(r['deposit'])))>.005:raise ValueError('Calcul réservation invalide.')
            else:
                date(r['date']);money(r['amount'])
                km=int(r['mileage']);next_km=int(r.get('next_mileage') or 0)
                if km<0 or next_km and next_km<km:raise ValueError('Échéance kilométrique invalide.')
                if r.get('next_date'):date(r['next_date'])
            c.execute('INSERT INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,?) ON CONFLICT(module,record_id) DO UPDATE SET payload=excluded.payload',(name,reference,json.dumps(r,ensure_ascii=False),now))
            if name=='maintenance':resync_maintenance(c,code)
        else:raise ValueError('Opération non autorisée.')
        c.execute('INSERT INTO audit_log(action,module,reference,details,created_at) VALUES(?,?,?,?,?)',('SYNCHRONISATION ANDROID',kind,r.get('code') or r.get('numero') or r.get('reference'),op['id'],now))
    except (ValueError,KeyError,TypeError,sqlite3.IntegrityError) as x:
        c.execute('ROLLBACK TO mobile_op');status='rejected';message=str(x)
    c.execute('RELEASE mobile_op')
    c.execute('INSERT INTO gp_mobile_receipts VALUES(?,?,?,?)',(op['id'],status,message,json.dumps(op,ensure_ascii=False)))
    return {'id':op['id'],'status':status,'message':message}
def exchange(base,token,payload):
    if not base.startswith('https://') and not base.startswith(('http://localhost:','http://127.0.0.1:')):raise ValueError('Adresse HTTPS obligatoire.')
    req=urllib.request.Request(base.rstrip('/')+'/api/pc-exchange',data=json.dumps(payload,ensure_ascii=False).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'},method='POST')
    with urllib.request.urlopen(req,timeout=30) as response:return json.load(response)
def sync_once(root=ROOT,transport=None):
    config=json.loads((root/'mobile_sync_config.json').read_text(encoding='utf-8'));send=transport or (lambda p:exchange(config['base_url'],config['pc_token'],p))
    with db(root/'gestionpro_hbz.db') as c:
        # Resend committed receipts even after a network interruption.
        receipts=[dict(r) for r in c.execute('SELECT id,status,message FROM gp_mobile_receipts')]
        pending=send({'snapshot':snapshot(c),'results':receipts})['pending']
        for op in sorted(pending,key=lambda o:0 if o['kind'].startswith('client_') else 1 if o['kind']=='vehicle_update' else 2):
            c.execute('BEGIN IMMEDIATE');apply_one(c,op,root);c.commit()
        receipts=[dict(r) for r in c.execute('SELECT id,status,message FROM gp_mobile_receipts')]
        send({'snapshot':snapshot(c),'results':receipts})
    return True
_started=False
def start(root=ROOT):
    global _started
    if _started:return
    _started=True
    def run():
        while True:
            try:
                if (root/'mobile_sync_config.json').exists():sync_once(root)
                status={'ok':True,'at':datetime.now().isoformat()}
            except Exception as x:status={'ok':False,'at':datetime.now().isoformat(),'error':str(x)}
            try:(root/'mobile_sync_status.json').write_text(json.dumps(status,ensure_ascii=False),encoding='utf-8')
            except OSError:pass
            time.sleep(60)
    threading.Thread(target=run,name='GestionProMobileSync',daemon=True).start()
if __name__=='__main__':sync_once()
