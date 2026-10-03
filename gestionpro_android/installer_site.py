"""Ajoute /mobile à un app.py Flask existant, sans modifier les autres routes."""
import ast,shutil,sys
from pathlib import Path
from datetime import datetime
source=Path(__file__).resolve().parent
target=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else source.parent/'site_web'
app=target/'app.py';text=app.read_text(encoding='utf-8-sig')
marker='# GESTION PRO ANDROID AUTONOME'
block='''
# GESTION PRO ANDROID AUTONOME
if os.environ.get('GP_MOBILE_TOKEN') and os.environ.get('GP_PC_TOKEN'):
    from werkzeug.middleware.dispatcher import DispatcherMiddleware
    from gestionpro_android.relay import Relay
    app.wsgi_app = DispatcherMiddleware(app.wsgi_app, {'/mobile': Relay()})
'''
if marker not in text:
    needle="if __name__ == '__main__':"
    if needle not in text:raise SystemExit('app.py non reconnu; monter Relay via DispatcherMiddleware manuellement.')
    new=text.replace(needle,block+'\n'+needle,1);ast.parse(new)
    shutil.copy2(app,target/('app_avant_android_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'.py'));app.write_text(new,encoding='utf-8')
package=target/'gestionpro_android';package.mkdir(exist_ok=True)
(package/'__init__.py').write_text('',encoding='utf-8');shutil.copy2(source/'relay.py',package/'relay.py');shutil.copytree(source/'mobile',package/'mobile',dirs_exist_ok=True)
print('Module Android ajouté au site. Configurer les variables GP_MOBILE_TOKEN, GP_PC_TOKEN et GP_RELAY_DB sur un volume persistant, puis redéployer.')
