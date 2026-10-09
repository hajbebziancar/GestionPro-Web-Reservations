"""Page indépendante Gestion du parc, basée sur les véhicules réels de HBZ."""
import json
import os
import re
import shutil
import tkinter as tk
from datetime import datetime, timedelta
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk


class FleetManagementMixin:
    def _fleet_photo(self, raw, code, size):
        path=self._resolve_vehicle_photo_path(raw,code)
        if not path:return None
        try:
            from PIL import Image, ImageOps, ImageTk
            with Image.open(path) as source:im=ImageOps.exif_transpose(source).convert('RGBA')
            im.thumbnail(size,Image.Resampling.LANCZOS)
            return ImageTk.PhotoImage(im)
        except (OSError,ValueError):return None

    def _build_fleet_management_page(self):
        page=self._new_page('fleet_management');page.configure(bg='#f3f7fc')
        canvas=tk.Canvas(page,bg='#f3f7fc',highlightthickness=0)
        scrollbar=ttk.Scrollbar(page,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        body=tk.Frame(canvas,bg='#f3f7fc');window=canvas.create_window((0,0),window=body,anchor='nw')
        body.bind('<Configure>',lambda _e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        self.fleet_search=tk.StringVar();self.fleet_filter=tk.StringVar(value='En service')
        self.fleet_selected_code='';self.fleet_tab='documents';self.fleet_images=[]
        months=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
        self.fleet_history_month=tk.StringVar(value=months[datetime.now().month-1])
        self.fleet_history_year=tk.StringVar(value=str(datetime.now().year))
        top=tk.Frame(body,bg='#202e42',height=78);top.pack(fill='x');top.pack_propagate(False)
        tk.Label(top,text='🚘',bg='#293e58',fg='white',font=('Segoe UI Emoji',25),width=3).pack(side='left',padx=(17,13),pady=10)
        names=tk.Frame(top,bg='#202e42');names.pack(side='left',pady=10)
        tk.Label(names,text='Gestion des véhicules - HBZ',bg='#202e42',fg='white',font=('Segoe UI',15,'bold')).pack(anchor='w')
        tk.Label(names,text='Suivi complet de votre parc automobile',bg='#202e42',fg='#deebfa',font=('Segoe UI',9)).pack(anchor='w')
        for icon,command in (('⚙',lambda:self.show_page('settings')),('♧',lambda:self.show_page('alerts'))):
            tk.Button(top,text=icon,command=command,bg='#31445e',fg='white',font=('Segoe UI Symbol',15),width=3,pady=6).pack(side='right',padx=5)
        tk.Button(top,text='＋  Nouveau véhicule',command=self._fleet_new_vehicle,bg='#3276f5',fg='white',font=('Segoe UI',9,'bold'),padx=14,pady=9).pack(side='right',padx=12)
        search=tk.Entry(top,textvariable=self.fleet_search,bg='#f8fbff',fg='#203d5f',font=('Segoe UI',10),relief='flat',width=35)
        search.pack(side='right',fill='x',expand=True,padx=(10,10),ipady=8)
        search.insert(0,'');self.fleet_search.trace_add('write',lambda *_:self.refresh_fleet_management())
        self.fleet_stats=tk.Frame(body,bg='#f3f7fc');self.fleet_stats.pack(fill='x',padx=11,pady=(11,8))
        self.fleet_stat_vars={key:tk.StringVar(value='0') for key in ('service','available','rented','out')}
        colors=(('service','En service','🚘','#08a849','#e9fbef','Véhicules actifs'),
                ('available','Disponibles','✓','#0877ec','#eaf3ff','Prêts à louer'),
                ('rented','Loués','⚿','#f38b00','#fff5e8','En location'),
                ('out','Hors service','🛠','#ed284e','#fff0f3','En maintenance'))
        for i,(key,label,icon,accent,soft,description) in enumerate(colors):
            self.fleet_stats.grid_columnconfigure(i,weight=1,uniform='fleet_metrics')
            card=tk.Frame(self.fleet_stats,bg=soft,highlightbackground='#dfe9f1',highlightthickness=1)
            card.grid(row=0,column=i,sticky='ew',padx=5)
            tk.Label(card,text=icon,bg=accent,fg='white',font=('Segoe UI Symbol',21,'bold'),width=3,pady=12).pack(side='left',padx=9,pady=9)
            text=tk.Frame(card,bg=soft);text.pack(side='left',fill='x',expand=True)
            tk.Label(text,text=label,bg=soft,fg='#27354a',font=('Segoe UI',10,'bold')).pack(anchor='w')
            line=tk.Frame(text,bg=soft);line.pack(anchor='w')
            tk.Label(line,textvariable=self.fleet_stat_vars[key],bg=soft,fg=accent,font=('Segoe UI',19,'bold')).pack(side='left')
            tk.Label(line,text=description,bg=soft,fg='#526473',font=('Segoe UI',8)).pack(side='left',padx=7)
        main=tk.Frame(body,bg='#f3f7fc');main.pack(fill='both',expand=True,padx=13,pady=(4,13))
        main.grid_columnconfigure(0,weight=1,minsize=240);main.grid_columnconfigure(1,weight=4,minsize=620)
        left=tk.Frame(main,bg='white',highlightbackground='#dce6f0',highlightthickness=1)
        left.grid(row=0,column=0,sticky='nsew',padx=(0,12))
        tk.Label(left,text='Liste des véhicules',bg='white',fg='#152e56',font=('Segoe UI',13,'bold'),anchor='w').pack(fill='x',padx=13,pady=(12,5))
        cb=ttk.Combobox(left,textvariable=self.fleet_filter,values=('En service','Hors service','Tous'),state='readonly')
        cb.pack(fill='x',padx=11,pady=5);cb.bind('<<ComboboxSelected>>',lambda _e:self.refresh_fleet_management())
        tk.Label(left,text='⌕  Rechercher par marque, modèle ou plaque',bg='white',fg='#61778e',font=('Segoe UI',8)).pack(anchor='w',padx=12,pady=(4,7))
        list_canvas=tk.Canvas(left,bg='white',height=610,highlightthickness=0)
        list_scroll=ttk.Scrollbar(left,orient='vertical',command=list_canvas.yview)
        list_canvas.configure(yscrollcommand=list_scroll.set)
        list_scroll.pack(side='right',fill='y');list_canvas.pack(side='left',fill='both',expand=True)
        self.fleet_list_host=tk.Frame(list_canvas,bg='white')
        lst=list_canvas.create_window((0,0),window=self.fleet_list_host,anchor='nw')
        self.fleet_list_host.bind('<Configure>',lambda _e:list_canvas.configure(scrollregion=list_canvas.bbox('all')))
        list_canvas.bind('<Configure>',lambda e:list_canvas.itemconfigure(lst,width=e.width))
        right=tk.Frame(main,bg='#f3f7fc');right.grid(row=0,column=1,sticky='nsew')
        tabs=tk.Frame(right,bg='#f3f7fc');tabs.pack(fill='x')
        self.fleet_tab_buttons={}
        for i,(key,title,icon) in enumerate((('maintenance','Entretien','⚙'),('documents','Documents & informations','▤'),('history','Historique de location','▦'),('state','État du véhicule','✎'))):
            tabs.grid_columnconfigure(i,weight=1,uniform='fleet_tabs')
            btn=tk.Button(tabs,text=f'{icon}  {title}',command=lambda k=key:self._fleet_select_tab(k),
                          bg='#e9eef5',fg='#304d6c',font=('Segoe UI',9,'bold'),pady=12)
            btn.grid(row=0,column=i,sticky='ew',padx=2)
            self.fleet_tab_buttons[key]=btn
        self.fleet_panel=tk.Frame(right,bg='white',highlightbackground='#d9e5f1',highlightthickness=1)
        self.fleet_panel.pack(fill='both',expand=True)
        self.refresh_fleet_management()

    def _fleet_select_tab(self,tab):
        self.fleet_tab=tab
        for key,button in self.fleet_tab_buttons.items():
            active=key==tab
            button.configure(bg='#086de1' if active else '#e9eef5',fg='white' if active else '#304d6c')
        self._fleet_render_panel()

    def refresh_fleet_management(self):
        if not hasattr(self,'fleet_list_host'):return
        rows=self.conn.execute('SELECT * FROM vehicles ORDER BY modele,code').fetchall()
        active=self._currently_rented_vehicle_codes()
        service=sum(bool(r['service']) for r in rows)
        for key,n in (('service',service),('available',sum(bool(r['service']) and r['code'] not in active for r in rows)),
                      ('rented',sum(bool(r['service']) and r['code'] in active for r in rows)),('out',len(rows)-service)):
            self.fleet_stat_vars[key].set(str(n))
        mode=self.fleet_filter.get();query=self.fleet_search.get().strip().casefold()
        visible=[r for r in rows if (mode=='Tous' or bool(r['service'])==(mode=='En service'))
                 and query in f"{r['code']} {r['modele']} {r['immatriculation']}".casefold()]
        self._fleet_visible_rows=visible;self._fleet_active=active
        if self.fleet_selected_code not in {r['code'] for r in rows}:
            self.fleet_selected_code=visible[0]['code'] if visible else ''
        for widget in self.fleet_list_host.winfo_children():widget.destroy()
        self.fleet_images=[]
        if not visible:
            tk.Label(self.fleet_list_host,text='Aucun véhicule trouvé',bg='white',fg='#56708a',pady=25).pack(fill='x')
        for r in visible:
            code=r['code'];selected=code==self.fleet_selected_code
            bg='#e5f2ff' if selected else 'white';frame=tk.Frame(self.fleet_list_host,bg=bg,highlightbackground='#c9dfff' if selected else '#e6edf3',highlightthickness=1,height=69)
            frame.pack(fill='x',padx=6,pady=2);frame.pack_propagate(False)
            photo=self._fleet_photo(r['photo'],code,(70,52))
            label=tk.Label(frame,image=photo,text='' if photo else '🚘',bg=bg,fg='#2975b8',font=('Segoe UI Emoji',21),
                           width=74 if photo else 5,height=56 if photo else 2)
            label.pack(side='left',padx=(5,7));self.fleet_images.append(photo)
            info=tk.Frame(frame,bg=bg);info.pack(side='left',fill='both',expand=True,pady=10)
            model=tk.Label(info,text=r['modele'] or code,bg=bg,fg='#1d304a',anchor='w',font=('Segoe UI',9,'bold'))
            model.pack(fill='x')
            plate=tk.Label(info,text=r['immatriculation'] or code,bg=bg,fg='#4a6581',anchor='w',font=('Segoe UI',8));plate.pack(fill='x')
            state='Hors service' if not r['service'] else 'Loué' if code in active else 'Disponible'
            color='#df3b55' if not r['service'] else '#eb871d' if code in active else '#0c9a4e'
            badge=tk.Label(frame,text=state,bg='#ffe8ed' if not r['service'] else '#fff0e3' if code in active else '#e3f8ea',fg=color,font=('Segoe UI',7,'bold'),padx=5,pady=4)
            badge.pack(side='right',padx=4)
            for w in (frame,label,info,model,plate,badge):w.bind('<Button-1>',lambda _e,c=code:self._fleet_choose(c))
        self._fleet_select_tab(self.fleet_tab)

    def _fleet_choose(self,code):
        if code!=self.fleet_selected_code and self.fleet_tab=='maintenance':
            self._fleet_maintenance_new(code)
        self.fleet_selected_code=code;self.refresh_fleet_management()

    def _fleet_selected(self):
        return self.conn.execute('SELECT * FROM vehicles WHERE code=?',(self.fleet_selected_code,)).fetchone() if self.fleet_selected_code else None

    def _fleet_details(self,code):
        row=self.conn.execute("SELECT payload FROM module_records WHERE module='fleet_details' AND record_id=?",(code,)).fetchone()
        try:return json.loads(row[0]) if row else {}
        except (ValueError,TypeError):return {}

    def _fleet_render_panel(self):
        if not hasattr(self,'fleet_panel'):return
        for widget in self.fleet_panel.winfo_children():widget.destroy()
        row=self._fleet_selected()
        if not row:
            tk.Label(self.fleet_panel,text='Sélectionnez un véhicule dans la liste',bg='white',fg='#557083',font=('Segoe UI',12),pady=38).pack(fill='x');return
        if self.fleet_tab=='maintenance':return self._fleet_render_maintenance(row)
        if self.fleet_tab=='history':return self._fleet_render_history(row)
        if self.fleet_tab=='state':
            from vehicle_condition import VehicleStateEditor
            self.fleet_state_editor=VehicleStateEditor(self.fleet_panel,self,lambda:row['code'])
            return
        d=self._fleet_details(row['code'])
        top=tk.Frame(self.fleet_panel,bg='white');top.pack(fill='x',padx=13,pady=(12,9))
        picture=tk.Frame(top,bg='#edf2f7',width=220,height=190);picture.pack(side='left',padx=(0,12));picture.pack_propagate(False)
        photo=self._fleet_photo(row['photo'],row['code'],(215,145))
        self.fleet_detail_image=photo
        tk.Label(picture,image=photo,text='' if photo else '🚘\nAucune photo',bg='#edf2f7',fg='#53708b',font=('Segoe UI Emoji',15)).pack(fill='both',expand=True,pady=3)
        tk.Button(picture,text='▣  Changer la photo',command=self._fleet_change_photo,bg='white',fg='#285282',font=('Segoe UI',8,'bold'),pady=5).pack(fill='x',padx=6,pady=(0,5))
        identity=tk.Frame(top,bg='white');identity.pack(side='left',fill='both',expand=True)
        tk.Label(identity,text=row['modele'] or 'Véhicule',bg='white',fg='#1549a3',font=('Segoe UI',21,'bold'),anchor='w').pack(fill='x',pady=(5,8))
        flags=tk.Frame(identity,bg='white');flags.pack(anchor='w',pady=(0,12))
        for caption,accent,soft in ((('●  En service' if row['service'] else '●  Hors service'),'#07974c','#e7f9ed'),
                    (('◉  Loué' if row['code'] in self._fleet_active else '◉  Disponible'),'#df721c' if row['code'] in self._fleet_active else '#07974c','#fff2e6' if row['code'] in self._fleet_active else '#e7f9ed')):
            tk.Label(flags,text=caption,bg=soft,fg=accent,font=('Segoe UI',9,'bold'),padx=9,pady=6).pack(side='left',padx=(0,7))
        tk.Label(identity,text=f"Code {row['code']}    •    {row['immatriculation'] or 'Immatriculation non renseignée'}",bg='white',fg='#526881',font=('Segoe UI',9)).pack(anchor='w')
        tk.Button(identity,text='✎  Modifier la fiche',command=lambda:self._fleet_edit('Identité'),bg='#e6f1ff',fg='#115ead',font=('Segoe UI',8,'bold')).pack(anchor='w',pady=12)
        counter=tk.Frame(top,bg='#edf6ff',highlightbackground='#d6e6f5',highlightthickness=1,width=193)
        counter.pack(side='right',fill='y',padx=(10,0));counter.pack_propagate(False)
        tk.Label(counter,text='◴  Compteur actuel',bg='#edf6ff',fg='#314c6b',font=('Segoe UI',9,'bold')).pack(pady=(20,5))
        tk.Label(counter,text=f"{int(row['compteur'] or 0):,} km".replace(',',' '),bg='#edf6ff',fg='#0769d3',font=('Segoe UI',17,'bold')).pack()
        tk.Button(counter,text='✎  Modifier compteur',command=self._fleet_counter,bg='#0977e7',fg='white',font=('Segoe UI',8,'bold'),padx=8,pady=7).pack(pady=(8,3),padx=8,fill='x')
        fuel_value=tk.StringVar(value=str(row['fuel_eighths'] if row['fuel_eighths'] is not None else 4))
        fuel_box=self._vehicle_fuel_editor(counter,fuel_value,'#edf6ff')
        def save_fuel():
            level=int(fuel_value.get())
            self.conn.execute('UPDATE vehicles SET fuel_eighths=? WHERE code=?',(level,row['code']))
            self._audit('MODIFICATION','CARBURANT VÉHICULE',row['code'],f'Niveau : {level}/8')
            self.conn.commit()
            if hasattr(self,'vehicle_form_vars') and self.vehicle_form_vars['code'].get()==row['code']:
                self.vehicle_form_vars['fuel_eighths'].set(str(level))
            self.refresh_fleet_management();self.schedule_web_sync()
        tk.Button(fuel_box,text='Enregistrer le niveau',command=save_fuel,bg='#0879e8',fg='white',
                  font=('Segoe UI',8,'bold'),relief='flat',pady=3).pack(side='bottom',fill='x',pady=3)

        specs=tk.Frame(self.fleet_panel,bg='#f5f9fe');specs.pack(fill='x',padx=13,pady=(0,9))
        for i,(label,value) in enumerate((('Immatriculation',row['immatriculation']),('Marque',d.get('marque') or (row['modele'] or '').split(' ')[0]),
                  ('Modèle',row['modele']),('Type',d.get('type')),('Carburant',d.get('carburant')),('Année',d.get('annee')),('Couleur',d.get('couleur')),('Places',d.get('places')))):
            specs.grid_columnconfigure(i,weight=1,uniform='fleet_specs')
            cell=tk.Frame(specs,bg='white',highlightbackground='#e4ecf3',highlightthickness=1)
            cell.grid(row=0,column=i,sticky='ew',padx=1)
            tk.Label(cell,text=label,bg='white',fg='#60748a',font=('Segoe UI',7)).pack(anchor='w',padx=5,pady=(6,2))
            tk.Label(cell,text=str(value or '—')[:20],bg='white',fg='#172a44',font=('Segoe UI',8,'bold')).pack(anchor='w',padx=5,pady=(0,7))
        panels=tk.Frame(self.fleet_panel,bg='white');panels.pack(fill='x',padx=10)
        for col in range(3):panels.grid_columnconfigure(col,weight=1,uniform='fleet_columns')
        self._fleet_section(panels,0,0,'🛡  Assurance','#11a554','#e9f9f0',
            [('Compagnie',d.get('assurance_compagnie')),('N° de police',d.get('assurance_police')),('Date de début',d.get('assurance_debut')),('Date de fin',row['assurance_fin'])],'Assurance')
        self._fleet_section(panels,0,1,'⚙  Contrôle technique','#e88613','#fff3e5',
            [('N° de contrôle',d.get('controle_numero')),('Date de contrôle',d.get('controle_date')),('Date d’expiration',row['controle_technique'])],'Contrôle technique')
        self._fleet_section(panels,0,2,'🚘  Mise en circulation','#2178ec','#eaf3ff',
            [('Date de 1ère mise en circulation',row['mise_circulation'])],'Mise en circulation')
        self._fleet_section(panels,1,0,'⚿  Mise en service','#803bd6','#f6edff',
            [('Date de mise en service',d.get('mise_service'))],'Mise en service')
        self._fleet_section(panels,1,1,'⊘  Retrait','#e6314d','#fff0f2',
            [('Date de retrait',row['fin_service'])],'Retrait')
        self._fleet_section(panels,1,2,'☷  Caractéristiques','#1976dd','#e9f5ff',
            [('Catégorie',d.get('categorie')),('Transmission',d.get('transmission')),('Puissance (CV)',d.get('puissance')),('Nombre de portes',d.get('portes'))],'Caractéristiques')
        self._fleet_documents(row)

    def _fleet_section(self,parent,r,c,title,accent,soft,fields,section):
        box=tk.Frame(parent,bg=soft,highlightbackground='#dce6ee',highlightthickness=1)
        box.grid(row=r,column=c,sticky='nsew',padx=4,pady=4)
        top=tk.Frame(box,bg=soft);top.pack(fill='x')
        tk.Label(top,text=title,bg=soft,fg=accent,font=('Segoe UI',10,'bold')).pack(side='left',padx=10,pady=9)
        tk.Button(top,text='✎',command=lambda:self._fleet_edit(section),bg=soft,fg=accent,font=('Segoe UI',10,'bold'),padx=5,pady=2).pack(side='right',padx=8)
        inner=tk.Frame(box,bg=soft);inner.pack(fill='both',expand=True,padx=7,pady=(0,8))
        for i,(label,value) in enumerate(fields):
            cell=tk.Frame(inner,bg='white');cell.grid(row=i//2,column=i%2,sticky='ew',padx=2,pady=2)
            inner.grid_columnconfigure(i%2,weight=1)
            tk.Label(cell,text=label,bg='white',fg='#65778c',font=('Segoe UI',7),anchor='w').pack(fill='x',padx=7,pady=(4,0))
            tk.Label(cell,text=str(value or '—'),bg='white',fg='#243247',font=('Segoe UI',9,'bold'),anchor='w').pack(fill='x',padx=7,pady=(1,5))

    def _fleet_documents(self,row):
        container=tk.Frame(self.fleet_panel,bg='white');container.pack(fill='x',padx=13,pady=(10,12))
        tk.Label(container,text='▣  Documents du véhicule',bg='white',fg='#1550a1',font=('Segoe UI',11,'bold')).pack(anchor='w',pady=(1,7))
        folder=Path(__file__).resolve().parent/'documents_vehicules'/re.sub(r'[^\w.-]','_',str(row['code']))
        files=sorted((p for p in folder.iterdir() if p.is_file()),key=lambda p:p.name.casefold()) if folder.exists() else []
        tiles=tk.Frame(container,bg='white');tiles.pack(fill='x')
        for i,path in enumerate(files):
            tiles.grid_columnconfigure(i%5,weight=1,uniform='fleet_docs')
            item=tk.Frame(tiles,bg='#f8fbff',highlightbackground='#dce6f3',highlightthickness=1)
            item.grid(row=i//5,column=i%5,sticky='ew',padx=3,pady=3)
            icon='▤' if path.suffix.lower()=='.pdf' else '▣'
            tk.Label(item,text=icon,bg='#e7f2ff',fg='#1b72ce',font=('Segoe UI Symbol',15),width=2).pack(side='left',padx=5,pady=7)
            label=tk.Frame(item,bg='#f8fbff');label.pack(side='left',fill='x',expand=True)
            tk.Label(label,text=path.stem[:18],bg='#f8fbff',fg='#25384c',font=('Segoe UI',8,'bold'),anchor='w').pack(fill='x')
            tk.Button(label,text='▣ Voir',command=lambda p=path:self._fleet_open_file(p),bg='#f8fbff',fg='#0768c9',font=('Segoe UI',7),anchor='w',pady=0).pack(anchor='w')
        add=tk.Button(tiles,text='☁\nAjouter un document\nPDF · JPG · PNG',command=self._fleet_import_documents,
                      bg='#edf6ff',fg='#1269d5',font=('Segoe UI',8,'bold'),pady=12)
        idx=len(files);tiles.grid_columnconfigure(idx%5,weight=1,uniform='fleet_docs')
        add.grid(row=idx//5,column=idx%5,sticky='ew',padx=3,pady=3)

    @staticmethod
    def _fleet_open_file(path):
        try:
            if os.name=='nt':os.startfile(str(path))
            else:
                import webbrowser
                webbrowser.open(path.as_uri())
        except Exception as exc:messagebox.showerror('Document',str(exc))

    def _fleet_import_documents(self):
        row=self._fleet_selected()
        if not row:return
        paths=filedialog.askopenfilenames(title='Documents du véhicule',filetypes=[('Documents','*.pdf *.png *.jpg *.jpeg'),('Tous les fichiers','*.*')])
        if not paths:return
        folder=Path(__file__).resolve().parent/'documents_vehicules'/re.sub(r'[^\w.-]','_',str(row['code']))
        folder.mkdir(parents=True,exist_ok=True)
        for path in paths:
            source=Path(path);safe=re.sub(r'[^\w.-]','_',source.name)
            target=folder/safe
            if source.resolve()!=target.resolve():shutil.copy2(source,target)
        self._fleet_render_panel()

    def _fleet_maintenance_new(self, code=None, service='Vidange'):
        """Prépare la fiche d'entretien existante pour le véhicule du parc."""
        code=code or self.fleet_selected_code
        row=self.conn.execute('SELECT * FROM vehicles WHERE code=?',(code,)).fetchone()
        if not row or 'maintenance' not in getattr(self,'module_vars',{}):return
        self.new_business_record('maintenance')
        values=self.module_vars['maintenance']
        values['vehicle'].set(f"{row['code']} | {row['modele']} | {row['immatriculation']}")
        values['current_counter'].set(str(row['compteur'] or 0))
        values['mileage'].set(str(row['compteur'] or 0))
        values['service'].set(service)
        self._calculate_maintenance_km()
        if hasattr(self,'maintenance_vehicle_info'):
            self._load_maintenance_vehicle_pro()

    def _fleet_maintenance_open(self, service=None):
        """Ouvre le formulaire complet avec la voiture déjà sélectionnée."""
        code=self.fleet_selected_code
        row=self.conn.execute('SELECT service FROM vehicles WHERE code=?',(code,)).fetchone()
        if not row:return
        self.show_page('maintenance')
        if hasattr(self,'maintenance_service_filter'):
            self.maintenance_service_filter.set('En service' if row['service'] else 'Hors service')
            self._apply_maintenance_global_filter()
        self._fleet_maintenance_new(code,service or 'Vidange')
        if hasattr(self,'maintenance_search'):
            self.maintenance_search.set(code);self._refresh_maintenance_history_filtered()

    def _fleet_render_maintenance(self,row):
        code=str(row['code'])
        head=tk.Frame(self.fleet_panel,bg='white');head.pack(fill='x',padx=16,pady=(15,9))
        tk.Label(head,text=f"🔧  Entretien · {row['modele']}",bg='white',fg='#1549a3',font=('Segoe UI',16,'bold')).pack(side='left')
        tk.Label(head,text=f"{row['immatriculation']}   •   {int(row['compteur'] or 0):,} km".replace(',',' '),bg='#eaf3ff',fg='#255480',font=('Segoe UI',9,'bold'),padx=11,pady=7).pack(side='right')
        records=[]
        for entry in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='maintenance' ORDER BY created_at DESC,rowid DESC"):
            try:data=json.loads(entry['payload'])
            except (ValueError,TypeError):continue
            if str(data.get('vehicle','')).split('|')[0].strip()==code:
                records.append((entry['record_id'],data))
        latest={}
        for ref,data in records:
            kind=str(data.get('service','')).casefold().replace('î','i')
            if kind not in latest:latest[kind]=data
        cards=tk.Frame(self.fleet_panel,bg='white');cards.pack(fill='x',padx=12,pady=(0,10))
        for column,(title,key,accent,soft) in enumerate((('🛢  Vidange','vidange','#bb7114','#fff7eb'),('💧  AdBlue','adblue','#1777b9','#edf8ff'),('⛓  Chaîne','chaine','#a6406d','#fff0f5'))):
            cards.grid_columnconfigure(column,weight=1,uniform='fleet_maintenance')
            box=tk.Frame(cards,bg=soft,highlightbackground='#d9e5ef',highlightthickness=1)
            box.grid(row=0,column=column,sticky='nsew',padx=4)
            tk.Label(box,text=title,bg=soft,fg=accent,font=('Segoe UI',11,'bold')).pack(anchor='w',padx=10,pady=(10,5))
            data=latest.get(key)
            for label,value in (('Dernière intervention',data.get('date') if data else '—'),
                                ('Km intervention',data.get('mileage') if data else '—'),
                                ('Prochain km',data.get('next_mileage') if data else '—'),
                                ('Km restants',str(max(0,int(self._number(data.get('next_mileage'))-self._number(row['compteur'])))) if data and self._number(data.get('next_mileage')) else '—')):
                tk.Label(box,text=f'{label} : {value or "—"}',bg=soft,fg='#365169',font=('Segoe UI',8),anchor='w').pack(fill='x',padx=10,pady=2)
            tk.Button(box,text='＋  Saisir une intervention',command=lambda t=title.split('  ',1)[1]:self._fleet_maintenance_editor(service=t),
                      bg=accent,fg='white',font=('Segoe UI',8,'bold'),relief='flat',pady=7).pack(fill='x',padx=9,pady=(8,10))
        bar=tk.Frame(self.fleet_panel,bg='#f0f6fc');bar.pack(fill='x',padx=16,pady=(4,0))
        tk.Label(bar,text=f'▤  Historique des interventions ({len(records)})',bg='#f0f6fc',fg='#184b86',font=('Segoe UI',10,'bold')).pack(side='left',padx=8,pady=9)
        tk.Button(bar,text='✎  Ouvrir la fiche entretien',command=self._fleet_maintenance_open,bg='#e2edfc',fg='#125eaa',font=('Segoe UI',8,'bold'),relief='flat',padx=11,pady=5).pack(side='right',padx=7)
        tk.Button(bar,text='＋  Nouvelle intervention',command=self._fleet_maintenance_editor,bg='#1779d0',fg='white',font=('Segoe UI',8,'bold'),relief='flat',padx=11,pady=5).pack(side='right',padx=7)
        columns=('date','type','km','next','remaining','product','amount','reference')
        table=tk.Frame(self.fleet_panel,bg='white');table.pack(fill='both',expand=True,padx=16,pady=(0,14))
        tree=ttk.Treeview(table,columns=columns,show='headings',height=9)
        for key,title,width in zip(columns,('Date','Intervention','Km effectué','Prochain km','Km restants','Produit','Montant MAD','Référence'),(95,105,100,110,100,115,105,105)):
            tree.heading(key,text=title);tree.column(key,width=width,anchor='center')
        for ref,data in records:
            nxt=self._number(data.get('next_mileage'))
            remain=str(max(0,int(nxt-self._number(row['compteur'])))) if nxt else '—'
            tree.insert('','end',iid=ref,values=(data.get('date'),data.get('service'),data.get('mileage'),data.get('next_mileage'),remain,data.get('product'),data.get('amount'),ref))
        scroll=ttk.Scrollbar(table,orient='vertical',command=tree.yview);tree.configure(yscrollcommand=scroll.set)
        tree.pack(side='left',fill='both',expand=True);scroll.pack(side='right',fill='y')
        tk.Button(bar,text='✎  Modifier la sélection',command=lambda:self._fleet_maintenance_editor(tree.selection()[0]) if tree.selection() else messagebox.showinfo('Entretien','Sélectionnez une intervention.'),bg='#e5a043',fg='white',font=('Segoe UI',8,'bold'),relief='flat',padx=11,pady=5).pack(side='right',padx=7)
        def open_intervention(_event=None):
            selected=tree.selection()
            if not selected:return
            self._fleet_maintenance_editor(selected[0])
        tree.bind('<Double-1>',open_intervention)

    def _fleet_maintenance_editor(self, record_id=None, service='Vidange'):
        """Édite l'intervention sur l'onglet Entretien du parc et ses données liées."""
        code=self.fleet_selected_code
        vehicle=self.conn.execute('SELECT code,modele,immatriculation,compteur FROM vehicles WHERE code=?',(code,)).fetchone()
        if not vehicle:return
        old=None
        if record_id:
            record=self.conn.execute("SELECT payload FROM module_records WHERE module='maintenance' AND record_id=?",(record_id,)).fetchone()
            if not record:return
            try:old=json.loads(record['payload'])
            except (ValueError,TypeError):return
            if str(old.get('vehicle','')).split('|')[0].strip()!=code:return
        defaults={
            'reference':record_id or f"ENT{datetime.now():%Y%m%d%H%M%S%f}",
            'vehicle':f"{vehicle['code']} | {vehicle['modele']} | {vehicle['immatriculation']}",
            'date':datetime.now().strftime('%d/%m/%Y'), 'service':service,
            'current_counter':str(vehicle['compteur'] or 0),'mileage':str(vehicle['compteur'] or 0),
            'product_km':'','next_mileage':'','remaining_km':'',
            'supplier':'','product':'','product_ref':'','quantity':'1','amount':'0',
            'payment_method':'ESPÈCES','notes':''}
        defaults.update(old or {})
        values={key:tk.StringVar(value=str(defaults[key]) if defaults[key] is not None else '') for key in defaults}
        win=tk.Toplevel(self.root);win.title('Modifier une intervention' if old else 'Nouvelle intervention')
        win.geometry('960x665');win.minsize(790,610);win.transient(self.root);win.grab_set();win.configure(bg='#eff5fb')
        header=tk.Frame(win,bg='#075eab');header.pack(fill='x')
        tk.Label(header,text=('✎  MODIFIER L’ENTRETIEN' if old else '＋  NOUVEL ENTRETIEN'),bg='#075eab',fg='white',font=('Segoe UI',15,'bold')).pack(side='left',padx=18,pady=12)
        tk.Label(header,text=f"{vehicle['modele']} · {vehicle['immatriculation']}",bg='#075eab',fg='#d9ebff',font=('Segoe UI',10,'bold')).pack(side='right',padx=18)
        form=tk.Frame(win,bg='white',highlightbackground='#d0e2f1',highlightthickness=1);form.pack(fill='both',expand=True,padx=14,pady=12)
        tk.Label(form,text='CHOISIR L’INTERVENTION',bg='white',fg='#203d60',font=('Segoe UI',9,'bold')).grid(row=0,column=0,columnspan=3,sticky='w',padx=11,pady=(12,3))
        cards=tk.Frame(form,bg='white');cards.grid(row=1,column=0,columnspan=3,sticky='ew',padx=7,pady=(0,6))
        card_widgets={}
        def select_service(kind):
            values['service'].set(kind)
            for name,(box,title,caption,canvas,accent,soft) in card_widgets.items():
                active=name==kind
                background=soft if active else '#f8fbfe'
                box.configure(bg=background,highlightbackground=accent if active else '#d7e5ef',highlightthickness=2 if active else 1)
                title.configure(bg=background,fg=accent if active else '#395873')
                caption.configure(bg=background,fg='#526c80')
                canvas.configure(bg=background)
        for col,(kind,caption,accent,soft) in enumerate((('AdBlue','Liquide et autonomie','#1377b7','#eaf6ff'),
                                                         ('Vidange','Huile et moteur','#b36b16','#fff5e8'),
                                                         ('Chaîne','Distribution et contrôle','#9044a6','#f7effd'))):
            cards.grid_columnconfigure(col,weight=1,uniform='maintenance_type')
            box=tk.Frame(cards,bg='#f8fbfe',highlightbackground='#d7e5ef',highlightthickness=1,cursor='hand2',takefocus=1)
            box.grid(row=0,column=col,sticky='ew',padx=4)
            canvas=tk.Canvas(box,width=44,height=48,bg='#f8fbfe',highlightthickness=0,cursor='hand2');canvas.pack(side='left',padx=(10,5),pady=6)
            if kind=='AdBlue':
                canvas.create_polygon(22,4,35,26,34,36,28,42,17,42,10,35,10,26,fill=accent,outline=accent,smooth=True)
                canvas.create_oval(16,31,21,36,fill='white',outline='')
            elif kind=='Vidange':
                canvas.create_rectangle(9,18,35,38,fill=accent,outline=accent)
                canvas.create_rectangle(14,11,29,19,fill=accent,outline=accent)
                canvas.create_line(33,19,39,15,41,15,fill=accent,width=3)
                canvas.create_oval(17,23,27,33,fill='white',outline='')
            else:
                canvas.create_oval(4,11,29,31,outline=accent,width=5)
                canvas.create_oval(17,21,41,41,outline=accent,width=5)
                canvas.create_line(18,27,28,21,fill=accent,width=5)
            label_box=tk.Frame(box,bg='#f8fbfe');label_box.pack(side='left',fill='both',expand=True,pady=7)
            title=tk.Label(label_box,text=kind,bg='#f8fbfe',fg='#395873',font=('Segoe UI',11,'bold'),anchor='w',cursor='hand2');title.pack(fill='x')
            subtitle=tk.Label(label_box,text=caption,bg='#f8fbfe',fg='#526c80',font=('Segoe UI',8),anchor='w',cursor='hand2');subtitle.pack(fill='x')
            card_widgets[kind]=(box,title,subtitle,canvas,accent,soft)
            for control in (box,canvas,label_box,title,subtitle):
                control.bind('<Button-1>',lambda _e,k=kind:select_service(k))
                control.bind('<Return>',lambda _e,k=kind:select_service(k))
                control.bind('<space>',lambda _e,k=kind:select_service(k))
        initial=str(values['service'].get()).casefold()
        initial_kind=next((k for k in card_widgets if k.casefold()==initial or (k=='Chaîne' and initial=='chaine')),None)
        if initial_kind:select_service(initial_kind)
        fields=(('Référence','reference'),('Date de l’opération','date'),('Compteur actuel (km)','current_counter'),
                ('Kilométrage intervention','mileage'),
                ('Kilométrage produit','product_km'),('Prochaine intervention (km)','next_mileage'),
                ('Kilométrage restant','remaining_km'),('Fournisseur','supplier'),('Produit','product'),
                ('Référence produit','product_ref'),('Quantité','quantity'),('Montant (MAD)','amount'),
                ('Type de règlement','payment_method'),('Observations','notes'))
        for col in range(3):form.grid_columnconfigure(col,weight=1,uniform='maintenance_edit')
        field_widgets={}
        for index,(label,key) in enumerate(fields):
            row,col=divmod(index,3);row+=2
            cell=tk.Frame(form,bg='white');cell.grid(row=row,column=col,sticky='ew',padx=10,pady=(8,3))
            tk.Label(cell,text=label,bg='white',fg='#1a385e',font=('Segoe UI',9,'bold')).pack(anchor='w')
            if key=='payment_method':widget=ttk.Combobox(cell,textvariable=values[key],values=('ESPÈCES','CHÈQUE','À CRÉDIT'),state='readonly')
            else:widget=ttk.Entry(cell,textvariable=values[key],state='readonly' if key=='reference' else 'normal')
            widget.pack(fill='x',ipady=5,pady=(4,0))
            field_widgets[key]=widget
            if key=='date':self._attach_date_picker(widget,values[key])
        editing={'busy':False}
        def recalculate(changed=None):
            if editing['busy']:return
            editing['busy']=True
            try:
                counter=self._number(values['current_counter'].get());mileage=self._number(values['mileage'].get())
                if changed=='next_mileage':
                    target=self._number(values['next_mileage'].get())
                    values['product_km'].set(str(max(0,int(target-mileage))) if target else '')
                elif changed=='remaining_km':
                    target=counter+self._number(values['remaining_km'].get())
                    values['product_km'].set(str(max(0,int(target-mileage))) if target else '')
                    values['next_mileage'].set(str(int(target)) if target else '')
                else:
                    target=mileage+self._number(values['product_km'].get())
                    values['next_mileage'].set(str(int(target)) if self._number(values['product_km'].get())>0 else '')
                values['remaining_km'].set(str(max(0,int(target-counter))) if target else '')
            finally:editing['busy']=False
        for key in ('current_counter','mileage','product_km'):
            values[key].trace_add('write',lambda *_args:recalculate())
        # Le champ modifié pilote les deux autres valeurs après saisie complète.
        for key in ('next_mileage','remaining_km'):
            field_widgets[key].bind('<FocusOut>',lambda _e,k=key:recalculate(k))
            field_widgets[key].bind('<Return>',lambda _e,k=key:recalculate(k))
        tk.Label(win,text='Prochain km = km intervention + km produit ; restant = prochain km − compteur actuel.',
                 bg='#eff5fb',fg='#355879',font=('Segoe UI',9)).pack(anchor='w',padx=18)
        actions=tk.Frame(win,bg='#eff5fb');actions.pack(fill='x',padx=16,pady=13)
        def save():
            raw={k:v.get().strip() for k,v in values.items()}
            if raw['service'] not in card_widgets:
                messagebox.showwarning('Entretien','Choisissez AdBlue, Vidange ou Chaîne.',parent=win);return
            for key in ('current_counter','mileage','product_km','quantity','amount'):
                if not re.fullmatch(r'\d+(?:[.,]\d+)?',raw[key]):
                    messagebox.showwarning('Entretien',f'Valeur invalide : {key}.',parent=win);return
            recalculate('next_mileage') if raw['next_mileage'] and self._number(raw['next_mileage'])!=self._number(raw['mileage'])+self._number(raw['product_km']) else recalculate()
            payload={k:v.get().strip() for k,v in values.items()}
            error=self._validate_maintenance(payload)
            if error:messagebox.showwarning('Entretien',error,parent=win);return
            if old:
                self.conn.execute("UPDATE module_records SET payload=?,created_at=? WHERE module='maintenance' AND record_id=?",
                                  (json.dumps(payload,ensure_ascii=False),datetime.now().isoformat(timespec='seconds'),record_id))
                # Un ancien entretien ne doit pas réinitialiser le compteur actuel du véhicule.
                updated=dict(payload)
                if str(payload['current_counter'])==str(old.get('current_counter','')):updated.pop('current_counter',None)
                self._sync_maintenance_vehicle(updated)
            else:
                self.conn.execute('INSERT INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,?)',
                                  ('maintenance',payload['reference'],json.dumps(payload,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')))
                self._sync_maintenance_vehicle(payload)
            self._sync_maintenance_finance(payload['reference'],payload)
            self._audit('MODIFICATION' if old else 'CRÉATION','ENTRETIEN',payload['reference'])
            self.conn.commit();self.refresh_business_records('maintenance');self._fleet_render_panel();win.destroy()
        tk.Button(actions,text='Annuler',command=win.destroy,bg='#64748b',fg='white',font=('Segoe UI',9,'bold'),relief='flat',padx=18,pady=9).pack(side='right',padx=5)
        tk.Button(actions,text='▣  Enregistrer les modifications' if old else '＋  Enregistrer l’intervention',command=save,bg='#15955c',fg='white',font=('Segoe UI',10,'bold'),relief='flat',padx=18,pady=9).pack(side='right',padx=5)

    def _fleet_render_history(self,row):
        tk.Label(self.fleet_panel,text=f"Historique de location · {row['modele']}",bg='white',fg='#1549a3',font=('Segoe UI',15,'bold')).pack(anchor='w',padx=14,pady=14)
        filters=tk.Frame(self.fleet_panel,bg='white');filters.pack(fill='x',padx=14,pady=(0,10))
        for title,variable,choices in (
            ('Mois',self.fleet_history_month,('Tous les mois','Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')),
            ('Année',self.fleet_history_year,('Toutes les années',)+tuple(str(y) for y in range(datetime.now().year+1,datetime.now().year-20,-1)))):
            tk.Label(filters,text=title,bg='white',fg='#304d6c',font=('Segoe UI',9,'bold')).pack(side='left',padx=(2,6))
            combo=ttk.Combobox(filters,textvariable=variable,values=choices,state='readonly',width=15)
            combo.pack(side='left',padx=(0,14));combo.bind('<<ComboboxSelected>>',lambda _e:self._fleet_render_panel())
        cols=('number','client','start','end','days','total','paid','balance')
        tree=ttk.Treeview(self.fleet_panel,columns=cols,show='headings',height=20)
        for key,label,width in zip(cols,('N° contrat','Client','Départ','Retour','Jours','Montant','Réglé','Reste'),(100,160,100,100,65,110,110,110)):
            tree.heading(key,text=label);tree.column(key,width=width,anchor='center')
        months=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
        selected_month=months.index(self.fleet_history_month.get())+1 if self.fleet_history_month.get() in months else None
        selected_year=int(self.fleet_history_year.get()) if self.fleet_history_year.get().isdigit() else None
        period_start=datetime(selected_year,selected_month,1).date() if selected_month and selected_year else None
        period_end=(period_start.replace(day=28)+timedelta(days=4)).replace(day=1) if period_start else None
        for c in self.conn.execute('''SELECT c.*,COALESCE(cl.nom,'') AS nom,COALESCE(cl.prenom,'') AS prenom
                    FROM contracts c LEFT JOIN clients cl ON cl.code=c.client_code WHERE c.vehicle_code=?
                    ORDER BY c.created_at DESC,c.numero DESC''',(row['code'],)):
            start=self._parse_french_date(c['date_depart']); end=self._parse_french_date(c['date_retour'])
            if period_start and (not start or start.date()>=period_end or (end and end.date()<period_start)):continue
            if not period_start and selected_month and (not start or all(day.month!=selected_month for day in (start,end or start))):continue
            if not period_start and selected_year and (not start or start.year>selected_year or (end or start).year<selected_year):continue
            values=(c['numero'],f"{c['nom']} {c['prenom']}".strip(),c['date_depart'],c['date_retour'],c['duree'],
                    f"{float(c['montant'] or 0):,.2f}",f"{float(c['reglement'] or 0):,.2f}",f"{max(0,float(c['montant'] or 0)-float(c['reglement'] or 0)):,.2f}")
            tree.insert('','end',values=values)
        tree.pack(fill='both',expand=True,padx=14,pady=(0,14))

    def _fleet_new_vehicle(self):
        self.show_page('vehicles');self.new_vehicle();self.vehicle_notebook.select(1)

    def _fleet_change_photo(self):
        if self._select_vehicle_code_v207(self.fleet_selected_code):
            self.choose_vehicle_photo();self.refresh_fleet_management()

    def _fleet_counter(self):
        row=self._fleet_selected()
        if not row:return
        old=int(row['compteur'] or 0)
        win=self._secondary_window(self.root);win.title('Modifier le compteur · HBZ Rent Car')
        win.geometry('480x365');win.resizable(False,False);win.transient(self.root)
        win.configure(bg='#eef5fb');win.grab_set()
        header=tk.Frame(win,bg='#0d579d');header.pack(fill='x')
        tk.Label(header,text='◴  COMPTEUR DU VÉHICULE',bg='#0d579d',fg='white',
                 font=('Segoe UI',15,'bold'),anchor='w',padx=20,pady=14).pack(fill='x')
        content=tk.Frame(win,bg='white',highlightbackground='#caddeb',highlightthickness=1)
        content.pack(fill='both',expand=True,padx=16,pady=15)
        tk.Label(content,text=row['modele'] or 'Véhicule',bg='white',fg='#173957',
                 font=('Segoe UI',14,'bold')).pack(anchor='w',padx=18,pady=(13,2))
        tk.Label(content,text=f"Code {row['code']}  •  {row['immatriculation'] or 'Sans immatriculation'}",
                 bg='white',fg='#62788b',font=('Segoe UI',9)).pack(anchor='w',padx=18)
        tk.Label(content,text=f"Compteur actuel : {old:,} km".replace(',',' '),bg='#eaf4ff',
                 fg='#0d579d',font=('Segoe UI',11,'bold'),anchor='w',padx=12,pady=8).pack(fill='x',padx=18,pady=12)
        tk.Label(content,text='Nouveau kilométrage (km)',bg='white',fg='#314b61',
                 font=('Segoe UI',9,'bold')).pack(anchor='w',padx=18)
        value=tk.StringVar(value=str(old))
        entry=tk.Entry(content,textvariable=value,justify='center',font=('Segoe UI',18,'bold'),
                       bg='#f5faff',fg='#075a9b',relief='solid',bd=1)
        entry.pack(fill='x',padx=18,pady=(5,3),ipady=6)
        info=tk.StringVar(value='Saisissez la valeur relevée sur le compteur.')
        tk.Label(content,textvariable=info,bg='white',fg='#638093',font=('Segoe UI',8)).pack(anchor='w',padx=18)
        def save(_event=None):
            raw=value.get().strip().replace(' ','')
            if not raw.isdigit():
                info.set('Saisissez un kilométrage entier positif.');entry.focus_set();return
            km=int(raw)
            if km<old and not messagebox.askyesno('Vérifier le compteur',
                    f'Le nouveau compteur ({km:,} km) est inférieur à la valeur actuelle ({old:,} km). Continuer ?'.replace(',',' '),parent=win):return
            self.conn.execute('UPDATE vehicles SET compteur=? WHERE code=?',(km,row['code']))
            self._audit('MODIFICATION','VÉHICULE',row['code'],f'Compteur : {km} km')
            self.conn.commit();win.destroy();self.refresh_fleet_management()
            if hasattr(self,'vehicles_tree'):
                self.refresh_vehicles()
                if self.vehicle_form_vars['code'].get()==row['code']:
                    self._select_vehicle_code_v207(row['code'])
            self.refresh_dashboard();self.schedule_web_sync()
        actions=tk.Frame(win,bg='#eef5fb');actions.pack(fill='x',padx=16,pady=(0,16))
        tk.Button(actions,text='Annuler',command=win.destroy,bg='white',fg='#49657b',
                  relief='flat',font=('Segoe UI',9,'bold'),padx=18,pady=9).pack(side='right',padx=(8,0))
        tk.Button(actions,text='✓  Enregistrer',command=save,bg='#0879e8',fg='white',
                  relief='flat',font=('Segoe UI',10,'bold'),padx=19,pady=9).pack(side='right')
        entry.bind('<Return>',save);entry.focus_set();entry.select_range(0,'end')

    def _fleet_edit(self,section):
        row=self._fleet_selected()
        if not row:return
        definitions={
            'Identité':(('Marque','marque'),('Marque / Modèle','modele'),('Immatriculation','immatriculation'),('Type','type'),('Carburant','carburant'),('Année','annee'),('Couleur','couleur'),('Places','places')),
            'Assurance':(('Compagnie','assurance_compagnie'),('N° police','assurance_police'),('Date début','assurance_debut'),('Date fin (JJ/MM/AAAA)','assurance_fin')),
            'Contrôle technique':(('N° contrôle','controle_numero'),('Date contrôle','controle_date'),('Date expiration (JJ/MM/AAAA)','controle_technique')),
            'Mise en circulation':(('Date 1ère circulation (JJ/MM/AAAA)','mise_circulation'),),
            'Mise en service':(('Date mise en service','mise_service'),),
            'Retrait':(('Date de retrait (JJ/MM/AAAA)','fin_service'),),
            'Caractéristiques':(('Catégorie','categorie'),('Transmission','transmission'),('Puissance (CV)','puissance'),('Portes','portes')),
        }
        fields=definitions[section];stored=self._fleet_details(row['code']);native={'modele','immatriculation','assurance_fin','controle_technique','mise_circulation','fin_service'}
        win=self._secondary_window(self.root);win.title(f'{section} · {row["modele"]}')
        win.geometry(f'520x{max(290,160+len(fields)*49)}');win.transient(self.root);win.grab_set();win.configure(bg='#f3f7fc')
        tk.Label(win,text=f'✎  {section}',bg='#0c58ad',fg='white',font=('Segoe UI',15,'bold'),anchor='w',padx=18,pady=12).pack(fill='x')
        form=tk.Frame(win,bg='white');form.pack(fill='both',expand=True,padx=12,pady=11)
        vars_={}
        for i,(label,key) in enumerate(fields):
            value=row[key] if key in native else stored.get(key,'')
            v=tk.StringVar(value=str(value or ''));vars_[key]=v
            tk.Label(form,text=label,bg='white',fg='#385872',font=('Segoe UI',9,'bold'),anchor='w').grid(row=i,column=0,sticky='w',padx=10,pady=8)
            tk.Entry(form,textvariable=v,font=('Segoe UI',10),bg='#f3f8fd',relief='flat').grid(row=i,column=1,sticky='ew',padx=10,pady=8,ipady=5)
        form.grid_columnconfigure(1,weight=1)
        def save():
            values={key:v.get().strip() for key,v in vars_.items()}
            for key in ('assurance_fin','controle_technique','mise_circulation','fin_service'):
                if values.get(key) and not self._parse_french_date(values[key]):
                    messagebox.showwarning('Date invalide',f'{key} : utilisez JJ/MM/AAAA.',parent=win);return
            db_fields={key:val for key,val in values.items() if key in native}
            if db_fields:
                setters=','.join(f'{key}=?' for key in db_fields)
                try:self.conn.execute(f'UPDATE vehicles SET {setters} WHERE code=?',(*db_fields.values(),row['code']))
                except Exception as exc:self.conn.rollback();messagebox.showerror('Véhicule',str(exc),parent=win);return
            stored.update({key:val for key,val in values.items() if key not in native})
            self.conn.execute("INSERT INTO module_records(module,record_id,payload,created_at) VALUES('fleet_details',?,?,?) ON CONFLICT(module,record_id) DO UPDATE SET payload=excluded.payload,created_at=excluded.created_at",
                              (row['code'],json.dumps(stored,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')))
            self._audit('MODIFICATION','PARC',row['code'],section)
            self.conn.commit();win.destroy();self.refresh_fleet_management()
            if hasattr(self,'vehicles_tree'):
                self.refresh_vehicles()
                if self.vehicle_form_vars['code'].get()==row['code']:
                    self._select_vehicle_code_v207(row['code'])
        footer=tk.Frame(win,bg='#f3f7fc');footer.pack(fill='x',padx=15,pady=(0,12))
        tk.Button(footer,text='✓  Enregistrer',command=save,bg='#15875c',fg='white',padx=14,pady=8).pack(side='right')
        tk.Button(footer,text='Annuler',command=win.destroy,bg='#e2eaf2',fg='#385066',padx=14,pady=8).pack(side='right',padx=8)
