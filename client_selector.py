"""Sélection compacte et commune aux deux conducteurs."""
import tkinter as tk
from tkinter import ttk
from contract_controls import IconButton,RoundedField
from history_layout import blue_history_headings

def open_client_selector(app,parent,on_select,title='Choisir un client',exclude='',on_clear=None):
    win=app._secondary_window(parent);win.title(title);win.transient(parent.winfo_toplevel());win.configure(bg='#f1f7fd')
    width=min(860,win.winfo_screenwidth()-60);height=min(500,win.winfo_screenheight()-100)
    win.geometry(f'{width}x{height}+{(win.winfo_screenwidth()-width)//2}+{(win.winfo_screenheight()-height)//2}')
    tk.Label(win,text=title,bg='#074575',fg='white',font=('Segoe UI',17,'bold'),anchor='w',padx=20,pady=15).pack(fill='x')
    bar=tk.Frame(win,bg='#f1f7fd');bar.pack(fill='x',padx=14,pady=12)
    query=tk.StringVar(win);field=RoundedField(bar,query);field.configure(height=36);field.pack(side='left',fill='x',expand=True)
    count=tk.StringVar(win,value='Code · CIN · Nom · Prénom · Téléphone')
    tk.Label(win,textvariable=count,bg='#f1f7fd',fg='#526b83',anchor='w').pack(fill='x',padx=18,pady=(0,6))
    host=tk.Frame(win,bg='white');host.pack(fill='both',expand=True,padx=14)
    style=ttk.Style(win);blue_history_headings(style,'ClientSelector.Treeview');style.configure('ClientSelector.Treeview',rowheight=31,font=('Segoe UI',10))
    cols=('code','nom','prenom','cin','telephone');tree=ttk.Treeview(host,columns=cols,show='headings',style='ClientSelector.Treeview')
    for col,title in zip(cols,('Code client','Nom','Prénom','CIN','Téléphone')):tree.heading(col,text=title);tree.column(col,width=140,anchor='center')
    tree.pack(side='left',fill='both',expand=True);scroll=ttk.Scrollbar(host,command=tree.yview);scroll.pack(side='right',fill='y');tree.configure(yscrollcommand=scroll.set)
    tree.tag_configure('even',background='#edf5fc')
    pending=[None]
    def refresh():
        pending[0]=None;term='%'+query.get().strip()+'%';tree.delete(*tree.get_children())
        data=app.conn.execute('SELECT code,nom,prenom,cin,telephone FROM clients WHERE code<>? AND (code LIKE ? OR cin LIKE ? OR nom LIKE ? OR prenom LIKE ? OR telephone LIKE ?) ORDER BY nom,prenom LIMIT 150',(exclude,)+(term,)*5).fetchall()
        for i,r in enumerate(data):tree.insert('','end',iid=str(r['code']),values=tuple(r),tags=('even',) if i%2==0 else ())
        count.set(f'{len(data)} résultat(s) · Double-cliquez ou appuyez sur Entrée pour choisir')
        if data:tree.selection_set(str(data[0]['code']))
    def schedule(*_):
        if pending[0]:win.after_cancel(pending[0])
        pending[0]=win.after(120,refresh)
    def choose(*_):
        if tree.selection():code=tree.selection()[0];win.destroy();on_select(code)
    def clear():win.destroy();on_clear()
    def add():app.open_quick_client_dialog(lambda code:(win.destroy(),on_select(code)))
    IconButton(bar,'Rechercher',refresh,icon='search',width=135,height=36).pack(side='left',padx=5)
    footer=tk.Frame(win,bg='#f1f7fd');footer.pack(fill='x',padx=14,pady=12)
    for text,fn,color,icon in [('Choisir',choose,'#009d54','check'),('Ajouter client',add,'#0789ee','plus'),('Fermer',win.destroy,'#64748b','cancel')]:IconButton(footer,text,fn,color,icon=icon,width=150,height=35).pack(side='right',padx=3)
    if on_clear:IconButton(footer,'Retirer',clear,'#dc3545',icon='trash',width=110,height=35).pack(side='left')
    query.trace_add('write',schedule);tree.bind('<Double-1>',choose);tree.bind('<Return>',choose);field.input.bind('<Return>',choose)
    win.bind('<Escape>',lambda _:win.destroy());refresh();field.input.focus_set();win.lift();return win
