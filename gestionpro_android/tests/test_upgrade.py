"""Validation des périodes comptables et du pont réservations publiques."""
import io,json,os,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from gestionpro_android.financial_rules import summary
from gestionpro_android.web_bookings import bookings,update_statuses
from gestionpro_android.pc.mobile_sync import apply_one,db
import test_sync

class UpgradeTests(unittest.TestCase):
    def test_production_boundary_and_payments(self):
        r={'numero':'T1','date_depart':'30/09/2026','date_retour':'03/10/2026','duree':3,'montant':900,'reglement':200,'reste':700}
        t=summary({'contracts':[r]},'2026-10-01','2026-10-31')
        self.assertEqual(t['revenue'],600);self.assertEqual(t['receivables'],600);self.assertEqual(t['cash'],0)
        previous=summary({'contracts':[r]},'2026-09-01','2026-09-30')
        self.assertEqual(previous['savings_future'],300);self.assertEqual(previous['savings_cash'],200)
    def test_transfers_are_not_revenue(self):
        data={'contracts':[],'transfers':[{'date':'03/10/2026','amount':100,'mode':'VERSEMENT BANQUE'}]}
        t=summary(data,'2026-10-01','2026-10-31');self.assertEqual(t['bank'],100);self.assertEqual(t['cash'],-100);self.assertEqual(t['revenue'],0);self.assertEqual(t['result'],0)
    def test_web_import_and_confirmation(self):
        x=test_sync.SyncTests();x.setUp()
        try:
            path=x.root/'public.sqlite'
            with sqlite3.connect(path) as c:
                c.execute('CREATE TABLE reservations(code_reservation,code_client,code_vehicule,date_depart,heure_depart,date_retour,heure_retour,avance,statut,cin,nom,prenom,telephone,marque_vehicule,immatriculation,duree,prix,montant,reste,observation)')
                c.execute('INSERT INTO reservations VALUES('+','.join('?' for _ in range(20))+')',('WEB1','CW1','V1','2026-10-10','09:00','2026-10-12','09:00',0,'EN ATTENTE','CIN-WEB','Client','Web','0600000000','Peugeot 208','TEST',2,300,600,600,''))
            with patch.dict(os.environ,{'GESTIONPRO_WEB_DB':str(path)}):
                r=bookings()[0]
                with db(x.path) as c:
                    result=apply_one(c,{'id':'web-import-WEB1','kind':'reservation_create','record':r,'trusted_web':True},x.root)
                    self.assertEqual(result['status'],'applied')
                    self.assertEqual(c.execute('SELECT nom FROM clients WHERE code="CW1"').fetchone()[0],'Client')
                    original=json.loads(c.execute('SELECT payload FROM module_records WHERE record_id="WEB1"').fetchone()[0]);updated={**original,'status':'CONFIRMÉ'}
                    result=apply_one(c,{'id':'op-confirm-web1','kind':'reservation_update','record':updated,'original':original},x.root)
                    self.assertEqual(result['status'],'applied')
                update_statuses([updated]);self.assertEqual(bookings()[0]['status'],'CONFIRMÉ')
                self.assertEqual(x.call('/mobile/api/sync',{'operations':[{'id':'op-forged-web','kind':'reservation_create','record':r,'trusted_web':True}]})[0],400)
        finally:x.tearDown()
if __name__=='__main__':unittest.main()
