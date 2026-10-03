"""Pont local entre les réservations publiques et le relais mobile/PC."""
import os,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def database():
    folder=Path(os.environ.get('GESTIONPRO_DATA_DIR',ROOT))
    return Path(os.environ.get('GESTIONPRO_WEB_DB',folder/'gestion.db'))

def bookings():
    path=database()
    if not path.is_file():return []
    c=sqlite3.connect(path,timeout=15);c.row_factory=sqlite3.Row
    try:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='reservations'").fetchone():return []
        rows=[{'reference':r['code_reservation'],'client':r['code_client'],'vehicle':r['code_vehicule'],'start_date':r['date_depart'],'start_time':r['heure_depart'],'end_date':r['date_retour'],'end_time':r['heure_retour'],'deposit':r['avance'],'status':r['statut'],'cin':r['cin'],'last_name':r['nom'],'first_name':r['prenom'],'phone':r['telephone'],'vehicle_model':r['marque_vehicule'],'plate':r['immatriculation'],'duration':r['duree'],'daily_price':r['prix'],'total':r['montant'],'balance':r['reste'],'notes':r['observation'],'source':'SITE WEB'} for r in c.execute('SELECT * FROM reservations')]
        for r in rows:
            r['status']=canonical(r['status'])
        return rows
    finally:c.close()

def canonical(value):
    s=str(value or '').upper().replace('É','E')
    return {'CONFIRMEE':'CONFIRMÉ','CONFIRME':'CONFIRMÉ','ANNULEE':'ANNULÉ','ANNULE':'ANNULÉ','TERMINEE':'TERMINÉ','TERMINE':'TERMINÉ','PAYE':'PAYÉ'}.get(s,value)

def update_statuses(rows,previous=None):
    path=database()
    if not path.is_file():return
    c=sqlite3.connect(path,timeout=15)
    try:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='reservations'").fetchone():return
        with c:
            for r in rows:
                old={x['reference']:canonical(x.get('status')) for x in previous} if previous is not None else None
                if old is not None and (r['reference'] not in old or canonical(r.get('status'))==old[r['reference']]):continue
                if r.get('source')=='SITE WEB' and r.get('status') in ('EN ATTENTE','CONFIRMÉ','PAYÉ','ANNULÉ','TERMINÉ'):
                    c.execute('UPDATE reservations SET statut=? WHERE code_reservation=?',({'CONFIRMÉ':'CONFIRMEE','ANNULÉ':'ANNULEE','TERMINÉ':'TERMINEE'}.get(r['status'],r['status']),r['reference']))
    finally:c.close()

def sync_fleet(snapshot):
    path=database()
    if not path.is_file():return
    c=sqlite3.connect(path,timeout=15)
    try:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE name='vehicules'").fetchone():return
        with c:
            c.execute("UPDATE vehicules SET service='HORS SERVICE'")
            for v in snapshot.get('vehicles',[]):
                if v.get('service')!=1:continue
                c.execute("INSERT INTO vehicules(code_vehicule,marque,immatriculation,num_chassis,compteur,service,prix_jour) VALUES(?,?,?,?,?,'EN SERVICE',?) ON CONFLICT(code_vehicule) DO UPDATE SET marque=excluded.marque,immatriculation=excluded.immatriculation,num_chassis=excluded.num_chassis,compteur=excluded.compteur,service=excluded.service,prix_jour=excluded.prix_jour",(v['code'],v.get('modele',''),v.get('immatriculation',''),v.get('chassis',''),v.get('compteur',0),v.get('prix',0)))
            if c.execute("SELECT 1 FROM sqlite_master WHERE name='locations'").fetchone():
                c.execute('DELETE FROM locations')
                active={v['code'] for v in snapshot.get('vehicles',[]) if v.get('service')==1}
                for r in snapshot.get('contracts',[]):
                    status=str(r.get('return_status','')).upper()
                    if r.get('vehicle_code') not in active or any(x in status for x in ('RETOUR CONFIRM','ANNUL','ANTICIP')):continue
                    c.execute('INSERT INTO locations(code_location,code_vehicule,date_depart,date_retour) VALUES(?,?,?,?)',(r['numero'],r['vehicle_code'],r['date_depart'],r.get('actual_return_date') or r['date_retour']))
    finally:c.close()
