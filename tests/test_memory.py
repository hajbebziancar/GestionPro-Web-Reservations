import os, sys, tempfile, unittest, sqlite3, threading, time, io, base64
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
_temp = tempfile.TemporaryDirectory()
os.environ['GESTIONPRO_DATA_DIR'] = _temp.name
os.environ['GESTIONPRO_API_TOKEN'] = 'test-only'
os.environ['HBZ_CHROMIUM_PATH'] = '/test/chromium'
import app as web
import remote_signatures as rs
from PIL import Image, ImageDraw
from pypdf import PdfWriter

class MemoryTests(unittest.TestCase):
    def test_database_closes_commits_and_rolls_back(self):
        with web.db() as c:
            c.execute('CREATE TABLE IF NOT EXISTS close_test(n INTEGER)')
            c.execute('INSERT INTO close_test VALUES(1)')
        with self.assertRaises(sqlite3.ProgrammingError): c.execute('SELECT 1')
        with self.assertRaises(RuntimeError):
            with web.db() as c:
                c.execute('INSERT INTO close_test VALUES(2)')
                raise RuntimeError('rollback')
        with web.db() as c:
            self.assertEqual(c.execute('SELECT COUNT(*) FROM close_test').fetchone()[0], 1)

    def test_one_renderer_and_slot_released_after_error(self):
        entered, release = threading.Event(), threading.Event()
        def work(content):
            entered.set()
            self.assertTrue(release.wait(3))
            return b'pdf'
        with patch.object(rs, '_render_pdf', side_effect=work):
            t = threading.Thread(target=rs.render_pdf, args=('html',))
            t.start()
            self.assertTrue(entered.wait(3))
            try:
                with self.assertRaises(RuntimeError): rs.render_pdf('second')
            finally:
                release.set(); t.join(3)
            self.assertFalse(t.is_alive())
        with patch.object(rs, '_render_pdf', side_effect=RuntimeError('failed')):
            with self.assertRaises(RuntimeError): rs.render_pdf('html')
        with patch.object(rs, '_render_pdf', return_value=b'ok'):
            self.assertEqual(rs.render_pdf('html'), b'ok')

    def test_signature_routes_and_repeated_status(self):
        client = web.app.test_client()
        html = "<html><head></head><body><div class='signature'>Signature du locataire</div></body></html>"
        response = client.post('/api/sync/signatures', json={'html':html,'contract_no':'TEST','client_codes':['C1']}, headers={'Authorization':'Bearer test-only'})
        self.assertEqual(response.status_code,200)
        token = response.json['token']
        im = Image.new('RGB',(200,80),'white')
        ImageDraw.Draw(im).line((20,20,170,60),fill='black',width=4)
        png = io.BytesIO(); im.save(png,'PNG')
        out=io.BytesIO(); writer=PdfWriter();writer.add_blank_page(width=595,height=842);writer.write(out)
        with patch.object(rs,'_render_pdf',return_value=out.getvalue()):
            self.assertEqual(client.get(f'/signature/{token}/original.pdf').status_code,200)
            saved=client.post(f'/signature/{token}/save',json={'accepted':True,'image':'data:image/png;base64,'+base64.b64encode(png.getvalue()).decode()})
            self.assertEqual(saved.status_code,200)
        for _ in range(50):
            with patch.object(rs,'get',wraps=rs.get) as get:
                self.assertTrue(client.get(f'/signature/{token}/status').json['saved'])
                self.assertNotIn('original',get.call_args.args[1])
                self.assertIn('pdf IS NOT NULL',get.call_args.args[1])
        self.assertEqual(client.get(f'/signature/{token}/pdf').data,out.getvalue())
        self.assertIn(b'hbz-verso-signature',client.get(f'/signature/{token}/contract').data)
        self.assertTrue(client.get(f'/api/sync/signatures/{token}',headers={'Authorization':'Bearer test-only'}).json['saved'])

if __name__ == '__main__': unittest.main()
