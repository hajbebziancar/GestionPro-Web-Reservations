"""Saisie client centrale et historique, avec scans individuels et PDF associé."""
import io,json,os,shutil,webbrowser,tempfile
from pathlib import Path,PureWindowsPath
from datetime import datetime,date
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from PIL import Image,ImageTk,ImageOps
BLUE='#0564ce';NAVY='#103d73';BG='#f0f7fe';INK='#173351';GREEN='#039c7b';EDGE='#c9deef'
KEYS=('code','cin','nom','prenom','adresse','date_naissance','telephone','permis','date_permis','profession','observations')
FACES=('CIN_RECTO','CIN_VERSO','PERMIS_RECTO','PERMIS_VERSO')

def render_preview(path,size,page=0):
    """Only file/PIL work here; all Tk updates stay on the UI thread."""
    path=Path(path);total=1;page=0 if path.suffix.lower()!='.pdf' else page
    if path.suffix.lower()=='.pdf':
        import fitz
        with fitz.open(path) as doc:
            total=len(doc);page=max(0,min(page,total-1));rect=doc[page].rect
            scale=min(size[0]/max(1,rect.width),size[1]/max(1,rect.height))*2
            pix=doc[page].get_pixmap(matrix=fitz.Matrix(scale,scale))
            pic=Image.open(io.BytesIO(pix.tobytes('png'))).convert('RGB')
    else:
        with Image.open(path) as im:pic=ImageOps.exif_transpose(im).copy()
    pic.thumbnail(size,Image.Resampling.LANCZOS)
    return pic,page,total

def parse_date(value):
    value=str(value or '').strip()
    if not value:return None
    for fmt in ('%d/%m/%Y','%Y-%m-%d'):
        try:return datetime.strptime(value[:10],fmt).date()
        except ValueError:pass
    raise ValueError('Date invalide : utilisez JJ/MM/AAAA.')

def years_since(value,today=None):
    try:d=parse_date(value)
    except ValueError:return ''
    if not d:return ''
    today=today or date.today()
    if d>today:return ''
    return str(today.year-d.year-((today.month,today.day)<(d.month,d.day)))

def history_rows(conn,code,start='',end='',needle=''):
    lo=parse_date(start);hi=parse_date(end)
    if lo and hi and lo>hi:raise ValueError('La date Du doit précéder la date Au.')
    rows=[]
    for record in conn.execute('SELECT c.*,v.modele,v.immatriculation,v.photo AS vehicle_photo FROM contracts c LEFT JOIN vehicles v ON v.code=c.vehicle_code WHERE c.client_code=? OR c.second_code=?',(code,code)):
        r=dict(record)
        try:d=parse_date(r['date_depart'])
        except ValueError:d=None
        if lo and (not d or d<lo) or hi and (not d or d>hi):continue
        if needle.casefold() not in ' '.join(str(r.get(k) or '') for k in ('numero','modele','vehicle_code','immatriculation')).casefold():continue
        rows.append(r)
    def sort_key(r):
        try:d=parse_date(r['date_depart'])
        except ValueError:d=None
        return d or date.min,str(r['numero'])
    return sorted(rows,key=sort_key,reverse=True)

def metrics(rows):
    total=sum(float(r.get('montant') or 0) for r in rows);days=sum(max(0,int(r.get('duree') or 0)) for r in rows);n=len(rows)
    return total,n,days,total/n if n else 0,total/days if days else 0

def save_record(app,values,existing_code=None):
    data={k:str(values.get(k,'')).strip() for k in KEYS}
    for key in ('code','cin','nom','prenom','telephone'):
        if not data[key]:raise ValueError('Renseignez '+{'code':'le code','cin':'la CIN','nom':'le nom','prenom':'le prénom','telephone':'le téléphone'}[key]+'.')
    for key in ('date_naissance','date_permis'):
        d=parse_date(data[key])
        if d and d>date.today():raise ValueError('La date ne peut pas être dans le futur.')
        if d:data[key]=d.strftime('%d/%m/%Y')
    if app.conn.execute('SELECT code FROM clients WHERE UPPER(TRIM(cin))=UPPER(?) AND code<>?',(data['cin'],data['code'])).fetchone():raise ValueError('Cette CIN appartient déjà à un autre client.')
    old=app.conn.execute('SELECT * FROM clients WHERE code=?',(data['code'],)).fetchone()
    if old and existing_code!=data['code']:raise ValueError('Code déjà utilisé. Recherchez le client avant de le modifier.')
    if old:
        keys=[k for k in KEYS if k!='code'];app.conn.execute('UPDATE clients SET '+','.join(k+'=?' for k in keys)+' WHERE code=?',[data[k] for k in keys]+[data['code']])
    else:
        data['date_enregistrement']=date.today().strftime('%d/%m/%Y');keys=list(data)
        app.conn.execute('INSERT INTO clients('+','.join(keys)+') VALUES('+','.join('?' for _ in keys)+')',list(data.values()))
    return data['code']

