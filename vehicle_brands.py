"""Brand assets and visual selection of vehicles in service."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk
BRANDS=('dacia','peugeot','opel','volkswagen','citroen','renault','fiat','ford','hyundai','kia','chevrolet')
def brand(model):
    text=str(model or '').lower()
    for key in BRANDS:
        if key in text:return key
    for alias,key in [('hunday','hyundai'),('daci','dacia'),('aveo','chevrolet'),('corsa','opel'),('t-roc','volkswagen')]:
        if alias in text:return key
    return None
def logo(app,model):
    key=brand(model)
    if not hasattr(app,'_brand_logo_cache'):app._brand_logo_cache={}
    if key not in app._brand_logo_cache:
        path=Path(__file__).parent/'assets'/'vehicle_brands'/f'{key}.png'
        app._brand_logo_cache[key]=tk.PhotoImage(file=str(path)) if path.exists() else tk.PhotoImage(width=1,height=1)
    return app._brand_logo_cache[key]
def choose_vehicle(app):
    win=tk.Toplevel(app.root);win.title('Véhicules en service');win.geometry('760x500');win.configure(bg='#f4f9ff')
    tk.Label(win,text='Rechercher un véhicule en service',bg='#123a62',fg='white',font=('Segoe UI',16,'bold'),pady=14).pack(fill='x')
    term=tk.StringVar();entry=ttk.Entry(win,textvariable=term);entry.pack(fill='x',padx=15,pady=12)
    tree=ttk.Treeview(win,columns=('code','model'),show='tree headings');tree.heading('#0',text='Marque');tree.column('#0',width=115);tree.heading('code',text='Code');tree.column('code',width=100);tree.heading('model',text='Véhicule');tree.pack(fill='both',expand=True,padx=15,pady=5)
    def refresh(*args):
        tree.delete(*tree.get_children());q=term.get().casefold()
        for row in app.conn.execute('SELECT code,modele FROM vehicles WHERE service=1 ORDER BY modele,code'):
            if q in (str(row[0])+' '+str(row[1])).casefold():tree.insert('', 'end',values=(row[0],row[1]),image=logo(app,row[1]))
    def select(*args):
        chosen=tree.selection()
        if chosen:app.vars['vehicle_code'].set(tree.item(chosen[0],'values')[0]);win.destroy();app.load_vehicle()
    ttk.Button(win,text='✓ Sélectionner',command=select).pack(side='right',padx=15,pady=12)
    ttk.Button(win,text='Fermer',command=win.destroy).pack(side='left',padx=15,pady=12)
    tree.bind('<Double-1>',select);tree.bind('<Return>',select);term.trace_add('write',refresh);refresh();entry.focus_set();return 'break'
