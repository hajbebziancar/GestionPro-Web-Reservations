import json,unittest,test_sync
from mobile_sync import db,snapshot,apply_one
class HBZFormsTests(unittest.TestCase):
    setUp=test_sync.SyncTests.setUp
    tearDown=test_sync.SyncTests.tearDown
    customer=test_sync.SyncTests.customer
    contract=test_sync.SyncTests.contract
    def test_form_metadata_roundtrip_and_second_driver(self):
        second=self.customer();second['id']='op-second';second['record']={**second['record'],'code':'MCL-002','cin':'SECOND-CIN','nom':'Deuxième'}
        with db(self.path) as c:
            apply_one(c,self.customer(),self.root);apply_one(c,second,self.root)
            op=self.contract(False)
            extras={'second_code':'MCL-002','departure_location':'Kénitra','return_location':'Rabat','payment_mode':'Carte','fuel_level':'¾','condition':{'observations':'Rayure arrière','equipment':{'Cric':True,'Extincteur':False}}}
            op['record'].update(extras);op['frozen']['record']=dict(op['record']);op['frozen']['second_client']=dict(second['record'])
            apply_one(c,op,self.root)
            r=snapshot(c)['contracts'][0]
            for key,value in extras.items():self.assertEqual(r[key],value)
            apply_one(c,op,self.root)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],1)
            self.assertEqual(json.loads(c.execute("SELECT payload FROM module_records WHERE module='contract_vehicle_condition'").fetchone()[0]),extras['condition'])
    def test_changed_second_driver_rolls_back(self):
        with db(self.path) as c:
            apply_one(c,self.customer(),self.root)
            op=self.contract(False);op['record']['second_code']='missing';op['frozen']['record']=dict(op['record']);op['frozen']['second_client']={'code':'missing'}
            self.assertEqual(apply_one(c,op,self.root)['status'],'rejected')
            self.assertEqual(c.execute('SELECT COUNT(*) FROM contracts').fetchone()[0],0)

    def test_client_profile_and_archiving_preserve_history(self):
        op=self.customer();op['record']['hbz_profile']={'email':'client@example.test','observations':'Client sérieux','archived':False}
        with db(self.path) as c:
            apply_one(c,op,self.root)
            original=snapshot(c)['clients'][0]
            update={'id':'op-archive-001','kind':'client_update','original':original,'record':{**original,'hbz_profile':{**original['hbz_profile'],'archived':True}}}
            self.assertEqual(apply_one(c,update,self.root)['status'],'applied')
            self.assertTrue(snapshot(c)['clients'][0]['hbz_profile']['archived'])
            self.assertEqual(c.execute('SELECT COUNT(*) FROM clients').fetchone()[0],1)
    def test_vehicle_create_and_full_update(self):
        record={'code':'MVH-TEST','modele':'DACIA TEST','immatriculation':'NEW-PLATE','chassis':'TEST','compteur':50,'prix':350,'service':1,'hbz_profile':{'brand':'DACIA','year':'2024','fuel_eighths':6}}
        with db(self.path) as c:
            self.assertEqual(apply_one(c,{'id':'op-new-vehicle','kind':'vehicle_create','record':record},self.root)['status'],'applied')
            original=next(v for v in snapshot(c)['vehicles'] if v['code']==record['code'])
            changed={**original,'compteur':60,'prix':400,'hbz_full_edit':True,'hbz_profile':{**original['hbz_profile'],'places':5}}
            self.assertEqual(apply_one(c,{'id':'op-edit-vehicle','kind':'vehicle_update','record':changed,'original':original},self.root)['status'],'applied')
            updated=next(v for v in snapshot(c)['vehicles'] if v['code']==record['code'])
            self.assertEqual(updated['prix'],400);self.assertEqual(updated['compteur'],60);self.assertEqual(updated['hbz_profile']['places'],5)
    def test_discount_validation(self):
        with db(self.path) as c:
            apply_one(c,self.customer(),self.root)
            op=self.contract(False);op['record'].update(base_price=300,discount_percent=10,prix=270,montant=810,reste=610);op['frozen']['record']=dict(op['record'])
            self.assertIsNone(apply_one(c,op,self.root))
            self.assertEqual(snapshot(c)['contracts'][0]['discount_percent'],10)
