"""Deux formulaires de location HBZ reliés aux contrats existants."""
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from pathlib import Path
import os
import subprocess
import sys
import json
import calendar

BLUE='#0868bb'; NAVY='#0b316d'; BG='#eaf4fc'; WHITE='white'

class LocationFormsReferenceMixin:
    def _loc_section(self,parent,title,color=BLUE):
        shell=tk.Frame(parent,bg=WHITE,highlightbackground='#c8dce9',highlightthickness=1)
        band=tk.Canvas(shell,height=34,highlightthickness=0,bg=color)
        band.pack(fill='x')
        label=band.create_text(12,17,text=title,fill=WHITE,font=('Segoe UI',10,'bold'),anchor='w')
        def paint(event):
            band.delete('gradient')
            start=(4,75,153);end=(0,148,224)
            for x in range(0,event.width,3):
                t=x/max(1,event.width)
                rgb=tuple(round(a+(b-a)*t) for a,b in zip(start,end))
                band.create_rectangle(x,0,x+3,34,fill='#%02x%02x%02x'%rgb,outline='',tags='gradient')
            band.tag_raise(label)
        band.bind('<Configure>',paint)
        return shell

    def _contract_ref_header_search(self,section,variable,command,values=None,width=112):
        """Place la recherche dans la bande du bloc, sans prendre une ligne du formulaire."""
        band=section.winfo_children()[0]
        tools=tk.Frame(band,bg='#dcecf8')
        if values is None:
            entry=tk.Entry(tools,textvariable=variable,width=12,relief='flat',bd=0,
                           bg='white',fg=NAVY,font=('Segoe UI',10))
            entry.pack(side='left',fill='x',expand=True,padx=(2,0),ipady=3)
        else:
            entry=ttk.Combobox(tools,textvariable=variable,values=values,width=13,font=('Segoe UI',10))
            entry.pack(side='left',fill='x',expand=True,padx=(2,0))
            entry.bind('<<ComboboxSelected>>',lambda _e:command())
        entry.bind('<Return>',lambda _e:command())
        tk.Button(tools,text='⌕',command=command,bg='#dcecf8',fg=NAVY,relief='flat',bd=0,
                  font=('Segoe UI',10,'bold'),cursor='hand2').pack(side='left',padx=2)
        window=band.create_window(0,17,window=tools,anchor='e',width=width)
        def place_search(event):
            band.coords(window,event.width-8,17)
            band.tag_raise(window)
        band.bind('<Configure>',place_search,add='+')
        return entry

    def _contract_ref_code_square(self,parent,title,variable,color):
        line=tk.Frame(parent,bg=WHITE);line.pack(fill='x',padx=7,pady=1)
        tk.Label(line,text=title,bg=WHITE,fg=NAVY,font=('Segoe UI',9,'bold'),
                 width=10,anchor='w').pack(side='left')
        square=tk.Frame(line,bg=color,width=38,height=38,highlightbackground=color,highlightthickness=1)
        square.pack(side='left');square.pack_propagate(False)
        entry=tk.Entry(square,textvariable=variable,state='readonly',readonlybackground=color,
                       fg='white',font=('Segoe UI',12,'bold'),justify='center',relief='flat',bd=0,
                       highlightthickness=0)
        entry.pack(fill='both',expand=True,padx=1,pady=1)
        return entry

    def _contract_ref_entry(self,parent,variable,width=12,readonly=True,yellow=False,underline=False,pixel_width=None):
        if underline:
            holder=tk.Frame(parent,bg=WHITE,width=pixel_width or 1)
            if pixel_width:
                holder.pack(side='left');holder.pack_propagate(False)
                holder.configure(height=26)
            else:holder.pack(side='left',fill='x',expand=True)
            entry=tk.Entry(holder,textvariable=variable,width=width,relief='flat',bd=0,
                           highlightthickness=0,bg=WHITE,readonlybackground=WHITE,
                           fg='#ae5d25' if yellow else NAVY,
                           font=('Segoe UI',11,'bold' if yellow else 'normal'))
            entry.pack(fill='x',padx=2,ipady=1)
            tk.Frame(holder,bg='#a7bdd0',height=1).pack(fill='x',pady=(1,0))
            if readonly:entry.configure(state='readonly')
            return entry
        border='#9bc8f5';fill='#fff29a' if yellow else '#f7fbff'
        outer=tk.Canvas(parent,width=max(58,width*8+15),height=27,bg=WHITE,highlightthickness=0)
        outer.pack(side='left')
        outer.create_arc(1,1,17,26,start=90,extent=180,fill=border,outline=border)
        outer.create_arc(max(58,width*8+15)-17,1,max(58,width*8+15)-1,26,start=270,extent=180,fill=border,outline=border)
        outer.create_rectangle(9,1,max(58,width*8+15)-9,26,fill=border,outline=border)
        outer.create_arc(2,2,18,25,start=90,extent=180,fill=fill,outline=fill)
        outer.create_arc(max(58,width*8+15)-18,2,max(58,width*8+15)-2,25,start=270,extent=180,fill=fill,outline=fill)
        outer.create_rectangle(10,2,max(58,width*8+15)-10,25,fill=fill,outline=fill)
        entry=tk.Entry(outer,textvariable=variable,width=width,relief='flat',bd=0,
                       bg=fill,readonlybackground=fill,fg=NAVY,font=('Segoe UI',10,'bold' if yellow else 'normal'))
        outer.create_window(max(58,width*8+15)/2,13,window=entry,width=max(42,width*8-5),height=20)
        if readonly:entry.configure(state='readonly')
        return entry

    def _contract_ref_search_client(self,second=False):
        query=(self.contract_ref_second_query if second else self.contract_ref_client_query).get().strip()
        if not query:return
        pattern=f'%{query}%'
        row=self.conn.execute('SELECT code FROM clients WHERE code LIKE ? OR cin LIKE ? OR nom LIKE ? OR prenom LIKE ? OR telephone LIKE ? ORDER BY CASE WHEN code=? OR cin=? THEN 0 ELSE 1 END,nom LIMIT 1',
                              (pattern,pattern,pattern,pattern,pattern,query,query)).fetchone()
        if not row:messagebox.showwarning('Recherche client','Aucun client trouvé.');return
        if second:self._contract_ref_pick_second(row[0])
        else:self._quick_client_to_contract(row[0])

    def _loc_button(self,parent,text,command,color):
        return tk.Button(parent,text=text,command=command,bg=color,fg=WHITE,relief='flat',font=('Segoe UI',9,'bold'),padx=7,pady=4)

    def _build_locations_reference_page(self,parent=None):
        page=parent if parent is not None else self._new_page('locations')
        head=tk.Frame(page,bg='#e1f0fc');head.pack(fill='x',padx=11,pady=(8,6))
        tk.Label(head,text='▦  Gestion des locations',bg='#e1f0fc',fg=NAVY,font=('Segoe UI',17,'bold')).pack(side='left',padx=10,pady=8)
        self.locations_search=tk.StringVar()
        tk.Entry(head,textvariable=self.locations_search,font=('Segoe UI',9),relief='solid',bd=1).pack(side='right',fill='x',expand=True,padx=15,ipady=6)
        self.locations_search.trace_add('write',lambda *_:self.refresh_locations_reference())
        toolbar=tk.Frame(page,bg=BG);toolbar.pack(fill='x',padx=12,pady=(0,6))
        for text,fn,color in (
            ('＋ Nouvelle location',lambda:(self.new_contract(),self.show_page('contract')),'#12a35c'),
            ('✎ Modifier',lambda:self._locations_open_selected(),'#087ff3'),
            ('▣ Supprimer',lambda:self._locations_action_selected('delete'),'#e42e48'),
            ('◉ Voir',lambda:self._locations_open_selected(),'#38a5e9'),
            ('▤ Imprimer',lambda:self._locations_action_selected('print'),'#0875cb'),
            ('⇩ Exporter',self.export_csv,'#087ff3'),('⇧ Importer',self.import_csv,'#087ff3'),
            ('⟳ Actualiser',self.refresh_locations_reference,'#0875cb')):
            self._loc_button(toolbar,text,fn,color).pack(side='left',padx=3)
        filters=tk.Frame(page,bg='#f0f7fe');filters.pack(fill='x',padx=12,pady=(0,6))
        today=datetime.now()
        self.locations_month=tk.StringVar(value='Tous')
        self.locations_year=tk.StringVar(value='Toutes')
        self.locations_from=tk.StringVar(value=today.replace(day=1).strftime('%d/%m/%Y'))
        self.locations_until=tk.StringVar(value=today.replace(day=calendar.monthrange(today.year,today.month)[1]).strftime('%d/%m/%Y'))
        self.locations_status=tk.StringVar(value='Tous')
        self.locations_vehicle=tk.StringVar(value='Tous')
        self.locations_client=tk.StringVar()
        period=tk.Frame(filters,bg='#f0f7fe');period.pack(side='left',padx=5,pady=6)
        tk.Label(period,text='Période',bg='#f0f7fe',fg=NAVY,font=('Segoe UI',8,'bold')).pack(anchor='w')
        for value in (self.locations_from,self.locations_until):
            entry=tk.Entry(period,textvariable=value,width=11,justify='center');entry.pack(side='left',padx=2,ipady=3)
            self._attach_date_picker(entry,value)
        for label,var,values,width in (
            ('Statut',self.locations_status,('Tous','En cours','Terminé','Retard','Annulé','À venir'),12),
            ('Véhicule',self.locations_vehicle,('Tous',)+tuple(f"{r['code']} | {r['modele']}" for r in self.conn.execute('SELECT code,modele FROM vehicles ORDER BY modele')),23)):
            group=tk.Frame(filters,bg='#f0f7fe');group.pack(side='left',padx=5,pady=6)
            tk.Label(group,text=label,bg='#f0f7fe',fg=NAVY,font=('Segoe UI',8,'bold')).pack(anchor='w')
            box=ttk.Combobox(group,textvariable=var,values=values,state='readonly',width=width);box.pack()
            box.bind('<<ComboboxSelected>>',lambda _e:self.refresh_locations_reference())
        group=tk.Frame(filters,bg='#f0f7fe');group.pack(side='left',fill='x',expand=True,padx=5)
        tk.Label(group,text='Client',bg='#f0f7fe',fg=NAVY,font=('Segoe UI',8,'bold')).pack(anchor='w')
        tk.Entry(group,textvariable=self.locations_client).pack(fill='x',ipady=3)
        self.locations_client.trace_add('write',lambda *_:self.refresh_locations_reference())
        self._loc_button(filters,'⌕ Rechercher',self.refresh_locations_reference,'#087ff3').pack(side='left',padx=4)
        self._loc_button(filters,'⟳ Réinitialiser',self._locations_reset,'#42617d').pack(side='left',padx=4)
        table=self._loc_section(page,'Toutes les locations')
        table.pack(fill='both',expand=True,padx=12,pady=(0,6))
        columns=('reference','start','time_start','end','time_end','days','vehicle','plate','client','total','balance','status','actions')
        labels=('Référence','Date départ','Heure','Date retour','Heure','Durée (j)','Véhicule','Immatriculation','Client','Montant (MAD)','Reste (MAD)','Statut','Actions')
        widths=(112,86,52,86,52,61,126,103,140,91,91,91,91)
        self.locations_tree=ttk.Treeview(table,columns=columns,show='tree headings',height=9,style='DashboardExcel.Treeview')
        self.locations_tree.heading('#0',text='Véhicule');self.locations_tree.column('#0',width=73,minwidth=63,stretch=False)
        for col,label,width in zip(columns,labels,widths):
            self.locations_tree.heading(col,text=label);self.locations_tree.column(col,width=width,minwidth=50,anchor='center',stretch=True)
        y=ttk.Scrollbar(table,orient='vertical',command=self.locations_tree.yview)
        x=ttk.Scrollbar(table,orient='horizontal',command=self.locations_tree.xview)
        self.locations_tree.configure(yscrollcommand=y.set,xscrollcommand=x.set)
        self.locations_tree.pack(side='left',fill='both',expand=True,padx=(6,0),pady=6);y.pack(side='right',fill='y')
        x.pack(side='bottom',fill='x')
        self.locations_tree.tag_configure('late',background='#ffe9eb')
        self.locations_tree.tag_configure('returned',background='#edf6f4')
        self.locations_tree.bind('<<TreeviewSelect>>',lambda _e:self._locations_show_details())
        self.locations_tree.bind('<Double-1>',lambda _e:self._locations_open_selected())
        self.locations_tree.bind('<ButtonRelease-1>',self._locations_table_action,add='+')
        details=self._loc_section(page,'▦  Détails location')
        details.pack(fill='x',padx=12,pady=(0,9))
        tabs=ttk.Notebook(details);tabs.pack(fill='x',padx=6,pady=5)
        self.locations_details={}
        for key,title in (('summary','Détails location'),('client','Client'),('vehicle','Véhicule'),('payments','Règlements'),('history','Historique'),('documents','Documents')):
            frame=tk.Frame(tabs,bg=WHITE,height=125);tabs.add(frame,text=title);frame.pack_propagate(False)
            self.locations_details[key]=tk.Label(frame,text='Sélectionnez une location.',bg=WHITE,fg=NAVY,font=('Segoe UI',9),justify='left',anchor='nw')
            self.locations_details[key].pack(side='left',fill='both',expand=True,padx=15,pady=12)
            if key=='summary':
                actions=tk.Frame(frame,bg=WHITE);actions.pack(side='right',padx=8)
                for text,kind,color in (('✓ Confirmer retour','confirm','#13a65b'),('◷ Prolonger','extend','#087ff3'),('➤ Anticiper','anticipate','#ff930c'),('✕ Annuler','cancel','#f3334e')):
                    self._loc_button(actions,text,lambda a=kind:self._locations_action_selected(a),color).pack(fill='x',pady=2)
            if key=='client':self._loc_button(frame,'Voir fiche client',lambda:self.show_page('clients'),'#087ff3').pack(side='right',padx=8)
            if key=='vehicle':self._loc_button(frame,'Voir fiche véhicule',lambda:self.show_page('vehicles'),'#087ff3').pack(side='right',padx=8)
            if key=='documents':self._loc_button(frame,'Aperçu PDF',lambda:self._locations_action_selected('preview'),'#d8354c').pack(side='right',padx=8)
        self.locations_photos=[];self.refresh_locations_reference()

    def _locations_reset(self):
        now=datetime.now()
        self.locations_from.set(now.replace(day=1).strftime('%d/%m/%Y'))
        self.locations_until.set(now.replace(day=calendar.monthrange(now.year,now.month)[1]).strftime('%d/%m/%Y'))
        self.locations_status.set('Tous');self.locations_vehicle.set('Tous');self.locations_client.set('');self.locations_search.set('')
        self.refresh_locations_reference()

    def _locations_selected_number(self):
        tree=getattr(self,'locations_tree',None);selected=tree.selection() if tree is not None else ()
        if not selected:return ''
        return selected[0].split(':',1)[1]

    def _locations_open_selected(self):
        number=self._locations_selected_number()
        if not number:return
        self.contract_search_var.set(number);self.load_contract_lookup();self.show_page('contract')

    def _open_location_tabs(self):
        return self.open_location_form()

    def _locations_table_action(self,event):
        tree=self.locations_tree
        if tree.identify_region(event.x,event.y)!='cell' or tree.identify_column(event.x)!='#13':return
        iid=tree.identify_row(event.y)
        if not iid:return
        tree.selection_set(iid)
        box=tree.bbox(iid,'actions')
        if not box:return
        offset=event.x-box[0]
        action=('preview','edit','delete')[min(2,max(0,int(offset*3/max(1,box[2]))))]
        if action=='edit':self._locations_open_selected()
        else:self._locations_action_selected(action)

    def _locations_action_selected(self,action):
        number=self._locations_selected_number()
        if not number:
            messagebox.showinfo('Gestion des locations','Sélectionnez une location.');return
        if action in ('confirm','extend','anticipate','cancel'):
            self._dashboard_contract_action_for(number,action)
        elif action=='delete':
            self.contract_search_var.set(number);self.load_contract_lookup();self.delete_contract()
        elif action=='preview':
            self.contract_search_var.set(number);self.load_contract_lookup();self.preview_contract()
        elif action=='print':
            self.contract_search_var.set(number);self.load_contract_lookup();self.print_contract()
        self.refresh_locations_reference()

    def refresh_locations_reference(self):
        tree=getattr(self,'locations_tree',None)
        if tree is None:return
        old=self._locations_selected_number();tree.delete(*tree.get_children());self.locations_photos=[]
        month=self.locations_month.get();year=self.locations_year.get();status=self.locations_status.get()
        lower=self._parse_french_date(self.locations_from.get());upper=self._parse_french_date(self.locations_until.get())
        vehicle=self.locations_vehicle.get().split('|')[0].strip();query=self.locations_search.get().casefold().strip();client=self.locations_client.get().casefold().strip()
        rows=self.conn.execute('''SELECT c.*,v.modele,v.immatriculation,
            cl.nom,cl.prenom,cl.cin,cl.telephone FROM contracts c
            LEFT JOIN vehicles v ON v.code=c.vehicle_code LEFT JOIN clients cl ON cl.code=c.client_code
            WHERE (?='Tous' OR substr(c.date_depart,4,2)=?)
              AND (?='Toutes' OR substr(c.date_depart,7,4)=?)
              AND (?='' OR substr(c.date_depart,7,4)||substr(c.date_depart,4,2)||substr(c.date_depart,1,2)>=?)
              AND (?='' OR substr(c.date_depart,7,4)||substr(c.date_depart,4,2)||substr(c.date_depart,1,2)<=?)
            ORDER BY substr(c.date_depart,7,4) DESC,substr(c.date_depart,4,2) DESC,substr(c.date_depart,1,2) DESC,c.heure_depart DESC''',
            (month,month,year,year,
             lower.strftime('%Y%m%d') if lower else '',lower.strftime('%Y%m%d') if lower else '',
             upper.strftime('%Y%m%d') if upper else '',upper.strftime('%Y%m%d') if upper else '')).fetchall()
        now=datetime.now()
        for r in rows:
            start=self._parse_french_date(r['date_depart']);end=self._contract_datetime(r['date_retour'],r['heure_retour'],True)
            if lower and (not start or start.date()<lower.date()):continue
            if upper and (not start or start.date()>upper.date()):continue
            if month!='Tous' and (not start or start.month!=int(month)):continue
            if year!='Toutes' and (not start or start.year!=int(year)):continue
            if vehicle!='Tous' and str(r['vehicle_code'])!=vehicle:continue
            person=f"{r['nom'] or ''} {r['prenom'] or ''}".strip()
            if client and client not in f"{person} {r['client_code']} {r['cin']} {r['telephone']}".casefold():continue
            if query and query not in f"{r['numero']} {person} {r['modele']} {r['immatriculation']} {r['client_code']}".casefold():continue
            state=str(r['return_status'] or '').upper()
            label='Annulé' if 'ANNUL' in state else 'Terminé' if self._is_returned_contract(state) or r['actual_return_date'] else 'À venir' if start and start>now else 'Retard' if end and end<now else 'En cours'
            if status!='Tous' and label!=status:continue
            photo=self._locations_vehicle_photo(r['vehicle_code'])
            values=(r['numero'],r['date_depart'],r['heure_depart'],r['date_retour'],r['heure_retour'],r['duree'],r['modele'] or r['vehicle_code'],r['immatriculation'] or '',person,
                f"{float(r['montant'] or 0):,.2f}",f"{float(r['reste'] or 0):,.2f}",label,'◉    ✎    ▣')
            iid='location:'+str(r['numero'])
            tree.insert('','end',iid=iid,image=photo,values=values,tags=('late' if label=='Retard' else 'returned' if label=='Terminé' else '',))
        if old and tree.exists('location:'+old):tree.selection_set('location:'+old);tree.see('location:'+old)
        self._locations_show_details()

    def _locations_vehicle_photo(self,code):
        path=self._vehicle_photo_path(code)
        if not path:return None
        try:
            from PIL import Image,ImageTk
            with Image.open(path) as source:
                picture=source.convert('RGBA');picture.thumbnail((58,32),Image.Resampling.LANCZOS)
            photo=ImageTk.PhotoImage(picture);self.locations_photos.append(photo)
            return photo
        except (OSError,ValueError,ImportError):return None

    def _locations_show_details(self):
        number=self._locations_selected_number()
        if not number:return
        r=self.conn.execute('''SELECT c.*,cl.nom,cl.prenom,cl.cin,cl.telephone,cl.adresse,v.modele,v.immatriculation,v.chassis
            FROM contracts c LEFT JOIN clients cl ON cl.code=c.client_code LEFT JOIN vehicles v ON v.code=c.vehicle_code WHERE c.numero=?''',(number,)).fetchone()
        if not r:return
        values={
            'summary':f"Référence : {number}    ·    Départ : {r['date_depart']} {r['heure_depart']}    ·    Retour : {r['date_retour']} {r['heure_retour']}\nDurée : {r['duree']} jour(s)",
            'client':f"Code : {r['client_code']}    Nom : {r['nom'] or ''} {r['prenom'] or ''}\nCIN : {r['cin'] or ''}    Téléphone : {r['telephone'] or ''}    Adresse : {r['adresse'] or ''}",
            'vehicle':f"{r['modele'] or ''}    ·    {r['immatriculation'] or ''}\nN° châssis : {r['chassis'] or ''}    Code : {r['vehicle_code']}",
            'payments':f"Montant total : {float(r['montant'] or 0):,.2f} MAD    ·    Règlement : {float(r['reglement'] or 0):,.2f} MAD\nReste à payer : {float(r['reste'] or 0):,.2f} MAD",
            'history':f"Contrat créé : {r['created_at'] or '—'}\nStatut : {r['return_status'] or 'En cours'}    Retour effectif : {r['actual_return_date'] or '—'} {r['actual_return_time'] or ''}",
            'documents':f"Contrat {number} : aperçu PDF et impression disponibles."
        }
        for key,label in self.locations_details.items():label.configure(text=values[key])

    def _build_contract_reference_layout(self):
        """Présente la saisie existante dans les zones de la maquette fournie."""
        for child in self.page.winfo_children():
            if child.winfo_manager()=='pack':child.pack_forget()
        root=tk.Frame(self.page,bg=BG);root.pack(fill='both',expand=True,padx=7,pady=4)
        ttk.Style().configure('ContractLine.TCombobox',fieldbackground=WHITE,
                              background=WHITE,borderwidth=0,relief='flat',padding=1)
        head=tk.Frame(root,bg='#e4f2ff');head.pack(fill='x',pady=(0,4))
        tk.Label(head,text='▤  Établir un contrat de location',bg='#e4f2ff',fg=NAVY,font=('Segoe UI',16,'bold')).pack(side='left',padx=10,pady=9)
        tk.Label(head,text='N° contrat / Référence',bg='#e4f2ff',fg=NAVY).pack(side='left',padx=(14,3))
        tk.Entry(head,textvariable=self.vars['contract_no'],width=12,font=('Segoe UI',10,'bold'),justify='center').pack(side='left')
        tk.Label(head,text='Date',bg='#e4f2ff',fg=NAVY).pack(side='left',padx=(12,3))
        tk.Entry(head,textvariable=self.vars['date_start'],width=12,justify='center').pack(side='left')
        for text,fn,color in (('▣ Enregistrer',self.save_contract,'#087ff3'),('▣ Modifier',self.update_contract,'#f29712'),
                              ('▤ Imprimer',self.print_contract,'#0b5fa9'),('▣ Aperçu PDF',self.preview_contract,'#df2544'),('✕ Annuler',self.new_contract,'#536c83')):
            self._loc_button(head,text,fn,color).pack(side='right',padx=3,pady=5)
        top=tk.Frame(root,bg=BG);top.pack(fill='x',pady=(0,4))
        for col in range(3):top.grid_columnconfigure(col,weight=1,uniform='contract_top')
        primary=self._loc_section(top,'♟  Client principal');primary.grid(row=0,column=0,sticky='nsew',padx=(0,4))
        second=self._loc_section(top,'♟  Deuxième conducteur (facultatif)');second.grid(row=0,column=1,sticky='nsew',padx=4)
        vehicle=self._loc_section(top,'🚘  Véhicule loué');vehicle.grid(row=0,column=2,sticky='nsew',padx=(4,0))
        def field(parent,title,key,editable=False,width=11,underline=False):
            line=tk.Frame(parent,bg=WHITE);line.pack(fill='x',padx=7,pady=1)
            label_width=(10 if key in ('vehicle_model','plate','chassis') else
                         14 if key in ('date_start','time_start','date_end','time_end','duration','km_start','km_return','km_used') else
                         10) if underline else 12
            shown_title={'vehicle_model':'Modèle','plate':'Immat.','chassis':'Châssis'}.get(key,title)
            shown_title={'Prix par jour (MAD)':'Prix / jour','Nombre de jours':'Jours'}.get(title,shown_title)
            tk.Label(line,text=shown_title,bg=WHITE,fg=NAVY,font=('Segoe UI',9,'bold'),width=label_width,anchor='w').pack(side='left')
            if key in ('time_start','time_end'):
                holder=tk.Frame(line,bg=WHITE,width=76,height=26) if underline else line
                if underline:holder.pack(side='left');holder.pack_propagate(False)
                entry=ttk.Combobox(holder,textvariable=self.vars[key],values=self._times(),width=6 if underline else width,
                                   font=('Segoe UI',10),style='ContractLine.TCombobox' if underline else 'TCombobox')
                if underline:entry.pack(fill='x')
                else:entry.pack(side='left')
                if underline:tk.Frame(holder,bg='#a7bdd0',height=1).pack(fill='x',pady=(1,0))
            else:
                bounded={'date_start':130,'date_end':130,'duration':80,
                         'km_start':115,'km_return':115,'km_used':115,
                         'vehicle_model':145,'plate':145,'chassis':145}.get(key) if underline else None
                entry=self._contract_ref_entry(line,self.vars[key],width=width,readonly=not editable,
                                               yellow=key in ('client_code','second_code'),underline=underline,
                                               pixel_width=bounded)
            if key in ('date_start','date_end'):self._attach_date_picker(entry,self.vars[key])
            return entry
        actions=tk.Frame(primary,bg=WHITE);actions.pack(side='right',anchor='ne',padx=(2,5),pady=3)
        self._loc_button(actions,'⌕ Client',lambda:self.open_quick_client_dialog(lambda c:self._quick_client_to_contract(c)),'#087ff3').pack(fill='x',pady=2)
        self._loc_button(actions,'▣ Scanner',lambda:self.open_scan_center(self.vars['client_code'].get()),'#0875cb').pack(fill='x',pady=2)
        self._loc_button(actions,'⇧ Importer',lambda:self.open_scan_center(self.vars['client_code'].get()),'#0b5fa9').pack(fill='x',pady=2)
        primary_photo=tk.Frame(primary,bg='#eff6ff',width=80,height=96);primary_photo.pack(side='left',padx=4,anchor='n')
        primary_photo.pack_propagate(False)
        self.contract_ref_client_photo=tk.Label(primary_photo,text='👤',bg='#eff6ff',fg='#345a83',font=('Segoe UI',26))
        self.contract_ref_client_photo.pack(expand=True)
        form=tk.Frame(primary,bg=WHITE);form.pack(side='left',fill='both',expand=True)
        self._contract_ref_code_square(form,'Code client',self.vars['client_code'],'#c46a23')
        self.contract_ref_client_query=tk.StringVar()
        self._contract_ref_header_search(primary,self.contract_ref_client_query,
                                         self._contract_ref_search_client,width=108)
        for title,key in (('Nom','last_name'),('Prénom','first_name'),('Téléphone','phone')):field(form,title,key,underline=True)
        second_actions=tk.Frame(second,bg=WHITE);second_actions.pack(side='right',anchor='ne',padx=(2,5),pady=3)
        self._loc_button(second_actions,'⌕ Client',lambda:self.open_quick_client_dialog(lambda c:self._contract_ref_pick_second(c)),'#087ff3').pack(fill='x',pady=2)
        self._loc_button(second_actions,'▣ Scanner',lambda:self.open_scan_center(self.vars['second_code'].get()),'#0875cb').pack(fill='x',pady=2)
        second_photo=tk.Frame(second,bg='#eff6ff',width=80,height=96);second_photo.pack(side='left',padx=4,anchor='n')
        second_photo.pack_propagate(False)
        self.contract_ref_second_photo=tk.Label(second_photo,text='👤',bg='#eff6ff',fg='#345a83',font=('Segoe UI',26))
        self.contract_ref_second_photo.pack(expand=True)
        second_form=tk.Frame(second,bg=WHITE);second_form.pack(side='left',fill='both',expand=True)
        self._contract_ref_code_square(second_form,'Code client 2',self.vars['second_code'],'#78943a')
        self.contract_ref_second_query=tk.StringVar()
        self._contract_ref_header_search(second,self.contract_ref_second_query,
                                         lambda:self._contract_ref_search_client(True),width=108)
        tk.Checkbutton(second_form,text='Non autorisé',variable=self.second_disabled,bg=WHITE,fg='#b22e3e',font=('Segoe UI',9,'bold')).pack(anchor='e',padx=8)
        for title,key in (('Nom','second_last'),('Prénom','second_first'),('Téléphone','second_phone')):field(second_form,title,key,underline=True)
        vehicle_photo=tk.Frame(vehicle,bg='#eff6ff',width=105,height=96);vehicle_photo.pack(side='left',padx=4,anchor='n')
        vehicle_photo.pack_propagate(False)
        self.contract_ref_vehicle_photo=tk.Label(vehicle_photo,text='🚘',bg='#eff6ff',fg='#345a83',font=('Segoe UI',26))
        self.contract_ref_vehicle_photo.pack(expand=True)
        veh_form=tk.Frame(vehicle,bg=WHITE);veh_form.pack(side='left',fill='both',expand=True)
        choices=[f"{r['code']} | {r['modele']}" for r in self.conn.execute('SELECT code,modele FROM vehicles WHERE service=1 ORDER BY modele')]
        self._contract_ref_header_search(vehicle,self.vars['vehicle_code'],
                                         lambda:self.load_vehicle(),choices,width=155)
        for title,key in (('Marque / Modèle','vehicle_model'),('Immatriculation','plate'),('N° châssis','chassis')):field(veh_form,title,key,underline=True)
        self._loc_button(veh_form,'📷 Changer photo',self._choose_contract_vehicle_photo,'#087ff3').pack(anchor='w',padx=7,pady=7)
        middle=tk.Frame(root,bg=BG);middle.pack(fill='x',pady=(0,4))
        for col,weight in enumerate((5,2,6)):middle.grid_columnconfigure(col,weight=weight)
        period=self._loc_section(middle,'▦  Période de location');period.grid(row=0,column=0,sticky='nsew',padx=(0,4))
        mileage=self._loc_section(middle,'▤  Kilométrage');mileage.grid(row=0,column=1,sticky='nsew',padx=4)
        equipment=self._loc_section(middle,'◉  Équipements remis');equipment.grid(row=0,column=2,sticky='nsew',padx=(4,0))
        for title,key in (('Date départ','date_start'),('Heure départ','time_start'),('Date retour','date_end'),('Heure retour','time_end'),('Durée','duration')):
            field(period,title,key,key not in ('duration',),underline=True)
        for title,key in (('Km départ','km_start'),('Km retour','km_return'),('Km parcourus','km_used')):field(mileage,title,key,key!='km_used',underline=True)
        eq=tk.Frame(equipment,bg=WHITE);eq.pack(fill='both',expand=True,padx=8,pady=4)
        for i,(title,var) in enumerate(self.contract_state_checks.items()):
            tk.Checkbutton(eq,text=title,variable=var,bg=WHITE,fg=NAVY,font=('Segoe UI',9),anchor='w').grid(row=i%4,column=i//4,sticky='w',padx=8,pady=2)
        fuel=tk.Frame(equipment,bg=WHITE);fuel.pack(fill='x',padx=10,pady=3)
        tk.Label(fuel,text='Niveau carburant (départ)',bg=WHITE,fg=NAVY,font=('Segoe UI',9,'bold')).pack(side='left')
        ttk.Combobox(fuel,textvariable=self.vars['fuel_level'],values=('E','⅛','¼','⅜','½','⅝','¾','Plein'),state='readonly',width=10,font=('Segoe UI',10)).pack(side='right')
        gauge=tk.Frame(equipment,bg=WHITE);gauge.pack(fill='x',padx=12,pady=(1,7))
        tk.Label(gauge,text='E',bg=WHITE,fg=NAVY).pack(side='left')
        self.contract_ref_fuel_segments=[]
        for i in range(8):
            segment=tk.Label(gauge,text=' ',bg='#dce8f1',width=3,relief='flat')
            segment.pack(side='left',fill='x',expand=True,padx=2)
            self.contract_ref_fuel_segments.append(segment)
        tk.Label(gauge,text='F',bg=WHITE,fg=NAVY).pack(side='left')
        self.vars['fuel_level'].trace_add('write',lambda *_:self._contract_ref_update_fuel())
        self._contract_ref_update_fuel()
        lower=tk.Frame(root,bg=BG);lower.pack(fill='x',pady=(0,4))
        for col,weight in enumerate((5,5,3)):lower.grid_columnconfigure(col,weight=weight)
        finance=self._loc_section(lower,'▤  Montants de la location');finance.grid(row=0,column=0,sticky='nsew',padx=(0,4))
        state=self._loc_section(lower,'🚘  État du véhicule · Photos et dessin');state.grid(row=0,column=1,sticky='nsew',padx=4)
        docs=self._loc_section(lower,'▤  Documents joints');docs.grid(row=0,column=2,sticky='nsew',padx=(4,0))
        for title,key,editable in (('Prix par jour (MAD)','daily_price',True),('Nombre de jours','duration',False)):
            field(finance,title,key,editable)
        cards=tk.Frame(finance,bg=WHITE);cards.pack(fill='x',padx=7,pady=5)
        for column in range(3):cards.grid_columnconfigure(column,weight=1,uniform='montants_location')
        for column,(title,key,soft,accent,editable) in enumerate((
            ('Montant total','total','#dff0ff','#0874df',False),
            ('Règlement / avance','paid','#ddf9e7','#12884c',True),
            ('Reste à payer','balance','#ffe7eb','#cb1637',False))):
            card=tk.Frame(cards,bg=soft,highlightbackground=accent,highlightthickness=1)
            card.grid(row=0,column=column,sticky='nsew',padx=2)
            tk.Label(card,text=title,bg=soft,fg=accent,font=('Segoe UI',9,'bold'),
                     wraplength=125).pack(fill='x',pady=(5,1))
            amount=tk.Entry(card,textvariable=self.vars[key],bg=soft,readonlybackground=soft,fg=accent,
                            relief='flat',bd=0,justify='center',
                            font=('Segoe UI',16 if key=='balance' else 13,'bold'),width=1)
            amount.pack(fill='x',padx=4,pady=(1,6))
            if not editable:amount.configure(state='readonly')
        tk.Label(finance,text='Mode de paiement',bg=WHITE,fg=NAVY,font=('Segoe UI',9,'bold')).pack(anchor='w',padx=10)
        ttk.Combobox(finance,textvariable=self.payment_mode_var,values=('ESPÈCES','CHÈQUE','VIREMENT','AUTRE'),state='readonly',font=('Segoe UI',10)).pack(fill='x',padx=10,pady=5)
        self._loc_button(state,'Vue extérieure / Photos / État',self.vehicle_state,'#087ff3').pack(fill='x',padx=8,pady=5)
        diagram=Path(__file__).parent/'assets'/'ETAT_VEHICULE_REFERENCE.png'
        if diagram.is_file():
            try:
                from PIL import Image,ImageTk
                picture=Image.open(diagram);picture.thumbnail((300,70))
                self.contract_ref_state_diagram=ImageTk.PhotoImage(picture)
                tk.Label(state,image=self.contract_ref_state_diagram,bg=WHITE).pack(fill='x',padx=8,pady=3)
            except (OSError,ImportError,tk.TclError):
                pass
        tk.Label(state,text='Observations / état général',bg=WHITE,fg=NAVY,font=('Segoe UI',9,'bold')).pack(anchor='w',padx=8)
        self.contract_ref_notes=tk.Text(state,height=3,font=('Segoe UI',10),relief='solid',bd=1)
        self.contract_ref_notes.pack(fill='x',padx=8,pady=4)
        self.contract_ref_notes.bind('<KeyRelease>',lambda _e:self._contract_ref_copy_notes())
        for title,fn in (('CNI client · Scanner',lambda:self.scan_client_front_image(self.vars['client_code'].get(),'CIN')),
                         ('Permis · Scanner',lambda:self.scan_client_front_image(self.vars['client_code'].get(),'PERMIS')),
                         ('Autres documents · Ouvrir',self._contract_ref_open_documents)):
            self._loc_button(docs,title,fn,'#087ff3').pack(fill='x',padx=10,pady=3)
        foot=tk.Frame(root,bg=BG);foot.pack(fill='x')
        conditions=self._loc_section(foot,'▣  Conditions générales');conditions.pack(side='left',fill='both',expand=True,padx=(0,5))
        tk.Label(conditions,text=self.conditions.get('1.0','end').strip()[:300],bg=WHITE,fg=NAVY,wraplength=600,justify='left',anchor='w').pack(fill='x',padx=10,pady=3)
        signature=self._loc_section(foot,'▣  Signatures');signature.pack(side='left',fill='both',expand=True,padx=(5,0))
        for title in ('Société','Conducteur 1','Conducteur 2'):
            tk.Label(signature,text=title,bg='#f7fbff',fg=NAVY,font=('Segoe UI',9,'bold'),width=18,height=2,relief='solid',bd=1).pack(side='left',fill='x',expand=True,padx=3,pady=3)
        self.vars['client_code'].trace_add('write',lambda *_:self._contract_ref_update_client_photo(False))
        self.vars['second_code'].trace_add('write',lambda *_:self._contract_ref_update_client_photo(True))
        self.vars['vehicle_code'].trace_add('write',lambda *_:self._contract_ref_update_vehicle_photo())
        self._contract_ref_update_client_photo(False)
        self._contract_ref_update_client_photo(True)
        self._contract_ref_update_vehicle_photo()

    def _contract_ref_update_fuel(self):
        level=self.vars['fuel_level'].get()
        count={'E':0,'⅛':1,'¼':2,'⅜':3,'½':4,'⅝':5,'¾':6,'Plein':8,'F':8}.get(level,4)
        for i,segment in enumerate(self.contract_ref_fuel_segments):
            segment.configure(bg=('#ed3151' if i<2 else '#ffad22' if i<4 else '#14ac65') if i<count else '#dce8f1')

    def _contract_ref_copy_notes(self):
        if not hasattr(self,'contract_ref_notes'):return
        self.contract_state_notes.delete('1.0','end');self.contract_state_notes.insert('1.0',self.contract_ref_notes.get('1.0','end'))

    def _contract_ref_save_state(self,number):
        if not number or not hasattr(self,'contract_ref_notes'):return
        previous=self.conn.execute('SELECT payload FROM contract_vehicle_states WHERE contract_no=?',(number,)).fetchone()
        try:payload=json.loads(previous[0]) if previous else {}
        except (TypeError,ValueError):payload={}
        payload['equipment']={name:bool(value.get()) for name,value in self.contract_state_checks.items()}
        payload['fuel_level']=self.vars['fuel_level'].get()
        payload['observations']=self.contract_ref_notes.get('1.0','end').strip()
        self.conn.execute('''INSERT INTO contract_vehicle_states(contract_no,payload,updated_at) VALUES(?,?,?)
            ON CONFLICT(contract_no) DO UPDATE SET payload=excluded.payload,updated_at=excluded.updated_at''',
            (number,json.dumps(payload,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')))

    def _contract_ref_load_state(self,number):
        if not hasattr(self,'contract_ref_notes'):return
        row=self.conn.execute('SELECT payload FROM contract_vehicle_states WHERE contract_no=?',(number,)).fetchone()
        try:payload=json.loads(row[0]) if row else {}
        except (TypeError,ValueError):payload={}
        equipment=payload.get('equipment') or {}
        for name,value in self.contract_state_checks.items():value.set(bool(equipment.get(name,False)))
        self.vars['fuel_level'].set(payload.get('fuel_level') or '½')
        self.contract_ref_notes.delete('1.0','end')
        self.contract_ref_notes.insert('1.0',payload.get('observations',''))
        self._contract_ref_copy_notes()

    def _contract_ref_open_documents(self):
        code=self.vars['client_code'].get().strip()
        if not self.conn.execute('SELECT 1 FROM clients WHERE code=?',(code,)).fetchone():
            messagebox.showwarning('Documents client','Sélectionnez un client enregistré.');return
        folder=self._organize_client_documents(code)
        if sys.platform.startswith('win'):os.startfile(str(folder))
        elif sys.platform=='darwin':subprocess.Popen(['open',str(folder)])
        else:subprocess.Popen(['xdg-open',str(folder)])

    def _contract_ref_pick_second(self,code):
        self.vars['second_code'].set(code);self._contract_ref_load_second()

    def _contract_ref_load_second(self):
        self.vars['second_search'].set(self.vars['second_code'].get())
        self.second_mode.set('Code client');self.load_second_driver()

    def _contract_ref_update_client_photo(self,second=False):
        code=self.vars['second_code' if second else 'client_code'].get().strip()
        target=self.contract_ref_second_photo if second else self.contract_ref_client_photo
        path=''
        if code:
            try:
                row=self.conn.execute('SELECT photo FROM clients WHERE code=?',(code,)).fetchone()
                path=str(row[0] or '') if row else ''
            except Exception:pass
            if not path or not self._contract_ref_resolve_path(path):
                path=self._client_front_image(code,'CIN') or self._client_front_image(code,'PERMIS')
        self._contract_ref_set_photo(target,path,(78,94),'👤')

    def _contract_ref_update_vehicle_photo(self):
        code=self.vars['vehicle_code'].get().split('|')[0].strip()
        path=self._vehicle_photo_path(code) if code else None
        self._contract_ref_set_photo(self.contract_ref_vehicle_photo,path,(103,94),'🚘')

    def _contract_ref_resolve_path(self,path):
        if not path:return ''
        original=Path(path)
        if original.is_file():return str(original)
        filename=str(path).replace('\\','/').split('/')[-1]
        for folder in ('client_photos','client_documents','vehicle_photos',''):
            candidate=Path(__file__).parent/'assets'/folder/filename
            if candidate.is_file():return str(candidate)
        for candidate in (Path(__file__).parent/'assets'/'client_documents').glob('*/'+filename):
            if candidate.is_file():return str(candidate)
        return ''

    def _contract_ref_set_photo(self,label,path,size,fallback):
        photo=None
        path=self._contract_ref_resolve_path(path)
        if path:
            try:
                from PIL import Image,ImageTk,ImageOps
                with Image.open(path) as image:
                    picture=ImageOps.exif_transpose(image).convert('RGBA')
                    picture.thumbnail(size,Image.Resampling.LANCZOS)
                photo=ImageTk.PhotoImage(picture)
            except (OSError,ValueError,ImportError):pass
        label._reference_photo=photo
        label.configure(image=photo if photo else '',text='' if photo else fallback,
                        width=photo.width() if photo else 0,
                        height=photo.height() if photo else 0)
