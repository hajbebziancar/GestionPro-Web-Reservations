"""Formulaire Client rapide : composition native d'après la référence fournie."""
import json
import shutil
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

BLUE='#0065ef'; INK='#08315e'; BG='#f4faff'; LINE='#d6e6f3'; SOFT='#eaf5ff'


def amounts(days,price,paid,discount=0,insurance=0):
    gross=round(days*price,2)
    net=round(max(0,gross-discount)+insurance,2)
    return gross,net,round(max(0,net-paid),2)


def client_vehicle_turnover(conn,client_code='',vehicle_code=''):
    """CA cumulé des contrats enregistrés, client principal et véhicule."""
    def total(column,code):
        if not code:return 0.0
        result=0.0
        for amount,start,end,duration in conn.execute(f'SELECT montant,date_depart,date_retour,duree FROM contracts WHERE {column}=?',(code,)):
            passages=month_passage_dates(start,end)
            try:days=max(1,(datetime.strptime(end,'%d/%m/%Y')-datetime.strptime(start,'%d/%m/%Y')).days)
            except (TypeError,ValueError):days=max(1,int(duration or 1))
            result+=float(amount or 0)*max(0,days-len(passages))/days
        return round(result,2)
    return total('client_code',client_code),total('vehicle_code',vehicle_code)

def month_passage_dates(departure,arrival):
    from datetime import timedelta
    try:first=datetime.strptime(departure,'%d/%m/%Y').date();last=datetime.strptime(arrival,'%d/%m/%Y').date()
    except (TypeError,ValueError):return []
    result=[];boundary=(first.replace(day=28)+timedelta(days=4)).replace(day=1)
    while boundary<=last:
        result.append(boundary);boundary=(boundary.replace(day=28)+timedelta(days=4)).replace(day=1)
    return result

def history_date_bounds(mode,month,year,start='',end=''):
    from datetime import date
    import calendar
    if mode=='Période':
        first=datetime.strptime(start.strip(),'%d/%m/%Y').date()
        last=datetime.strptime(end.strip(),'%d/%m/%Y').date()
        if first>last:raise ValueError('La date de début doit précéder la date de fin.')
    elif mode=='Année':first=date(int(year),1,1);last=date(int(year),12,31)
    else:
        first=date(int(year),int(month),1)
        last=date(int(year),int(month),calendar.monthrange(int(year),int(month))[1])
    return first.isoformat(),last.isoformat()

def history_contract_overlaps(row,first,last):
    from datetime import date
    def parsed(raw):
        for fmt in ('%d/%m/%Y','%Y-%m-%d'):
            try:return datetime.strptime(str(raw or '').strip().split(' ')[0],fmt).date()
            except ValueError:pass
        return None
    start=parsed(row['date_depart']);end=parsed(row['date_retour'])
    if not start:return False
    end=end or start+timedelta(days=max(1,int(row['duree'] or 1)))
    return start<=date.fromisoformat(last) and end>=date.fromisoformat(first)

def history_period_metrics(rows,first,last):
    """Jours de production et CA dans la période, hors passage réservé épargne."""
    from datetime import date
    first=date.fromisoformat(first);last=date.fromisoformat(last)
    count=0;amount=0.0
    for row in rows:
        try:start=datetime.strptime(row['date_depart'],'%d/%m/%Y').date()
        except (TypeError,ValueError):continue
        try:end=datetime.strptime(row['date_retour'],'%d/%m/%Y').date()
        except (TypeError,ValueError):end=start+timedelta(days=max(1,int(row['duree'] or 1)))
        days=max(1,(end-start).days)
        begin=max(first,start+timedelta(days=1));finish=min(last,start+timedelta(days=days))
        selected=max(0,(finish-begin).days+1)
        if selected:
            selected-=sum(begin<=day<=finish for day in month_passage_dates(row['date_depart'],(start+timedelta(days=days)).strftime('%d/%m/%Y')))
        count+=selected;amount+=float(row['montant'] or 0)*selected/days
    return count,round(amount,2),round(amount/count,2) if count else 0.0

class HistoryMetricCard(tk.Canvas):
    def __init__(self,parent,title,variable,accent,soft):
        super().__init__(parent,height=72,bg=BG,highlightthickness=0)
        self.title=title;self.variable=variable;self.accent=accent;self.soft=soft
        self.bind('<Configure>',lambda _:self.paint())
        variable.trace_add('write',lambda *_:self.paint())
    def paint(self):
        from reservation_reference import _reservation_round,_reservation_icon
        self.delete('all');w=self.winfo_width();h=self.winfo_height()
        if w<2:return
        _reservation_round(self,0,0,w,h,10,'#bedcf4')
        _reservation_round(self,1,1,w-1,h-1,9,self.soft)
        _reservation_icon(self,'money',12,25,.85,self.accent)
        self.create_text(42,19,text=self.title,anchor='w',fill=INK,font=('Segoe UI',9,'bold'))
        self.create_text(42,46,text=self.variable.get(),anchor='w',fill=self.accent,font=('Segoe UI',15,'bold'))