class QuickClient:
    def __init__(self,app,on_select=None,initial_client=''):
        self.app=app;self.callback=on_select;self.loaded=None;self.images={};self.pending={};self.results={};self.rows={};self.refresh_job=None;self.preview_poll=None;self.preview_jobs={};self.preview_cache={};self.preview_worker=ThreadPoolExecutor(max_workers=1);self.closed=False;self.history_dirty=True;self.brand_paths={}
        w=self.win=tk.Toplevel(app.root);w.withdraw();w.title('Client rapide · Saisie et historique');w.configure(bg=BG);w.transient(app.root)
        app.root.update_idletasks();sw=w.winfo_screenwidth();sh=w.winfo_screenheight();width=min(1140,sw-70);height=min(790,sh-95)
        x=max(0,min(sw-width,app.root.winfo_rootx()+(app.root.winfo_width()-width)//2));y=max(0,min(sh-height,app.root.winfo_rooty()+(app.root.winfo_height()-height)//2))
        w.geometry(f'{width}x{height}+{x}+{y}');w.minsize(min(960,width),min(630,height));w.protocol('WM_DELETE_WINDOW',self.close);w.bind('<Escape>',lambda e:self.close());w.columnconfigure(0,weight=1);w.rowconfigure(3,weight=1)
        self.v={k:tk.StringVar(w) for k in KEYS};self.age=tk.StringVar(w);self.seniority=tk.StringVar(w);self.active=tk.BooleanVar(w,value=True)
        for k in ('date_naissance','date_permis'):self.v[k].trace_add('write',self.ages)
        header=tk.Frame(w,bg=BLUE);header.grid(row=0,column=0,sticky='ew');header.columnconfigure(0,weight=1)
        tk.Label(header,text='Client rapide · Saisie et historique',bg=BLUE,fg='white',font=('Segoe UI',19,'bold'),anchor='w').grid(row=0,column=0,padx=20,pady=14)
        self.btn(header,'Fermer',self.close,BLUE,'close').grid(row=0,column=1,padx=12)
        search=tk.Frame(w,bg='#e5f0fe');search.grid(row=1,column=0,sticky='ew',padx=12,pady=8);search.columnconfigure(1,weight=1)
        tk.Label(search,text='⌕  Rechercher un client',bg='#e5f0fe',fg=NAVY,font=('Segoe UI',11,'bold')).grid(row=0,column=0,padx=8)
        self.query=tk.StringVar(w);entry=self.entry(search,self.query);entry.grid(row=0,column=1,sticky='ew',padx=8,pady=6);entry.bind('<Return>',lambda e:self.search());self.query.trace_add('write',self.schedule_search)
        self.btn(search,'Rechercher',self.search,BLUE,'search').grid(row=0,column=2,padx=6)
        self.matches=ttk.Combobox(search,state='readonly');self.matches.grid(row=1,column=1,columnspan=2,sticky='ew',padx=8,pady=(0,6));self.matches.bind('<<ComboboxSelected>>',lambda e:self.load(self.results[self.matches.get()]))
        style=ttk.Style(w);style.configure('QuickClient.TNotebook.Tab',padding=(15,7),font=('Segoe UI',10,'bold'));style.configure('QuickClient.Treeview',rowheight=37,font=('Segoe UI',9));style.configure('QuickClient.Treeview.Heading',font=('Segoe UI',9,'bold'))
        self.book=ttk.Notebook(w,style='QuickClient.TNotebook');self.book.grid(row=3,column=0,sticky='nsew',padx=12,pady=(0,10))
        self.form=tk.Frame(self.book,bg=BG);self.history=tk.Frame(self.book,bg=BG);self.book.add(self.form,text='  Saisie client  ');self.book.add(self.history,text='  Historique des locations  ');self.book.bind('<<NotebookTabChanged>>',self.tab_changed)
        style.layout('QuickClient.TNotebook.Tab',[])
        tabbar=tk.Frame(w,bg=BG);tabbar.grid(row=2,column=0,sticky='ew',padx=12,pady=(0,4));self.tabbuttons=[]
        for i,(title,color,frame) in enumerate([('Saisie client',BLUE,self.form),('Historique des locations',GREEN,self.history)]):
            button=self.btn(tabbar,title,lambda f=frame:self.book.select(f),color,'clients' if i==0 else 'history');button.pack(side='left',padx=(0,5));self.tabbuttons.append(button)
        self.build_form();self.build_history();self.reset()
        if initial_client:self.load(str(initial_client).split('|')[0].strip())
        w.deiconify();self.present()
    def present(self):
        # Attach to the active rental dialog so Windows keeps the client above it.
        previous=self.win.grab_current()
        if previous is not self.win:
            self.previous_grab=previous
            focused=self.app.root.focus_get()
            parent=(previous or focused or self.app.root).winfo_toplevel()
            if parent is self.win:parent=self.app.root
            self.dialog_parent=parent
            self.win.transient(parent)
        self.win.deiconify()
        self.win.lift()
        self.win.grab_set()
        self.win.focus_set()
    def icon(self,name,size=20):
        key=(name,size)
        if key not in self.images:
            file=Path(__file__).parent/'assets'/'check_express'/(name+'.png')
            if not file.exists():file=Path(__file__).parent/'assets'/'check_express'/'paper.png'
            pic=Image.open(file);pic.thumbnail((size,size));self.images[key]=ImageTk.PhotoImage(pic,master=self.win)
        return self.images[key]
    def btn(self,parent,text,cmd,color=BLUE,icon='paper'):
        return tk.Button(parent,text=' '+text,image=self.icon(icon),compound='left',command=cmd,bg=color,fg='white' if color not in ('#e6edf5','white') else INK,relief='flat',bd=0,padx=9,pady=7,font=('Segoe UI',9,'bold'),cursor='hand2')
    def entry(self,parent,var,readonly=False,tint='white'):
        return tk.Entry(parent,textvariable=var,width=12,relief='flat',highlightthickness=1,highlightbackground=EDGE,highlightcolor=BLUE,bg=tint,readonlybackground=tint,fg=INK,state='readonly' if readonly else 'normal',font=('Segoe UI',10))
    def section(self,parent,title,icon='paper'):
        frame=tk.Frame(parent,bg='white',highlightbackground=EDGE,highlightthickness=1)
        tk.Label(frame,text=' '+title,image=self.icon(icon),compound='left',bg='#e0edff',fg=NAVY,font=('Segoe UI',11,'bold'),anchor='w',padx=8,pady=7).pack(fill='x')
        body=tk.Frame(frame,bg='white');body.pack(fill='both',expand=True,padx=9,pady=6);return frame,body
    def field(self,body,title,key,row,icon='paper',readonly=False,tint='white'):
        tk.Label(body,text=' '+title,image=self.icon(icon,17),compound='left',bg='white',fg=INK,font=('Segoe UI',9,'bold'),anchor='w').grid(row=row,column=0,sticky='w',padx=4,pady=2)
        widget=self.entry(body,self.v[key],readonly,tint);widget.grid(row=row,column=1,sticky='ew',padx=5,pady=2,ipady=3)
        if key=='code':
            widget.configure(width=7,justify='center',font=('Segoe UI',16,'bold'),bg='#fff0b3',readonlybackground='#fff0b3',fg=NAVY,highlightbackground='#e6c76c')
            widget.grid_configure(sticky='w',ipady=3)
        if key in ('date_naissance','date_permis') and hasattr(self.app,'_attach_date_picker'):self.app._attach_date_picker(widget,self.v[key])
        return widget
    def build_form(self):
        self.form.columnconfigure(0,weight=1,uniform='quick');self.form.columnconfigure(1,weight=1,uniform='quick');self.form.rowconfigure(0,weight=1)
        left=tk.Frame(self.form,bg=BG);left.grid(row=0,column=0,sticky='nsew',padx=(5,4),pady=5);left.columnconfigure(0,weight=1)
        identity,body=self.section(left,'Informations client','clients');identity.grid(row=0,column=0,sticky='nsew');body.columnconfigure(1,weight=1)
        for i,(label,key,icon) in enumerate([('Code client *','code','paper'),('N° Carte nationale *','cin','paper'),('Nom *','nom','clients'),('Prénom *','prenom','clients'),('Adresse','adresse','bank'),('Date de naissance','date_naissance','calendar'),('Téléphone *','telephone','clients')]):self.field(body,label,key,i,icon,key=='code','#e8eff7' if key=='code' else 'white')
        agebar=tk.Frame(body,bg='#e4f8d9');agebar.grid(row=5,column=0,sticky='ew',padx=4,pady=2);tk.Label(agebar,text='Âge',bg='#e4f8d9',fg=NAVY,font=('Segoe UI',9,'bold')).pack(side='left',padx=8);ageentry=self.entry(agebar,self.age,True,'#e4f8d9');ageentry.configure(width=3);ageentry.pack(side='left',fill='x',expand=True);tk.Label(agebar,text='ans',bg='#e4f8d9',fg=NAVY,font=('Segoe UI',9)).pack(side='left',padx=7)
        permit,pb=self.section(left,'Permis de conduire','draft_blue');permit.grid(row=1,column=0,sticky='ew',pady=(8,0));pb.columnconfigure(1,weight=1)
        self.field(pb,'N° Permis','permis',0);self.field(pb,'Date d’obtention','date_permis',1,'calendar')
        tk.Label(pb,text='Ancienneté (ans)',bg='#e4f8d9',fg=NAVY,font=('Segoe UI',9,'bold')).grid(row=2,column=0,sticky='ew');senioritybox=tk.Frame(pb,bg='white');senioritybox.grid(row=2,column=1,sticky='w',padx=5);seniorityentry=self.entry(senioritybox,self.seniority,True,'#e4f8d9');seniorityentry.configure(width=3,justify='center');seniorityentry.pack(side='left',ipady=4);tk.Label(senioritybox,text='ans',bg='white',fg=INK,font=('Segoe UI',9)).pack(side='left',padx=5)
        right=tk.Frame(self.form,bg=BG);right.grid(row=0,column=1,sticky='nsew',padx=(4,5),pady=5);right.columnconfigure(0,weight=1);right.rowconfigure(0,weight=1)
        documents,db=self.section(right,'Aperçus des documents · recto / verso','scan');documents.grid(row=0,column=0,sticky='nsew');self.previews={}
        for i,kind in enumerate(FACES):
            db.columnconfigure(i,weight=1,uniform='faces');tile=tk.Frame(db,bg='#f8fbff',highlightbackground=EDGE,highlightthickness=1);tile.grid(row=0,column=i,sticky='nsew',padx=2)
            tk.Label(tile,text=kind.replace('_','\n').replace('PERMIS','Permis'),bg='#f8fbff',fg=NAVY,font=('Segoe UI',9,'bold')).pack(pady=5)
            label=tk.Label(tile,text='Aucun scan',bg='#f8fbff',fg='#7891a9',height=5,width=1);label.pack(fill='both',expand=True,padx=2);label.bind('<Button-1>',lambda e,k=kind:self.open_face(k));self.previews[kind]=label
            self.btn(tile,'Scanner',lambda k=kind:self.scan(k),GREEN,'scan').pack(fill='x',padx=3,pady=2)
            self.btn(tile,'Importer',lambda k=kind:self.import_face(k),BLUE,'paper').pack(fill='x',padx=3,pady=(0,5))
        tk.Label(db,text='CIN recto / verso et permis recto / verso\narchivés en un seul PDF à l’enregistrement.',bg='#e0edff',fg=NAVY,font=('Segoe UI',10),wraplength=420,pady=10).grid(row=1,column=0,columnspan=4,sticky='ew',pady=8)
        pdfbox=tk.Frame(db,bg='#f3f8ff',highlightbackground=EDGE,highlightthickness=1);pdfbox.grid(row=2,column=0,columnspan=4,sticky='ew');pdfbox.columnconfigure(1,weight=1)
        self.pdf_preview_label=tk.Label(pdfbox,text='Aucun PDF',bg='#f3f8ff',fg=INK,width=12,height=5);self.pdf_preview_label.grid(row=0,column=0,rowspan=3,padx=5,pady=4);self.pdf_preview_label.bind('<Button-1>',lambda e:self.open_preview_pdf())
        tk.Label(pdfbox,text='Aperçu du document PDF du client',bg='#f3f8ff',fg=NAVY,font=('Segoe UI',9,'bold'),anchor='w').grid(row=0,column=1,sticky='ew',padx=5)
        self.pdf_selector=ttk.Combobox(pdfbox,state='readonly',width=24);self.pdf_selector.grid(row=1,column=1,sticky='ew',padx=5);self.pdf_selector.bind('<<ComboboxSelected>>',lambda e:self.show_pdf_page(0))
        controls=tk.Frame(pdfbox,bg='#f3f8ff');controls.grid(row=2,column=1,sticky='w',pady=4)
        self.btn(controls,'◀',lambda:self.show_pdf_page(self.pdf_page-1),BLUE,'pdf').pack(side='left',padx=2)
        self.pdf_page_text=tk.StringVar(self.win,value='—');tk.Label(controls,textvariable=self.pdf_page_text,bg='#f3f8ff',fg=INK,font=('Segoe UI',9)).pack(side='left',padx=4)
        self.btn(controls,'▶',lambda:self.show_pdf_page(self.pdf_page+1),BLUE,'pdf').pack(side='left',padx=2)
        self.btn(controls,'Ouvrir PDF',self.open_preview_pdf,BLUE,'pdf').pack(side='left',padx=2)
        self.btn(controls,'Ajouter PDF',self.import_client_pdf,GREEN,'plus').pack(side='left',padx=2)
        self.pdf_files=[];self.pdf_page=0
        extra,eb=self.section(right,'Autres informations','notes');extra.grid(row=1,column=0,sticky='ew',pady=(8,0));eb.columnconfigure(1,weight=1);self.field(eb,'Profession','profession',0,'bank');self.field(eb,'Observation','observations',1,'notes')
        footer=tk.Frame(self.form,bg=BG);footer.grid(row=1,column=0,columnspan=2,sticky='ew',padx=8,pady=7)
        tk.Checkbutton(footer,text='Client actif',variable=self.active,bg=BG,fg=INK).pack(side='left')
        self.btn(footer,'Enregistrer',self.save,GREEN,'save').pack(side='right',padx=4);self.btn(footer,'Annuler',self.close,BLUE,'clear').pack(side='right',padx=4);self.btn(footer,'Nouveau / réinitialiser',self.reset,'#e6edf5','new').pack(side='right',padx=4)
        self.btn(footer,'Utiliser ce client',self.use,GREEN,'plus').pack(side='left',padx=8)
        self.btn(footer,'Contrat rapide',self.contract,GREEN,'draft_blue').pack(side='left',padx=4)
        self.btn(footer,'Ajouter une réservation',self.reservation,BLUE,'plus').pack(side='left',padx=4)
        self.btn(footer,'Documents PDF',self.pdfs,BLUE,'pdf').pack(side='left',padx=4)
    def build_history(self):
        h=self.history;h.columnconfigure(0,weight=25);h.columnconfigure(1,weight=75);h.rowconfigure(0,weight=1)
        side,sb=self.section(h,'Informations client','clients');side.grid(row=0,column=0,sticky='nsew',padx=5,pady=5);self.info=tk.StringVar(self.win)
        tk.Label(sb,textvariable=self.info,bg='white',fg=INK,font=('Segoe UI',10),justify='left',anchor='nw',wraplength=205).pack(fill='x',pady=8)
        self.history_faces={}
        for kind in ('CIN_RECTO','PERMIS_RECTO'):
            label=tk.Label(sb,bg='white',height=4);label.pack(fill='x',pady=3);self.history_faces[kind]=label
        for title,cmd,color,icon in [('Fiche client',lambda:self.book.select(self.form),BLUE,'clients'),('Établir un contrat',self.contract,GREEN,'plus'),('Documents PDF',self.pdfs,'#e6edf5','pdf'),('Modifier les informations',lambda:self.book.select(self.form),'#e6edf5','notes')]:self.btn(sb,title,cmd,color,icon).pack(fill='x',pady=4)
        right=tk.Frame(h,bg=BG);right.grid(row=0,column=1,sticky='nsew',padx=5,pady=5);right.columnconfigure(0,weight=1);right.rowconfigure(2,weight=1)
        cards=tk.Frame(right,bg=BG);cards.grid(row=0,column=0,sticky='ew');self.cardvars=[]
        for i,(title,color,fg,icon) in enumerate([('Chiffre d’affaires','#e6f7e8','#135e3c','report'),('Locations','#e2f1fc',BLUE,'check'),('Jours loués','#fff0d7','#ce5a0a','calendar'),('Moyenne / location','#f0e3fc','#7334a9','bank'),('Moyenne / jour','#fde5eb','#c62945','report')]):
            cards.columnconfigure(i,weight=1,uniform='metrics');frame=tk.Frame(cards,bg=color);frame.grid(row=0,column=i,sticky='nsew',padx=2);tk.Label(frame,text=' '+title,image=self.icon(icon),compound='top',bg=color,fg=fg,font=('Segoe UI',8,'bold'),wraplength=110).pack(pady=(6,2));var=tk.StringVar(self.win,value='0');tk.Label(frame,textvariable=var,bg=color,fg=fg,font=('Segoe UI',12,'bold')).pack(pady=(0,8));self.cardvars.append(var)
        filters=tk.Frame(right,bg='#e1efff');filters.grid(row=1,column=0,sticky='ew',pady=8);filters.columnconfigure(3,weight=1)
        self.period=tk.StringVar(self.win,value='Toutes les dates');self.from_date=tk.StringVar(self.win);self.to_date=tk.StringVar(self.win);self.hist_search=tk.StringVar(self.win)
        cb=ttk.Combobox(filters,textvariable=self.period,values=['Toutes les dates','Ce mois','Cette année','Période personnalisée'],state='readonly',width=18);cb.grid(row=0,column=0,padx=4,pady=6);cb.bind('<<ComboboxSelected>>',self.period_changed)
        for col,var,title in [(1,self.from_date,'Du'),(2,self.to_date,'Au')]:
            box=tk.Frame(filters,bg='#e1efff');box.grid(row=0,column=col,padx=3);tk.Label(box,text=title,bg='#e1efff').pack(side='left');entry=self.entry(box,var);entry.configure(width=10);entry.pack(side='left');entry.bind('<Return>',lambda e:self.refresh_history())
            if hasattr(self.app,'_attach_date_picker'):self.app._attach_date_picker(entry,var)
        entry=self.entry(filters,self.hist_search);entry.grid(row=1,column=0,columnspan=3,sticky='ew',padx=4,pady=(0,5));entry.bind('<Return>',lambda e:self.refresh_history());self.btn(filters,'Actualiser',self.refresh_history,BLUE,'history').grid(row=1,column=3,padx=5)
        box=tk.Frame(right,bg='white');box.grid(row=2,column=0,sticky='nsew');box.rowconfigure(0,weight=1);box.columnconfigure(0,weight=1)
        cols=('numero','start','end','vehicle','days','amount','status','actions');self.tree=ttk.Treeview(box,columns=cols,show='tree headings',style='QuickClient.Treeview',selectmode='browse');self.tree.heading('#0',text='Photo / marque');self.tree.column('#0',width=84,minwidth=70,stretch=False)
        for key,label,width in [('numero','N° contrat',85),('start','Début',77),('end','Fin',77),('vehicle','Véhicule',120),('days','Jours',42),('amount','Montant DH',80),('status','Statut',78),('actions','Actions',70)]:self.tree.heading(key,text=label);self.tree.column(key,width=width,minwidth=38,anchor='center',stretch=True)
        self.tree.grid(row=0,column=0,sticky='nsew');scroll=ttk.Scrollbar(box,command=self.tree.yview);scroll.grid(row=0,column=1,sticky='ns');self.tree.configure(yscrollcommand=scroll.set);self.tree.bind('<Double-1>',lambda e:self.view_contract());self.tree.bind('<ButtonRelease-1>',self.row_action)
        bottom=tk.Frame(right,bg='#e2effc');bottom.grid(row=3,column=0,sticky='ew',pady=(6,0));self.totals=tk.StringVar(self.win);tk.Label(bottom,textvariable=self.totals,bg='#e2effc',fg=NAVY,font=('Segoe UI',9,'bold')).pack(side='left',padx=8,pady=8);self.btn(bottom,'Voir',self.view_contract,BLUE,'eye').pack(side='right',padx=3);self.btn(bottom,'PDF',lambda:self.view_contract('save'),'#d92043','pdf').pack(side='right',padx=3)
    def tab_changed(self,event=None):
        selected=self.book.select()
        for button,frame in zip(self.tabbuttons,(self.form,self.history)):
            button.configure(relief='sunken' if selected==str(frame) else 'flat')
        if selected==str(self.history) and self.history_dirty:self.refresh_history()
    def invalidate_history(self):
        self.history_dirty=True
        if self.book.select()==str(self.history):self.refresh_history()
    def close(self):
        self.closed=True
        if self.preview_poll:
            self.win.after_cancel(self.preview_poll);self.preview_poll=None
        for future,_key,_apply in self.preview_jobs.values():future.cancel()
        self.preview_jobs.clear();self.preview_worker.shutdown(wait=False,cancel_futures=True)

        if self.refresh_job:
            try:self.win.after_cancel(self.refresh_job)
            except tk.TclError:pass
        previous=getattr(self,'previous_grab',None)
        parent=getattr(self,'dialog_parent',self.app.root)
        self.win.destroy()
        try:
            if previous is not None and previous.winfo_exists():previous.grab_set()
            if parent.winfo_exists():parent.lift();parent.focus_set()
        except tk.TclError:pass
    def ages(self,*_):self.age.set(years_since(self.v['date_naissance'].get()));self.seniority.set(years_since(self.v['date_permis'].get()))
    def reset(self):
        self.loaded=None;self.pending.clear()
        for var in self.v.values():var.set('')
        self.v['code'].set(self.app._next_client_code());self.active.set(True);self.refresh_documents();self.invalidate_history();self.book.select(self.form)
    def schedule_search(self,*_):
        if self.refresh_job:self.win.after_cancel(self.refresh_job)
        self.refresh_job=self.win.after(100,self.search)
    def search(self):
        self.refresh_job=None;needle=self.query.get().strip();self.results.clear();rows=[]
        if needle:
            # Parameterized substring search, keeping exact code/CIN matches first.
            term='%'+needle+'%'
            rows=self.app.conn.execute("SELECT code,cin,nom,prenom,telephone FROM clients WHERE code LIKE ? OR cin LIKE ? OR nom LIKE ? OR prenom LIKE ? OR telephone LIKE ? ORDER BY CASE WHEN code=? OR UPPER(cin)=UPPER(?) THEN 0 ELSE 1 END,nom,prenom LIMIT 60",(term,term,term,term,term,needle,needle)).fetchall()
            for r in rows:self.results[f"{r['code']} · {r['nom']} {r['prenom']} · {r['cin']}"]=r['code']
        self.matches.configure(values=list(self.results))
        if self.results:self.matches.current(0)
        else:self.matches.set('Aucun client trouvé' if needle else '')
        if rows:
            exact=[]
            for key in ('code','cin','telephone','nom','prenom'):
                exact=[r for r in rows if str(r[key] or '').strip().casefold()==needle.casefold()]
                if exact:break
            selected=exact[0]['code'] if len(exact)==1 else next(iter(self.results.values())) if len(self.results)==1 else None
            if selected is not None:
                self.load(selected)
                self.matches.set(next(label for label,code in self.results.items() if code==selected))
    def load(self,code):
        if str(code)==self.loaded:return
        row=self.app.conn.execute('SELECT * FROM clients WHERE code=?',(str(code),)).fetchone()
        if not row:return
        self.loaded=str(row['code']);self.pending.clear()
        for key,var in self.v.items():var.set(str(row[key] or ''))
        preference=self.app.conn.execute("SELECT payload FROM module_records WHERE module='client_quick_preferences' AND record_id=?",(self.loaded,)).fetchone()
        self.active.set(json.loads(preference[0]).get('active',True) if preference else True);self.refresh_documents();self.invalidate_history()
    def resolve(self,raw,code=None):
        p=Path(str(raw or ''))
        if p.is_file():return p
        p=self.app._client_documents_folder(code or self.v['code'].get(),create=False)/PureWindowsPath(str(raw or '')).name
        return p if p.is_file() else None
    def face_path(self,kind):
        if kind in self.pending:return Path(self.pending[kind])
        row=self.app.conn.execute('SELECT file_path FROM client_documents WHERE client_code=? AND document_type=? ORDER BY id DESC LIMIT 1',(self.v['code'].get(),kind)).fetchone()
        return self.resolve(row[0]) if row else None
    def queue_preview(self,slot,path,size,apply,page=0):
        old=self.preview_jobs.pop(slot,None)
        if old:old[0].cancel()
        try:key=(str(path),path.stat().st_mtime_ns,path.stat().st_size,size,page)
        except OSError:return
        if key in self.preview_cache:apply(self.preview_cache[key]);return
        future=self.preview_worker.submit(render_preview,str(path),size,page)
        self.preview_jobs[slot]=(future,key,apply)
        if not self.preview_poll:self.preview_poll=self.win.after(20,self.poll_previews)
    def poll_previews(self):
        self.preview_poll=None
        if self.closed:return
        for slot,(future,key,apply) in list(self.preview_jobs.items()):
            if not future.done():continue
            self.preview_jobs.pop(slot,None)
            try:
                result=future.result();self.preview_cache[key]=result
                if len(self.preview_cache)>32:self.preview_cache.pop(next(iter(self.preview_cache)))
                apply(result)
            except Exception:
                if slot=='pdf_preview':
                    self.pdf_preview_label.configure(image='',text='PDF · ouvrir',width=12,height=5);self.pdf_page_text.set('—')
                else:
                    kind=next((k for k in FACES if slot.startswith(k)),None)
                    label=(self.previews if slot.endswith('form') else self.history_faces).get(kind)
                    if label:label.configure(image='',text='Ouvrir le document',height=5,width=1)
        if self.preview_jobs:self.preview_poll=self.win.after(20,self.poll_previews)
    def apply_face(self,label,key,result):
        self.images[key]=ImageTk.PhotoImage(result[0],master=self.win)
        label.configure(image=self.images[key],text='',height=0,width=0)
    def refresh_documents(self):
        for kind in FACES:
            path=self.face_path(kind)
            for suffix,label in [('form',getattr(self,'previews',{}).get(kind)),('hist',getattr(self,'history_faces',{}).get(kind))]:
                if label is None:continue
                previous=self.preview_jobs.pop(kind+suffix,None)
                if previous:previous[0].cancel()
                label.configure(image='',text='Aucun scan' if not path else '',height=5 if suffix=='form' else 4,width=1)
                if path:
                    label.configure(text='Chargement…')
                    self.queue_preview(kind+suffix,path,(110,94) if suffix=='form' else (175,78),lambda result,l=label,k=kind+suffix:self.apply_face(l,k,result))
        self.refresh_pdf_preview()
    def open_file(self,path):
        if os.name=='nt':os.startfile(str(path.resolve()))
        else:webbrowser.open(path.resolve().as_uri())
    def open_face(self,kind):
        path=self.face_path(kind)
        if path:self.open_file(path)
    def import_face(self,kind):
        file=filedialog.askopenfilename(parent=self.win,title='Importer '+kind.replace('_',' '),filetypes=[('Image ou PDF','*.jpg *.jpeg *.png *.bmp *.pdf')])
        if not file:return
        try:
            p=Path(file)
            if p.suffix.lower()=='.pdf':
                from pypdf import PdfReader
                if not PdfReader(p).pages:raise ValueError('PDF vide.')
            else:
                with Image.open(p) as im:im.verify()
            self.pending[kind]=file;self.refresh_documents()
        except Exception as exc:messagebox.showerror('Document',str(exc),parent=self.win)
    def scan(self,kind):
        if not self.loaded:
            messagebox.showinfo('Scanner','Enregistrez la fiche avant de scanner, ou utilisez Importer.',parent=self.win);return
        base,face=kind.split('_',1)
        self.app.scan_client_front_image(self.loaded,base,on_complete=lambda *_:(self.merge_pdf(),self.refresh_documents()),face=face)
    def merge_pdf(self):
        paths=[self.face_path(k) for k in FACES]
        if not any(paths):return None
        from pypdf import PdfReader,PdfWriter
        writer=PdfWriter()
        for path in paths:
            if not path:continue
            if path.suffix.lower()=='.pdf':writer.append(str(path))
            else:
                buf=io.BytesIO()
                with Image.open(path) as im:ImageOps.exif_transpose(im).convert('RGB').save(buf,'PDF',resolution=200)
                buf.seek(0);writer.append(PdfReader(buf))
        code=self.v['code'].get();destination=self.app._client_documents_folder(code)/'PIECES_IDENTITE_FACES.pdf';tmp=destination.with_suffix('.tmp')
        with tmp.open('wb') as f:writer.write(f)
        tmp.replace(destination)
        old=self.app.conn.execute("SELECT id FROM client_documents WHERE client_code=? AND document_type='AUTRE_FACES' ORDER BY id DESC LIMIT 1",(code,)).fetchone()
        if old:self.app.conn.execute('UPDATE client_documents SET file_path=? WHERE id=?',(str(destination),old[0]))
        else:self.app.conn.execute('INSERT INTO client_documents(client_code,document_type,file_path,created_at) VALUES(?,?,?,?)',(code,'AUTRE_FACES',str(destination),datetime.now().isoformat(timespec='seconds')))
        self.app.conn.commit();return destination
    def save(self):
        try:
            if hasattr(self.app,'_user_has_permission') and not self.app._user_has_permission('Clients'):raise ValueError('Droit Clients requis.')
            with self.app.conn:
                code=save_record(self.app,{k:v.get() for k,v in self.v.items()},self.loaded)
                self.app.conn.execute("INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES('client_quick_preferences',?,?,?)",(code,json.dumps({'active':self.active.get()}),datetime.now().isoformat(timespec='seconds')))
            self.loaded=code
            for kind,source in self.pending.items():
                folder=self.app._client_documents_folder(code);target=folder/(kind+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+Path(source).suffix.lower());shutil.copyfile(source,target)
                self.app.conn.execute('INSERT INTO client_documents(client_code,document_type,file_path,created_at) VALUES(?,?,?,?)',(code,kind,str(target),datetime.now().isoformat(timespec='seconds')))
            self.app.conn.commit();self.pending.clear()
            try:self.merge_pdf()
            except Exception as exc:messagebox.showwarning('Document PDF','Fiche et scans enregistrés ; assemblage PDF à reprendre : '+str(exc),parent=self.win)
            for method in ('refresh_clients','_load_search_values','refresh_dashboard','_client_reference_refresh_documents'):
                callback=getattr(self.app,method,None)
                if callback:callback()
            self.refresh_documents();self.invalidate_history();messagebox.showinfo('Client rapide','Fiche client enregistrée.',parent=self.win)
        except Exception as exc:messagebox.showerror('Client rapide',str(exc),parent=self.win)
    def use(self):
        if self.pending or not self.loaded:
            messagebox.showinfo('Client','Enregistrez la fiche et les scans avant de sélectionner le client.',parent=self.win);return
        if self.callback:self.callback(self.loaded);self.close()
        else:self.contract()
    def contract(self):
        if not self.loaded:messagebox.showinfo('Client','Sélectionnez ou enregistrez un client.',parent=self.win);return
        if self.pending:
            messagebox.showinfo('Contrat rapide','Enregistrez les scans avant d’ouvrir le contrat.',parent=self.win);return
        code=self.loaded
        if not getattr(self,'embedded',False):self.close()
        self.app.open_quick_contract_dialog(initial_client=code)
    def reservation(self):
        if not self.loaded or self.v['code'].get()!=self.loaded or self.pending:
            messagebox.showinfo('Réservation','Sélectionnez ou enregistrez le client et ses documents.',parent=self.win);return
        code=self.loaded
        if not getattr(self,'embedded',False):self.close()
        self.app.new_business_record('reservations')
        self.app.module_vars['reservations']['client'].set(code)
        self.app._load_reservation_client()
        self.app.show_page('reservations')
    def import_client_pdf(self):
        code=self.loaded
        if not code or code!=self.v['code'].get():
            messagebox.showinfo('Document PDF','Sélectionnez ou enregistrez le client avant d’ajouter son PDF.',parent=self.win);return
        if hasattr(self.app,'_user_has_permission') and not self.app._user_has_permission('Clients'):
            messagebox.showerror('Document PDF','Droit Clients requis.',parent=self.win);return
        file=filedialog.askopenfilename(parent=self.win,title='Ajouter un PDF au client '+code,filetypes=[('Document PDF','*.pdf')])
        if not file:return
        target=None
        try:
            from pypdf import PdfReader
            reader=PdfReader(file)
            if reader.is_encrypted:raise ValueError('Déverrouillez le PDF avant de l’importer.')
            if not len(reader.pages):raise ValueError('Le fichier PDF ne contient aucune page.')
            folder=self.app._client_documents_folder(code);target=folder/('PDF_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+Path(file).name)
            shutil.copyfile(file,target)
            with self.app.conn:
                self.app.conn.execute('INSERT INTO client_documents(client_code,document_type,file_path,created_at) VALUES(?,?,?,?)',(code,'AUTRE',str(target),datetime.now().isoformat(timespec='seconds')))
        except Exception as exc:
            if target and target.exists():target.unlink()
            messagebox.showerror('Document PDF',str(exc),parent=self.win);return
        self.refresh_pdf_preview()
        refresh=getattr(self.app,'_client_reference_refresh_documents',None)
        if refresh:refresh()
    def client_pdf_files(self):
        code=self.v['code'].get();files=[]
        for r in self.app.conn.execute("SELECT file_path FROM client_documents WHERE client_code=? AND LOWER(file_path) LIKE '%.pdf' ORDER BY id DESC",(code,)):
            path=self.resolve(r[0])
            if path and path not in files:files.append(path)
        return files
    def refresh_pdf_preview(self):
        if not hasattr(self,'pdf_selector'):return
        self.pdf_files=self.client_pdf_files();self.pdf_selector.configure(values=[p.name for p in self.pdf_files])
        if self.pdf_files:self.pdf_selector.current(0);self.show_pdf_page(0)
        else:
            previous=self.preview_jobs.pop('pdf_preview',None)
            if previous:previous[0].cancel()
            self.pdf_selector.set('');self.pdf_preview_label.configure(image='',text='Aucun PDF',width=12,height=5);self.pdf_page_text.set('—')
    def show_pdf_page(self,page):
        if not self.pdf_files:return
        path=self.pdf_files[max(0,self.pdf_selector.current())]
        self.pdf_page=max(0,page);self.pdf_preview_label.configure(image='',text='Chargement…',width=12,height=5)
        def apply(result):
            pic,self.pdf_page,total=result
            self.images['pdf_preview']=ImageTk.PhotoImage(pic,master=self.win)
            self.pdf_preview_label.configure(image=self.images['pdf_preview'],text='',width=0,height=0)
            self.pdf_page_text.set(f'{self.pdf_page+1} / {total}')
        self.queue_preview('pdf_preview',path,(120,96),apply,self.pdf_page)
    def open_preview_pdf(self):
        if self.pdf_files:self.open_file(self.pdf_files[max(0,self.pdf_selector.current())])
    def pdfs(self):
        code=self.v['code'].get();rows=self.app.conn.execute("SELECT file_path FROM client_documents WHERE client_code=? AND LOWER(file_path) LIKE '%.pdf' ORDER BY id DESC",(code,)).fetchall();files=[]
        for r in rows:
            p=self.resolve(r[0])
            if p and p not in files:files.append(p)
        if not files:messagebox.showinfo('Document PDF','Aucun PDF disponible pour ce client.',parent=self.win);return
        if len(files)==1:self.open_file(files[0]);return
        win=tk.Toplevel(self.win);win.title('Documents PDF · '+code);win.transient(self.win)
        lb=tk.Listbox(win,width=64,height=min(10,len(files)),font=('Segoe UI',10));lb.pack(fill='both',expand=True,padx=12,pady=12)
        for p in files:lb.insert('end',p.name)
        lb.selection_set(0)
        def open_selected():
            if lb.curselection():self.open_file(files[lb.curselection()[0]])
        self.btn(win,'Ouvrir',open_selected,BLUE,'pdf').pack(pady=10);lb.bind('<Double-1>',lambda e:open_selected())
    def period_changed(self,e=None):
        today=date.today();period=self.period.get()
        if period=='Toutes les dates':self.from_date.set('');self.to_date.set('')
        elif period=='Ce mois':self.from_date.set(today.replace(day=1).strftime('%d/%m/%Y'));self.to_date.set(today.strftime('%d/%m/%Y'))
        elif period=='Cette année':self.from_date.set(today.replace(month=1,day=1).strftime('%d/%m/%Y'));self.to_date.set(today.strftime('%d/%m/%Y'))
        self.refresh_history()
    def vehicle_image(self,r):
        canvas=Image.new('RGB',(78,30),'white');path=self.app._vehicle_photo_path(str(r.get('vehicle_code') or ''),str(r.get('vehicle_photo') or ''))
        if path and Path(path).is_file():
            with Image.open(path) as im:pic=ImageOps.exif_transpose(im).convert('RGB');pic.thumbnail((54,30));canvas.paste(pic,(0,(30-pic.height)//2))
        brand=next((b for b in ('peugeot','opel','dacia','renault','citroen','kia','hyundai','volkswagen','fiat','toyota','ford') if b in str(r.get('modele','')).lower()),None)
        if brand:
            folder=Path(__file__).parent/'assets'
            if brand not in self.brand_paths:self.brand_paths[brand]=list(folder.glob('**/'+brand+'*.png'))
            paths=self.brand_paths[brand]
            if paths:
                with Image.open(paths[0]) as im:pic=im.convert('RGBA');pic.thumbnail((22,26));canvas.paste(pic,(55,(30-pic.height)//2),pic)
        key='vehicle:'+str(r['numero']);self.images[key]=ImageTk.PhotoImage(canvas,master=self.win);return self.images[key]
    def refresh_history(self):
        if self.book.select()!=str(self.history):self.history_dirty=True;return
        self.history_dirty=False
        if not hasattr(self,'tree'):return
        self.tree.delete(*self.tree.get_children());self.rows.clear();code=self.loaded or ''
        self.info.set('\n'.join([f"Code client : {code or '—'}",f"CIN : {self.v['cin'].get()}",f"{self.v['nom'].get()} {self.v['prenom'].get()}",f"Naissance : {self.v['date_naissance'].get()} · {self.age.get()} ans",self.v['adresse'].get(),self.v['telephone'].get()]))
        try:rows=history_rows(self.app.conn,code,self.from_date.get(),self.to_date.get(),self.hist_search.get()) if code else []
        except ValueError as exc:messagebox.showerror('Période',str(exc),parent=self.win);return
        data=metrics(rows)
        for i,var in enumerate(self.cardvars):var.set(f'{data[i]:,.2f} DH' if i in (0,3,4) else str(data[i]))
        self.totals.set(f'Totaux affichés · {data[1]} locations · {data[2]} jours · {data[0]:,.2f} DH')
        for r in rows:
            self.rows[str(r['numero'])]=r
            try:d=parse_date(r['date_retour']);status='Terminé' if r.get('return_status') in ('RETOUR_CONFIRMÉ','RETURNED','CONFIRMÉ') or d and d<date.today() else 'En cours'
            except ValueError:status='—'
            try:pic=self.vehicle_image(r)
            except Exception:pic=''
            self.tree.insert('','end',iid=str(r['numero']),image=pic,values=(r['numero'],r['date_depart'],r['date_retour'],r.get('modele') or r['vehicle_code'],r['duree'] or 0,f"{float(r['montant'] or 0):,.2f}",status,'Voir · PDF'))
    def view_contract(self,action='preview'):
        selected=self.tree.selection()
        if selected:self.app._dashboard_contract_document(selected[0],action)
    def row_action(self,e):
        row=self.tree.identify_row(e.y)
        if row and self.tree.identify_column(e.x)=='#8':
            self.tree.selection_set(row);self.view_contract('save' if e.x>self.tree.bbox(row,'actions')[0]+self.tree.bbox(row,'actions')[2]/2 else 'preview')

def open_quick_client(app,on_select=None,initial_client=''):
    old=getattr(app,'_quick_client_tabs',None)
    if old and old.win.winfo_exists():
        old.callback=on_select
        if initial_client:old.load(initial_client)
        old.present();return old.win
    panel=QuickClient(app,on_select,initial_client);app._quick_client_tabs=panel;return panel.win
