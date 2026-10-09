"""Contrat de location : disposition native de la maquette du 6 octobre 2026."""
import io
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from datetime import datetime
from PIL import Image, ImageTk, ImageOps
from contract_controls import IconButton, RoundedField, AlertCard, vehicle_alerts, ModernCheck

BASE=Path(__file__).resolve().parent
BG='#f4faff';INK='#092d50';NAVY='#074575';BLUE='#0789ee';GREEN='#009d54';LINE='#d5e4ef'


def discount_amount(gross, percent):
    percent=float(percent)
    if not 0<=percent<=100:raise ValueError('La remise doit être comprise entre 0 et 100 %.')
    return round(float(gross)*percent/100,2)


def build_contract_mockup(app, win, q, commands):
    for child in win.winfo_children():child.pack_forget()
    embedded=getattr(win,'_location_embedded',False)
    if not embedded:
        width=min(1320,win.winfo_screenwidth()-50);height=min(860,win.winfo_screenheight()-100)
        win.geometry(f'{width}x{height}+{max(0,(win.winfo_screenwidth()-width)//2)}+{max(0,(win.winfo_screenheight()-height)//2)}')
        win.title('Contrat de location — Gestion Pro');win.minsize(1000,650)
    from contract_rental_histories import build_history_tabs
    root,tabs=build_history_tabs(app,win,q)
    widgets=[];images={};trace_ids=[]
    style=ttk.Style(win)
    style.configure('ContractRounded.TCombobox',padding=0,borderwidth=0,relief='flat',fieldbackground='white',foreground=INK)
    style.map('ContractRounded.TCombobox',fieldbackground=[('readonly','white')],background=[('readonly','white')],foreground=[('readonly',INK)])
    style.layout('ContractRounded.TCombobox',[('Combobox.padding',{'sticky':'nswe','children':[('Combobox.downarrow',{'side':'right','sticky':'ns'}),('Combobox.textarea',{'sticky':'nswe'})]})])
    def put(w,x,y,width,height,font=10):
        widgets.append((w,x,y,width,height,font));return w
    def label(text,x,y,w,h=28,bg=BG,fg=INK,bold=False,var=None,size=10):
        return put(tk.Label(root,text=text,textvariable=var,bg=bg,fg=fg,anchor='center',font=('Segoe UI',size,'bold' if bold else 'normal'),justify='center'),x,y,w,h,size)
    def action(text,fn,x,y,w,h=40,color=BLUE,ink='white',icon='document'):
        return put(IconButton(root,text,fn,color,ink,icon=icon),x,y,w,h)
    def entry(key,x,y,w,h=36,readonly=False,bg='white',bold=False):
        field=RoundedField(root,q[key],readonly=readonly,tint=bg,bold=bold,background=NAVY if y<62 else 'white')
        put(field,x,y,w,h,11);return field
    def combo(key,values,x,y,w,h=36,readonly=False):
        return put(RoundedField(root,q[key],values=values,readonly=readonly,background='white'),x,y,w,h)
    def panel(title,x,y,w,h,soft='#e5f1fc',icon='document'):
        put(tk.Frame(root,bg='white',highlightbackground=LINE,highlightthickness=1),x,y,w,h)
        label(title,x,y,w,38,soft,INK,True,size=12).configure(anchor='w',padx=40)
        put(IconButton(root,'',lambda:None,soft,BLUE,icon=icon),x+5,y+3,29,30)
    def keyvar(key,value=''):
        if key not in q:q[key]=tk.StringVar(value=value)
    for key in ('ui_age','ui_permit','ui_obtained','ui_seniority','ui_plate','ui_signature','ui_discount','ui_client_code','ui_vehicle_status','ui_counter'):
        keyvar(key)
    for key in ('code','nom','prenom','age','seniority','phone','address','cin','permit'):
        keyvar('ui_second_'+key)
    for key in ('ref_km_return','ref_gps','ref_baby','ref_extra_insurance','ref_extra_driver','ref_category'):
        keyvar(key,'0' if key.startswith('ref_extra') or key in ('ref_gps','ref_baby') else '')
    from company_agencies import AgencyStore
    names=tuple(r['name'] for r in AgencyStore(app.conn).list()) or ('Agence principale',)
    put(tk.Frame(root,bg=NAVY),0,0,1536,70)
    title_label=label('Contrat de location',26,4,730,62,NAVY,'white',True,size=23);title_label.configure(anchor='w',padx=48)
    put(IconButton(root,'',lambda:None,NAVY,icon='document'),22,16,40,40)
    label('N° Contrat',803,3,180,23,NAVY,'white');entry('numero',803,28,180,35,True,'#e3f1ff',True)
    label('Date',994,3,165,23,NAVY,'white')
    issue=tk.StringVar(value=datetime.now().strftime('%d/%m/%Y'))
    put(RoundedField(root,issue,readonly=True,background=NAVY),994,28,165,35,11)
    label('Agence',1171,3,220,23,NAVY,'white');combo('ref_depart',names,1171,28,220,35,True)
    action('',lambda:app.show_page('dashboard') if embedded else win.destroy(),1475,16,40,40,NAVY,icon='cancel')
    identity_previews={}
    for second,x,title,soft in ((False,17,'Premier conducteur','#e3f1ff'),(True,777,'Deuxième conducteur (optionnel)','#e3f7e7')):
        panel(title,x,82,742,207,soft,'person')
        if second:
            action('Rechercher un client',lambda:search_second(),x+453,85,225,31,BLUE,icon='search')
            action('',lambda:app.open_quick_client_dialog(select_second),x+683,85,43,31,GREEN,icon='plus')
        else:
            client=combo('client',commands['clients'],x+400,85,270,31)
            action('',lambda:search_first(),x+675,85,50,31,BLUE,icon='search')
        for i,(caption,first,other) in enumerate((('Code client :','ui_client_code','code'),('Nom :','ref_nom','nom'),('Prénom :','ref_prenom','prenom'),('Âge :','ui_age','age'),('Ancienneté permis :','ui_seniority','seniority'))):
            y=128+i*30
            label(caption,x+12,y,153,27,'white').configure(anchor='w')
            key='ui_second_'+other if second else first
            label('',x+168,y,145,27,'#e6f4fd' if i==3 else '#e5f8e6' if i==4 else 'white',bold=True,var=q[key]).configure(anchor='w',padx=6)
        for i,(caption,first,other,icon) in enumerate((('','ref_phone','phone','phone'),('','ref_address','address','location'),('CIN : ','ref_cin','cin','document'),('Permis : ','ui_permit','permit','document'))):
            y=133+i*37;key='ui_second_'+other if second else first
            put(IconButton(root,'',lambda:None,'white',NAVY,icon=icon),x+329,y,28,28)
            text=label('',x+362,y,218,28,'white',var=q[key]);text.configure(anchor='w')
        for i,kind in enumerate(('CIN_RECTO','PERMIS_RECTO')):
            doc=put(tk.Label(root,bg='#f0f5f8',fg='#60778a',text='CIN recto' if i==0 else 'Permis recto'),x+590,132+i*73,135,65)
            identity_previews[('ref_second' if second else 'client',kind)]=doc
            doc.bind('<Button-1>',lambda e,k='ref_second' if second else 'client',d=kind:open_identity(k,d))
    panel('3. Véhicule',17,302,913,254,icon='car')
    panel('4. Période de location',942,302,577,254,icon='calendar')
    action('Choisir un véhicule',commands['choose_vehicle'],677,306,238,31,GREEN,icon='search')
    photo=put(tk.Label(root,text='Photo du véhicule',bg='#e6eef5',fg=INK),35,351,252,120)
    photo.bind('<Button-1>',lambda e:commands['choose_vehicle']())
    gallery_paths=[];gallery_thumbs=[]
    for i in range(3):
        thumb=put(tk.Label(root,text='Photo',bg='#edf5fa',fg='#66798a'),35+i*84,478,78,43);gallery_thumbs.append(thumb)
        thumb.bind('<Button-1>',lambda e,n=i:select_vehicle_photo(n))
    brand_logo=put(tk.Label(root,bg='white'),299,353,32,30)
    label('',339,351,226,34,'white',bold=True,var=q['ref_brand'],size=14)
    label('',302,388,262,39,'white',bold=True,var=q['ref_model'])
    plate_choices={str(r['immatriculation']):str(r['code']) for r in app.conn.execute('SELECT code,immatriculation FROM vehicles WHERE service=1 OR code=?',(q['vehicle'].get(),))}
    vehicle=combo('ui_plate',tuple(plate_choices),302,434,262,34,True)
    def select_plate(_=None):
        q['vehicle'].set(plate_choices.get(q['ui_plate'].get(),''));load_vehicle()
    label('Km départ',36,523,90,30,'white',fg='#0879cf',bold=True)
    km_field=entry('km_start',127,521,160,33,bg='#ddf3ff',bold=True)
    km_field.input.configure(fg='#0070bb',font=('Segoe UI',18,'bold'))
    widgets[-1]=(*widgets[-1][:-1],18)
    label('',302,477,262,29,'#e3f8e8',bold=True,var=q['ui_vehicle_status'])
    label('Compteur',302,513,59,31,'#092d50',fg='#a6c3df',size=8)
    label('',361,513,99,31,'#092d50',fg='#70efc2',bold=True,var=q['ui_counter'],size=12)
    action('Réglages',lambda:options_dialog(),466,513,98,31,'#edf5fc',INK,icon='gear')
    alert_cards=[]
    for i,alert in enumerate(vehicle_alerts({})):
        x=579+(i%2)*167;y=352+(i//2)*64
        card=AlertCard(root,alert);put(card,x,y,159,57);alert_cards.append(card)
    current_alert_row=[None];blink_phase=[False];blink_job=[None]
    def update_alerts(*_):
        for card,alert in zip(alert_cards,vehicle_alerts(current_alert_row[0] or {},q['km_start'].get())):card.set_alert(alert)
    def blink_alerts():
        if not root.winfo_exists():return
        visible=not embedded or getattr(app,'current_page_name','location_integrated')=='location_integrated'
        blink_phase[0]=not blink_phase[0] if visible else False
        for card in alert_cards:card.paint(blink_phase[0] if card.alert['active'] else False)
        blink_job[0]=root.after(650,blink_alerts)
    blink_job[0]=root.after(650,blink_alerts)
    trace_ids.append((q['km_start'],q['km_start'].trace_add('write',update_alerts)))
    fuel_buttons=[];label('Carburant',753,479,153,24,'white')
    for i in range(8):
        fuel_buttons.append(put(tk.Button(root,relief='flat',command=lambda n=i+1:q['ref_fuel'].set(str(n))),754+i*17,509,15,23))
    fuel_text=tk.StringVar();label('',875,530,40,22,'white',var=fuel_text,size=9)
    for caption,k,t,x in (('Date et heure départ','start','start_time',959),('Date et heure retour','end','end_time',1180)):
        label(caption,x,350,209,25,'white');e=entry(k,x,382,128,37);app._attach_date_picker(e,q[k]);combo(t,app._times(),x+133,382,76,37)
    label('Nombre de jours',1400,350,104,25,'white');entry('ref_days',1400,382,104,37,True,'#eaf4ff',True)
    for caption,k,x in (('Lieu de départ','ref_depart',959),('Lieu de retour','ref_return',1231)):
        label(caption,x,448,265,25,'white');combo(k,names,x,478,265,38,True)
    panel('5. État du véhicule',17,568,779,243,icon='car')
    panel('6. Tarifs et paiements',808,568,711,243,'#eeeafa','money')
    condition_pages={};condition_buttons=[];tools=[]
    for i,(caption,icon) in enumerate((('Carrosserie','car'),('Équipement','gear'),('Photos','camera'))):
        condition_buttons.append(action(caption,lambda n=i:select_condition(n),30+i*138,610,132,29,BLUE if i==0 else '#e9f2f9','white' if i==0 else INK,icon=icon))
    state_canvas=put(tk.Canvas(root,bg='white',highlightthickness=0),30,646,240,148)
    state_tool=tk.StringVar(value='#ed3345');strokes=[];current=[];state_source=None;transform=(0,0,1,1);equipment={}
    condition_pages[0]=state_canvas
    gear=put(tk.Frame(root,bg='white'),30,646,425,148);condition_pages[1]=gear
    from vehicle_condition import EQUIPMENT
    for i,name in enumerate(EQUIPMENT):
        v=tk.BooleanVar();equipment[name]=v;ModernCheck(gear,text=name,variable=v,width=205,height=26).grid(row=i//2,column=i%2,sticky='ew',padx=2,pady=1)
    photo_page=put(tk.Frame(root,bg='white'),30,646,425,148);condition_pages[2]=photo_page
    photo_list=ttk.Combobox(photo_page,state='readonly');photo_list.pack(fill='x',padx=5,pady=6)
    photo_paths=[]
    def add_photos():
        import shutil
        paths=filedialog.askopenfilenames(parent=win,filetypes=[('Images','*.png *.jpg *.jpeg')])
        for path in paths:
            try:
                with Image.open(path) as im:im.verify()
                folder=BASE/'documents_contrats'/q['numero'].get().strip();folder.mkdir(parents=True,exist_ok=True)
                target=folder/(datetime.now().strftime('%Y%m%d%H%M%S%f')+'_'+Path(path).name);shutil.copy2(path,target);photo_paths.append(str(target))
            except (OSError,ValueError) as exc:messagebox.showerror('Photo',str(exc),parent=win)
        photo_list.configure(values=[Path(p).name for p in photo_paths]);photo_list.current(len(photo_paths)-1) if photo_paths else None
        refresh_damage_photos()
    def open_photo():
        import webbrowser
        i=photo_list.current()
        if i>=0:webbrowser.open(Path(photo_paths[i]).resolve().as_uri())
    photo_add=IconButton(photo_page,'Ajouter des photos',add_photos,GREEN,icon='camera');photo_add.configure(width=175,height=35);photo_add.pack(side='left',padx=5)
    photo_open=IconButton(photo_page,'Ouvrir la photo',open_photo,BLUE,icon='search');photo_open.configure(width=160,height=35);photo_open.pack(side='left')
    label('Observations état du véhicule',470,610,306,27,'white').configure(anchor='w')
    state_notes=put(tk.Text(root,bg='white',fg=INK,font=('Segoe UI',10),wrap='word',highlightthickness=1,highlightbackground=LINE),470,643,306,99)
    damage_previews=[put(tk.Label(root,text='Photo',bg='#edf5fa',fg='#66798a'),470+i*96,754,90,40) for i in range(2)]
    action('Ajouter photos',add_photos,665,754,111,40,'#edf5fc',INK,icon='camera')
    damage_types={}
    for i,(caption,color) in enumerate((('Rayure','#ed3345'),('Choc','#0086ee'),('Pare-brise','#efad00'),('Rétroviseur','#efad00'),('Jante','#efad00'),('Autre','#0fa260'))):
        var=tk.BooleanVar();damage_types[caption]=var
        tools.append(put(ModernCheck(root,text=caption,variable=var,command=lambda c=color:state_tool.set(c),color=color,width=166,height=22),284,644+i*22,166,22))
    tools.append(action('Effacer',lambda:clear_strokes(),284,781,166,21,'#e9f2f9',INK,icon='eraser'))
    condition_index=[0]
    def select_condition(index):
        condition_index[0]=index
        for i,b in enumerate(condition_buttons):b.configure(bg=BLUE if i==index else '#e9f2f9',fg='white' if i==index else INK)
        resize(None)
    for caption,k,x,width,tint in (('Tarif journalier (DH)','price',824,217,'white'),('Remise (%)','ui_discount',1056,186,'white'),('Total (DH)','total',1256,245,'#fff5ce')):
        label(caption,x,610,width,25,'white');entry(k,x,640,width,37,k=='total',tint,True)
    label('Mode de paiement',824,681,677,24,'white').configure(anchor='w')
    payment_buttons=[]
    for i,(title,value,icon) in enumerate((('Espèces','ESPÈCES','money'),('Carte','CARTE','document'),('Virement','VIREMENT','money'),('Chèque','CHÈQUE','document'),('Traite','TRAITE','document'))):
        b=action(title,lambda v=value:q['payment_mode'].set(v),824+i*137,709,129,33,BLUE if q['payment_mode'].get()==value else '#e9f3ff','white' if q['payment_mode'].get()==value else INK,icon=icon);payment_buttons.append((b,value))
    def payment_changed(*_):
        for b,value in payment_buttons:b.configure(bg=BLUE if q['payment_mode'].get()==value else '#e9f3ff',fg='white' if q['payment_mode'].get()==value else INK)
    trace_ids.append((q['payment_mode'],q['payment_mode'].trace_add('write',payment_changed)))
    for caption,k,x,w,tint in (('Acompte (DH)','paid',824,318,'white'),('Reste à payer (DH)','balance',1157,344,'#fff5ce')):
        label(caption,x,745,w,23,'white');entry(k,x,772,w,31,k=='balance',tint,True)
    panel('7. Observations générales',17,823,779,122,icon='document')
    notes=put(tk.Text(root,bg='white',fg=INK,font=('Segoe UI',10),wrap='word',highlightthickness=1,highlightbackground=LINE),30,869,749,65)
    notes.insert('1.0',q['ref_notes'].get())
    panel('8. Signatures',808,823,711,122,icon='signature')
    label('Signature client',824,867,160,22,'white',size=9)
    signature=put(tk.Label(root,bg='white',fg=INK,text='En attente de signature'),985,867,177,48)
    label('',824,917,338,22,'white',bold=True,var=q['ui_signature'],size=8)
    label('Signature agence',1179,867,151,22,'white',size=9)
    agency_signature=put(tk.Label(root,bg='white',fg=INK,text='Signature agence'),1331,867,168,49)
    agency_name=app._get_setting('company_name','HBZ RENT CAR') if hasattr(app,'_get_setting') else 'HBZ RENT CAR'
    label(agency_name,1179,918,320,21,'white',size=8)
    try:
        with Image.open(BASE/'assets'/'CACHET_SIGNATURE.png') as im:
            im=im.convert('RGBA');im.thumbnail((160,46));images['agency_signature']=ImageTk.PhotoImage(im);agency_signature.configure(image=images['agency_signature'],text='')
    except OSError:pass
    def modify():
        number=q['numero'].get().strip()
        if not app.conn.execute('SELECT 1 FROM contracts WHERE numero=?',(number,)).fetchone():
            number=''
            for tree in getattr(tabs,'_history_trees',{}).values():
                if tree.selection():number=str(tree.item(tree.selection()[0],'values')[0]);break
        if not number:
            messagebox.showinfo('Modifier','Sélectionnez un contrat depuis un historique pour le modifier.',parent=win);tabs.select(1);return
        if commands['modify'](number):tabs.select(0);price_field.input.focus_set()
    def send_email():
        from contract_email import prepare_contract_email
        if not commands['save']():return
        row=app.conn.execute('SELECT email FROM clients WHERE code=?',(code('client'),)).fetchone()
        prepare_contract_email(app,win,q['numero'].get(),str(row[0] or '') if row else '')
    price_field=next(w for w,x,y,ww,hh,fs in widgets if isinstance(w,RoundedField) and x==824 and y==640)
    footer=(('Nouveau',commands['new'],GREEN,'plus',126),('Modifier',modify,BLUE,'edit',126),('Enregistrer',lambda:commands['save'](),BLUE,'save',143),('Supprimer',commands['delete'],'#ee303e','trash',134),('Aperçu',commands['pdf'],'#68798d','search',112),('PDF',lambda:after_signature(),NAVY,'pdf',103),('Imprimer',commands['print'],BLUE,'print',125),('Signature électronique',commands['signature'],GREEN,'signature',212),('Envoyer WhatsApp',commands['whatsapp'],GREEN,'whatsapp',189),('Envoyer Email',send_email,BLUE,'mail',171))
    x=17
    for title,fn,color,icon,width in footer:action(title,fn,x,962,width,47,color,icon=icon);x+=width+7
    label('',17,1010,1502,14,var=q['status'],size=8)
    def refresh_damage_photos():
        for i,target in enumerate(damage_previews):
            try:
                with Image.open(photo_paths[i]) as im:
                    im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((90,40));images['damage_'+str(i)]=ImageTk.PhotoImage(im)
                target.configure(image=images['damage_'+str(i)],text='')
                target.bind('<Button-1>',lambda e,n=i:open_damage_photo(n))
            except (IndexError,OSError):target.configure(image='',text='Photo')
    def open_damage_photo(n):
        import webbrowser
        if n<len(photo_paths):webbrowser.open(Path(photo_paths[n]).resolve().as_uri())
    def select_vehicle_photo(n):
        nonlocal state_source
        if n>=len(gallery_paths):return
        try:
            with Image.open(gallery_paths[n]) as im:state_source=ImageOps.exif_transpose(im).convert('RGB').copy()
            resize(None)
        except OSError:pass
    def refresh_gallery():
        for i,target in enumerate(gallery_thumbs):
            try:
                with Image.open(gallery_paths[i]) as im:
                    im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((78,43));images['gallery_'+str(i)]=ImageTk.PhotoImage(im)
                target.configure(image=images['gallery_'+str(i)],text='')
            except (IndexError,OSError):target.configure(image='',text='Photo')
    def vehicle_status(row):
        from datetime import datetime
        today=datetime.now().strftime('%Y-%m-%d')
        rent=app.conn.execute("SELECT 1 FROM contracts WHERE vehicle_code=? AND (substr(date_depart,7,4)||'-'||substr(date_depart,4,2)||'-'||substr(date_depart,1,2))<=? AND (substr(date_retour,7,4)||'-'||substr(date_retour,4,2)||'-'||substr(date_retour,1,2))>=? AND COALESCE(return_status,'') NOT IN ('RETURNED','RETOUR CONFIRMÉ','RETOUR CONFIRME') AND numero<>? LIMIT 1",(row['code'],today,today,q['numero'].get())).fetchone()
        return 'Loué' if rent else 'Disponible' if row['service'] else 'Hors service'
    identity_cache={}
    def identity_path(k,kind):
        row=app.conn.execute('SELECT file_path FROM client_documents WHERE client_code=? AND document_type=? ORDER BY id DESC LIMIT 1',(code(k),kind)).fetchone()
        if not row:return None
        from client_reference_ui import _resolve_existing_client_document
        return _resolve_existing_client_document(app,code(k),row[0])
    def refresh_identity(k):
        for kind in ('CIN_RECTO','PERMIS_RECTO'):
            target=identity_previews[(k,kind)];path=identity_path(k,kind)
            if not path:target.configure(image='',text='CIN recto' if kind=='CIN_RECTO' else 'Permis recto');continue
            cache_key=(str(path),path.stat().st_mtime_ns)
            try:
                if cache_key not in identity_cache:
                    with Image.open(path) as im:
                        im=ImageOps.exif_transpose(im).convert('RGB');im.thumbnail((130,62));identity_cache[cache_key]=ImageTk.PhotoImage(im)
                target.configure(image=identity_cache[cache_key],text='')
            except (OSError,ValueError):target.configure(image='',text='Ouvrir le document')
    def open_identity(k,kind):
        import webbrowser
        path=identity_path(k,kind)
        if path:webbrowser.open(path.as_uri())
    def options_dialog():
        dialog=app._secondary_window(win);dialog.title('Réglages du contrat');dialog.transient(win.winfo_toplevel())
        for key,caption in (('ref_category','Catégorie'),('ref_km_return','Kilométrage retour prévu'),('ref_deposit','Caution (DH)'),('ref_insurance','Assurance (DH)')):
            tk.Label(dialog,text=caption).pack(anchor='w',padx=12,pady=3);ttk.Entry(dialog,textvariable=q[key]).pack(fill='x',padx=12)
        for key,caption in (('ref_gps','GPS'),('ref_baby','Siège bébé'),('ref_extra_insurance','Assurance complémentaire'),('ref_extra_driver','Conducteur supplémentaire')):
            ModernCheck(dialog,text=caption,variable=q[key],onvalue='1',offvalue='0',width=280,height=30).pack(fill='x',padx=12,pady=3)
        IconButton(dialog,'Fermer',dialog.destroy,BLUE,icon='check',width=130,height=34).pack(pady=12)
    def code(k):return q[k].get().split('|',1)[0].strip()
    def update_drivers():
        q['ui_client_code'].set(code('client'))
        for k in ('client','ref_second'):
            row=app.conn.execute('SELECT * FROM clients WHERE code=?',(code(k),)).fetchone()
            if k=='ref_second':
                mapping={'code':'code','nom':'nom','prenom':'prenom','phone':'telephone','address':'adresse','cin':'cin','permit':'permis'}
                for key,column in mapping.items():q['ui_second_'+key].set(str(row[column] or '') if row else '')
                q['ui_second_age'].set(str(app._age_from_birth_date(row['date_naissance'] or ''))+' ans' if row else '')
                q['ui_second_seniority'].set(str(app._age_from_birth_date(row['date_permis'] or ''))+' ans' if row else '')
            refresh_identity(k)
    def search_first():
        from client_selector import open_client_selector
        def select(c):q['client'].set(c);load_client()
        return open_client_selector(app,win,select,title='Premier conducteur — rechercher un client')
    def search_second():
        from client_selector import open_client_selector
        def clear():q['ref_second'].set('');update_drivers()
        return open_client_selector(app,win,select_second,title='Deuxième conducteur — rechercher un client',exclude=code('client'),on_clear=clear)
    def select_second(c):
        if c==code('client'):messagebox.showwarning('Conducteur','Choisissez un autre client.',parent=win);return
        q['ref_second'].set(c);update_drivers()
    def load_client(*_):
        commands['load_client']();r=app.conn.execute('SELECT * FROM clients WHERE code=?',(code('client'),)).fetchone()
        if r:
            for key,column in (('ref_cin','cin'),('ref_nom','nom'),('ref_prenom','prenom'),('ref_phone','telephone'),('ref_address','adresse'),('ui_permit','permis'),('ui_obtained','date_permis')):q[key].set(str(r[column] or ''))
            q['ui_age'].set(str(app._age_from_birth_date(r['date_naissance'] or ''))+' ans')
            years=app._age_from_birth_date(r['date_permis'] or '');q['ui_seniority'].set(str(years)+' ans' if years else '')
            q['ui_signature'].set('CIN : '+str(r['cin'] or ''))
        update_drivers();refresh_signature()
        if not r:
            for key in ('ref_cin','ref_nom','ref_prenom','ref_phone','ref_address','ui_permit','ui_obtained','ui_age','ui_seniority'):q[key].set('')
            q['ui_signature'].set('');signature.configure(image='',text='En attente de signature')
    def load_vehicle(*_,initial=False):
        nonlocal state_source
        saved_price=q['price'].get();saved_km=q['km_start'].get()
        commands['load_vehicle']()
        if initial:
            if saved_price:q['price'].set(saved_price)
            if saved_km:q['km_start'].set(saved_km)
        r=app.conn.execute('SELECT * FROM vehicles WHERE code=?',(code('vehicle'),)).fetchone()
        current_alert_row[0]=r;update_alerts()
        q['ui_counter'].set(f"{int(r['compteur'] or 0):,} km".replace(',', ' ') if r else '')
        if not r:
            state_source=None;strokes.clear();photo_paths.clear();gallery_paths.clear();refresh_gallery();refresh_damage_photos();state_notes.delete('1.0','end');q['ui_vehicle_status'].set('');resize(None);return
        model=str(r['modele'] or '');q['ref_brand'].set(model.split()[0] if model else '');q['ref_model'].set(model);q['ui_plate'].set(str(r['immatriculation'] or ''));q['ui_vehicle_status'].set(vehicle_status(r))
        logo=BASE/'assets'/'vehicle_brands'/(q['ref_brand'].get().casefold()+'.png')
        try:
            with Image.open(logo) as im:
                im=im.convert('RGBA');im.thumbnail((30,30));images['brand']=ImageTk.PhotoImage(im)
            brand_logo.configure(image=images['brand'])
        except (OSError,ValueError):brand_logo.configure(image='')
        path=app._resolve_vehicle_photo_path(r['photo'],r['code'])
        try:
            if not path:raise OSError('Photo absente')
            with Image.open(path) as im:state_source=ImageOps.exif_transpose(im).convert('RGB').copy()
        except (OSError,TypeError):state_source=None
        from vehicle_condition import read_state
        data=read_state(app.conn,'contract_vehicle_condition',q['numero'].get()) or read_state(app.conn,'vehicle_condition',code('vehicle'))
        strokes[:]=data.get('strokes',[])
        state_notes.delete('1.0','end');state_notes.insert('1.0',data.get('observations',''))
        photo_paths[:]=[p for p in data.get('photos',[]) if Path(p).is_file()]
        photo_list.configure(values=[Path(p).name for p in photo_paths])
        if photo_paths:photo_list.current(0)
        gallery_paths[:]=([str(path)] if path and Path(path).is_file() else [])
        refresh_gallery();refresh_damage_photos()
        for name,v in damage_types.items():v.set(bool(data.get('damage_types',{}).get(name)))
        for name,v in equipment.items():v.set(bool(data.get('equipment',{}).get(name)))
        paint_state();resize(None)
    pending=[None]
    def search_client(_=None):
        if pending[0]:root.after_cancel(pending[0])
        typed=q['client'].get().strip()
        def apply():
            pending[0]=None
            exact=app.conn.execute('SELECT code,nom,prenom,telephone,cin FROM clients WHERE code=? OR cin=? OR telephone=? OR nom=? OR prenom=?',(typed,)*5).fetchall()
            if len(exact)==1:
                q['client'].set(exact[0]['code']);load_client();return
            like='%'+typed+'%'
            rows=app.conn.execute('SELECT code,nom,prenom,telephone,cin FROM clients WHERE code LIKE ? OR nom LIKE ? OR prenom LIKE ? OR telephone LIKE ? OR cin LIKE ? ORDER BY nom,prenom LIMIT 51',(like,)*5).fetchall()
            client.configure(values=[f"{r['code']} | {r['nom']} {r['prenom']} | {r['telephone']} | {r['cin']}" for r in rows[:50]])
            if typed and len(rows)==1:q['client'].set(rows[0]['code']);load_client()
        pending[0]=root.after(120,apply)
    client.bind('<<ComboboxSelected>>',load_client);client.bind('<Return>',load_client);client.bind('<KeyRelease>',search_client)
    vehicle.bind('<<ComboboxSelected>>',select_plate);vehicle.bind('<Return>',select_plate)
    # The photo chooser uses the original callback: synchronize display after it closes.
    last_vehicle=['']
    def vehicle_changed(*_):
        if getattr(win,'_maquette_suspend_vehicle',False):last_vehicle[0]=code('vehicle');return
        if code('vehicle')!=last_vehicle[0]:
            last_vehicle[0]=code('vehicle');root.after_idle(load_vehicle)
    trace_ids.append((q['vehicle'],q['vehicle'].trace_add('write',vehicle_changed)))
    def paint_fuel(*_):
        try:level=max(0,min(8,int(q['ref_fuel'].get())))
        except ValueError:level=0
        colors=('#ed2939','#efb928','#c5dd62')+('#009e54',)*5
        for i,b in enumerate(fuel_buttons):b.configure(bg=colors[i] if i<level else '#d3dce6')
        fuel_text.set(f'{level}/8')
    trace_ids.append((q['ref_fuel'],q['ref_fuel'].trace_add('write',paint_fuel)));paint_fuel()
    discount_lock=[False]
    try:
        gross=app._number(q['ref_gross'].get());q['ui_discount'].set(f'{app._number(q["ref_discount"].get())*100/gross:.2f}' if gross else '0')
    except (ValueError,ZeroDivisionError):q['ui_discount'].set('0')
    def apply_discount(*_):
        if discount_lock[0]:return
        try:
            discount_lock[0]=True
            amount=discount_amount(app._number(q['ref_gross'].get()),app._number(q['ui_discount'].get()))
            if abs(app._number(q['ref_discount'].get())-amount)>.001:q['ref_discount'].set(str(amount))
        except ValueError:pass
        finally:discount_lock[0]=False
    for k in ('ui_discount','ref_gross'):trace_ids.append((q[k],q[k].trace_add('write',apply_discount)))
    def paint_state(*_):
        nonlocal transform
        from vehicle_condition import draw_state
        try:
            im=draw_state(strokes+([{'points':current,'color':state_tool.get()}] if current else []))
            im.thumbnail((max(1,state_canvas.winfo_width()),max(1,state_canvas.winfo_height())))
            x=(state_canvas.winfo_width()-im.width)/2;y=(state_canvas.winfo_height()-im.height)/2
            transform=(x,y,im.width,im.height);images['state']=ImageTk.PhotoImage(im)
            state_canvas.delete('all');state_canvas.create_image(x,y,image=images['state'],anchor='nw')
        except (OSError,ValueError):state_canvas.delete('all');state_canvas.create_text(20,20,text='Choisissez un véhicule pour annoter son état.',anchor='w',fill=INK)
    def point(e):
        x,y,w,h=transform
        if w>0 and h>0 and x<=e.x<=x+w and y<=e.y<=y+h:return ((e.x-x)/w,(e.y-y)/h)
    def begin(e):current.clear();p=point(e);current.append(p) if p else None
    def drag(e):
        p=point(e)
        if current and p:current.append(p);paint_state()
    def finish(e):
        if len(current)>1:strokes.append({'points':current.copy(),'color':state_tool.get()})
        current.clear();paint_state()
    def clear_strokes():strokes.clear();paint_state()
    state_canvas.bind('<Button-1>',begin);state_canvas.bind('<B1-Motion>',drag);state_canvas.bind('<ButtonRelease-1>',finish);state_canvas.bind('<Configure>',paint_state)
    signature_cache={}
    signature_revision=[None]
    def refresh_signature():
        from phone_signature import saved_signature
        from client_contract_signature import client_preview_signature
        from client_contract_signature import contract_signature
        client_code=code('client')
        payload=contract_signature(app.conn,q['numero'].get(),client_code)
        if not payload:
            if client_code not in signature_cache:signature_cache[client_code]=client_preview_signature(app.conn,q['numero'].get(),client_code)
            payload=signature_cache[client_code]
        import hashlib
        revision=(client_code,q['numero'].get(),hashlib.sha256(payload).hexdigest() if payload else '')
        if revision==signature_revision[0]:return
        signature_revision[0]=revision
        if payload:
            try:
                im=Image.open(io.BytesIO(payload));im.thumbnail((170,46));images['signature']=ImageTk.PhotoImage(im);signature.configure(image=images['signature'],text='')
            except (OSError,ValueError):signature.configure(image='',text='Signature indisponible')
        else:signature.configure(image='',text='En attente de signature')
    def client_identity_changed(*_):
        signature.configure(image='',text='En attente de signature');signature_revision[0]=None
        refresh_signature()
    trace_ids.append((q['client'],q['client'].trace_add('write',client_identity_changed)))
    signature_job=[None]
    def signature_poll():
        if not root.winfo_exists():return
        refresh_signature();signature_job[0]=root.after(2000,signature_poll)
    signature_job[0]=root.after(2000,signature_poll)
    def after_signature():
        from phone_signature import saved_signature
        from client_contract_signature import contract_signature
        if not contract_signature(app.conn,q['numero'].get(),code('client')):messagebox.showinfo('Signature','Faites signer le contrat avant de générer ce PDF.',parent=win);return
        commands['recto_pdf']()
    def sync():
        q['ref_notes'].set(notes.get('1.0','end-1c'))
        try:discount_amount(app._number(q['ref_gross'].get()),app._number(q['ui_discount'].get()))
        except ValueError:q['ref_discount'].set('-1')
    original_save=commands['save']
    def save():
        try:discount_amount(app._number(q['ref_gross'].get()),app._number(q['ui_discount'].get()))
        except ValueError as exc:messagebox.showwarning('Remise',str(exc),parent=win);return
        sync();return original_save()
    def store_condition(number,vehicle_code):
        from vehicle_condition import draw_state
        import json
        from uuid import uuid4
        folder=BASE/'assets'/'vehicle_states';folder.mkdir(parents=True,exist_ok=True)
        dest=folder/(uuid4().hex+'.png');draw_state(strokes).save(dest)
        data={'vehicle_code':vehicle_code,'observations':state_notes.get('1.0','end-1c'),'strokes':strokes,'damage_types':{k:v.get() for k,v in damage_types.items()},'equipment':{k:v.get() for k,v in equipment.items()},'drawing':str(dest.relative_to(BASE)),'photos':photo_paths.copy()}
        app.conn.execute('INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,?)',('contract_vehicle_condition',number,json.dumps(data,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')))
    commands['save']=save
    win._contract_condition_snapshot=store_condition
    win._client_rapide_sync=sync;win._client_rapide_reload=load_client;win._maquette_vehicle_reload=load_vehicle;win._location_number_var=q['numero']
    def resize(e):
        if e is not None and e.widget is not root:return
        sx=max(1,root.winfo_width())/1536;sy=max(1,root.winfo_height())/1024;scale=min(sx,sy)
        for w,x,y,width,height,size in widgets:
            if w in condition_pages.values() and w is not condition_pages[condition_index[0]] or w in tools and condition_index[0]!=0:w.place_forget();continue
            w.place(x=round(x*sx),y=round(y*sy),width=max(1,round(width*sx)),height=max(1,round(height*sy)))
            if 'font' in w.keys():w.configure(font=('Segoe UI',max(8,round(size*scale)),'bold' if 'bold' in str(w.cget('font')) else 'normal'))
        if state_source:
            im=state_source.copy();im.thumbnail((max(1,round(252*sx)),max(1,round(120*sy))));images['vehicle']=ImageTk.PhotoImage(im);photo.configure(image=images['vehicle'],text='')
        else:photo.configure(image='',text='Photo du véhicule')
        paint_state()
    def cleanup(e):
        if e.widget is not root:return
        for job in (blink_job[0],signature_job[0],pending[0]):
            if job:
                try:root.after_cancel(job)
                except tk.TclError:pass
        for v,tid in trace_ids:
            try:v.trace_remove('write',tid)
            except tk.TclError:pass
    root.bind('<Configure>',resize);root.bind('<Destroy>',cleanup,add='+')
    root._maquette_widgets=widgets;root._maquette_q=q;root._search_second=search_second
    load_client();load_vehicle(initial=True);commands['calculate']();resize(None)
    return root
