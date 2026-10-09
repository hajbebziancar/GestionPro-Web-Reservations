"""Client and global histories shared with the compact contract mockup."""
import tkinter as tk
from tkinter import ttk,messagebox
from datetime import datetime,timedelta
from client_rapide_form import (ContractAction,HistoryMetricCard,history_date_bounds,
    history_contract_overlaps,history_period_metrics,month_passage_dates,BG,BLUE,INK)

def build_history_tabs(app,win,q):
    style=ttk.Style(win)
    from history_layout import blue_history_headings
    blue_history_headings(style,'ContractHistory.Treeview')
    style.layout('ContractRental.TNotebook.Tab',[])
    tabs_bar=tk.Frame(win,bg='#eaf4ff');tabs_bar.pack(fill='x')
    notebook=ttk.Notebook(win,style='ContractRental.TNotebook');notebook.pack(fill='both',expand=True)
    tab_buttons=[]
    for index,(title,color,soft) in enumerate((('Contrat de location','#008d4b','#e5f5eb'),
            ('Historique du client','#0065ef','#e5f0ff'),('Historique global','#7153dc','#eee8ff'))):
        tab=ContractAction(tabs_bar,title,lambda i=index:notebook.select(i),soft,color)
        tab.configure(width=190,height=36);tab.pack(side='left',padx=3,pady=3)
        tab_buttons.append((tab,color,soft))
    def color_tabs():
        current=notebook.index('current')
        for i,(tab,color,soft) in enumerate(tab_buttons):tab.configure(bg=color if i==current else soft,fg='white' if i==current else color)
    contract_page=tk.Frame(notebook,bg=BG);notebook.add(contract_page,text='Contrat de location')
    history_trees={}
    archive_refreshes={}
    now=datetime.now()
    history_filters={};history_metrics={};pending_filters={}
    def schedule_filter(key):
        if key in pending_filters:win.after_cancel(pending_filters[key])
        def apply():pending_filters.pop(key,None);refresh_history(key,silent=True)
        pending_filters[key]=win.after(350,apply)
    for key,title in (('client','Historique du client'),('global','Historique global')):
        page=tk.Frame(notebook,bg=BG);notebook.add(page,text=title)
        tk.Label(page,text=title,bg=BG,fg=BLUE,font=('Segoe UI',16,'bold')).pack(anchor='w',padx=16,pady=12)
        history_filter={'mode':tk.StringVar(value='Mois'),'month':tk.StringVar(value=f'{now.month:02d}'),
            'year':tk.StringVar(value=str(now.year)),'start':tk.StringVar(value=now.replace(day=1).strftime('%d/%m/%Y')),
            'end':tk.StringVar(value=now.strftime('%d/%m/%Y'))}
        history_filters[key]=history_filter
        if key in ('client','global'):
            filters=tk.Frame(page,bg='#eaf4ff');filters.pack(fill='x',padx=12,pady=(0,6))
            inputs={}
            fields=(('Afficher','mode',('Mois','Année','Période'),12),('Mois','month',tuple(f'{m:02d}' for m in range(1,13)),5),
                ('Année','year',tuple(str(y) for y in range(now.year-15,now.year+6)),7),('Du','start',None,11),('Au','end',None,11))
            for caption,name,values,width in fields:
                block=tk.Frame(filters,bg='#eaf4ff');block.pack(side='left',padx=6,pady=6)
                tk.Label(block,text=caption,bg='#eaf4ff',fg=INK,font=('Segoe UI',9,'bold')).pack(anchor='w')
                widget=ttk.Combobox(block,textvariable=history_filter[name],values=values,width=width,state='readonly' if name in ('mode','month') else 'normal') if values else ttk.Entry(block,textvariable=history_filter[name],width=width)
                widget.pack();inputs[name]=widget
                if name in ('start','end'):app._attach_date_picker(widget,history_filter[name])
                widget.bind('<<ComboboxSelected>>',lambda _e,k=key:refresh_history(k))
                widget.bind('<Return>',lambda _e,k=key:refresh_history(k))
                widget.bind('<FocusOut>',lambda _e,k=key:schedule_filter(k))
            action=ContractAction(filters,'Filtrer',lambda k=key:refresh_history(k),'#0065ef');action.configure(width=95,height=32);action.pack(side='left',padx=8,pady=(16,5))
            def filter_states(*_,history_filter=history_filter,inputs=inputs):
                mode=history_filter['mode'].get()
                inputs['month'].configure(state='readonly' if mode=='Mois' else 'disabled')
                inputs['year'].configure(state='normal' if mode!='Période' else 'disabled')
                for name in ('start','end'):inputs[name].configure(state='normal' if mode=='Période' else 'disabled')
            history_filter['mode'].trace_add('write',filter_states);filter_states()
            def date_changed(*_,selected=history_filter,k=key):
                selected['mode'].set('Période');schedule_filter(k)
            for name in ('start','end'):history_filter[name].trace_add('write',date_changed)
        cards=tk.Frame(page,bg=BG);cards.pack(fill='x',padx=12,pady=(2,4))
        history_metrics[key]={name:tk.StringVar(value='0 jours' if name=='days' else '0,00 MAD/jour' if name=='average' else '0,00 MAD') for name in ('days','amount','average')}
        for col,(name,title,accent,soft) in enumerate((('days','Jours loués · période','#0065ef','#eaf4ff'),
                ('amount','CA client · période' if key=='client' else 'Montant global · période','#16864b','#e5f5eb'),
                ('average','Moyenne de location / jour','#7153dc','#eee8ff'))):
            cards.grid_columnconfigure(col,weight=1,uniform='history_metrics')
            card=HistoryMetricCard(cards,title,history_metrics[key][name],accent,soft)
            card.grid(row=0,column=col,sticky='ew',padx=(0 if col==0 else 4,0))
        if key=='global':
            for col,name,title,accent,soft in ((3,'annual','CA moyen / année couverte','#b27a37','#fff1e0'),(4,'monthly','CA moyen / mois couvert','#087f82','#e3f5f2')):
                history_metrics[key][name]=tk.StringVar(value='0,00 MAD')
                cards.grid_columnconfigure(col,weight=1,uniform='history_metrics')
                HistoryMetricCard(cards,title,history_metrics[key][name],accent,soft).grid(row=0,column=col,sticky='ew',padx=(4,0))
            tk.Label(page,text='Moyennes : CA de la période ÷ nombre d’années / de mois calendaires couverts, même partiellement.',bg=BG,fg='#60788a',font=('Segoe UI',8),anchor='w').pack(fill='x',padx=16)
        tk.Label(page,text='Période sélectionnée · jours loués et CA hors journées de passage réservées à l’épargne',bg=BG,fg='#60788a',font=('Segoe UI',8),anchor='w').pack(fill='x',padx=16)
        holder=tk.Frame(page,bg=BG);holder.pack(fill='both',expand=True,padx=12,pady=8)
        columns=('numero','client','second','vehicle','start','end','days','total','paid','balance','status')
        tree=ttk.Treeview(holder,columns=columns,show='tree headings',style='ContractHistory.Treeview')
        style.configure('ContractHistory.Treeview',rowheight=52,font=('Segoe UI',9))
        style.layout('ContractHistory.Treeview.Item',[('Treeitem.padding',{'sticky':'nswe','children':[('Treeitem.image',{'side':'left','sticky':'ns'}),('Treeitem.text',{'side':'left','sticky':'nswe'})]})])
        tree.tag_configure('passage',background='#fff5d9',foreground='#946b12')
        tree.heading('#0',text='Photo');tree.column('#0',width=58,minwidth=48,stretch=False)
        tree._vehicle_images={}
        for col,title,width in zip(columns,('Contrat','Client principal','Deuxième conducteur','Véhicule','Départ','Retour','Jours contrat','Montant contrat MAD','Réglé MAD','Reste MAD','Statut'),(72,120,110,135,88,88,58,82,75,75,88)):
            tree.heading(col,text=title);tree.column(col,width=width,minwidth=45,stretch=True)
        sy=ttk.Scrollbar(holder,orient='vertical',command=tree.yview)
        tree.configure(yscrollcommand=sy.set)
        tree.grid(row=0,column=0,sticky='nsew');sy.grid(row=0,column=1,sticky='ns')
        holder.grid_columnconfigure(0,weight=1);holder.grid_rowconfigure(0,weight=1)
        history_trees[key]=tree
        from document_archives import install_table_actions
        archive_refreshes[key]=install_table_actions(app,page,'contracts',tree,checkbox_column='archive_check')
        def open_history(event,t=tree):
            selected=t.selection()
            if selected:
                app.contract_search_var.set(t.item(selected[0],'values')[0]);app.load_contract_lookup();app.preview_contract()
        from signed_contracts import install_signed_column
        install_signed_column(tree,app.open_signed_contract)
        from history_layout import fit_history_columns
        tree.configure(displaycolumns=('archive_check',*columns,'signed_contract'))
        # Keep every original heading when adding selection and signed-PDF columns.
        for col,title in zip(columns,('Contrat','Client principal','Deuxième conducteur','Véhicule','Départ','Retour','Jours contrat','Montant contrat MAD','Réglé MAD','Reste MAD','Statut')):tree.heading(col,text=title)
        style.configure('ContractHistory.Treeview.Heading',background='#074575',foreground='white',font=('Segoe UI',9,'bold'))
        fit_history_columns(tree)
        def history_double(event,t=tree):
            if t.identify_column(event.x) in ('#1','#'+str(len(t['columns']))):return 'break'
            return open_history(event,t)
        tree.bind('<Double-1>',history_double)
        from table_transfers import export_history,import_history
        transfers=tk.Frame(page,bg=BG);transfers.pack(fill='x',padx=12,pady=4,before=holder)
        from contract_controls import IconButton
        IconButton(transfers,'Exporter',lambda t=tree:export_history(app,win,t),'#0789ee',icon='save',width=130,height=34).pack(side='left',padx=4)
        IconButton(transfers,'Importer',lambda k=key:import_history(app,win,lambda:refresh_history(k),q['client'].get().split('|')[0].strip() if k=='client' else None),'#7153dc',icon='document',width=130,height=34).pack(side='left',padx=4)
        action=ContractAction(transfers,'Actualiser',lambda k=key:refresh_history(k),BLUE);action.configure(width=130,height=32);action.pack(side='left',padx=4)
    def history_vehicle_photo(code,raw,tree):
        if code in tree._vehicle_images:return tree._vehicle_images[code]
        path=app._resolve_vehicle_photo_path(raw,code)
        if path:
            try:
                from PIL import Image,ImageTk
                with Image.open(path) as original:
                    from PIL import ImageOps
                    source=ImageOps.exif_transpose(original).convert('RGB')
                    source.thumbnail((46,34),Image.Resampling.LANCZOS)
                    image=Image.new('RGB',(54,42),'#f4f8fc')
                    image.paste(source,((54-source.width)//2,(42-source.height)//2))
                photo=ImageTk.PhotoImage(image);tree._vehicle_images[code]=photo;return photo
            except (OSError,ValueError):pass
        return ''
    def refresh_history(only=None,silent=False):
        code=q['client'].get().split('|')[0].strip()
        for key,tree in history_trees.items():
            if only is not None and key!=only:continue
            selected_filter=history_filters[key]
            try:first,last=history_date_bounds(*(selected_filter[name].get() for name in ('mode','month','year','start','end')))
            except (ValueError,OverflowError):
                if not silent:messagebox.showwarning('Historique','Indiquez un mois, une année et des dates valides (JJ/MM/AAAA), dans l’ordre chronologique.',parent=win)
                continue
            condition='WHERE (c.client_code=? OR c.second_code=?)' if key=='client' else ''
            parameters=(code,code) if key=='client' else ()
            tree.delete(*tree.get_children());tree._vehicle_images={}
            rows=app.conn.execute('''SELECT c.*,p.nom AS client_nom,p.prenom AS client_prenom,
                s.nom AS second_nom,s.prenom AS second_prenom,v.modele,v.immatriculation,v.photo AS vehicle_photo
                FROM contracts c LEFT JOIN clients p ON p.code=c.client_code
                LEFT JOIN clients s ON s.code=c.second_code LEFT JOIN vehicles v ON v.code=c.vehicle_code '''+
                condition+''' ORDER BY (substr(c.date_depart,7,4)||substr(c.date_depart,4,2)||substr(c.date_depart,1,2)) DESC,c.numero DESC''',
                parameters).fetchall()
            rows=[row for row in rows if history_contract_overlaps(row,first,last)]
            days,total,average=history_period_metrics(rows,first,last)
            history_metrics[key]['days'].set(str(days)+' jours')
            history_metrics[key]['amount'].set(f'{total:,.2f}'.replace(',',' ').replace('.',',')+' MAD')
            history_metrics[key]['average'].set(f'{average:,.2f}'.replace(',',' ').replace('.',',')+' MAD/jour')
            if key=='global':
                from history_layout import calendar_ca_averages
                annual,monthly,years,months=calendar_ca_averages(total,first,last)
                history_metrics[key]['annual'].set(f'{annual:,.2f}'.replace(',',' ').replace('.',',')+' MAD/an')
                history_metrics[key]['monthly'].set(f'{monthly:,.2f}'.replace(',',' ').replace('.',',')+' MAD/mois')
            for r in rows:
                photo=history_vehicle_photo(r['vehicle_code'],r['vehicle_photo'],tree)
                tree.insert('','end',image=photo,text='' if photo else '—',values=(r['numero'],f"{r['client_nom'] or ''} {r['client_prenom'] or ''}".strip(),
                    f"{r['second_nom'] or ''} {r['second_prenom'] or ''}".strip(),f"{r['modele'] or ''} · {r['immatriculation'] or ''}",
                    r['date_depart'],r['date_retour'],r['duree'],f"{float(r['montant'] or 0):.2f}",
                    f"{float(r['reglement'] or 0):.2f}",f"{float(r['reste'] or 0):.2f}",r['return_status'] or 'En cours'))
                for boundary in month_passage_dates(r['date_depart'],r['date_retour']):
                    # Show at the junction on both adjacent month views, without monetary cells.
                    previous=boundary.replace(day=1)-timedelta(days=1)
                    if not (first<=boundary.isoformat()<=last or first<=previous.isoformat()<=last):continue
                    shown=boundary.strftime('%d/%m/%Y')
                    tree.insert('','end',image=photo,text='' if photo else '—',tags=('passage',),values=(r['numero'],
                        f"{r['client_nom'] or ''} {r['client_prenom'] or ''}".strip(),'Épargne',
                        f"{r['modele'] or ''} · {r['immatriculation'] or ''}",previous.strftime('%d/%m/%Y'),shown,'','','','','Jour de passage · Épargne'))
            from signed_contracts import refresh_signed_column
            refresh_signed_column(tree)
            archive_refreshes[key]()
    def selected_tab(_e=None):
        color_tabs()
        if notebook.index('current')>0:refresh_history('client' if notebook.index('current')==1 else 'global')
    notebook.bind('<<NotebookTabChanged>>',selected_tab)
    color_tabs()

    def cleanup(event):
        if event.widget is not notebook:return
        for job in pending_filters.values():
            try:win.after_cancel(job)
            except tk.TclError:pass
    notebook.bind('<Destroy>',cleanup,add='+')
    notebook._history_trees=history_trees
    notebook._history_filters=history_filters
    notebook._history_metrics=history_metrics
    notebook._refresh_history=refresh_history
    return contract_page,notebook
