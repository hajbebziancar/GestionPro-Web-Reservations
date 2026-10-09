"""Maquette réservation HBZ, une page ajustée à l'espace de travail."""
import calendar,json,webbrowser
from datetime import datetime,timedelta
from pathlib import Path,PureWindowsPath
from urllib.parse import quote
import tkinter as tk
from tkinter import ttk,messagebox
from PIL import Image,ImageTk,ImageOps
from contract_controls import IconButton,RoundedField,ModernCheck
from history_layout import blue_history_headings
from client_selector import open_client_selector
BG='#f1f7fe';INK='#092d50';BLUE='#0069ed';GREEN='#009d54'

def build(app,name,title,fields):
    if not hasattr(app,'module_vars'):app.module_vars,app.module_trees,app.module_fields={},{},{}
    extras=(('Deuxième conducteur','second_client'),('Remise (%)','discount'),('Mode paiement','payment_method'),('Agence','agency'),('Source','source'),('Lieu départ','departure_place'),('Lieu retour','return_place'))
    fields=tuple(fields)+tuple((label,key) for label,key in extras if key not in dict((k,l) for l,k in fields))
    app.module_fields[name]=fields;v=app.module_vars[name]={k:tk.StringVar() for _,k in fields}
    page=app._new_page(name);page.configure(bg=BG);ui=ReservationPage(app,page,v);app.reservation_mockup=ui
    app.reservation_reference_table=ui.tree;app.module_trees[name]=ui.tree
    app.new_business_record(name);v['agency'].set(ui.agencies[0]);v['discount'].set('0');v['payment_method'].set('ESPÈCES');v['source'].set('Agence')
    for key in ('start_date','start_time','end_date','end_time','daily_price','deposit','discount'):v[key].trace_add('write',ui.changed)
    v['client'].trace_add('write',lambda *_:ui.client_details(False));v['second_client'].trace_add('write',lambda *_:ui.client_details(True))
    v['vehicle'].trace_add('write',lambda *_:ui.schedule_vehicles())
    v['status'].trace_add('write',ui.changed)
    ui.refresh();return page

