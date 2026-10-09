from pathlib import Path
from datetime import datetime
import shutil,tkinter as tk
from tkinter import filedialog,messagebox
root=tk.Tk();root.withdraw()
messagebox.showinfo('GestionPro','Fermez GestionPro avant la mise à jour. Sélectionnez ensuite son dossier actuel.')
choice=filedialog.askdirectory(title='Dossier GestionPro actuel')
if not choice:raise SystemExit()
target=Path(choice);source=Path(__file__).resolve().parent
if not (target/'main.py').exists() or not (target/'gestionpro_hbz.db').exists():messagebox.showerror('GestionPro','Le dossier choisi ne contient pas GestionPro et sa base de données.');raise SystemExit(1)
if target.resolve()==source.resolve():messagebox.showerror('GestionPro','Choisissez le dossier de votre application actuelle, pas celui du ZIP extrait.');raise SystemExit(1)
files=['main.py', 'contract_revisions.py', 'financial_center.py']
backup=target/'sauvegardes'/('code_contrat_une_page_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'));backup.mkdir(parents=True)
for name in files:
 if (target/name).exists():shutil.copy2(target/name,backup/name)
try:
 for name in files:shutil.copy2(source/name,target/name)
except Exception:
 for name in files:
  if (backup/name).exists():shutil.copy2(backup/name,target/name)
 raise
messagebox.showinfo('GestionPro','Corrections installées. Les bases de données, photos et contrats signés actuels sont conservés. Relancez GestionPro.')
