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