class ContractAction(__import__('contract_controls').IconButton):
    """Professional pictograms on the restored contract layout."""
    def __init__(self,parent,text,command,color,ink='white'):
        caption=text.strip().lstrip('▰▦✉＋▣▤ϟ×◉⌕✍ ')
        lower=caption.casefold()
        icon=next((icon for word,icon in (
            ('signature','signature'),('signé','signature'),('whatsapp','whatsapp'),
            ('enregistrer','save'),('supprimer','trash'),('imprimer','print'),
            ('chercher','search'),('rechercher','search'),('⌕','search'),
            ('client','person'),('conducteur','person'),('annuler','cancel'),
            ('dupliquer','plus'),('nouveau','plus'),('importer','document'),
            ('exporter','pdf'),('pdf','pdf'),('scanner','camera'),
            ('actualiser','search'),('filtrer','search'),('agence','location'),
            ('historique','calendar'),('location','car'),('contrat','document'),
            ('réservation','calendar'),('véhicule','car'),('entretien','gear'),
            ('alerte','shield'),('paramètre','gear'),('financier','money'))
            if word in lower or word in text.casefold()),'document')
        super().__init__(parent,caption,command,color,ink,icon=icon)
        self.empty=not text
    def paint(self):
        if getattr(self,'empty',False):
            self.delete('all');self.create_rectangle(0,0,self.winfo_width(),self.winfo_height(),fill=self.fill,outline=self.fill)
        else:super().paint()


def resolve_client_media(app,code,raw):
    """Chemin direct, relatif ou provenant d'une ancienne installation Windows."""
    text=str(raw or '').strip()
    if not text:return None
    base=Path(__file__).resolve().parent
    direct=Path(text)
    if direct.is_file():return direct
    parts=[part for part in text.replace('\\','/').split('/') if part]
    name=parts[-1] if parts else ''
    candidates=[base.joinpath(*parts)]
    if 'assets' in parts:candidates.append(base.joinpath(*parts[parts.index('assets'):]))
    directory=base/'assets'/'client_documents'/str(code)
    candidates.append(directory/name)
    for path in candidates:
        if path.is_file():return path
    if directory.is_dir():
        for path in directory.rglob(name):
            if path.is_file():return path
    return None


def client_portrait_path(app,code):
    row=app.conn.execute('SELECT photo FROM clients WHERE code=?',(code,)).fetchone()
    path=resolve_client_media(app,code,row[0]) if row else None
    if path:return path
    rows=app.conn.execute("SELECT file_path FROM client_documents WHERE client_code=? AND document_type IN ('CIN_RECTO','PERMIS_RECTO') ORDER BY CASE document_type WHEN 'CIN_RECTO' THEN 0 ELSE 1 END,id DESC",(code,)).fetchall()
    return next((path for row in rows if (path:=resolve_client_media(app,code,row[0]))),None)