class ReservationPage:
    def __init__(self,app,page,v):
        self.app,self.page,self.v=app,page,v;self.widgets=[];self.images={};self.vehicle_offset=0;self.vehicle_job=None;self.ready=False
        self.month=datetime.now().replace(day=1);self.phase='start'
        self.search=tk.StringVar();self.vehicle_query=tk.StringVar();self.only_free=tk.BooleanVar(value=False)
        self.driver_vars={};self.driver_photos={};self.recap=tk.StringVar()
        self.put(tk.Frame(page,bg='#062e58'),0,0,1320,60)
        self.label('Réservation de véhicule',20,9,540,40,bg='#062e58',fg='white',size=23,bold=True)
        self.field(self.search,775,15,425,33);self.button('',self.refresh,1207,15,45,33,icon='search')
        self.button('',app.sync_public_website,1260,15,44,33,icon='gear')
        for second,y,heading,soft in [(False,72,'1. Client','#e2f1ff'),(True,274,'2. Deuxième conducteur (optionnel)','#e0f7e8')]:
            self.panel(heading,12,y,556,194,soft,'person')
            query=tk.StringVar();entry=self.field(query,24,y+43,374,29);self.label('Code, CIN, nom ou téléphone',28,y+76,345,15,size=7,fg='#60788d')
            choose=lambda c,s=second:self.choose_client(c,s)
            fn=lambda s=second,q=query:open_client_selector(app,page,lambda c:self.choose_client(c,s),title='Deuxième conducteur' if s else 'Client de la réservation',exclude=v['client'].get() if s else '')
            self.button('',fn,403,y+43,45,29,icon='search');self.button('Ajouter',lambda cb=choose:app.open_quick_client_dialog(cb),453,y+43,100,29,icon='plus')
            entry.input.bind('<Return>',lambda _,f=fn:f())
            job=[None]
            def autocomplete(*_,q=query,s=second,j=job):
                if j[0]:page.after_cancel(j[0])
                def run():
                    j[0]=None;raw=q.get().strip()
                    if not raw:return
                    rows=app.conn.execute('SELECT code FROM clients WHERE code=? OR cin=? OR telephone=? OR nom=? OR prenom=?',(raw,)*5).fetchall()
                    if len(rows)==1:self.choose_client(rows[0][0],s)
                j[0]=page.after(160,run)
            query.trace_add('write',autocomplete)
            for i,(caption,key) in enumerate([('Code client','code'),('CIN','cin'),('Nom','nom'),('Prénom','prenom'),('Âge','age'),('Téléphone','telephone')]):
                var=tk.StringVar();self.driver_vars[second,key]=var
                self.label(caption+' :',24,y+94+i*15,102,15,size=8);self.label('',129,y+94+i*15,165,15,var=var,bold=True,size=8)
            for i,(caption,key) in enumerate([('Adresse','adresse'),('Permis N°','permis'),('Date obtention','date_permis'),('Ancienneté','seniority')]):
                var=tk.StringVar();self.driver_vars[second,key]=var
                self.label(caption+' :',300,y+102+i*18,85,17,size=8);self.label('',385,y+102+i*18,98,17,var=var,bold=True,size=8)
            self.driver_photos[second]=self.put(tk.Label(page,bg='#eef4f8',text='CIN',fg='#526c82'),487,y+96,67,62)
            if not second:self.button('Voir fiche client',lambda:app.open_quick_client_dialog(initial_client=v['client'].get()),410,y+163,145,24,icon='person')
        self.panel('3. Véhicule',12,476,556,250,'#e2f1ff','car')
        self.field(self.vehicle_query,24,518,530,31)
        self.vehicle_query.trace_add('write',lambda *_:self.schedule_vehicles())
        check=ModernCheck(page,'Uniquement disponibles',self.only_free,command=self.schedule_vehicles);self.put(check,302,480,245,29)
        self.vehicle_tiles=[]
        for i in range(4):
            host=tk.Frame(page,bg='white',highlightbackground='#ccdfef',highlightthickness=1);self.put(host,26+i*130,565,122,147)
            photo=tk.Label(host,bg='#eef5fa',text='Photo');photo.pack(fill='both',expand=True)
            model=tk.Label(host,bg='white',fg=INK,font=('Segoe UI',8,'bold'),wraplength=116);model.pack(fill='x')
            plate=tk.Label(host,bg='#eaf4fc',fg=INK,font=('Segoe UI',8,'bold'));plate.pack(fill='x')
            state=tk.Label(host,bg='#dcf5df',fg='#137137',font=('Segoe UI',8,'bold'));state.pack(fill='x',pady=3)
            self.vehicle_tiles.append((host,photo,model,plate,state))
        self.button('',lambda:self.move_vehicle(-4),14,548,25,25,icon='search');self.button('',lambda:self.move_vehicle(4),529,548,25,25,icon='car')
        self.panel('4. Période de réservation',578,72,532,295,'#fff7db','calendar')
        for caption,key,x,w in [('Départ','start_date',591,125),('Heure','start_time',721,71),('Retour','end_date',808,125),('Heure','end_time',938,71),('Jours','duration',1019,76)]:
            self.label(caption,x,113,w,19,size=8);f=self.field(v[key],x,136,w,30,readonly=key=='duration',tint='#e4f1ff' if key=='duration' else 'white')
            if key.endswith('date'):app._attach_date_picker(f.input,v[key])
        self.calendar_hosts=[]
        for i in range(2):
            host=tk.Frame(page,bg='white',highlightbackground='#d4e4f1',highlightthickness=1);self.put(host,591+i*254,176,246,179);self.calendar_hosts.append(host)
        self.panel('Récapitulatif rapide',1120,72,187,295,'#ece0fc','check')
        self.label('',1131,119,162,199,var=self.recap,size=9,bg='#faf7ff')
        self.panel('5. Tarif et conditions',578,377,340,282,'#efe2fc','money')
        for caption,key,x,w in [('Tarif / jour (DH)','daily_price',590,110),('Remise (%)','discount',706,81),('Total (DH)','total',793,112)]:
            self.label(caption,x,420,w,18,size=8);self.field(v[key],x,441,w,33,readonly=key=='total',tint='#fff3cc' if key=='total' else 'white',bold=True)
        self.label('Mode de paiement prévu',590,481,310,18,size=8)
        for i,(text,icon) in enumerate([('Espèces','money'),('Carte','document'),('Virement','money'),('Chèque','document'),('Traite','document')]):
            self.button(text,lambda t=text:v['payment_method'].set(t.upper()),590+(i%3)*106,501+(i//3)*24,101,22,icon=icon)
        for caption,key,x in [('Acompte (DH)','deposit',590),('Reste à payer (DH)','balance',754)]:
            self.label(caption,x,540,150,18,size=8);self.field(v[key],x,560,150,33,readonly=key=='balance',tint='#fff3cc' if key=='balance' else 'white',bold=True)
        self.label('Observations / Conditions',590,600,306,18,size=8);self.field(v['notes'],590,621,314,28)
        self.panel('6. Statut de la réservation',928,377,379,244,'#ffe8ed','car')
        self.label('Statut',940,420,352,18,size=8);self.field(v['status'],940,441,352,31,values=('EN ATTENTE','CONFIRMÉ','PAYÉ','TERMINÉ','ANNULÉ'),readonly=True,tint='#dff8e6')
        from company_agencies import AgencyStore
        agencies=self.agencies=tuple(r['name'] for r in AgencyStore(app.conn).list()) or ('Agence principale',)
        for caption,key,x,w,opts in [('Agence','agency',940,199,agencies),('Source','source',1149,145,('Agence','Téléphone','Site Web','WhatsApp','Email'))]:
            self.label(caption,x,482,w,18,size=8);self.field(v[key],x,503,w,31,values=opts)
        for caption,key,x,w in [('Référence','reference',940,199),('Création','created_display',1149,145)]:
            self.label(caption,x,545,w,18,size=8)
            if key not in v:self.created=tk.StringVar(value=datetime.now().strftime('%d/%m/%Y %H:%M'));var=self.created
            else:var=v[key]
            self.field(var,x,566,w,31,readonly=True,tint='#e9f3ff')
        self.panel('7. Documents',578,669,340,57,'#e2f1ff','document')
        for text,fn,icon,x,w,color in [('Bon PDF',app.preview_reservation,'pdf',589,100,BLUE),('WhatsApp',lambda:self.send('whatsapp'),'whatsapp',695,103,GREEN),('Email',lambda:self.send('mail'),'mail',804,103,BLUE)]:self.button(text,fn,x,705,w,20,color,icon)
        self.panel('8. Actions',928,631,379,95,'#e0f7e8','save')
        actions=[('Nouveau',self.new,'plus',GREEN),('Enregistrer',self.save,'save',BLUE),('Modifier',lambda:app.update_business_record('reservations'),'edit',BLUE),('Imprimer',app.preview_reservation,'print',BLUE),('Annuler',app._reservation_reference_cancel,'cancel','#e52e42'),('Vers location',app.reservation_to_contract,'car',GREEN)]
        for i,(text,fn,icon,color) in enumerate(actions):self.button(text,fn,940+(i%3)*118,669+(i//3)*27,112,25,color,icon)
        self.panel('Réservations en cours',12,738,1295,218,'#e2f1ff','calendar')
        keys=tuple(k for _,k in app.module_fields['reservations']);cols=keys+('booking_date','client_display','departure_display','return_display','actions')
        shown=('reference','booking_date','client_display','phone','vehicle_model','departure_display','return_display','duration','status','agency','actions')
        style=ttk.Style(page);blue_history_headings(style,'ReservationMockup.Treeview');style.configure('ReservationMockup.Treeview',rowheight=26,font=('Segoe UI',8))
        self.tree=ttk.Treeview(page,columns=cols,displaycolumns=shown,show='headings',height=5,style='ReservationMockup.Treeview');self.put(self.tree,21,781,1275,161)
        titles=('N° réservation','Date création','Client','Téléphone','Véhicule','Départ','Retour','Jours','Statut','Agence','Actions')
        for key in cols:self.tree.column(key,width=90,minwidth=20,anchor='center')
        for key,text in zip(shown,titles):self.tree.heading(key,text=text)
        self.tree.tag_configure('confirmed',background='#e8f8ed');self.tree.tag_configure('pending',background='#fff5dd');self.tree.tag_configure('cancelled',background='#fde9eb')
        self.tree.bind('<<TreeviewSelect>>',lambda _:self.select());self.tree.bind('<Double-1>',lambda _:app.preview_reservation());self.tree.bind('<ButtonRelease-1>',self.table_action,add='+')
        self.search.trace_add('write',lambda *_:self.refresh())
        self.page.bind('<Configure>',self.resize,add='+');self.ready=True;self.calendar();self.resize()
    def put(self,w,x,y,width,height,size=None):self.widgets.append((w,x,y,width,height,size));return w
    def label(self,text,x,y,w,h,bg='white',fg=INK,size=9,bold=False,var=None):return self.put(tk.Label(self.page,text=text,textvariable=var,bg=bg,fg=fg,anchor='w',font=('Segoe UI',size,'bold' if bold else 'normal'),justify='left'),x,y,w,h,size)
    def field(self,var,x,y,w,h,**kw):return self.put(RoundedField(self.page,var,**kw),x,y,w,h,10)
    def button(self,text,fn,x,y,w,h,color=BLUE,icon='document'):return self.put(IconButton(self.page,text,fn,color,icon=icon),x,y,w,h,9)
    def panel(self,title,x,y,w,h,soft,icon):
        self.put(tk.Frame(self.page,bg='white',highlightbackground='#d2e3ef',highlightthickness=1),x,y,w,h)
        self.label('     '+title,x+1,y+1,w-2,35,soft,size=11,bold=True)
        self.put(IconButton(self.page,'',lambda:None,soft,INK,icon=icon),x+5,y+4,26,26)
    def resize(self,event=None):
        if event is not None and event.widget is not self.page:return
        sx=max(1,self.page.winfo_width())/1320;sy=max(1,self.page.winfo_height())/968
        for widget,x,y,w,h,size in self.widgets:
            widget.place(x=round(x*sx),y=round(y*sy),width=max(1,round(w*sx)),height=max(1,round(h*sy)))
            if size:
                font=('Segoe UI',max(7,round(size*min(sx,sy))), 'bold' if isinstance(widget,IconButton) or isinstance(widget,RoundedField) and 'bold' in str(widget.input.cget('font')) or isinstance(widget,tk.Label) and 'bold' in str(widget.cget('font')) else 'normal')
                try:widget.configure(font=font)
                except tk.TclError:pass
        widths=(125,100,156,104,176,105,105,50,94,92,105);total=sum(widths)
        for key,w in zip(self.tree['displaycolumns'],widths):self.tree.column(key,width=max(20,round(1270*sx*w/total)),minwidth=20,stretch=False)
    def choose_client(self,code,second=False):
        if second and str(code)==self.v['client'].get():messagebox.showwarning('Conducteur','Choisissez un autre client.',parent=self.page);return
        self.v['second_client' if second else 'client'].set(str(code))
        if not second:self.app._load_reservation_client()
    def client_details(self,second):
        code=self.v['second_client' if second else 'client'].get().split('|')[0].strip();r=self.app.conn.execute('SELECT * FROM clients WHERE code=?',(code,)).fetchone()
        for (s,k),var in self.driver_vars.items():
            if s!=second:continue
            value=str(self.app._age_from_birth_date(r['date_naissance' if k=='age' else 'date_permis'] or ''))+' ans' if r and k in ('age','seniority') else str(r[k] or '') if r else ''
            if not r and not second:
                source={'code':'client','cin':'cin','nom':'last_name','prenom':'first_name','telephone':'phone'}.get(k)
                if source:value=self.v[source].get()
            var.set(value)
        label=self.driver_photos[second];label.configure(image='',text='CIN');self.images.pop(('client',second),None)
        if r:
            d=self.app.conn.execute("SELECT file_path FROM client_documents WHERE client_code=? AND document_type='CIN_RECTO' ORDER BY id DESC LIMIT 1",(code,)).fetchone()
            if d:
                p=Path(str(d[0]));p=p if p.is_file() else self.app._client_documents_folder(code,create=False)/PureWindowsPath(str(d[0])).name
                self.picture(label,p,('client',second),(90,65))
    def picture(self,label,path,key,size):
        try:
            with Image.open(path) as im:pic=ImageOps.exif_transpose(im).convert('RGB');pic.thumbnail(size)
            image=ImageTk.PhotoImage(pic);self.images[key]=image;label.configure(image=image,text='')
        except (OSError,ValueError):pass
    def changed(self,*_):
        if not self.ready:return
        self.app._calculate_reservation();self.recap.set(f"Départ\n{self.v['start_date'].get()} {self.v['start_time'].get()}\n\nRetour\n{self.v['end_date'].get()} {self.v['end_time'].get()}\n\nDurée : {self.v['duration'].get()} jours\n\n{self.v['vehicle_model'].get()}\n{self.v['plate'].get()}\n\n{self.v['status'].get()}")
        self.schedule_vehicles();self.calendar()
    def schedule_vehicles(self,*_):
        if not self.ready:return
        if self.vehicle_job:self.page.after_cancel(self.vehicle_job)
        self.vehicle_job=self.page.after(120,self.vehicles)
    def move_vehicle(self,step):self.vehicle_offset=max(0,self.vehicle_offset+step);self.vehicles()
    def vehicles(self):
        self.vehicle_job=None;term='%'+self.vehicle_query.get().strip()+'%'
        rows=self.app.conn.execute('SELECT code,modele,immatriculation FROM vehicles WHERE service=1 AND (modele LIKE ? OR immatriculation LIKE ?) ORDER BY modele',(term,term)).fetchall()
        availability={}
        for row in rows:
            p={k:var.get() for k,var in self.v.items()};p['client']=p['client'] or 'preview';p['vehicle']=row['code'];p['second_client']='';p['discount']='0'
            availability[row['code']]=not self.app._validate_reservation(p,self.v['reference'].get())
        if self.only_free.get():rows=[r for r in rows if availability[r['code']]]
        self.vehicle_offset=min(self.vehicle_offset,max(0,len(rows)-4))
        for i,tile in enumerate(self.vehicle_tiles):
            host,photo,model,plate,state=tile;index=self.vehicle_offset+i
            for widget in tile:widget.unbind('<Button-1>')
            photo.configure(image='',text='Aucun véhicule');model.configure(text='');plate.configure(text='');state.configure(text='')
            if index>=len(rows):continue
            r=rows[index];free=availability[r['code']];model.configure(text=r['modele']);plate.configure(text=r['immatriculation']);state.configure(text='Disponible' if free else 'Indisponible',bg='#dcf5df' if free else '#fde1e5',fg='#137137' if free else '#b82035');host.configure(highlightbackground=BLUE if r['code']==self.v['vehicle'].get() else '#ccdfef',highlightthickness=2 if r['code']==self.v['vehicle'].get() else 1)
            for widget in tile:widget.bind('<Button-1>',lambda _,c=r['code']:self.choose_vehicle(c))
            self.picture(photo,self.app._vehicle_photo_path(r['code']),('vehicle',i),(130,85))
    def choose_vehicle(self,code):self.v['vehicle'].set(code);self.app._load_reservation_vehicle();self.changed()
    def calendar(self):
        for offset,host in enumerate(self.calendar_hosts):
            for child in host.winfo_children():child.destroy()
            m=self.month.month-1+offset;dt=self.month.replace(year=self.month.year+m//12,month=m%12+1)
            months=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
            bar=tk.Frame(host,bg='#edf6ff');bar.pack(fill='x')
            tk.Button(bar,text='‹',command=lambda:self.shift(-1),relief='flat',bg='#edf6ff').pack(side='left')
            tk.Label(bar,text=f'{months[dt.month-1]} {dt.year}',bg='#edf6ff',fg=INK,font=('Segoe UI',8,'bold')).pack(side='left',expand=True)
            tk.Button(bar,text='›',command=lambda:self.shift(1),relief='flat',bg='#edf6ff').pack(side='right')
            body=tk.Frame(host,bg='white');body.pack(fill='both',expand=True)
            weeks=calendar.monthcalendar(dt.year,dt.month)
            for col,day in enumerate(('Lu','Ma','Me','Je','Ve','Sa','Di')):body.columnconfigure(col,weight=1);tk.Label(body,text=day,bg='white',font=('Segoe UI',7)).grid(row=0,column=col,sticky='nsew')
            for row,week in enumerate(weeks,1):
                body.rowconfigure(row,weight=1)
                for col,day in enumerate(week):
                    if not day:continue
                    text=f'{day:02d}/{dt.month:02d}/{dt.year}';date=dt.replace(day=day)
                    start=self.app._parse_french_date(self.v['start_date'].get());end=self.app._parse_french_date(self.v['end_date'].get())
                    color=BLUE if text in (self.v['start_date'].get(),self.v['end_date'].get()) else '#dfedff' if start and end and start<=date<=end else 'white'
                    tk.Button(body,text=day,command=lambda d=text:self.pick(d),relief='flat',bg=color,fg='white' if color==BLUE else INK,font=('Segoe UI',7)).grid(row=row,column=col,sticky='nsew')
    def shift(self,step):m=self.month.month-1+step;self.month=self.month.replace(year=self.month.year+m//12,month=m%12+1);self.calendar()
    def pick(self,day):self.v['start_date' if self.phase=='start' else 'end_date'].set(day);self.phase='end' if self.phase=='start' else 'start'
    def new(self):self.app.new_business_record('reservations');self.v['agency'].set(self.agencies[0]);self.v['discount'].set('0');self.v['payment_method'].set('ESPÈCES');self.v['source'].set('Agence');self.created.set(datetime.now().strftime('%d/%m/%Y %H:%M'));self.tree.selection_remove(self.tree.selection())
    def refresh(self,query=''):
        self.tree.delete(*self.tree.get_children());keys=[k for _,k in self.app.module_fields['reservations']];term=(query or self.search.get()).strip().casefold()
        for record in self.app.conn.execute("SELECT record_id,payload,created_at FROM module_records WHERE module='reservations' ORDER BY created_at DESC"):
            try:p=json.loads(record['payload'])
            except (ValueError,TypeError):continue
            if term and term not in ' '.join(str(x) for x in p.values()).casefold():continue
            status=str(p.get('status','')).upper()
            if status in ('ANNULÉ','ANNULE','TERMINÉ','TERMINE'):continue
            tag='cancelled' if status in ('ANNULÉ','ANNULE') else 'pending' if status=='EN ATTENTE' else 'confirmed'
            extra=[str(record['created_at'])[:10],f"{p.get('last_name','')} {p.get('first_name','')}",p.get('start_date',''),p.get('end_date',''),'◉   ▣   ×']
            self.tree.insert('','end',iid='reservations:'+str(record['record_id']),values=[p.get(k,'') for k in keys]+extra,tags=(tag,))
        self.client_details(False);self.client_details(True);self.changed()
    def select(self):
        self.app.select_business_record('reservations');iid=self.tree.selection()
        if iid:
            row=self.app.conn.execute("SELECT created_at FROM module_records WHERE module='reservations' AND record_id=?",(iid[0].split(':',1)[1],)).fetchone()
            if row:self.created.set(str(row[0])[:16])
        self.client_details(False);self.client_details(True);self.changed()
    def table_action(self,e):
        if self.tree.identify_column(e.x)!='#11':return
        iid=self.tree.identify_row(e.y)
        if not iid:return
        self.tree.selection_set(iid);self.select();box=self.tree.bbox(iid,'actions')
        if not box:return
        part=(e.x-box[0])*3//max(1,box[2])
        if part==2:self.app.delete_business_record('reservations')
        else:self.app.preview_reservation()
    def save(self):
        exists=self.app.conn.execute("SELECT 1 FROM module_records WHERE module='reservations' AND record_id=?",(self.v['reference'].get(),)).fetchone()
        return (self.app.update_business_record if exists else self.app.save_business_record)('reservations')
    def send(self,kind):
        p=self.app._business_payload('reservations');self.app.preview_reservation()
        text=f"Réservation {p.get('reference','')} — {p.get('vehicle_model','')} — du {p.get('start_date','')} au {p.get('end_date','')}. Total : {p.get('total','')} DH."
        if kind=='whatsapp':
            phone=''.join(c for c in p.get('phone','') if c.isdigit());phone='212'+phone[1:] if phone.startswith('0') else phone
            webbrowser.open('https://wa.me/'+phone+'?text='+quote(text))
        else:webbrowser.open('mailto:?subject='+quote('Bon de réservation '+p.get('reference',''))+'&body='+quote(text))
