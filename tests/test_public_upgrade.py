import unittest
from datetime import date,timedelta
import test_memory
from gestionpro_android.web_bookings import sync_fleet,bookings
web=test_memory.web
class PublicUpgradeTests(unittest.TestCase):
    def test_public_fleet_and_reservation_duration(self):
        sync_fleet({'vehicles':[{'code':'UPGRADE-V','modele':'MARQUE TEST','immatriculation':'PLAQUE-CONFIDENTIELLE','chassis':'CHASSIS','compteur':987654,'prix':300,'service':1}],'contracts':[]})
        client=web.app.test_client();home=client.get('/').get_data(as_text=True)
        self.assertIn('MARQUE TEST',home);self.assertNotIn('PLAQUE-CONFIDENTIELLE',home);self.assertNotIn('987654',home);self.assertIn('company-logo.png',home)
        with client.session_transaction() as s:csrf=s.get('_csrf') or s.get('csrf_token')
        if not csrf:
            with client.session_transaction() as s:csrf=next(v for k,v in s.items() if 'csrf' in k)
        start=date.today()+timedelta(days=8);end=start+timedelta(days=2)
        response=client.post('/reserver',data={'_csrf':csrf,'nom':'Client Test','prenom':'Fictif','telephone':'0600000000','cin':'TEST-UPGRADE','code_vehicule':'UPGRADE-V','date_depart':start.isoformat(),'date_retour':end.isoformat(),'heure_depart':'09:00','heure_retour':'09:00'})
        self.assertEqual(response.status_code,200)
        r=next(r for r in bookings() if r['cin']=='TEST-UPGRADE');self.assertEqual(r['duration'],2);self.assertEqual(r['total'],600)
        sync_fleet({'vehicles':[],'contracts':[]});self.assertNotIn('MARQUE TEST',client.get('/').get_data(as_text=True))
if __name__=='__main__':unittest.main()
