import time,unittest,uuid
import test_memory
web=test_memory.web
class CancelledDeleteTests(unittest.TestCase):
    def setUp(self):
        self.client=web.app.test_client()
        self.csrf='test-cancelled-delete'
        with self.client.session_transaction() as s:
            s['web_user']='test-admin';s['_last_active']=time.time();s['_csrf']=self.csrf
    def row(self,status):
        code='DELETE-'+uuid.uuid4().hex
        with web.db() as c:
            rid=c.execute("INSERT INTO reservations(code_reservation,code_client,code_vehicule,date_depart,heure_depart,date_retour,heure_retour,statut) VALUES(?,?,?,'2026-10-07','09:00','2026-10-08','09:00',?)",(code,'CLIENT','VEHICLE',status)).lastrowid
        self.addCleanup(self.clean,rid)
        return rid,code
    def clean(self,rid):
        with web.db() as c:c.execute('DELETE FROM reservations WHERE id=?',(rid,))
    def exists(self,rid):
        with web.db() as c:return c.execute('SELECT 1 FROM reservations WHERE id=?',(rid,)).fetchone() is not None
    def test_delete_and_audit_with_filters(self):
        for status in ['ANNULEE','Annulé',' ANNULÉE ']:
            rid,code=self.row(status)
            self.assertIn('/admin/reservation/'+str(rid)+'/delete',self.client.get('/admin').get_data(as_text=True))
            r=self.client.post(f'/admin/reservation/{rid}/delete',data={'_csrf':self.csrf,'statut':'ANNULEE','q':'TEST'})
            self.assertEqual(r.status_code,302);self.assertIn('q=TEST',r.location);self.assertFalse(self.exists(rid))
            with web.db() as c:self.assertIsNotNone(c.execute("SELECT 1 FROM web_audit WHERE action='RESERVATION_DELETE' AND details=?",(code,)).fetchone())
    def test_active_rejected_even_after_button_rendered(self):
        for status in ['EN ATTENTE','CONFIRMEE','TERMINEE']:
            rid,_=self.row(status)
            self.assertNotIn('/admin/reservation/'+str(rid)+'/delete',self.client.get('/admin').get_data(as_text=True))
            self.assertEqual(self.client.post(f'/admin/reservation/{rid}/delete',data={'_csrf':self.csrf}).status_code,409)
            self.assertTrue(self.exists(rid))
    def test_csrf_auth_and_repeat(self):
        rid,_=self.row('ANNULEE')
        self.assertEqual(self.client.post(f'/admin/reservation/{rid}/delete').status_code,400)
        self.assertTrue(self.exists(rid))
        outsider=web.app.test_client()
        with outsider.session_transaction() as s:s['_csrf']=self.csrf
        self.assertEqual(outsider.post(f'/admin/reservation/{rid}/delete',data={'_csrf':self.csrf}).status_code,302)
        self.assertTrue(self.exists(rid))
        self.assertEqual(self.client.post(f'/admin/reservation/{rid}/delete',data={'_csrf':self.csrf}).status_code,302)
        self.assertEqual(self.client.post(f'/admin/reservation/{rid}/delete',data={'_csrf':self.csrf}).status_code,404)