def build_client_rapide(app,win,q,commands):
    """Les commandes métier restent celles de Location rapide ; seul le rendu change."""
    for child in win.winfo_children():child.pack_forget()
    embedded=getattr(win,'_location_embedded',False)
    win.configure(bg=BG)
    if not embedded:
        win.title('GEST PRO — Location — Client rapide — V240.82')
        width=min(1536,win.winfo_screenwidth()-30);height=min(1024,win.winfo_screenheight()-70)
        win.geometry(f'{width}x{height}+10+10');win.minsize(1000,680)
    style=ttk.Style(win)
    style.configure('ClientRapide.TCombobox',padding=3,font=('Segoe UI',10),fieldbackground='#f8fbff')
    tabs_bar=tk.Frame(win,bg='#eaf4ff');tabs_bar.pack(fill='x')
    style.layout('ClientLocation.TNotebook.Tab',[])
    notebook=ttk.Notebook(win,style='ClientLocation.TNotebook');notebook.pack(fill='both',expand=True)
    tab_buttons=[]
    for index,(title,color,soft) in enumerate((('Contrat de location','#008d4b','#e5f5eb'),
            ('Historique du client','#0065ef','#e5f0ff'),('Historique global','#7153dc','#eee8ff'))):
        tab=ContractAction(tabs_bar,title,lambda i=index:notebook.select(i),soft,color)
        tab.configure(width=170 if index!=1 else 185,height=32)
        tab.pack(side='left',padx=3,pady=3);tab_buttons.append((tab,color,soft))
    signature_controls=tk.Frame(win,bg='#eaf4ff');signature_controls.pack(fill='x')
    signature_action=ContractAction(signature_controls,'✍ Signature électronique',commands['signature'],'#6b4bc3','white')
    signature_action.configure(width=175,height=32);signature_action.pack(side='left',padx=4,pady=3)
    signed_access=ContractAction(signature_controls,'✍ Contrat signé',lambda:app.open_signed_contract(q['numero'].get()), '#e4f4ed','#087f50')
    signed_access.configure(width=150,height=32);signed_access.pack(side='left',padx=5,pady=3)
    def color_tabs():
        current=notebook.index('current')
        for i,(tab,color,soft) in enumerate(tab_buttons):tab.configure(bg=color if i==current else soft,fg='white' if i==current else color)

    contract_page=tk.Frame(notebook,bg=BG);notebook.add(contract_page,text='Contrat de location')
    viewport=tk.Canvas(contract_page,bg=BG,highlightthickness=0)
    vertical=ttk.Scrollbar(contract_page,orient='vertical',command=viewport.yview)
    horizontal=ttk.Scrollbar(contract_page,orient='horizontal',command=viewport.xview)
    viewport.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
    viewport.grid(row=0,column=0,sticky='nsew');vertical.grid(row=0,column=1,sticky='ns');horizontal.grid(row=1,column=0,sticky='ew')
    contract_page.grid_rowconfigure(0,weight=1);contract_page.grid_columnconfigure(0,weight=1)
    root=tk.Frame(viewport,bg=BG)
    content=viewport.create_window(0,0,window=root,anchor='nw')
    def resize_viewport(event):
        viewport.itemconfigure(content,width=max(1100,event.width),height=max(850,event.height))
        viewport.configure(scrollregion=(0,0,max(1100,event.width),max(850,event.height)))
    viewport.bind('<Configure>',resize_viewport)
    viewport.bind('<MouseWheel>',lambda event:viewport.yview_scroll(-int(event.delta/120),'units'))
    history_trees={}
    archive_refreshes={}
    now=datetime.now()
    history_filters={};history_metrics={};pending_filters={}
    def schedule_filter(key):
        if key in pending_filters:root.after_cancel(pending_filters[key])
        def apply():pending_filters.pop(key,None);refresh_history(key,silent=True)
        pending_filters[key]=root.after(350,apply)
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
        archive_refreshes[key]=install_table_actions(app,page,'contracts',tree)
        def open_history(event,t=tree):
            selected=t.selection()
            if selected:
                app.contract_search_var.set(t.item(selected[0],'values')[0]);app.load_contract_lookup();app.preview_contract()
        from signed_contracts import install_signed_column
        install_signed_column(tree,app.open_signed_contract)
        from history_layout import fit_history_columns
        fit_history_columns(tree)
        def history_double(event,t=tree):
            if t.identify_column(event.x)=='#'+str(len(t['columns'])):return 'break'
            return open_history(event,t)
        tree.bind('<Double-1>',history_double)
        action=ContractAction(page,'Actualiser',lambda k=key:refresh_history(k),BLUE);action.configure(width=130,height=32);action.pack(pady=8)
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

    widgets=[];photos=[]
    # Use the unmodified supplied artwork for exact panel gradients, icons and borders.
    # Real editable controls and business actions are placed above it.
    from PIL import Image,ImageTk
    source_art=Image.new('RGB',(1536,1024),BG)
    artwork=tk.Label(root,bd=0,highlightthickness=0)
    artwork.place(x=0,y=0,relwidth=1,relheight=1)
    art_photo=[None]
    hit_areas=[]
    static_widgets=set()

    # All positions are measured in the 1536 x 1024 supplied reference.
    def position(widget,x,y,w,h,font=10):
        widgets.append((widget,x,y,w,h,font));return widget
    def frame(x,y,w,h,bg='white',border=True):
        from reservation_reference import _reservation_round
        widget=position(tk.Canvas(root,bg=BG,highlightthickness=0),x,y,w,h)
        def paint(event):
            widget.delete('all')
            if border:
                _reservation_round(widget,0,0,event.width,event.height,10,LINE)
                _reservation_round(widget,1,1,event.width-1,event.height-1,9,bg)
            else:_reservation_round(widget,0,0,event.width,event.height,9,bg)
        widget.bind('<Configure>',paint);return widget
    def label(text,x,y,w,h,size=10,bold=False,color=INK,bg=BG,var=None):
        widget=position(tk.Label(root,text=text,textvariable=var,bg=bg,fg=color,anchor='w',
                     font=('Segoe UI',size,'bold' if bold else 'normal')),x,y,w,h,size)

        return widget
    def button(text,command,x,y,w,h,color=BLUE,ink='white'):
        if h>=39:y+=(h-34)//2;h=34
        return position(ContractAction(root,text,command,color,ink),x,y,w,h)
    def entry(key,x,y,w,h=34,readonly=False,bg='#f8fbff'):
        holder=tk.Canvas(root,bg='white',highlightthickness=0,bd=0)
        e=tk.Entry(holder,textvariable=q[key],bg=bg,readonlybackground=bg,fg=INK,relief='flat',bd=0,
                   highlightthickness=0,font=('Segoe UI',10),state='readonly' if readonly else 'normal')
        e.place(x=7,y=3,relwidth=1,width=-14,relheight=1,height=-6)
        def draw(event,active=False):
            width=event.width;height=event.height;r=min(6,height/4)
            holder.delete('border')
            points=[r,1,width-r,1,width-1,1,width-1,r,width-1,height-r,width-1,height-1,width-r,height-1,
                    r,height-1,1,height-1,1,height-r,1,r,1,1]
            holder.create_polygon(points,smooth=True,splinesteps=20,fill=bg,outline='#2685dc' if active else '#c6d7e5',width=1,tags='border')
            holder.tag_lower('border');e.configure(font=('Segoe UI',max(9,round(10*height/34))))
        holder.bind('<Configure>',draw)
        e.bind('<FocusIn>',lambda _e:draw(type('Size',(),{'width':holder.winfo_width(),'height':holder.winfo_height()})(),True))
        e.bind('<FocusOut>',lambda _e:draw(type('Size',(),{'width':holder.winfo_width(),'height':holder.winfo_height()})()))
        position(holder,x,y,w,h);return e
    def combo(key,values,x,y,w,h=34,readonly=False):
        e=ttk.Combobox(root,textvariable=q[key],values=values,state='readonly' if readonly else 'normal',style='ClientRapide.TCombobox')
        return position(e,x,y,w,h)
    def panel(title,x,y,w,h):
        frame(x,y,w,h);frame(x,y,w,38,SOFT,False)
        label(title,x+14,y+4,w-28,30,12,True,BLUE,SOFT)
    def gradient(x,y,w,h,a,b):
        c=position(tk.Canvas(root,highlightthickness=0),x,y,w,h)
        def draw(e):
            c.delete('all');rgb1=tuple(int(a[i:i+2],16) for i in (1,3,5));rgb2=tuple(int(b[i:i+2],16) for i in (1,3,5))
            for i in range(0,e.width,4):
                ratio=i/max(1,e.width);color='#'+''.join(f'{round(u+(v-u)*ratio):02x}' for u,v in zip(rgb1,rgb2))
                c.create_rectangle(i,0,i+4,e.height,fill=color,outline=color)
        c.bind('<Configure>',draw);return c
    # Full app shell copied structurally from the image.
    gradient(0,0,1536,50,'#174e7a','#0089ec')
    label('🚘   GEST PRO - Client rapide',20,5,760,40,18,True,'white','#155b8b')
    clock=tk.StringVar(value=datetime.now().strftime('%d/%m/%Y   %H:%M'))
    label('',1130,10,300,30,10,False,'white','#0874bf',clock)
    frame(0,50,222,974,'#07375f',False)
    nav=[('⌂  Tableau de bord','dashboard'),('●  Location','contract'),('ϟ  Location rapide','quick_contract'),
         ('▦  Réservations','reservations'),('◴  Historique','history'),('♙  Clients','clients'),('●  Véhicules','vehicles'),
         ('▱  Gestion du parc','fleet_management'),('▦  Dépôt de parc','parking_deposits'),('⚒  Entretien','maintenance'),
         ('▧  Centre financier','financial_center'),('!  Produits & charges','expenses'),('!  Créances / Règlement','receivables'),
         ('△  Infractions','infractions'),('◷  Planning','planning'),('▣  Tâche libre','free_tasks'),('△  Centre d’alerte','alerts'),
         ('▧  Fournisseurs','suppliers'),('⚙  Paramètres','settings')]
    def navigate(target):
        if not embedded:win.grab_release();win.destroy()
        if target=='quick_contract':app.open_quick_contract_dialog()
        else:app.show_page(target)
    for i,(name,target) in enumerate(nav):
        button(name,lambda d=target:navigate(d),6,66+i*41,210,39,BLUE if target=='clients' else '#07375f')
    label('HBZ RENT CAR',40,930,170,28,11,True,'white','#07375f')
    frame(234,61,1292,46,'#edf7ff')
    button('＋  Nouveau contrat',commands['new'],732,61,180,46,'#009643')
    button('▣  Enregistrer',lambda:commands['save'](),922,61,141,46)
    button('▤  Supprimer',commands['delete'],1074,61,137,46,'#ff173b')
    button('▣  Imprimer',commands['print'],1222,61,125,46,'#e9f4ff',BLUE)
    button('▤  Exporter',commands['pdf'],1358,61,165,46,'#f4faff',INK)
    gradient(234,120,1292,52,'#034caf','#008ded')
    label('▤  CONTRAT DE LOCATION  -',251,129,355,33,15,True,'white','#075cc1')
    label('',605,129,420,33,15,True,'white','#0876d0',q['numero'])
    label('● EN COURS',1380,128,130,35,11,True,'#c57e00','#fff0c1')
    def load_client():
        commands['load_client']();code=q['client'].get().split('|')[0].strip()
        row=app.conn.execute('SELECT * FROM clients WHERE code=?',(code,)).fetchone()
        if row:
            for key,column in [('ref_cin','cin'),('ref_nom','nom'),('ref_prenom','prenom'),('ref_phone','telephone'),('ref_address','adresse')]:q[key].set(row[column] or '')
    def load_vehicle():
        commands['load_vehicle']();code=q['vehicle'].get().split('|')[0].strip()
        row=app.conn.execute('SELECT * FROM vehicles WHERE code=?',(code,)).fetchone()
        if not row:return
        model=str(row['modele'] or '');q['ref_brand'].set(model.split()[0] if model else '')
        q['ref_model'].set(model);q['ref_color'].set(row['couleur'] if 'couleur' in row.keys() else '')
        q['ref_year'].set(str(row['mise_circulation'] or '')[-4:] if 'mise_circulation' in row.keys() else '')
        path=app._resolve_vehicle_photo_path(row['photo'],code)
        if path:
            from PIL import Image,ImageTk
            im=Image.open(path).convert('RGB');im.thumbnail((185,135));photo=ImageTk.PhotoImage(im);photos.append(photo)
            vehicle_photo.configure(image=photo,text='')
    def live_label(*args,**kwargs):
        w=label(*args,**kwargs);static_widgets.discard(w);return w
    def live_panel(title,x,width):
        w=frame(x,183,width,233);static_widgets.discard(w)
        w=frame(x,183,width,38,SOFT,False);static_widgets.discard(w)
        live_label(title,x+10,188,180 if x==241 else width-20,28,10,True,BLUE,SOFT)
    live_panel('♙ Informations client',241,343)
    live_panel('♙ Deuxième conducteur',594,347)
    panel('🚘   Véhicule loué',951,183,572,233)
    client_ca=tk.StringVar(value='CA : 0,00 MAD');vehicle_ca=tk.StringVar(value='CA : 0,00 MAD')
    label('',432,188,143,28,9,True,'#16864b',SOFT,client_ca)
    label('',1210,188,264,28,10,True,'#16864b',SOFT,vehicle_ca)
    def refresh_turnover(*_):
        client_total,vehicle_total=client_vehicle_turnover(app.conn,q['client'].get().split('|')[0].strip(),q['vehicle'].get().split('|')[0].strip())
        def money(value):return f'{value:,.2f}'.replace(',',' ').replace('.',',')+' MAD'
        client_ca.set('CA : '+money(client_total));vehicle_ca.set('CA : '+money(vehicle_total))
    for key in ('client','vehicle'):q[key].trace_add('write',refresh_turnover)
    refresh_turnover()
    original_save=commands['save']
    def save_with_turnover():
        result=original_save();refresh_turnover();return result
    commands['save']=save_with_turnover
    fiches=ContractAction(tabs_bar,'Fiches clients',lambda:app.show_page('clients'),'#0065ef')
    fiches.configure(width=140,height=32);fiches.pack(side='right',padx=6,pady=3)
    win.bind('<Map>',refresh_turnover,add='+')
    portrait_labels={};portrait_images={};portrait_sources={}
    for x,key in ((251,'client'),(604,'second')):
        portrait_labels[key]=position(tk.Label(root,text='♙',bg='#e2eef8',fg='#77acd4',font=('Segoe UI',24)),x,239,90,140,24)
    live_label('Code client',350,229,75,27,bg='white')
    client=combo('client',commands['clients'],426,228,149,30)
    client.bind('<<ComboboxSelected>>',lambda _e:load_client());client.bind('<Return>',lambda _e:load_client())
    def choose_client():
        app.open_quick_client_dialog(lambda code:(q['client'].set(code),load_client()),initial_client=q['client'].get().split('|')[0].strip())
    client_access=ContractAction(tabs_bar,'Rechercher / ajouter client',choose_client,BLUE)
    client_access.configure(width=220,height=32);client_access.pack(side='right',padx=4,pady=3)
    search_job=[None]
    def suggest_client(_event=None):
        typed=q['client'].get().strip().casefold()
        if search_job[0]:root.after_cancel(search_job[0])
        def apply_search():
            search_job[0]=None
            choices=[]
            for row in app.conn.execute('SELECT code,nom,prenom,telephone,cin FROM clients'):
                if typed in ' '.join(str(v or '') for v in row).casefold():
                    choices.append(f"{row['code']} | {row['nom']} {row['prenom']} | {row['telephone']}")
            client.configure(values=choices[:60])
            exact=next((v for v in choices if v.split('|')[0].strip().casefold()==typed),None)
            if exact or len(choices)==1:
                q['client'].set((exact or choices[0]).split('|')[0].strip());load_client()
        search_job[0]=root.after(180,apply_search)
    client.bind('<KeyRelease>',suggest_client)

    for i,(text,key) in enumerate((('CIN','ref_cin'),('Nom *','ref_nom'),('Prénom *','ref_prenom'),('Téléphone','ref_phone'),('Adresse','ref_address'))):
        y=262+i*29;live_label(text,350,y,75,27,bg='white');entry(key,426,y,149,27)
    live_label('Code client 2',700,229,89,27,bg='white')
    second_box=combo('ref_second',('',*commands['clients']),790,228,141,30)
    def load_second(*_):
        code=q['ref_second'].get().split('|')[0].strip()
        row=app.conn.execute('SELECT * FROM clients WHERE code=?',(code,)).fetchone()
        for key,column in [('ref_second_name','nom'),('ref_second_cin','cin'),('ref_second_phone','telephone'),('ref_second_permis','permis')]:
            value=str(row[column] or '') if row and column in row.keys() else ''
            if key=='ref_second_name' and row:value+=' '+str(row['prenom'] or '')
            q[key].set(value)
        display_portrait(code,'second')
    second_box.bind('<<ComboboxSelected>>',load_second);second_box.bind('<Return>',load_second)
    for i,(text,key) in enumerate((('Nom / prénom','ref_second_name'),('CIN','ref_second_cin'),('Téléphone','ref_second_phone'),('Permis','ref_second_permis'))):
        y=270+i*30;live_label(text,700,y,89,27,bg='white');entry(key,790,y,141,27,True)
    second_docs=ContractAction(root,'Documents du conducteur',lambda:show_client_documents(q['ref_second'].get().split('|')[0].strip()),'#eaf5ff',BLUE)
    position(second_docs,604,389,327,25)
    def display_portrait(code,kind):
        target=portrait_labels[kind];target.configure(image='',text='♙');portrait_images.pop(kind,None);portrait_sources.pop(kind,None)
        path=client_portrait_path(app,code)
        if path:
            try:
                im=open_preview(path);portrait_sources[kind]=im.copy()
                width=target.winfo_width();height=target.winfo_height()
                im.thumbnail((max(12,width-2) if width>1 else 88,max(12,height-2) if height>1 else 138))
                photo=ImageTk.PhotoImage(im);portrait_images[kind]=photo
                target.configure(image=photo,text='')
            except Exception:pass
    def resolve_document(code,raw):return resolve_client_media(app,code,raw)
    def client_documents(code):
        try:rows=app.conn.execute('SELECT document_type,file_path FROM client_documents WHERE client_code=? ORDER BY id DESC',(code,)).fetchall()
        except Exception:return []
        return [(r[0],path) for r in rows if (path:=resolve_document(code,str(r[1] or '')))]
    def open_preview(path):
        if path.suffix.lower()=='.pdf':
            import fitz
            with fitz.open(path) as pdf:
                pix=pdf[0].get_pixmap(matrix=fitz.Matrix(1,1))
                return Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
        return Image.open(path).convert('RGB')
    def show_client_documents(code):
        docs=client_documents(code)
        popup=tk.Toplevel(win);popup.title('Documents du client '+code);popup.geometry('640x500');popup.configure(bg=BG)
        popup.transient(win.winfo_toplevel())
        if not docs:tk.Label(popup,text='Aucun document scanné pour ce client.',bg=BG,fg=INK).pack(pady=25)
        canvas=tk.Canvas(popup,bg=BG,highlightthickness=0)
        scrollbar=ttk.Scrollbar(popup,orient='vertical',command=canvas.yview)
        scrollbar.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        canvas.configure(yscrollcommand=scrollbar.set)
        content=tk.Frame(canvas,bg=BG);item=canvas.create_window((0,0),window=content,anchor='nw')
        content.bind('<Configure>',lambda _e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(item,width=e.width))
        keep=[]
        for kind,path in docs:
            row=tk.Frame(content,bg='white');row.pack(fill='x',padx=8,pady=3)
            try:
                im=open_preview(path);im.thumbnail((80,65));photo=ImageTk.PhotoImage(im);keep.append(photo)
                tk.Label(row,image=photo,bg='white').pack(side='left')
            except Exception:pass
            tk.Button(row,text=kind+' · '+path.name,command=lambda p=path:webbrowser.open(p.resolve().as_uri()),bg='#eaf5ff',fg=BLUE,relief='flat').pack(side='left',fill='x',expand=True,padx=8)
        popup._document_images=keep
    vehicle_photo=position(tk.Label(root,text='🚘',bg='#edf1f3',fg=BLUE,font=('Segoe UI',42)),964,231,193,143,42)
    for i,(text,key) in enumerate([('Immatriculation','vehicle'),('Marque','ref_brand'),('Modèle','ref_model'),('Année','ref_year'),('Couleur','ref_color'),('Kilométrage départ','km_start')]):
        y=231+i*30;label(text,1189,y,143,26,bg='white')
        if key=='vehicle':
            v=combo(key,commands['vehicles'],1333,y,175,26);v.bind('<<ComboboxSelected>>',lambda _e:load_vehicle());v.bind('<Return>',lambda _e:load_vehicle())
        else:entry(key,1333,y,175,26,readonly=key!='km_start')
    button('⌕',commands['choose_vehicle'],1480,188,32,27,'#eaf5ff',BLUE)
    label('Carburant',964,379,92,27,bg='white')
    fuel_buttons=[]
    def set_fuel(level):q['ref_fuel'].set(str(level))
    def paint_fuel(*_):
        try:level=max(0,min(8,int(q['ref_fuel'].get())))
        except ValueError:level=0
        from contract_print_details import FUEL_COLORS
        for i,bar in enumerate(fuel_buttons,1):bar.configure(bg=FUEL_COLORS[i-1] if i<=level else '#d6e6f3')
    button('0',lambda:set_fuel(0),1055,382,22,22,'#e3f2ff',BLUE)
    for i in range(1,9):
        bar=button('',lambda n=i:set_fuel(n),1078+(i-1)*10,382,7,22,'#009642')
        fuel_buttons.append(bar)
    q['ref_fuel'].trace_add('write',paint_fuel);paint_fuel()
    panel('▦   Détails du contrat' ,241,428,657,302)
    panel('▤   Tarification',911,428,324,302)
    panel('$   Statut et paiement',1250,428,273,302)
    for text,x,y in [('Date de départ *',258,482),('Heure départ',563,482),('Date de retour prévue *',258,526),('Heure retour',563,526),('Durée (jours)',258,569),('Type de location',563,569),('Lieu de départ',258,612),('Lieu de retour',258,655)]:
        label(text,x,y,138,29,bg='white')
    for key,x,y,w in [('start',397,481,145),('end',397,525,145),('duration',397,568,145),('start_time',709,481,171),('end_time',709,525,171)]:
        e=entry(key,x,y,w,34,readonly=key=='duration')
        if key in ('start','end'):app._attach_date_picker(e,q[key])
    combo('ref_type',('Location classique','Longue durée'),709,568,171,readonly=True)
    from company_agencies import AgencyStore,open_agencies
    agencies=AgencyStore(app.conn)
    def agency_names():return tuple(r['name'] for r in agencies.list()) or ('Agence Tanger','Agence principale')
    depart=combo('ref_depart',agency_names(),397,610,483)
    retour=combo('ref_return',agency_names(),397,652,483)
    def refresh_agencies():depart.configure(values=agency_names());retour.configure(values=agency_names())
    def agency_window():open_agencies(win,agencies,refresh_agencies)
    button('▰ Importer',lambda:document('AUTRE'),241,61,132,46,'#e3f2ff',BLUE)
    button('▦ Agences',agency_window,381,61,132,46,'#6950f1','white')
    button('✉ Email agence',agency_window,521,61,180,46,'#009642','white')
    label('Chauffeur',258,691,128,28,bg='white')
    for text,value,x in [('Avec chauffeur','Avec chauffeur',398),('Sans chauffeur','Sans chauffeur',562)]:
        position(tk.Radiobutton(root,text=text,value=value,variable=q['ref_driver'],bg='white',fg=INK,font=('Segoe UI',10)),x,688,160,30)
    price_fields=[('Prix journalier (DH)','price'),('Nombre de jours','ref_days'),('Montant total (DH)','ref_gross'),('Réduction (DH)','ref_discount'),('Caution (DH)','ref_deposit'),('Assurance (DH)','ref_insurance'),('Montant net (DH)','total')]
    for i,(text,key) in enumerate(price_fields):
        y=480+i*35;label(text,927,y,142,30,10,i in (2,6),bg='white')
        e=entry(key,1064,y,156,31,readonly=key in ('ref_days','ref_gross','total'),bg='#ddf5ec' if key=='total' else '#e5f2ff' if key=='ref_gross' else '#f8fbff')
    label('Statut du contrat',1267,480,235,26,10,True,bg='white')
    combo('ref_state',('En cours',),1267,503,241,35,True)
    label('Mode de paiement',1267,551,235,25,10,True,bg='white')
    combo('payment_mode',('ESPÈCES','CHÈQUE','VIREMENT'),1267,576,241,35,True)
    label('Montant payé (DH)',1267,626,130,32,10,True,bg='white');entry('paid',1385,621,123,38)
    label('Reste dû (DH)',1267,665,125,36,10,True,'#ed163b','white');entry('balance',1385,662,123,38,True,'#ffe8ed')
    panel('▤   Conditions / Observations',241,741,702,172)
    panel('▰   Documents du contrat',955,741,568,172)
    button('Dossier client',lambda:show_client_documents(q['client'].get().split('|')[0].strip()),1365,746,142,27,SOFT,BLUE)
    label('Conditions particulières',256,785,335,23,bg='white');label('Observations',637,785,285,23,bg='white')
    conditions=position(tk.Text(root,bg='#fbfdff',fg=INK,relief='solid',bd=1,font=('Segoe UI',10),wrap='word'),256,809,367,87)
    observations=position(tk.Text(root,bg='#fbfdff',fg=INK,relief='solid',bd=1,font=('Segoe UI',10),wrap='word'),637,809,294,87)
    conditions.insert('1.0',q['ref_conditions'].get());observations.insert('1.0',q['ref_notes'].get())
    def document(kind):
        path=filedialog.askopenfilename(parent=win,title=kind,filetypes=[('Documents','*.pdf *.png *.jpg *.jpeg'),('Tous','*.*')])
        if path:
            folder=Path(__file__).resolve().parent/'documents_contrats'/q['numero'].get().strip()
            folder.mkdir(parents=True,exist_ok=True)
            destination=folder/(kind+'_'+Path(path).name)
            if Path(path).resolve()!=destination.resolve():shutil.copy2(path,destination)
            q['ref_doc_'+kind].set(str(destination));doc_labels[kind].configure(text=destination.name)
            messagebox.showinfo('Document joint',f'{kind} : {destination.name}',parent=win)
    def open_document(kind):
        path=q['ref_doc_'+kind].get()
        if path and Path(path).is_file():webbrowser.open(Path(path).resolve().as_uri())
        elif kind in ('CIN','PERMIS'):show_client_documents(q['client'].get().split('|')[0].strip())
    doc_labels={}
    for i,kind in enumerate(('CIN','PERMIS','CONTRAT','AUTRE')):
        y=786+i*32;label({'CIN':"Carte nationale d’identité",'PERMIS':'Permis de conduire','CONTRAT':'Contrat signé','AUTRE':'Autres documents'}[kind],970,y,292,27,bg='white')
        doc_labels[kind]=button('▰  Choisir un fichier',lambda k=kind:document(k),1281,y,158,26,'#edf6ff',BLUE)
        button('◉',lambda k=kind:open_document(k),1460,y,48,26,'#edf6ff',BLUE)
    frame(241,928,1282,86,'#f4faff')
    label('ϟ   Actions rapides',255,921,380,28,12,True,BLUE)
    def save_new():
        if commands['save']():commands['new']()
    def mail():
        code=q['client'].get().split('|')[0].strip();r=app.conn.execute('SELECT email FROM clients WHERE code=?',(code,)).fetchone()
        if r and r[0]:webbrowser.open('mailto:'+quote(r[0])+'?subject='+quote('Contrat '+q['numero'].get()))
        else:messagebox.showinfo('Email','Ajoutez une adresse email dans la fiche client.',parent=win)
    for text,fn,x,w,color,ink in [('Enregistrer + nouveau',save_new,251,175,'#009642','white'),('Imprimer',commands['print'],435,100,BLUE,'white'),('Scanner',lambda:app.open_scan_center(q['client'].get().split('|')[0].strip()),544,100,'#e3f2ff',BLUE),('Envoyer par email',mail,653,145,'#6950f1','white'),('▣  Dupliquer',commands['duplicate'],807,115,'#ff9d00','white'),('×  Annuler',lambda:app.show_page('dashboard') if embedded else win.destroy(),931,100,'#ffe9eb','#ed1537')]:
        button(text,fn,x,954,w,45,color,ink)
    button('Enregistrer en PDF',commands['recto_pdf'],1040,954,155,45,'#0065ef','white')
    button('✍ Signature électronique',commands['signature'],1204,954,175,45,'#6b4bc3','white')
    button('WhatsApp',commands['whatsapp'],1388,954,120,45,'#159447','white')
    status=label('',240,1014,1280,10,8,False,INK,BG,q['status'])
    def redraw(e):
        if e.widget is not root:return
        ox,oy=(234,61) if embedded else (0,0)
        logical_width,logical_height=(1302,963) if embedded else (1536,1024)
        sx=e.width/logical_width;sy=e.height/logical_height;scale=min(sx,sy)
        art_photo[0]=ImageTk.PhotoImage(source_art.crop((ox,oy,1536,1024)).resize((max(1,e.width),max(1,e.height)),Image.Resampling.LANCZOS))
        artwork.configure(image=art_photo[0]);artwork.lower()
        for kind,source in portrait_sources.items():
            image=source.copy();image.thumbnail((max(12,round(90*sx)-2),max(12,round(140*sy)-2)))
            photo=ImageTk.PhotoImage(image);portrait_images[kind]=photo;portrait_labels[kind].configure(image=photo,text='')
        for widget,x,y,w,h,size in widgets:
            if embedded and (x<234 or y<61):widget.place_forget();continue
            widget.place(x=round((x-ox)*sx),y=round((y-oy)*sy),width=round(w*sx),height=round(h*sy))
            if 'font' in widget.keys():
                old=widget.cget('font');bold='bold' in str(old)
                widget.configure(font=('Segoe UI',max(8,round(size*scale)),'bold' if bold else 'normal'))
    root.bind('<Configure>',redraw)
    def hit(e):
        ox,oy=(234,61) if embedded else (0,0)
        sx=max(1,root.winfo_width())/(1302 if embedded else 1536);sy=max(1,root.winfo_height())/(963 if embedded else 1024)
        x=e.x/sx+ox;y=e.y/sy+oy
        for left,top,width,height,fn in reversed(hit_areas):
            if left<=x<=left+width and top<=y<=top+height:fn();return
    hit_areas.append((888,318,39,32,lambda:webbrowser.open('tel:'+quote(q['ref_phone'].get().replace(' ','')))))
    artwork.bind('<Button-1>',hit)
    def pointer(e):
        sx=max(1,root.winfo_width())/1536;sy=max(1,root.winfo_height())/1024
        inside=any(x<=e.x/sx<=x+w and y<=e.y/sy<=y+h for x,y,w,h,_ in hit_areas)
        artwork.configure(cursor='hand2' if inside else '')
    artwork.bind('<Motion>',pointer)
    def sync_text():
        q['ref_conditions'].set(conditions.get('1.0','end-1c'));q['ref_notes'].set(observations.get('1.0','end-1c'))
    def update_vehicle_labels(*_):
        code=q['vehicle'].get().split('|')[0].strip()
        row=app.conn.execute('SELECT * FROM vehicles WHERE code=?',(code,)).fetchone()
        if row:
            q['ref_model'].set(row['modele'] or '');q['ref_brand'].set(str(row['modele'] or '').split(' ')[0])
    q['vehicle'].trace_add('write',update_vehicle_labels)
    for key,picture in portrait_labels.items():picture.bind('<Button-1>',lambda _e,k=key:show_client_documents(q['client' if k=='client' else 'ref_second'].get().split('|')[0].strip()))
    win._client_rapide_sync=sync_text
    win._client_rapide_reload=load_client
    win._client_portrait_images=portrait_images
    win._location_number_var=q['numero']
    original_load_client=load_client
    def load_client():
        original_load_client()
        code=q['client'].get().split('|')[0].strip()
        display_portrait(code,'client')
        for kind in ('CIN','PERMIS'):
            path=next((p for dtype,p in client_documents(code) if dtype==kind or dtype.startswith(kind+'_')),None)
            current=q['ref_doc_'+kind].get().replace('\\','/')
            if '/documents_contrats/' not in current:q['ref_doc_'+kind].set(str(path) if path else '')
    hit_areas.append((251,229,57,60,lambda:show_client_documents(q['client'].get().split('|')[0].strip())))
    win._client_rapide_reload=load_client
    win._client_portrait_images=portrait_images
    win._location_number_var=q['numero']
    load_client();load_second();load_vehicle();commands['calculate']()
    return root
