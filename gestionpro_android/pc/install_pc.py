"""Installation additive : sauvegarde le main.py existant, puis ajoute le démarrage."""
import ast, json, shutil, tkinter as tk
from pathlib import Path
from tkinter import filedialog,messagebox,simpledialog
from datetime import datetime
root=tk.Tk();root.withdraw()
try:
    chosen=filedialog.askdirectory(title='Choisir le dossier Gestion Pro contenant main.py et gestionpro_hbz.db')
    if not chosen:raise SystemExit()
    target=Path(chosen);main=target/'main.py'
    if not main.exists() or not (target/'gestionpro_hbz.db').exists():raise ValueError('Choisissez le dossier de votre application Gestion Pro déjà utilisée.')
    url=simpledialog.askstring('Adresse du relais','Adresse HTTPS du relais, terminée par /mobile/ :',parent=root)
    if not url:raise SystemExit()
    if not url.startswith('https://') or not url.rstrip('/').endswith('/mobile'):raise ValueError('Utilisez https://votre-adresse/mobile/')
    token=simpledialog.askstring('Clé PC','Clé GP_PC_TOKEN du relais (différente de la clé Android) :',show='*',parent=root)
    if not token:raise SystemExit()
    text=main.read_text(encoding='utf-8-sig');needle='        self._create_database()'
    marker='from mobile_sync import start as start_mobile_sync'
    backup=target/('sauvegarde_avant_android_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));backup.mkdir()
    for filename in ('main.py','gestionpro_hbz.db','mobile_sync.py','mobile_sync_config.json'):
        if (target/filename).exists():shutil.copy2(target/filename,backup/filename)
    if marker not in text:
        if text.count(needle)!=1:raise ValueError('Version de main.py non reconnue. Aucune modification effectuée.')
        new=text.replace(needle,needle+'\n        '+marker+'\n        start_mobile_sync(APP_DIR)',1)
        ast.parse(new)
        main.write_text(new,encoding='utf-8')
    shutil.copy2(Path(__file__).with_name('mobile_sync.py'),target/'mobile_sync.py')
    (target/'mobile_sync_config.json').write_text(json.dumps({'base_url':url.rstrip('/'),'pc_token':token},ensure_ascii=False,indent=2),encoding='utf-8')
    messagebox.showinfo('Installation terminée','Fermez puis relancez Gestion Pro avec son lanceur habituel.\nLa synchronisation fonctionnera en arrière-plan sans fenêtre noire supplémentaire.\nLe téléphone pourra travailler quand le PC est éteint.')
except Exception as e:messagebox.showerror('Installation',str(e))
