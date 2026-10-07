import unittest,uuid
from datetime import date,timedelta
import test_memory
web=test_memory.web
class ReturnDayTests(unittest.TestCase):
    def setUp(self):
        self.code='DAY-'+uuid.uuid4().hex
        self.start=date.today()+timedelta(days=10)
        self.return_day=self.start+timedelta(days=4)
        with web.db() as c:
            c.execute("INSERT INTO vehicules(code_vehicule,marque,immatriculation,service,prix_jour) VALUES(?,?,?,'EN SERVICE',300)",(self.code,'TEST',self.code))
    def tearDown(self):
        with web.db() as c:
            c.execute('DELETE FROM reservations WHERE code_vehicule=?',(self.code,));c.execute('DELETE FROM locations WHERE code_vehicule=?',(self.code,));c.execute('DELETE FROM vehicules WHERE code_vehicule=?',(self.code,))
    def reservation(self):
        with web.db() as c:
            c.execute("INSERT INTO reservations(code_reservation,code_client,code_vehicule,date_depart,heure_depart,date_retour,heure_retour,statut) VALUES(?,?,?,?,'10:00',?,'23:00','CONFIRMEE')",('R-'+self.code,'CLIENT',self.code,self.start.isoformat(),self.return_day.isoformat()))
    def overlap(self,a,b):
        with web.db() as c:return web.reservation_overlap(c,self.code,a,b)
    def test_reservation_boundaries_and_overlap(self):
        self.reservation()
        self.assertFalse(self.overlap(self.return_day,self.return_day+timedelta(days=2)))
        self.assertFalse(self.overlap(self.start-timedelta(days=2),self.start))
        self.assertTrue(self.overlap(self.return_day-timedelta(days=1),self.return_day+timedelta(days=2)))
        self.assertTrue(self.overlap(self.start,self.start))
        self.assertFalse(self.overlap(self.return_day,self.return_day))
    def test_rental_return_day(self):
        with web.db() as c:c.execute('INSERT INTO locations(code_location,code_vehicule,date_depart,date_retour) VALUES(?,?,?,?)',('L-'+self.code,self.code,self.start.isoformat(),self.return_day.isoformat()))
        self.assertFalse(self.overlap(self.return_day,self.return_day+timedelta(days=1)))
        self.assertTrue(self.overlap(self.return_day-timedelta(days=1),self.return_day))
    def test_public_booking_before_previous_return_time(self):
        self.reservation();client=web.app.test_client();client.get('/')
        with client.session_transaction() as s:csrf=s['_csrf']
        response=client.post('/reserver',data={'_csrf':csrf,'nom':'Test','prenom':'Client','telephone':'0600000000','code_vehicule':self.code,'date_depart':self.return_day.isoformat(),'heure_depart':'08:00','date_retour':(self.return_day+timedelta(days=2)).isoformat(),'heure_retour':'09:00'})
        self.assertEqual(response.status_code,200)
        with web.db() as c:self.assertEqual(c.execute('SELECT COUNT(*) FROM reservations WHERE code_vehicule=?',(self.code,)).fetchone()[0],2)
