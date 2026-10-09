"""Client rental history with explicit month, year and date-range filters."""
import calendar
from datetime import date, datetime
import tkinter as tk
from tkinter import ttk, messagebox
from contract_controls import IconButton, RoundedField

def filtered_rows(conn, client, mode='Toutes', month=1, year=None, start='', end=''):
    from quick_client_tabs import history_rows
    year=int(year or date.today().year)
    if mode=='Mois':
        month=int(month);start=f'01/{month:02d}/{year}';end=f'{calendar.monthrange(year,month)[1]:02d}/{month:02d}/{year}'
    elif mode=='Année':start=f'01/01/{year}';end=f'31/12/{year}'
    elif mode!='Période':start=end=''
    return history_rows(conn,str(client),start,end) if client else []

def build_history(parent, app, client_getter):
    frame=tk.Frame(parent,bg='#f4faff')
    bar=tk.Frame(frame,bg='white');bar.pack(fill='x',padx=12,pady=12)
    mode=tk.StringVar(value='Toutes');month=tk.StringVar(value=str(date.today().month));year=tk.StringVar(value=str(date.today().year))
    start=tk.StringVar();end=tk.StringVar();summary=tk.StringVar(value='Sélectionnez un client dans le contrat.')
    for caption,var,values,width in [('Filtre',mode,('Toutes','Mois','Année','Période'),120),('Mois',month,tuple(map(str,range(1,13))),65),('Année',year,tuple(map(str,range(2000,date.today().year+3))),85),('Du',start,None,120),('Au',end,None,120)]:
        tk.Label(bar,text=caption,bg='white',fg='#092d50').pack(side='left',padx=(8,3))
        field=RoundedField(bar,var,values=values,readonly=values is not None);field.pack(side='left',ipady=0);field.configure(width=width,height=34)
        if values:field.bind('<<ComboboxSelected>>',lambda e:refresh())
        else:app._attach_date_picker(field,var);field.bind('<Return>',lambda e:refresh())
    IconButton(bar,'Actualiser',lambda:refresh(),icon='search',width=125,height=35).pack(side='left',padx=10)
    tk.Label(frame,textvariable=summary,bg='#e4f2ff',fg='#074575',font=('Segoe UI',11,'bold'),pady=10).pack(fill='x',padx=12)
    holder=tk.Frame(frame,bg='white');holder.pack(fill='both',expand=True,padx=12,pady=12)
    cols=('numero','date_depart','date_retour','duree','modele','immatriculation','montant','reste')
    tree=ttk.Treeview(holder,columns=cols,show='headings')
    for key,title,width in zip(cols,('Contrat','Départ','Retour','Jours','Véhicule','Immatriculation','Montant (DH)','Reste (DH)'),(120,110,110,55,140,120,115,115)):
        tree.heading(key,text=title);tree.column(key,width=width,minwidth=50,anchor='center')
    tree.pack(side='left',fill='both',expand=True);scroll=ttk.Scrollbar(holder,command=tree.yview);scroll.pack(side='right',fill='y');tree.configure(yscrollcommand=scroll.set)
    def refresh():
        try:rows=filtered_rows(app.conn,client_getter(),mode.get(),month.get(),year.get(),start.get(),end.get())
        except (ValueError,TypeError) as exc:messagebox.showwarning('Historique des locations',str(exc),parent=frame);return
        tree.delete(*tree.get_children())
        for r in rows:tree.insert('','end',values=[f"{float(r.get(k) or 0):,.2f}" if k in ('montant','reste') else r.get(k,'') for k in cols])
        summary.set(f"{len(rows)} locations · {sum(int(r.get('duree') or 0) for r in rows)} jours · Chiffre d’affaires : {sum(float(r.get('montant') or 0) for r in rows):,.2f} DH")
    def selected():
        selection=tree.selection();return str(tree.item(selection[0],'values')[0]) if selection else ''
    actions=tk.Frame(frame,bg='#f4faff');actions.pack(fill='x',padx=12,pady=(0,12))
    IconButton(actions,'Ouvrir le contrat',lambda:app.open_quick_contract_dialog(contract_number=selected()) if selected() else None,icon='document',width=180,height=38).pack(side='left')
    IconButton(actions,'Contrat signé',lambda:app.open_signed_contract(selected()) if selected() else None,icon='signature',width=160,height=38).pack(side='left',padx=8)
    def archive_selected():
        if not selected():return
        from document_archives import archive_contract,open_archives
        try:archive_contract(app,selected());open_archives(app,'contracts')
        except Exception as exc:messagebox.showerror('Archivage',str(exc),parent=frame)
    from document_archives import open_archives
    IconButton(actions,'Archiver le contrat',archive_selected,icon='save',width=175,height=38).pack(side='left',padx=8)
    IconButton(actions,'Contrats archivés',lambda:open_archives(app,'contracts'),icon='document',width=170,height=38).pack(side='left',padx=8)
    tree.bind('<Double-1>',lambda e:app.open_quick_contract_dialog(contract_number=selected()) if selected() else None)
    return frame,refresh
