"""Fiche client selon la maquette du 06/10/2026, intégrée au menu Gestion Pro."""
import io,json,html,re,shutil,tempfile,webbrowser
from pathlib import Path
from datetime import datetime,date
from concurrent.futures import ThreadPoolExecutor
import tkinter as tk
from tkinter import ttk,filedialog,messagebox
from PIL import Image,ImageTk,ImageDraw
from quick_client_tabs import QuickClient,KEYS,FACES,history_rows,metrics,years_since,save_record
NAVY='#194d7c';BLUE='#258de9';GREEN='#12ab68';BG='#f3f8fc';INK='#163551';EDGE='#d7e5ef'
class ClientSheet(QuickClient):
 def __init__(self,app,on_select=None,container=None):
  self.app=app;self.callback=on_select;self.embedded=container is not None;self.loaded=None;self.images={};self.pending={};self.results={};self.rows={};self.refresh_job=None;self.preview_poll=None;self.preview_jobs={};self.preview_cache={};self.preview_worker=ThreadPoolExecutor(max_workers=1);self.closed=False;self.history_dirty=True;self.brand_paths={};self.pdf_files=[];self.pdf_page=0
  self.win=tk.Frame(container,bg=BG) if self.embedded else tk.Toplevel(app.root)
  w=self.win
  if self.embedded:w.pack(fill='both',expand=True)
  else:
   w.title('Fiche client');w.transient(app.root);sw=w.winfo_screenwidth();sh=w.winfo_screenheight();width=min(1500,sw-30);height=min(970,sh-75);w.geometry(f'{width}x{height}+{(sw-width)//2}+{(sh-height)//2}');w.protocol('WM_DELETE_WINDOW',self.close)
  app._client_reference_window=w;app._client_mockup_sheet=self
  self.v={k:tk.StringVar(w) for k in KEYS+('date_enregistrement','source','photo','blocked')};self.age=tk.StringVar(w);self.seniority=tk.StringVar(w);self.active=tk.BooleanVar(w,value=True);self.query=tk.StringVar(w);self.from_date=tk.StringVar(w);self.to_date=tk.StringVar(w);self.hist_search=tk.StringVar(w)
  self.profile={};self.previews={};self.history_faces={};self.cardvars=[];self.history_tables=[]
  for k in ('date_naissance','date_permis'):self.v[k].trace_add('write',self.ages)
  w.columnconfigure(0,weight=1);w.rowconfigure(3,weight=1)
  header=tk.Frame(w,bg=NAVY);header.grid(row=0,column=0,sticky='ew');header.columnconfigure(0,weight=1)
  tk.Label(header,text='  Fiche client',image=self.icon('clients',32),compound='left',bg=NAVY,fg='white',font=('Segoe UI',18,'bold'),anchor='w').grid(row=0,column=0,padx=18,pady=7)
  self.btn(header,'✕',self.close,NAVY,'clear').grid(row=0,column=1,padx=12)
  tabbar=tk.Frame(w,bg=BG);tabbar.grid(row=1,column=0,sticky='ew',padx=12,pady=8);self.tabbuttons=[]
  searchbar=tk.Frame(w,bg='#e2f0fb');searchbar.grid(row=2,column=0,sticky='ew',padx=12,pady=(0,6));searchbar.columnconfigure(1,weight=1);searchbar.columnconfigure(2,weight=1)
  tk.Label(searchbar,text='Rechercher un client',bg='#e2f0fb',fg=INK,font=('Segoe UI',10,'bold')).grid(row=0,column=0,padx=8,pady=6)
  self.search_entry=self.entry(searchbar,self.query);self.search_entry.grid(row=0,column=1,sticky='ew',padx=6,ipady=5)
  self.matches=ttk.Combobox(searchbar,state='readonly');self.matches.grid(row=0,column=2,sticky='ew',padx=6)
  self.matches.bind('<<ComboboxSelected>>',lambda e:self.accept_match());self.search_entry.bind('<Return>',lambda e:(self.search(),self.accept_match()))
  self.body=tk.Frame(w,bg=BG);self.body.grid(row=3,column=0,sticky='nsew',padx=12);self.body.columnconfigure(0,weight=1);self.body.rowconfigure(0,weight=1)
  self.pages=[tk.Frame(self.body,bg=BG) for _ in range(3)]
  for page in self.pages:page.grid(row=0,column=0,sticky='nsew')
  for i,(title,icon) in enumerate([('Fiche client','clients'),('Historique de location (par client)','check'),('Historique global du client','report')]):
   b=self.btn(tabbar,title,lambda n=i:self.show_tab(n),'#dcebf6',icon);b.configure(fg=INK);b.pack(side='left',padx=(0,5));self.tabbuttons.append(b)
  for title,command,color,icon in [('Supprimer',self.delete_client,'#f58383','clear'),('Enregistrer',self.save,BLUE,'save'),('Nouveau',self.reset,GREEN,'plus')]:self.btn(tabbar,title,command,color,icon).pack(side='right',padx=5)
  self.btn(tabbar,'Importer',app.import_clients_csv,'#7153dc','paper').pack(side='right',padx=3)
  self.btn(tabbar,'Exporter',app.export_clients_csv,BLUE,'save').pack(side='right',padx=3)
  self.build_sheet();self.build_history_page(self.pages[1],False);self.build_history_page(self.pages[2],True)
  footer=tk.Frame(w,bg='white',highlightbackground=EDGE,highlightthickness=1);footer.grid(row=4,column=0,sticky='ew',padx=12,pady=10)
  for title,command,color,icon in [('Établir un contrat',self.use,BLUE,'paper'),('Consulter/modifier',lambda:self.show_tab(0),'#e8eff5','notes'),('Nouveau contrat',self.contract,'#e8eff5','plus'),('Envoyer par WhatsApp',self.whatsapp,'#e8eff5','clients'),('Imprimer fiche',self.print_sheet,'#e8eff5','print')]:self.btn(footer,title,command,color,icon).pack(side='left',padx=5,pady=8)
  self.btn(footer,'Fermer',self.close,'#b2bcc8','clear').pack(side='right',padx=8)
  w._reference_values={**self.v,'age':self.age,'permis_age':self.seniority};w._reference_select_client=self.load;w._reference_save_client=lambda update=False:self.save();w._reference_new_client=self.reset
  self.list_tree=ttk.Treeview(w,columns=('nom','prenom'),show='headings');w._reference_tables={'clients':self.list_tree,'history':self.history_tables[0],'notes':self.list_tree,'finance':self.history_tables[1]}
  app._client_reference_refresh_documents=self.refresh_documents
  self.query.trace_add('write',self.schedule_search);self.reset();self.show_tab(0)
  initial=str(getattr(app,'client_vars',{}).get('code',tk.StringVar(w)).get()).strip()
  if initial:self.load(initial)
 def btn(self,parent,text,cmd,color=BLUE,icon='paper'):
  light=color in ('#dcebf6','#e8eff5','#b2bcc8')
  return tk.Button(parent,text=' '+text,image=self.icon(icon),compound='left',command=cmd,bg=color,fg=INK if light else 'white',font=('Segoe UI',9,'bold'),relief='flat',bd=0,padx=8,pady=5,cursor='hand2')
 def white_icon(self,name,size):
  key=('white',name,size)
  if key not in self.images:
   path=Path(__file__).parent/'assets'/'check_express'/(name+'.png')
   if not path.exists():path=Path(__file__).parent/'assets'/'check_express'/'paper.png'
   with Image.open(path) as im:pic=im.convert('RGBA');pic.thumbnail((size,size));white=Image.new('RGBA',pic.size,'white');white.putalpha(pic.getchannel('A'))
   self.images[key]=ImageTk.PhotoImage(white,master=self.win)
  return self.images[key]
 def entry(self,parent,var,readonly=False,tint='white'):
  return tk.Entry(parent,textvariable=var,width=10,state='readonly' if readonly else 'normal',bg=tint,readonlybackground=tint,fg=INK,font=('Segoe UI',10),relief='flat',highlightthickness=1,highlightbackground=EDGE)
 def panel(self,parent,title=''):
  f=tk.Frame(parent,bg='white',highlightthickness=1,highlightbackground=EDGE)
  if title:tk.Label(f,text=title,bg='#e2f0fb',fg=INK,font=('Segoe UI',10,'bold'),anchor='w',padx=12,pady=6).pack(fill='x')
  body=tk.Frame(f,bg='white');body.pack(fill='both',expand=True,padx=8,pady=6);return f,body
 def build_sheet(self):
  p=self.pages[0];p.columnconfigure(0,weight=1);p.rowconfigure(2,weight=1)
  top=tk.Frame(p,bg=BG);top.grid(row=0,column=0,sticky='ew');top.columnconfigure(0,weight=1,uniform='top');top.columnconfigure(1,weight=1,uniform='top')
  identity,ib=self.panel(top);identity.grid(row=0,column=0,sticky='nsew',padx=(0,6));ib.columnconfigure(1,weight=1)
  photo=tk.Frame(ib,bg='#f5f9fd',highlightthickness=1,highlightbackground=EDGE);photo.grid(row=0,column=0,sticky='nsew',padx=(0,12))
  self.photo_label=tk.Label(photo,bg='#e6f0f8',width=17,height=11);self.photo_label.pack(padx=6,pady=6)
  self.btn(photo,'Ajouter photo',self.choose_photo,'#e8eff5','clients').pack(fill='x',padx=5,pady=5)
  fb=tk.Frame(ib,bg='white');fb.grid(row=0,column=1,sticky='nsew');fb.columnconfigure(1,weight=1)
  for row,(label,key) in enumerate([('Code client','code'),('CIN *','cin'),('Nom *','nom'),('Prénom *','prenom'),('Date naissance','date_naissance'),('Téléphone *','telephone'),('Adresse','adresse')]):
   tk.Label(fb,text=label,bg='white',fg=INK,font=('Segoe UI',9),anchor='w').grid(row=row,column=0,sticky='w',padx=5,pady=5)
   holder=tk.Frame(fb,bg='white');holder.grid(row=row,column=1,sticky='ew',pady=2);holder.columnconfigure(0,weight=1)
   entry=self.entry(holder,self.v[key],key=='code','#d1e8ff' if key=='code' else 'white');entry.grid(row=0,column=0,sticky='ew',ipady=3)
   if key=='code':
    entry.configure(width=8,font=('Segoe UI',14,'bold'),justify='center');entry.grid_configure(sticky='w');self.btn(holder,'',self.focus_search,NAVY,'search').grid(row=0,column=1,padx=5)
   if key=='date_naissance':
    if hasattr(self.app,'_attach_date_picker'):self.app._attach_date_picker(entry,self.v[key])
    tk.Label(holder,text='Âge',bg='#e1effc',fg=INK,font=('Segoe UI',9)).grid(row=0,column=1,padx=(8,0),ipadx=7,ipady=6)
    age=self.entry(holder,self.age,True,'#cfe3f4');age.configure(width=3,justify='center',font=('Segoe UI',12,'bold'));age.grid(row=0,column=2,ipady=2)
  right=tk.Frame(top,bg=BG);right.grid(row=0,column=1,sticky='nsew',padx=(0,0));right.columnconfigure(0,weight=1)
  permit,pb=self.panel(right,'Permis de conduire');permit.grid(row=0,column=0,sticky='ew')
  for col,(label,key) in enumerate([('N° permis','permis'),('Date d’obtention','date_permis')]):
   tk.Label(pb,text=label,bg='white',fg=INK,font=('Segoe UI',9)).grid(row=0,column=col*2,padx=4)
   e=self.entry(pb,self.v[key]);e.grid(row=0,column=col*2+1,sticky='ew',ipady=3);pb.columnconfigure(col*2+1,weight=1)
   if key=='date_permis' and hasattr(self.app,'_attach_date_picker'):self.app._attach_date_picker(e,self.v[key])
  tk.Label(pb,text='Ancienneté',bg='white',fg=INK,font=('Segoe UI',9)).grid(row=0,column=4,padx=7);sen=self.entry(pb,self.seniority,True,'#fff6d8');sen.configure(width=3,justify='center',font=('Segoe UI',12,'bold'));sen.grid(row=0,column=5,ipady=3)
  documents,db=self.panel(right,'Documents');documents.grid(row=1,column=0,sticky='nsew',pady=(6,0))
  for i,kind in enumerate(FACES):
   db.columnconfigure(i,weight=1,uniform='docs');tile=tk.Frame(db,bg='#f8fbfe',highlightbackground=EDGE,highlightthickness=1);tile.grid(row=1,column=i,sticky='nsew',padx=2)
   label=tk.Label(tile,text='Aucun scan',bg='#f8fbfe',fg=INK,width=1,height=5);label.pack(fill='both',expand=True,padx=2,pady=3);label.bind('<Button-1>',lambda e,k=kind:self.open_face(k));self.previews[kind]=label
   controls=tk.Frame(tile,bg='#f8fbfe');controls.pack(fill='x');self.btn(controls,'',lambda k=kind:self.open_face(k),NAVY,'search').pack(side='right');tk.Label(controls,text='Recto' if kind.endswith('RECTO') else 'Verso',bg='#f8fbfe',fg=INK,font=('Segoe UI',8)).pack(side='left')
   menu=tk.Menu(tile,tearoff=0);menu.add_command(label='Importer',command=lambda k=kind:self.import_face(k));menu.add_command(label='Scanner',command=lambda k=kind:self.scan(k));label.bind('<Button-3>',lambda e,m=menu:m.tk_popup(e.x_root,e.y_root))
  for col,title in [(0,'CIN (Recto/Verso)'),(2,'Permis (Recto/Verso)')]:tk.Label(db,text=title,bg='#e8eff6',fg=INK,font=('Segoe UI',9),pady=5).grid(row=0,column=col,columnspan=2,sticky='ew',padx=3,pady=(0,6))
  db.columnconfigure(4,weight=1,uniform='docs');tk.Label(db,text='Document PDF',bg='#eef3f8',fg=INK,font=('Segoe UI',9),pady=5).grid(row=0,column=4,sticky='ew',padx=3,pady=(0,6))
  pdf=tk.Frame(db,bg='#f8fbfe');pdf.grid(row=1,column=4,sticky='nsew',padx=5);self.pdf_preview_label=tk.Label(pdf,image=self.icon('pdf',48),bg='#f8fbfe',width=0,height=0);self.pdf_preview_label.pack(fill='both',expand=True);self.pdf_preview_label.bind('<Button-1>',lambda e:self.open_preview_pdf());self.pdf_selector=ttk.Combobox(pdf,state='readonly',width=12);self.pdf_selector.pack(fill='x');self.pdf_selector.bind('<<ComboboxSelected>>',lambda e:self.show_pdf_page(0));self.pdf_page_text=tk.StringVar(self.win)
  self.btn(pdf,'Ajouter PDF',self.import_client_pdf,'#e8eff5','plus').pack(fill='x',pady=2)
  cards=tk.Frame(p,bg='white',highlightbackground=EDGE,highlightthickness=1);cards.grid(row=1,column=0,sticky='ew',pady=8)
  for i,(label,bg,icon) in enumerate([('Chiffre d’affaires total','#258de9','bank'),('Nombre de locations','#2eae4c','calendar'),('Nombre de jours loués','#ff8526','calendar'),('Moyenne / location','#8a59bd','report'),('Moyenne / jour','#08a2b7','bank')]):
   cards.columnconfigure(i,weight=1,uniform='cards');f=tk.Frame(cards,bg=bg);f.grid(row=0,column=i,sticky='nsew',padx=5,pady=5);tk.Label(f,image=self.white_icon(icon,36),bg=bg).pack(side='left',padx=12);tx=tk.Frame(f,bg=bg);tx.pack(side='left',fill='both',expand=True,pady=7);tk.Label(tx,text=label,bg=bg,fg='white',font=('Segoe UI',9,'bold')).pack(anchor='w');v=tk.StringVar(self.win,value='0');self.cardvars.append(v);tk.Label(tx,textvariable=v,bg=bg,fg='white',font=('Segoe UI',16,'bold')).pack(anchor='w')
  lower=tk.Frame(p,bg=BG);lower.grid(row=2,column=0,sticky='nsew');lower.columnconfigure(1,weight=1);lower.rowconfigure(0,weight=1)
  extra,eb=self.panel(lower,'▤  Informations complémentaires');extra.grid(row=0,column=0,sticky='nsew',padx=(0,8));eb.columnconfigure(1,weight=1)
  tk.Label(eb,text='Remarques',bg='white',fg=INK,font=('Segoe UI',9)).grid(row=0,column=0,columnspan=2,sticky='w');self.notes=tk.Text(eb,width=26,height=2,font=('Segoe UI',9),relief='flat',highlightthickness=1,highlightbackground=EDGE);self.notes.grid(row=1,column=0,columnspan=2,sticky='nsew',pady=5)
  for row,(label,key) in enumerate([('Date d’inscription','date_enregistrement'),('Source','source')],start=2):
   tk.Label(eb,text=label,bg='white',fg=INK,font=('Segoe UI',9)).grid(row=row,column=0,sticky='w',pady=7)
   if key=='source':entry=ttk.Combobox(eb,textvariable=self.v[key],values=['Agence','Internet','Recommandation','Autre'],width=13)
   else:
    entry=self.entry(eb,self.v[key]);self.app._attach_date_picker(entry,self.v[key])
   entry.grid(row=row,column=1,sticky='ew',ipady=3)
  tk.Label(eb,text='Statut',bg='white',fg=INK,font=('Segoe UI',9)).grid(row=4,column=0,sticky='w');self.status_var=tk.StringVar(self.win,value='Actif');status=ttk.Combobox(eb,textvariable=self.status_var,values=['Actif','Inactif'],state='readonly',width=13);status.grid(row=4,column=1,sticky='ew',pady=6)
  history,hb=self.panel(lower);history.grid(row=0,column=1,sticky='nsew');self.build_table(hb,'Historique de location (par client)')
 def build_table(self,parent,title):
  parent.columnconfigure(0,weight=1);parent.rowconfigure(1,weight=1);bar=tk.Frame(parent,bg='white');bar.grid(row=0,column=0,sticky='ew',pady=(0,5));bar.columnconfigure(1,weight=1)
  tk.Label(bar,text='  '+title,image=self.icon('check'),compound='left',bg='white',fg=INK,font=('Segoe UI',11,'bold')).grid(row=0,column=0,sticky='w')
  e=self.entry(bar,self.hist_search);e.grid(row=0,column=1,sticky='ew',padx=8);e.bind('<Return>',lambda e:self.refresh_history());self.btn(bar,'Filtres',self.filters,'#e8eff5','search').grid(row=0,column=2,padx=3);self.btn(bar,'Exporter',self.export_history,'#e8eff5','paper').grid(row=0,column=3);self.btn(bar,'Importer',lambda:self.import_locations(), '#7153dc','paper').grid(row=0,column=4,padx=4)
  columns=('numero','start','end','days','vehicle','plate','amount','status','actions');tree=ttk.Treeview(parent,columns=columns,show='headings',height=5,selectmode='browse',style='MockupClient.Treeview');tree.grid(row=1,column=0,sticky='nsew');scroll=ttk.Scrollbar(parent,command=tree.yview);scroll.grid(row=1,column=1,sticky='ns');tree._action_buttons={}
  def scroll_changed(a,b):scroll.set(a,b);tree.after_idle(lambda:self.place_actions(tree))
  tree.configure(yscrollcommand=scroll_changed);tree.bind('<Configure>',lambda e:tree.after_idle(lambda:self.place_actions(tree)))
  for key,label,width in [('numero','N° contrat',112),('start','Date début',85),('end','Date fin',85),('days','Durée (j)',56),('vehicle','Véhicule',103),('plate','Immatriculation',105),('amount','Montant (DH)',95),('status','Statut',90),('actions','Aperçu',92)]:tree.heading(key,text=label);tree.column(key,width=width,minwidth=40,anchor='center',stretch=True)
  tree.tag_configure('finished',background='#f5fbf7');tree.bind('<Double-1>',lambda e,t=tree:self.open_row(t,'preview'));tree.bind('<ButtonRelease-1>',lambda e,t=tree:self.table_action(e,t));self.history_tables.append(tree)
  style=ttk.Style(self.win);style.configure('MockupClient.Treeview',rowheight=25,font=('Segoe UI',9),background='white',fieldbackground='white');style.configure('MockupClient.Treeview.Heading',font=('Segoe UI',9,'bold'));style.map('MockupClient.Treeview',background=[('selected','#c5e6fb')])
 def build_history_page(self,page,global_client):
  page.columnconfigure(0,weight=1);page.rowconfigure(1,weight=1)
  title='Historique global du client' if global_client else 'Historique de location (par client)'
  tk.Label(page,text=title,bg=BG,fg=NAVY,font=('Segoe UI',18,'bold'),anchor='w').grid(row=0,column=0,sticky='ew',pady=10)
  frame=tk.Frame(page,bg='white');frame.grid(row=1,column=0,sticky='nsew');self.build_table(frame,title)
  if global_client:
   self.finance_tree=ttk.Treeview(page,columns=('date','reference','contract','mode','amount'),show='headings',height=5)
   for key,label in zip(self.finance_tree['columns'],('Date','Référence','Contrat','Mode de règlement','Montant DH')):self.finance_tree.heading(key,text=label);self.finance_tree.column(key,width=140)
   self.finance_tree.grid(row=2,column=0,sticky='ew',pady=8)
 def show_tab(self,index):
  self.pages[index].tkraise()
  for i,b in enumerate(self.tabbuttons):b.configure(bg=BLUE if i==index else '#dcebf6',fg='white' if i==index else INK)
  if index:self.refresh_history()
 def accept_match(self):
  chosen=self.matches.get()
  if chosen in self.results:self.load(self.results[chosen])
 def focus_search(self):
  self.search_entry.focus_set();self.search_entry.selection_range(0,'end')
 def import_locations(self):
  from table_transfers import import_history
  if not self.loaded:messagebox.showinfo('Import','Choisissez un client.',parent=self.win);return
  import_history(self.app,self.win,self.refresh_history,self.loaded)
 def schedule_search(self,*_):
  if self.refresh_job:self.win.after_cancel(self.refresh_job)
  self.refresh_job=self.win.after(100,self.search)
 def search(self):
  if hasattr(self,'matches') and self.matches.winfo_exists():super().search()
 def reset(self):
  self.loaded=None;self.pending.clear();self.profile={}
  for var in self.v.values():var.set('')
  self.v['code'].set(self.app._next_client_code());self.v['date_enregistrement'].set(date.today().strftime('%d/%m/%Y'));self.status_var.set('Actif');self.notes.delete('1.0','end');self.refresh_documents();self.display_photo();self.refresh_history()
 def load(self,code):
  row=self.app.conn.execute('SELECT * FROM clients WHERE code=?',(str(code),)).fetchone()
  if not row:return
  self.loaded=str(row['code']);self.pending.clear()
  for key,var in self.v.items():
   if key in row.keys():var.set(str(row[key] or ''))
  for key,var in getattr(self.app,'client_vars',{}).items():
   if key in row.keys():var.set(str(row[key] or ''))
  profile=self.app.conn.execute("SELECT payload FROM module_records WHERE module='client_profile' AND record_id=?",(self.loaded,)).fetchone()
  try:self.profile=json.loads(profile[0]) if profile else {}
  except ValueError:self.profile={}
  self.v['source'].set(self.profile.get('source',''));self.status_var.set('Inactif' if str(self.profile.get('blocked','')).upper() in ('1','OUI','TRUE') else 'Actif');self.notes.delete('1.0','end');self.notes.insert('1.0',self.v['observations'].get());self.refresh_documents();self.display_photo();self.refresh_history()
 def save(self):
  if hasattr(self.app,'_user_has_permission') and not self.app._user_has_permission('Clients'):messagebox.showerror('Fiche client','Droit Clients requis.',parent=self.win);return
  self.v['observations'].set(self.notes.get('1.0','end').strip())
  try:
   with self.app.conn:
    code=save_record(self.app,{k:v.get() for k,v in self.v.items()},self.loaded)
    self.app.conn.execute('UPDATE clients SET date_enregistrement=?,photo=? WHERE code=?',(self.v['date_enregistrement'].get(),self.v['photo'].get(),code))
    self.profile.update(source=self.v['source'].get(),blocked='1' if self.status_var.get()=='Inactif' else '0')
    self.app.conn.execute("INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES('client_profile',?,?,?)",(code,json.dumps(self.profile,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')))
   self.loaded=code
   for kind,source in self.pending.items():
    target=self.app._client_documents_folder(code)/(kind+'_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f')+Path(source).suffix.lower());shutil.copyfile(source,target);self.app.conn.execute('INSERT INTO client_documents(client_code,document_type,file_path,created_at) VALUES(?,?,?,?)',(code,kind,str(target),datetime.now().isoformat(timespec='seconds')))
   self.app.conn.commit();self.pending.clear();self.merge_pdf();self.load(code);self.app.refresh_clients();self.app._load_search_values();messagebox.showinfo('Fiche client','Client enregistré.',parent=self.win)
  except Exception as exc:messagebox.showerror('Fiche client',str(exc),parent=self.win)
 def display_photo(self):
  path=Path(self.v['photo'].get());pic=Image.new('RGB',(150,170),'#e6f0f8');draw=ImageDraw.Draw(pic);draw.ellipse((52,15,98,63),fill='#7ba2c7');draw.ellipse((25,68,125,190),fill='#7ba2c7')
  if path.is_file():
   try:
    with Image.open(path) as im:pic=im.convert('RGB');pic.thumbnail((150,170))
   except Exception:pass
  self.images['client_photo']=ImageTk.PhotoImage(pic,master=self.win);self.photo_label.configure(image=self.images['client_photo'],height=0,width=0)
 def choose_photo(self):
  file=filedialog.askopenfilename(parent=self.win,filetypes=[('Images','*.png *.jpg *.jpeg *.bmp')])
  if not file:return
  if not self.loaded:messagebox.showinfo('Photo','Enregistrez le client avant d’ajouter sa photo.',parent=self.win);return
  try:
   with Image.open(file) as im:im.verify()
   target=self.app._client_documents_folder(self.loaded)/('PHOTO_'+datetime.now().strftime('%Y%m%d_%H%M%S')+Path(file).suffix.lower());shutil.copyfile(file,target);self.v['photo'].set(str(target));self.display_photo()
  except Exception as exc:messagebox.showerror('Photo',str(exc),parent=self.win)
 def refresh_history(self):
  rows=history_rows(self.app.conn,self.loaded or '',self.from_date.get(),self.to_date.get(),self.hist_search.get()) if self.loaded else [];self.rows={str(r['numero']):r for r in rows}
  for i,(var,value) in enumerate(zip(self.cardvars,metrics(rows))):var.set(f'{value:,.2f} DH' if i in (0,3,4) else str(value))
  for tree in self.history_tables:
   tree.delete(*tree.get_children())
   for r in rows:
    finished=str(r.get('return_status','')).upper() in ('RETOUR CONFIRMÉ','RETOUR CONFIRME','RETURNED');status='Terminé' if finished else 'En cours'
    tree.insert('','end',iid=str(r['numero']),values=(r['numero'],r['date_depart'],r['date_retour'],r['duree'],r.get('modele') or r['vehicle_code'],r.get('immatriculation') or '',f"{float(r['montant'] or 0):,.2f}",status,'PDF   ◉'),tags=('finished',) if finished else ())
   tree.after_idle(lambda t=tree:self.place_actions(t))
  if hasattr(self,'finance_tree'):
   self.finance_tree.delete(*self.finance_tree.get_children())
   for ref,raw in self.app.conn.execute("SELECT record_id,payload FROM module_records WHERE module='payments' ORDER BY created_at DESC"):
    try:q=json.loads(raw)
    except ValueError:continue
    if str(q.get('client',''))==self.loaded:self.finance_tree.insert('','end',values=(q.get('date',''),ref,q.get('contract',''),q.get('mode',''),q.get('amount','')))
 def invalidate_history(self):self.refresh_history()
 def place_actions(self,tree):
  if not tree.winfo_exists():return
  visible=set()
  for number in tree.get_children():
   box=tree.bbox(number,'actions')
   if not box:continue
   visible.add(number)
   if number not in tree._action_buttons:
    frame=tk.Frame(tree,bg='white')
    for action,color,icon in [('save','#ef3d49','pdf'),('preview',NAVY,'eye')]:
     def invoke(n=number,a=action):tree.selection_set(n);self.open_row(tree,a)
     tk.Button(frame,image=self.icon(icon,16),command=invoke,bg=color,relief='flat',bd=0,cursor='hand2',padx=3,pady=2).pack(side='left',expand=True)
    tree._action_buttons[number]=frame
   tree._action_buttons[number].place(x=box[0]+2,y=box[1]+2,width=max(1,box[2]-4),height=max(1,box[3]-4))
  for number,frame in list(tree._action_buttons.items()):
   if number not in visible:frame.place_forget()
   if not tree.exists(number):frame.destroy();del tree._action_buttons[number]
 def open_row(self,tree,action):
  selected=tree.selection()
  if selected:self.app._dashboard_contract_document(selected[0],action)
 def table_action(self,e,tree):
  row=tree.identify_row(e.y)
  if row and tree.identify_column(e.x)=='#9':
   tree.selection_set(row);box=tree.bbox(row,'actions');self.open_row(tree,'save' if e.x<box[0]+box[2]/2 else 'preview')
 def filters(self):
  w=tk.Toplevel(self.win);w.title('Filtres de location');w.transient(self.win)
  for title,var in [('Du',self.from_date),('Au',self.to_date)]:tk.Label(w,text=title).pack();entry=self.entry(w,var);entry.pack(padx=20,pady=5);self.app._attach_date_picker(entry,var)
  def apply():
   try:self.refresh_history();w.destroy()
   except ValueError as exc:messagebox.showerror('Filtres',str(exc),parent=w)
  self.btn(w,'Appliquer',apply,BLUE,'search').pack(pady=10)
 def export_history(self):
  path=filedialog.asksaveasfilename(parent=self.win,defaultextension='.xlsx',filetypes=[('Excel','*.xlsx')])
  if not path:return
  try:
   from openpyxl import Workbook
   wb=Workbook();ws=wb.active;ws.title='Locations';ws.append(['Contrat','Début','Fin','Durée','Véhicule','Immatriculation','Montant DH','Règlement','Reste'])
   for r in self.rows.values():ws.append([r['numero'],r['date_depart'],r['date_retour'],r['duree'],r.get('modele'),r.get('immatriculation'),r['montant'],r['reglement'],r['reste']])
   wb.save(path)
  except Exception as exc:messagebox.showerror('Exporter',str(exc),parent=self.win)
 def delete_client(self):
  if not self.loaded:return
  if hasattr(self.app,'_user_has_permission') and not self.app._user_has_permission('Clients'):return
  if self.app.conn.execute('SELECT 1 FROM contracts WHERE client_code=? OR second_code=?',(self.loaded,self.loaded)).fetchone():messagebox.showwarning('Client','Ce client possède des contrats : suppression refusée.',parent=self.win);return
  if not messagebox.askyesno('Supprimer','Supprimer cette fiche client ?',parent=self.win):return
  self.app.conn.execute('DELETE FROM clients WHERE code=?',(self.loaded,));self.app.conn.commit();self.reset();self.app.refresh_clients()
 def use(self):
  if not self.loaded:messagebox.showinfo('Client','Enregistrez ou sélectionnez un client.',parent=self.win);return
  if self.callback:self.callback(self.loaded)
  else:self.contract()
 def whatsapp(self):
  phone=re.sub(r'\D','',self.v['telephone'].get())
  if phone.startswith('0'):phone='212'+phone[1:]
  if phone:webbrowser.open('https://wa.me/'+phone)
 def print_sheet(self):
  rows=''.join('<tr><th>'+html.escape(k)+'</th><td>'+html.escape(v.get())+'</td></tr>' for k,v in self.v.items() if k not in ('photo','blocked'))
  out=Path(tempfile.mkdtemp(prefix='gestionpro_client_'))/'fiche.html';out.write_text('<meta charset="utf-8"><title>Fiche client</title><style>body{font:14px Arial}table{border-collapse:collapse}th,td{padding:8px;border:1px solid #ddd;text-align:left}</style><h1>Fiche client</h1><table>'+rows+'</table><script>window.onload=()=>window.print()</script>',encoding='utf-8');webbrowser.open(out.as_uri())
 def close(self):
  if self.embedded:
   self.app.show_page('dashboard');return
  self.closed=True
  if self.preview_poll:self.win.after_cancel(self.preview_poll)
  if self.refresh_job:self.win.after_cancel(self.refresh_job)
  for future,key,apply in self.preview_jobs.values():future.cancel()
  self.preview_jobs.clear();self.preview_worker.shutdown(wait=False,cancel_futures=True);self.win.destroy();self.app._client_reference_window=None
  if self.embedded:self.app.show_page('dashboard')
def open_sheet(app,on_select=None,container=None):
 old=getattr(app,'_client_reference_window',None)
 if old is not None and old.winfo_exists():
  app._client_mockup_sheet.callback=on_select
  if container is None:app.show_page('clients')
  return old
 return ClientSheet(app,on_select,container).win
