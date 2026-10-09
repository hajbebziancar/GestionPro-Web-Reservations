"""Vue synthétique du tableau de bord HBZ, alimentée par les données de GestionPro."""
import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import tkinter as tk
from tkinter import ttk


class DashboardReferenceMixin:
    def _dashboard_reference_layout(self, page, legacy):
        for widget in legacy:widget.pack_forget()
        root=tk.Frame(page,bg='#f3f6fa');root.pack(fill='both',expand=True,padx=12,pady=(8,8))
        self.dashboard_reference_vars={key:tk.StringVar(value='—') for key in
            ('service','reservations','returns','tomorrow','dues','revenue','available','rented','due_count','near_count','return_late','ticket','parc')}
        def section(parent,title,command,accent='#0b3a78'):
            panel=tk.Frame(parent,bg='white',highlightbackground='#c8dfef',highlightthickness=1)
            bar=tk.Frame(panel,bg='white');bar.pack(fill='x',pady=2)
            tk.Label(bar,text=title,bg='white',fg=accent,font=('Segoe UI',10,'bold'),anchor='w',padx=11,pady=6).pack(side='left',fill='x',expand=True)
            tk.Button(bar,text='Voir tous  ›',command=command,bg='#f7fbff',fg='#0b3a78',activebackground='#e9f4fd',
                      relief='flat',font=('Segoe UI',8),cursor='hand2').pack(side='right',padx=7)
            return panel
        def table(panel,columns,widths,photo=False,height=4):
            keys=tuple(k for k,_ in columns)
            tree=ttk.Treeview(panel,columns=keys,show='tree headings' if photo else 'headings',height=height,
                              style='DashboardExcel.Treeview')
            if photo:tree.heading('#0',text='Photo');tree.column('#0',width=55,minwidth=45,stretch=False)
            for (key,label),width in zip(columns,widths):
                tree.heading(key,text=label);tree.column(key,width=width,minwidth=55,anchor='center',stretch=True)
            tree.pack(fill='both',expand=True,padx=5,pady=5)
            return tree
        # Barre, cinq cartes, puis deux rangs de trois panneaux comme la maquette.
        header=tk.Frame(root,bg='white',highlightbackground='#dbe5ee',highlightthickness=1);header.pack(fill='x',pady=(0,7))
        tk.Label(header,text='TABLEAU DE BORD',bg='white',fg='#173c61',font=('Segoe UI',11,'bold')).pack(side='left',padx=(14,18))
        tk.Label(header,text='⌕',bg='#e6f3ff',fg='#092e69',font=('Segoe UI',14,'bold')).pack(side='left',padx=(12,4))
        search=tk.Entry(header,textvariable=self.global_search_var,bg='white',fg='#173571',relief='solid',bd=1,font=('Segoe UI',10))
        search.pack(side='left',fill='x',expand=True,padx=5,pady=5,ipady=6);search.bind('<Return>',self._global_reference_search)
        tk.Button(header,text='⌕',command=self._global_reference_search,bg='#087ff3',fg='white',relief='flat',font=('Segoe UI',12,'bold'),width=3).pack(side='left',padx=(0,12))
        self.dashboard_reference_clock=tk.StringVar()
        tk.Label(header,textvariable=self.dashboard_reference_clock,bg='#e6f3ff',fg='#092e69',font=('Segoe UI',10,'bold')).pack(side='left',padx=8)
        banner=tk.Canvas(root,bg='#12518a',height=98,highlightthickness=0)
        banner.pack(fill='x',pady=(0,11))
        self.dashboard_reference_banner=banner
        self.dashboard_reference_welcome=tk.StringVar(value='Bienvenue !')
        self.dashboard_reference_welcome.trace_add('write',lambda *_:self._dashboard_reference_draw_banner())
        banner.bind('<Configure>',self._dashboard_reference_draw_banner)
        period=tk.Frame(banner,bg='white')
        self.dashboard_reference_period_label=tk.StringVar()
        tk.Button(period,text='‹',command=lambda:self._dashboard_reference_shift_month(-1),bg='white',fg='#0b3a78',relief='flat',font=('Segoe UI',16,'bold'),width=3).pack(side='left')
        tk.Label(period,textvariable=self.dashboard_reference_period_label,bg='white',fg='#0b3a78',font=('Segoe UI',10,'bold'),width=16,pady=10).pack(side='left')
        tk.Button(period,text='›',command=lambda:self._dashboard_reference_shift_month(1),bg='white',fg='#0b3a78',relief='flat',font=('Segoe UI',16,'bold'),width=3).pack(side='left')
        self.dashboard_reference_period_window=banner.create_window(0,12,window=period,anchor='ne')
        ticker=tk.Canvas(banner,bg='#103d70',height=31,highlightthickness=0,cursor='hand2')
        ticker.place(x=17,y=63,relwidth=.72,height=29)
        ticker.bind('<Button-1>',lambda _e:self.show_page('contract'))
        self.dashboard_reference_ticker=ticker
        self.dashboard_reference_ticker_items=[]
        self.dashboard_reference_ticker_images=[]
        self.dashboard_reference_ticker_index=0
        self.dashboard_reference_ticker_x=None
        self._dashboard_reference_animate_ticker()
        cards=tk.Frame(root,bg='#eaf4fc');cards.pack(fill='x',pady=(0,9))
        self.dashboard_reference_cards=[]
        definitions=(('service','Véhicules en service','🚘','vehicles'),('returns','Retours aujourd’hui','▦','contract'),
                     ('tomorrow','Retours demain','▦','contract'),('rented','Véhicules loués','▦','contract'),
                     ('dues','Échéances dues','▤','financial_center'),
                     ('parc','Frais cumulés du parc','P','parking_deposits'))
        palette=(('#29729b','#eaf4f9'),('#268367','#e9f7f1'),('#486c9c','#edf2fa'),('#7565a0','#f3effa'),('#c87842','#fcf2e9'),('#a85b00','#fff0ce'))
        for index,(key,title,icon,destination) in enumerate(definitions):
            accent,soft=palette[index];cards.grid_columnconfigure(index,weight=1,uniform='dashboard_cards')
            card=tk.Frame(cards,bg=soft,highlightbackground='#dbe5ee',highlightthickness=1,cursor='hand2');card.grid(row=0,column=index,sticky='nsew',padx=3)
            tk.Label(card,text=icon,bg='#eef6fd',fg=accent,font=('Segoe UI Symbol',18,'bold'),width=3).pack(side='left',padx=(8,8),pady=13)
            right=tk.Frame(card,bg=soft);right.pack(side='left',fill='both',expand=True,pady=10)
            tk.Label(right,text=title,bg=soft,fg='#112c5b',font=('Segoe UI',8,'bold'),wraplength=150,justify='left',anchor='w').pack(anchor='w')
            tk.Label(right,textvariable=self.dashboard_reference_vars[key],bg=soft,fg='#071b56',font=('Segoe UI',13,'bold'),anchor='w').pack(anchor='w',pady=(2,0))
            detail=tk.StringVar(value='');tk.Label(right,textvariable=detail,bg=soft,fg='#415d7a',font=('Segoe UI',8),anchor='w').pack(anchor='w')
            self.dashboard_reference_cards.append(detail)
            for widget in (card,*card.winfo_children(),*right.winfo_children()):widget.bind('<Button-1>',lambda _e,d=destination:self.show_page(d))
        upper=tk.Frame(root,bg='#eaf4fc');upper.pack(fill='x',pady=(0,9))
        for col in range(3):upper.grid_columnconfigure(col,weight=1,uniform='operations')
        self.dashboard_reference_return_hosts={}
        for col,(key,title,color) in enumerate((('returns','▦  Retours aujourd’hui','#0b3a78'),('tomorrow','▦  Retours demain','#0b3a78'))):
            panel=section(upper,title,lambda:self.show_page('contract'),color)
            panel.grid(row=0,column=col,sticky='nsew',padx=(0,4) if col==0 else 4)
            host=tk.Frame(panel,bg='white',height=250);host.pack(fill='both',expand=True,padx=4,pady=3);host.pack_propagate(False)
            self.dashboard_reference_return_hosts[key]=host
        rented_panel=section(upper,'▦  Véhicules loués',lambda:self.show_page('contract'),'#0b3a78')
        rented_panel.grid(row=0,column=2,sticky='nsew',padx=(4,0))
        self.dashboard_reference_rented_host=tk.Frame(rented_panel,bg='white',height=250)
        self.dashboard_reference_rented_host.pack(fill='both',expand=True,padx=4,pady=3);self.dashboard_reference_rented_host.pack_propagate(False)
        bottom=tk.Frame(root,bg='#eaf4fc');bottom.pack(fill='x')
        for col in range(3):bottom.grid_columnconfigure(col,weight=1,uniform='dashboard_bottom')
        self.dashboard_reference_top={}
        month_names=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
        self.dashboard_reference_month=tk.StringVar(value=month_names[datetime.now().month-1]);self.dashboard_reference_year=tk.StringVar(value=str(datetime.now().year))
        self.dashboard_reference_period_label.set(f'{self.dashboard_reference_month.get()} {self.dashboard_reference_year.get()}')
        for col,(title,key,color,target) in enumerate((('▥  Top 5 véhicules (CA du mois)','vehicles','#0b3a78','vehicles'),
                                                        ('🚘  Véhicules disponibles','available','#268367','vehicles'))):
            panel=tk.Frame(bottom,bg='white',highlightbackground='#c8dfef',highlightthickness=1)
            panel.grid(row=0,column=col,sticky='nsew',padx=(0,4) if col==0 else 4)
            bar=tk.Frame(panel,bg='white');bar.pack(fill='x')
            tk.Label(bar,text=title,bg='white',fg=color,font=('Segoe UI',10,'bold'),anchor='w',padx=8,pady=6).pack(side='left',fill='x',expand=True)
            if key=='vehicles':
                chooser=tk.Frame(bar,bg='white');chooser.pack(side='right',padx=4)
                mc=ttk.Combobox(chooser,textvariable=self.dashboard_reference_month,values=month_names,state='readonly',width=10);mc.pack(side='left')
                yc=ttk.Combobox(chooser,textvariable=self.dashboard_reference_year,values=tuple(str(y) for y in range(datetime.now().year+1,datetime.now().year-12,-1)),state='readonly',width=5);yc.pack(side='left')
                for combo in (mc,yc):combo.bind('<<ComboboxSelected>>',lambda _e:self._refresh_dashboard_reference_period())
            self.dashboard_reference_top[key]=tk.Frame(panel,bg='white',height=185)
            self.dashboard_reference_top[key].pack(fill='both',expand=True,padx=4,pady=3);self.dashboard_reference_top[key].pack_propagate(False)
        alerts=section(bottom,'♟  Alertes & échéances',lambda:self.show_page('alerts'),'#0b3a78')
        alerts.grid(row=0,column=2,sticky='nsew',padx=(4,0))
        self.dashboard_reference_alerts=table(alerts,(('label','Description'),('due','Échéance'),('days','Jours')),(225,85,55),height=5)
        self.dashboard_reference_rank_photos=[];self.dashboard_reference_table_photos=[];self.dashboard_reference_available_photos=[]
        self.root.after(30000,self._dashboard_reference_parc_clock)

    def _dashboard_reference_parc_clock(self):
        if not self.dashboard_reference_banner.winfo_exists():return
        deposits=self._dashboard_open_depot_rows()
        total=sum(item['total'] for item in deposits)
        self.dashboard_reference_vars['parc'].set(f'{total:,.2f} MAD'.replace(',',' '))
        self.dashboard_reference_cards[5].set(f'{len(deposits)} véhicule(s) · depuis le dépôt')
        self._dashboard_reference_available_rows(self._currently_rented_vehicle_codes(),deposits)
        self.root.after(30000,self._dashboard_reference_parc_clock)

    def _dashboard_reference_draw_banner(self,event=None):
        banner=self.dashboard_reference_banner
        if not banner.winfo_exists():return
        width=max(1,banner.winfo_width() if event is None else event.width)
        banner.delete('gradient')
        first=(80,153,197);last=(10,44,91)
        for x in range(0,width,6):
            ratio=x/width
            color='#%02x%02x%02x'%tuple(round(a+(b-a)*ratio) for a,b in zip(first,last))
            banner.create_rectangle(x,0,x+6,98,fill=color,outline=color,tags='gradient')
        banner.create_text(19,27,text=self.dashboard_reference_welcome.get(),anchor='w',
                           fill='white',font=('Segoe UI',17,'bold'),tags='gradient')
        banner.create_text(19,52,text='HBZ RENT CAR  ·  Vue d’ensemble de l’activité',anchor='w',
                           fill='#deeffa',font=('Segoe UI',9),tags='gradient')
        banner.tag_lower('gradient')
        banner.coords(self.dashboard_reference_period_window,width-16,12)

    def _dashboard_reference_animate_ticker(self):
        ticker=getattr(self,'dashboard_reference_ticker',None)
        if ticker is None or not ticker.winfo_exists():return
        width=max(1,ticker.winfo_width())
        if self.dashboard_reference_ticker_x is None:self.dashboard_reference_ticker_x=width
        ticker.delete('all')
        items=self.dashboard_reference_ticker_items
        if items:
            item_data=items[self.dashboard_reference_ticker_index%len(items)]
            photo=item_data['photo']
            if photo:ticker.create_image(self.dashboard_reference_ticker_x,16,image=photo,anchor='w')
            item=ticker.create_text(self.dashboard_reference_ticker_x+(58 if photo else 0),16,text=item_data['text'],
                                    anchor='w',fill='white',font=('Segoe UI',9,'bold'))
        else:
            item=ticker.create_text(self.dashboard_reference_ticker_x,16,text='Aucun retour prévu aujourd’hui',
                                    anchor='w',fill='white',font=('Segoe UI',9,'bold'))
        bbox=ticker.bbox(item)
        self.dashboard_reference_ticker_x-=2
        if bbox and bbox[2]<0:
            self.dashboard_reference_ticker_x=width
            if items:self.dashboard_reference_ticker_index=(self.dashboard_reference_ticker_index+1)%len(items)
        ticker.after(55,self._dashboard_reference_animate_ticker)

    def _dashboard_reference_return_rows(self,key,items):
        host=self.dashboard_reference_return_hosts[key]
        for child in host.winfo_children():child.destroy()
        head=tk.Frame(host,bg='#edf3f8',height=24);head.pack(fill='x');head.pack_propagate(False)
        tk.Label(head,text='HEURE   ·   VÉHICULE   ·   CLIENT   ·   IMMATRICULATION',bg='#edf3f8',fg='#35536d',font=('Segoe UI',8,'bold'),anchor='w').pack(fill='x',padx=9)
        if not items:
            tk.Label(host,text='Aucun retour prévu',bg='white',fg='#58708b',font=('Segoe UI',10)).pack(expand=True)
            return
        for number,hour,car,person,status,code,plate,phone in sorted(items,key=lambda item:item[1])[:3]:
            row=tk.Frame(host,bg='white',height=73,highlightbackground='#e4eff8',highlightthickness=1)
            row.pack(fill='x');row.pack_propagate(False)
            info=tk.Frame(row,bg='white');info.pack(fill='x',padx=6)
            tk.Label(info,text=hour[:5],bg='white',fg='#ae5260',font=('Segoe UI',8,'bold'),width=6).pack(side='left')
            photo=self._dashboard_reference_photo(code,(39,25))
            tk.Label(info,image=photo,text='🚘' if photo is None else '',bg='white',width=40).pack(side='left')
            tk.Label(info,text=car[:13],bg='white',fg='#173c61',font=('Segoe UI',8,'bold'),anchor='w').pack(side='left',fill='x',expand=True)
            tk.Label(info,text=person[:16],bg='white',fg='#344f67',font=('Segoe UI',8),anchor='w').pack(side='left',fill='x',expand=True)
            tk.Label(info,text=plate[:12],bg='white',fg='#526d83',font=('Segoe UI',7)).pack(side='right')
            actions=tk.Frame(row,bg='white');actions.pack(fill='x',padx=7,pady=(1,2))
            for label,action,color,ink in (('Confirmer','confirm','#dff1e9','#21654f'),
                                           ('Prolonger','extend','#fff0da','#90601e'),
                                           ('Anticiper','anticipate','#e6edf8','#345b84')):
                tk.Button(actions,text=label,command=lambda a=action,n=number:self._dashboard_contract_action_for(n,a),
                          bg=color,fg=ink,activebackground=color,relief='flat',
                          font=('Segoe UI',7,'bold'),cursor='hand2').pack(side='left',fill='x',expand=True,padx=2)

    def _dashboard_reference_rented_rows(self,active_codes):
        host=self.dashboard_reference_rented_host
        for child in host.winfo_children():child.destroy()
        head=tk.Frame(host,bg='#edf3f8',height=25);head.pack(fill='x');head.pack_propagate(False)
        for label in ('PHOTO','VÉHICULE','IMMATRICULATION','CONTRAT'):
            tk.Label(head,text=label,bg='#edf3f8',fg='#35536d',font=('Segoe UI',8,'bold')).pack(side='left',fill='x',expand=True)
        if not active_codes:
            tk.Label(host,text='Aucun véhicule loué actuellement',bg='white',fg='#58708b',font=('Segoe UI',10)).pack(expand=True)
            return
        for code in sorted(active_codes)[:4]:
            vehicle=self.conn.execute('SELECT modele,immatriculation FROM vehicles WHERE code=?',(code,)).fetchone()
            row=tk.Frame(host,bg='white',height=52,highlightbackground='#e8eef3',highlightthickness=1)
            row.pack(fill='x');row.pack_propagate(False)
            photo=self._dashboard_reference_photo(code,(58,38))
            tk.Label(row,image=photo,text='🚘' if photo is None else '',bg='white',width=60).pack(side='left',padx=5)
            tk.Label(row,text=str(vehicle['modele'] or code)[:19] if vehicle else code,bg='white',fg='#173c61',font=('Segoe UI',9,'bold'),anchor='w').pack(side='left',fill='x',expand=True)
            tk.Label(row,text=str(vehicle['immatriculation'] or '')[:17] if vehicle else '',bg='white',fg='#526d83',font=('Segoe UI',8),width=16).pack(side='left')
            tk.Button(row,text='Voir ›',command=lambda:self.show_page('contract'),bg='#e8f2f9',fg='#14557e',relief='flat',font=('Segoe UI',8,'bold')).pack(side='right',padx=6)

    def _dashboard_reference_available_rows(self,active_codes,deposits=None):
        host=self.dashboard_reference_top['available']
        for child in host.winfo_children():child.destroy()
        self.dashboard_reference_available_photos=[]
        deposits=self._dashboard_open_depot_rows() if deposits is None else deposits
        by_code={item['code']:item for item in deposits}
        head=tk.Frame(host,bg='#edf3f8',height=25);head.pack(fill='x');head.pack_propagate(False)
        tk.Label(head,text='VÉHICULE · STATUT · FRAIS DU PARC',bg='#edf3f8',fg='#35536d',
                 font=('Segoe UI',8,'bold'),anchor='w').pack(fill='x',padx=8)
        body=tk.Frame(host,bg='white');body.pack(fill='both',expand=True)
        canvas=tk.Canvas(body,bg='white',highlightthickness=0)
        scroll=ttk.Scrollbar(body,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        content=tk.Frame(canvas,bg='white');window=canvas.create_window((0,0),window=content,anchor='nw')
        content.bind('<Configure>',lambda _e:canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>',lambda e:canvas.itemconfigure(window,width=e.width))
        vehicles=self.conn.execute('SELECT code,modele,immatriculation,photo FROM vehicles WHERE service=1 ORDER BY modele,code').fetchall()
        free=[v for v in vehicles if str(v['code']).strip() not in active_codes]
        if not free:tk.Label(content,text='Aucun véhicule disponible',bg='white',fg='#58708b').pack(pady=28)
        for vehicle in free:
            code=str(vehicle['code']).strip();deposit=by_code.get(code)
            soft='#fff4df' if deposit else 'white'
            row=tk.Frame(content,bg=soft,highlightbackground='#e2d0ad' if deposit else '#e8eef3',highlightthickness=1)
            row.pack(fill='x',pady=2)
            info=tk.Frame(row,bg=soft);info.pack(fill='x',padx=3,pady=2)
            photo=self._dashboard_reference_photo(code,(43,27),rank='available',stored_path=vehicle['photo'])
            tk.Label(info,image=photo,text='🚘' if photo is None else '',bg=soft,width=45).pack(side='left',padx=3)
            tk.Label(info,text=str(vehicle['modele'] or code),bg=soft,fg='#173c61',font=('Segoe UI',8,'bold'),anchor='w').pack(side='left',fill='x',expand=True)
            tk.Label(info,text='AU PARC' if deposit else 'DISPONIBLE',bg='#ed920f' if deposit else '#e3f3e9',
                     fg='white' if deposit else '#21654f',font=('Segoe UI',8,'bold'),padx=4).pack(side='right',padx=3)
            tk.Label(row,text=str(vehicle['immatriculation'] or ''),bg=soft,fg='#526d83',font=('Segoe UI',8),anchor='w').pack(fill='x',padx=8)
            if deposit:
                text=(f"Depuis le {deposit['entry_at']} · {deposit['daily_rate']:,.2f} MAD/j\n"
                      f"{deposit['days']} jour(s) · Frais cumulés : {deposit['total']:,.2f} MAD").replace(',',' ')
                detail=tk.Label(row,text=text,bg=soft,fg='#925000',font=('Segoe UI',8,'bold'),justify='left',anchor='w')
                detail.pack(fill='x',padx=8,pady=(1,5))
                row.bind('<Configure>',lambda e,label=detail:label.configure(wraplength=max(120,e.width-16)))
                for widget in (row,info,*info.winfo_children(),detail):
                    widget.bind('<Double-1>',lambda _e:self.show_page('parking_deposits'))

    def _dashboard_reference_reservation_rows(self,items):
        host=self.dashboard_reference_reservation_host
        for child in host.winfo_children():child.destroy()
        head=tk.Frame(host,bg='#eaf4fc',height=26);head.pack(fill='x');head.pack_propagate(False)
        for title,width in (('Date',5),('Véhicule',12),('Client',9),('Statut',8),('Actions',12)):
            tk.Label(head,text=title,bg='#eaf4fc',fg='#0b315c',font=('Segoe UI',8,'bold'),width=width).pack(side='left',fill='x',expand=True)
        if not items:
            tk.Label(host,text='Aucune réservation à venir',bg='white',fg='#58708b',font=('Segoe UI',10)).pack(expand=True)
            return
        for payload in items[:4]:
            ref=str(payload.get('_record_id',''));code=str(payload.get('vehicle','')).split('|')[0].strip()
            row=tk.Frame(host,bg='white',height=54,highlightbackground='#e4eff8',highlightthickness=1)
            row.pack(fill='x');row.pack_propagate(False)
            tk.Label(row,text=str(payload.get('start_date',''))[:5],bg='white',fg='#142f69',font=('Segoe UI',8,'bold'),width=6).pack(side='left',fill='y')
            photo=self._dashboard_reference_photo(code,(50,30))
            vehicle=tk.Frame(row,bg='white');vehicle.pack(side='left',fill='both',expand=True)
            tk.Label(vehicle,image=photo,text='🚘' if photo is None else '',bg='white',width=photo.width() if photo else 6).pack(side='left')
            tk.Label(vehicle,text=str(payload.get('vehicle_model') or payload.get('vehicle') or '—')[:13],bg='white',fg='#102b57',font=('Segoe UI',7),wraplength=72).pack(side='left')
            tk.Label(row,text=f"{payload.get('last_name','')} {payload.get('first_name','')}"[:18],bg='white',fg='#102b57',font=('Segoe UI',8),wraplength=90,width=12).pack(side='left',fill='y')
            actions=tk.Frame(row,bg='white');actions.pack(side='right',fill='y',padx=2)
            state=str(payload.get('status','')).upper()
            tk.Label(actions,text=state.title(),bg='#dff5e6' if state in ('CONFIRMÉ','CONFIRME') else '#fff1d9',fg='#216644' if state in ('CONFIRMÉ','CONFIRME') else '#a15d0d',font=('Segoe UI',7),width=9).pack(side='left',padx=2)
            tk.Button(actions,text='Location',command=lambda r=ref:self._dashboard_reference_reservation_to_contract(r),bg='#075da8',fg='white',relief='flat',font=('Segoe UI',8,'bold')).pack(side='left',fill='x',expand=True,padx=2)
            tk.Button(actions,text='Modifier',command=lambda r=ref:self._dashboard_reference_open_reservation(r),bg='#087ff3',fg='white',relief='flat',font=('Segoe UI',8,'bold')).pack(side='left',fill='x',expand=True,padx=2)

    def _dashboard_reference_open_reservation(self,reference):
        row=self.conn.execute("SELECT payload FROM module_records WHERE module='reservations' AND record_id=?",(reference,)).fetchone()
        if not row:return
        try:payload=json.loads(row[0])
        except (TypeError,ValueError):return
        self.show_page('reservations')
        def select():
            values=self.module_vars.get('reservations',{})
            for key,var in values.items():var.set(payload.get(key,''))
            tree=self.module_trees.get('reservations');iid='reservations:'+reference
            if tree is not None and tree.exists(iid):tree.selection_set(iid);tree.focus(iid);tree.see(iid)
        self.root.after(80,select)

    def _dashboard_reference_reservation_to_contract(self,reference):
        row=self.conn.execute("SELECT payload FROM module_records WHERE module='reservations' AND record_id=?",(reference,)).fetchone()
        if not row:return
        try:payload=json.loads(row[0])
        except (TypeError,ValueError):return
        self.new_contract()
        client=str(payload.get('client_code') or payload.get('client') or '').split('|')[0].strip()
        vehicle=str(payload.get('vehicle') or payload.get('vehicle_code') or '').split('|')[0].strip()
        if client:self.vars['client_code'].set(client);self.load_client()
        if vehicle:self.vars['vehicle_code'].set(vehicle);self.load_vehicle(check_conflict=False)
        for source,target in (('start_date','date_start'),('end_date','date_end'),
                              ('start_time','time_start'),('end_time','time_end')):
            if payload.get(source):self.vars[target].set(str(payload[source]))
        self.calculate();self.show_page('contract')

    def _dashboard_reference_cancel_reservation(self,reference):
        from tkinter import messagebox
        row=self.conn.execute("SELECT payload FROM module_records WHERE module='reservations' AND record_id=?",(reference,)).fetchone()
        if not row:return
        try:payload=json.loads(row[0])
        except (TypeError,ValueError):return
        if str(payload.get('status','')).upper() in ('ANNULÉ','ANNULE','TERMINÉ','TERMINE'):return
        if not messagebox.askyesno('Annuler une réservation',f'Annuler la réservation {reference} ?'):return
        payload['status']='ANNULÉ'
        self.conn.execute("UPDATE module_records SET payload=? WHERE module='reservations' AND record_id=?",(json.dumps(payload,ensure_ascii=False),reference))
        self._audit('MODIFICATION','RESERVATIONS',reference,'Annulation depuis le tableau de bord')
        self.conn.commit();self.refresh_business_records('reservations');self.refresh_dashboard();self.schedule_web_sync()

    def _dashboard_reference_photo(self, code, size=(55,32), rank=False, stored_path=''):
        try:
            from PIL import Image,ImageTk
            path=self._vehicle_photo_path(code,stored_path)
            if not path and hasattr(self,'_resolve_vehicle_photo_path'):
                path=self._resolve_vehicle_photo_path(stored_path,code)
            if path:
                with Image.open(path) as source:
                    im=source.convert('RGBA');im.thumbnail(size,Image.Resampling.LANCZOS)
                photo=ImageTk.PhotoImage(im)
                target=(self.dashboard_reference_available_photos if rank=='available' else
                        self.dashboard_reference_rank_photos if rank else self.dashboard_reference_table_photos)
                target.append(photo)
                return photo
        except (OSError,ImportError,ValueError):pass
        return None

    def _dashboard_reference_period_data(self):
        names=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
        year=int(self.dashboard_reference_year.get()) if self.dashboard_reference_year.get().isdigit() else datetime.now().year
        month=names.index(self.dashboard_reference_month.get())+1 if self.dashboard_reference_month.get() in names else datetime.now().month
        start=datetime(year,month,1)
        next_month=datetime(year+1,1,1) if month==12 else datetime(year,month+1,1)
        return year,month,start,next_month

    def _dashboard_reference_shift_month(self,delta):
        year,month,_,_=self._dashboard_reference_period_data()
        shifted=datetime(year,month,1)+timedelta(days=32 if delta>0 else -1)
        if delta>0:shifted=shifted.replace(day=1)
        names=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
        self.dashboard_reference_month.set(names[shifted.month-1]);self.dashboard_reference_year.set(str(shifted.year))
        self._refresh_dashboard_reference_period()

    def _refresh_dashboard_reference_period(self):
        if not hasattr(self,'dashboard_reference_vars'):return
        year,month,start,next_month=self._dashboard_reference_period_data()
        self.dashboard_reference_period_label.set(f'{self.dashboard_reference_month.get()} {year}')
        cache_key=(year,month,self.conn.total_changes)
        if getattr(self,'_dashboard_reference_period_cache',None)==cache_key:return
        for key in ('vehicles',):
            for child in self.dashboard_reference_top[key].winfo_children():child.destroy()
        self.dashboard_reference_rank_photos=[]
        cars=defaultdict(lambda:[0.0,set()]);people=defaultdict(lambda:[0.0,set()])
        for row in self.conn.execute("SELECT numero,vehicle_code,client_code,date_depart,date_retour,duree,montant,return_status FROM contracts"):
            if 'ANNUL' in str(row['return_status'] or '').upper():continue
            share=self._contract_period_share(row['date_depart'],row['date_retour'],row['duree'],start,next_month-timedelta(days=1))
            if share<=0:continue
            amount=float(row['montant'] or 0)*share
            for mapping,code in ((cars,str(row['vehicle_code'] or '')),(people,str(row['client_code'] or ''))):
                mapping[code][0]+=amount;mapping[code][1].add(row['numero'])
        for key,mapping,table in (('vehicles',cars,'vehicles'),):
            host=self.dashboard_reference_top[key]
            headings=('N°','Véhicule','Immatriculation','Nb loc.','CA (MAD)') if key=='vehicles' else ('N°','Client','Téléphone','Nb loc.','CA (MAD)')
            heading=tk.Frame(host,bg='#eaf4fc',height=27);heading.pack(fill='x');heading.pack_propagate(False)
            for label,width in zip(headings,(3,24,16,8,13)):
                tk.Label(heading,text=label,bg='#eaf4fc',fg='#142f69',font=('Segoe UI',7,'bold'),width=width,anchor='w').pack(side='left')
            top=sorted(mapping.items(),key=lambda item:item[1][0],reverse=True)[:5]
            if not top:tk.Label(host,text='Aucune location sur la période',bg='white',fg='#5c7185',font=('Segoe UI',9)).pack(pady=25)
            for index,(code,(amount,numbers)) in enumerate(top,1):
                info=self.conn.execute(f'SELECT * FROM {table} WHERE code=?',(code,)).fetchone()
                name=(f"{info['nom']} {info['prenom']}" if key=='clients' else str(info['modele'] or code)) if info else code
                secondary=str(info['telephone'] or '') if key=='clients' and info else str(info['immatriculation'] or '') if info else ''
                row=tk.Frame(host,bg='white' if index%2 else '#f4faff',height=30);row.pack(fill='x');row.pack_propagate(False)
                tk.Label(row,text=str(index),bg='#f2b329' if index==1 else '#a9b9ce',fg='white',font=('Segoe UI',8,'bold'),width=2).pack(side='left',padx=2)
                if key=='vehicles':
                    photo=self._dashboard_reference_photo(code,(43,27),rank=True)
                    tk.Label(row,image=photo,text='🚘' if photo is None else '',bg=row['bg'],width=45).pack(side='left')
                tk.Label(row,text=name[:21],bg=row['bg'],fg='#102b57',font=('Segoe UI',8,'bold'),anchor='w').pack(side='left',fill='x',expand=True)
                tk.Label(row,text=secondary[:16],bg=row['bg'],fg='#102b57',font=('Segoe UI',8),width=14).pack(side='left')
                tk.Label(row,text=str(len(numbers)),bg=row['bg'],fg='#102b57',font=('Segoe UI',8),width=5).pack(side='left')
                tk.Label(row,text=f'{amount:,.0f}'.replace(',',' '),bg=row['bg'],fg='#102b57',font=('Segoe UI',8,'bold'),width=10,anchor='e').pack(side='right',padx=2)
        self._dashboard_reference_period_cache=(year,month,self.conn.total_changes)

    def _refresh_dashboard_reference(self,service,available,rented,contracts,reservations,alerts,near_returns):
        vars=self.dashboard_reference_vars;now=datetime.now();today=now.date()
        user=str(getattr(self,'current_user','Admin') or 'Admin')
        self.dashboard_reference_welcome.set(f'Bienvenue {user} !')
        today_returns=[];tomorrow_returns=[];self.dashboard_reference_table_photos=[]
        self.dashboard_reference_clock.set(now.strftime('%d/%m/%Y  %H:%M'))
        codes={str(row['vehicle_code']) for row in contracts}
        vehicles={r['code']:r for r in self.conn.execute('SELECT * FROM vehicles') if r['code'] in codes}
        clients={r['code']:r for r in self.conn.execute('SELECT code,nom,prenom,telephone FROM clients')}
        active_codes=self._currently_rented_vehicle_codes(now)
        for row in contracts:
            due=self._parse_french_date(row['date_retour'])
            vehicle=vehicles.get(row['vehicle_code']);client=clients.get(row['client_code'])
            car=str(vehicle['modele'] if vehicle else row['vehicle_code'])
            person=(f"{client['nom']} {client['prenom']}".strip() if client else str(row['client_code'] or '—'))
            if due and due.date() in (today,today+timedelta(days=1)):
                target=today_returns if due.date()==today else tomorrow_returns
                try:hour=datetime.strptime(str(row['heure_retour'] or '23:59')[:5],'%H:%M').time()
                except ValueError:hour=datetime.strptime('23:59','%H:%M').time()
                late=due.date()==today and now.time()>hour
                target.append((str(row['numero']),row['heure_retour'] or '—',car,person,'En retard' if late else 'En cours' if due.date()==today else 'À venir',str(row['vehicle_code']),str(vehicle['immatriculation'] or '') if vehicle else '',str(client['telephone'] or '') if client else ''))
        vars['service'].set(str(service))
        vars['returns'].set(str(len(today_returns)));vars['tomorrow'].set(str(len(tomorrow_returns)))
        self.dashboard_reference_ticker_images=[]
        ticker_items=[]
        for number,hour,car,person,status,code,plate,phone in sorted(today_returns,key=lambda item:item[1]):
            photo=self._dashboard_reference_photo(code,(52,28))
            if photo:self.dashboard_reference_ticker_images.append(photo)
            ticker_items.append({'photo':photo,'text':f"RETOUR AUJOURD’HUI  ·  {hour[:5]}  ·  {car}  ·  {person}  ·  {plate}  ·  contrat {number}"})
        previous=[item['text'] for item in self.dashboard_reference_ticker_items]
        self.dashboard_reference_ticker_items=ticker_items
        if previous!=[item['text'] for item in ticker_items]:
            self.dashboard_reference_ticker_index=0
            self.dashboard_reference_ticker_x=None
        dues=float(self._hbz_credit_due_10d_total() or 0)
        vars['dues'].set(f'{dues:,.2f} MAD'.replace(',',' '))
        vars['available'].set(str(available));vars['rented'].set(str(rented));vars['near_count'].set(str(len(near_returns)))
        self.dashboard_reference_cards[0].set(f'Disponibles : {available}  ·  Loués : {rented}')
        future_res=[]
        for p in reservations:
            when=self._parse_french_date(p.get('start_date',''))
            if when and when.date()>=today:future_res.append(p)
        vars['reservations'].set(str(len(future_res)))
        self.dashboard_reference_cards[1].set(f'En retard : {sum(item[4]=="En retard" for item in today_returns)}')
        self.dashboard_reference_cards[2].set(f'Prévus : {len(tomorrow_returns)}')
        self.dashboard_reference_cards[3].set('En location actuellement')
        self.dashboard_reference_cards[4].set('À moins de 10 jours')
        self._dashboard_reference_return_rows('returns',today_returns)
        self._dashboard_reference_return_rows('tomorrow',tomorrow_returns)
        self._dashboard_reference_rented_rows(active_codes)
        self._refresh_dashboard_reference_period()
        deposits=self._dashboard_open_depot_rows(now)
        total=sum(item['total'] for item in deposits)
        vars['parc'].set(f'{total:,.2f} MAD'.replace(',',' '))
        self.dashboard_reference_cards[5].set(f'{len(deposits)} véhicule(s) · depuis le dépôt')
        self._dashboard_reference_available_rows(active_codes,deposits)
        alert_rows=[]
        for item in alerts[:6]:
            # collect_alerts renvoie (priorité, libellé, détail, ..., date) selon le type.
            title=str(item[1]) if len(item)>1 else 'Alerte'
            description=str(item[3]) if len(item)>3 else ''
            stamp=str(item[4]) if len(item)>4 else ''
            date=self._parse_french_date(stamp)
            days=(date.date()-today).days if date else None
            alert_rows.append((f'{title} — {description}'[:55],stamp,f'{days:+d} j' if days is not None else '—'))
        self.dashboard_reference_alerts.delete(*self.dashboard_reference_alerts.get_children())
        for values in alert_rows[:5]:self.dashboard_reference_alerts.insert('','end',values=values)
        if not alert_rows:self.dashboard_reference_alerts.insert('','end',values=('Aucune alerte',))
