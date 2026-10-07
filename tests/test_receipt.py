import time, unittest
from io import BytesIO
from unittest.mock import patch
from pypdf import PdfReader
import test_memory
web=test_memory.web

class ReceiptTests(unittest.TestCase):
    def setUp(self):
        with web.db() as c:
            self.rid=c.execute("INSERT INTO reservations(code_reservation,code_client,code_vehicule,nom,prenom,telephone,marque_vehicule,date_depart,heure_depart,date_retour,heure_retour,duree,prix,montant,avance,reste,statut) VALUES('RECU-TEST','CLIENT','VEHICLE','El Idrissi','Ahmed','0612345678','DACIA SANDERO STEPWAY','2026-10-07','10:00','2026-10-11','10:00',4,350,1400,0,1400,'EN ATTENTE')").lastrowid
        self.client=web.app.test_client()
    def tearDown(self):
        with web.db() as c:c.execute('DELETE FROM reservations WHERE id=?',(self.rid,))
    def test_pdf_status_and_access(self):
        token=web.receipt_token('RECU-TEST')
        response=self.client.get('/reservation/recu/'+token+'.pdf')
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response.headers['Cache-Control'])
        reader=PdfReader(BytesIO(response.data))
        self.assertEqual(len(reader.pages),1)
        text=reader.pages[0].extract_text()
        for value in ['RECU-TEST','EN ATTENTE','1 400.00 MAD','Ahmed']:self.assertIn(value,text)
        self.assertEqual(self.client.get('/reservation/recu/forged.pdf').status_code,404)
        with patch('itsdangerous.timed.time.time',return_value=time.time()+8*86400):
            self.assertEqual(self.client.get('/reservation/recu/'+token+'.pdf').status_code,410)
        with web.db() as c:c.execute("UPDATE reservations SET statut='ANNULEE' WHERE id=?",(self.rid,))
        self.assertIn('ANNULEE',PdfReader(BytesIO(self.client.get('/reservation/recu/'+token+'.pdf').data)).pages[0].extract_text())
    def test_admin_download_and_share(self):
        path=f'/admin/reservation/{self.rid}/recu.pdf'
        self.assertEqual(self.client.get(path).status_code,302)
        with self.client.session_transaction() as s:s['web_user']='test-admin';s['_last_active']=time.time()
        self.assertEqual(self.client.get(path).status_code,200)
        response=self.client.get(f'/admin/reservation/{self.rid}/envoyer-recu')
        self.assertEqual(response.status_code,200)
        self.assertIn('https://wa.me/212612345678',response.get_data(as_text=True))
