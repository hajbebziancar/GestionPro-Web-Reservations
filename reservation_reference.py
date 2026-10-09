"""Réservations HBZ : présentation calquée sur la maquette validée."""
import calendar
import json
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import ttk, messagebox


def _reservation_round(canvas, x0, y0, x1, y1, radius, fill):
    """Rectangle aux coins arrondis, indépendant des polices d'icônes Windows."""
    r = min(radius, (x1-x0)/2, (y1-y0)/2)
    canvas.create_rectangle(x0+r, y0, x1-r, y1, fill=fill, outline=fill)
    canvas.create_rectangle(x0, y0+r, x1, y1-r, fill=fill, outline=fill)
    for x, y, start in ((x0, y0, 90), (x1-2*r, y0, 0),
                        (x1-2*r, y1-2*r, 270), (x0, y1-2*r, 180)):
        canvas.create_arc(x, y, x+2*r, y+2*r, start=start, extent=90,
                          style='pieslice', fill=fill, outline=fill)


def _reservation_icon(canvas, kind, x, y, scale=1, color='white'):
    """Petits pictogrammes vectoriels : ils restent visibles sans police spéciale."""
    def line(*points, width=2):
        canvas.create_line(*(x+a*scale if i % 2 == 0 else y+a*scale
                             for i, a in enumerate(points)), fill=color,
                           width=width*scale, capstyle='round', joinstyle='round')
    def rect(a,b,c,d, **kwargs):
        canvas.create_rectangle(x+a*scale,y+b*scale,x+c*scale,y+d*scale,
                                outline=color, width=2*scale, **kwargs)
    if kind in ('calendar', 'new'):
        rect(2,4,22,22);line(2,10,22,10);line(7,1,7,7);line(17,1,17,7)
        if kind == 'calendar':
            for px,py in ((7,14),(13,14),(18,14),(7,19),(13,19)):
                canvas.create_oval(x+(px-1)*scale,y+(py-1)*scale,x+(px+1)*scale,y+(py+1)*scale,fill=color,outline=color)
    elif kind == 'check':
        rect(2,3,22,22);line(6,13,10,17,19,8,width=3)
    elif kind == 'clock':
        canvas.create_oval(x+2*scale,y+2*scale,x+22*scale,y+22*scale,outline=color,width=2.5*scale)
        line(12,6,12,13,17,16,width=2.5)
    elif kind in ('cross','cancel'):
        if kind == 'cross':
            canvas.create_oval(x+2*scale,y+2*scale,x+22*scale,y+22*scale,outline=color,width=2.5*scale)
        line(8,8,16,16,width=3);line(16,8,8,16,width=3)
    elif kind == 'car':
        line(2,15,4,8,8,6,17,6,21,10,23,15,23,19,2,19,2,15)
        line(4,12,20,12)
        for px in (7,19):
            canvas.create_oval(x+(px-2)*scale,y+17*scale,x+(px+2)*scale,y+21*scale,fill=color,outline=color)
    elif kind == 'person':
        canvas.create_oval(x+8*scale,y+2*scale,x+16*scale,y+10*scale,fill=color,outline=color)
        line(4,21,5,15,9,12,15,12,19,15,20,21,width=3)
    elif kind == 'save':
        rect(3,2,21,22);rect(7,2,17,9);rect(7,14,17,21)
    elif kind == 'edit':
        line(5,19,7,13,17,3,21,7,11,17,5,19,width=3)
    elif kind == 'trash':
        rect(5,6,19,22);line(3,5,21,5);line(9,2,15,2);line(10,10,10,18);line(14,10,14,18)
    elif kind == 'print':
        rect(5,2,19,9);rect(3,10,21,19);rect(6,15,18,23)
    elif kind == 'arrow':
        line(2,12,21,12);line(14,5,21,12,14,19,width=3)
    elif kind == 'sync':
        line(4,10,7,5,15,4,20,7);line(19,3,20,7,16,8)
        line(20,14,17,19,9,20,4,17);line(5,21,4,17,8,16)
    elif kind == 'money':
        for px,py in ((12,7),(9,12),(12,17)):
            canvas.create_oval(x+(px-5)*scale,y+(py-4)*scale,x+(px+5)*scale,y+(py+4)*scale,outline=color,width=2*scale)


def _reservation_action(parent, text, kind, fill, command, width, pale=False, side='left', background='#edf5fd'):
    """Bouton arrondi avec icône tracée sur canevas et raccourci clavier standard."""
    height = 39
    button = tk.Canvas(parent, width=width, height=height, bg=background,
                       highlightthickness=0, cursor='hand2')
    def paint(active=False):
        button.delete('all')
        background = '#d4eafc' if active and pale else ('#126eb6' if active else fill)
        if pale:
            _reservation_round(button,1,1,width-1,height-1,10,'#bedcf4')
            _reservation_round(button,2,2,width-2,height-2,9,background)
        else:
            _reservation_round(button,1,1,width-1,height-1,9,background)
        ink = '#164b7d' if pale else 'white'
        _reservation_icon(button,kind,11,8,.9,ink)
        button.create_text(38,height/2,text=text,anchor='w',fill=ink,font=('Segoe UI',9,'bold'))
    paint()
    button.bind('<Enter>',lambda _e:paint(True))
    button.bind('<Leave>',lambda _e:paint(False))
    button.bind('<Button-1>',lambda _e:command())
    button.pack(side=side,padx=3)
    return button


class ReservationReferenceMixin:
    def _build_reservations_reference_page(self, name, title, fields):
        from reservation_mockup import build
        return build(self,name,title,fields)
        if not hasattr(self, 'module_vars'):
            self.module_vars, self.module_trees, self.module_fields = {}, {}, {}
        page = self._new_page(name)
        page.configure(bg='#edf5fd')
        self.module_fields[name] = fields
        v = self.module_vars[name] = {key: tk.StringVar() for _label, key in fields}
        self.reservation_search_var = tk.StringVar()
        self.reservation_reference_months=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
        self.reservation_reference_month = tk.StringVar(value=self.reservation_reference_months[datetime.now().month-1])
        self.reservation_reference_year = tk.StringVar(value=str(datetime.now().year))
        self.reservation_reference_status = tk.StringVar(value='Tous les statuts')
        self.reservation_reference_kind = tk.StringVar(value='Avec acompte')
        self.reservation_reference_summary = {k: tk.StringVar(value='0') for k in ('total', 'confirmed', 'pending', 'cancelled', 'available')}
        self.reservation_reference_calendar_month = datetime.now().replace(day=1)
        self.reservation_reference_day_phase = 'start'
        self.reservation_reference_count = tk.StringVar(value='Total : 0 réservation(s)')
        self.reservation_reference_page = 1
        self.reservation_reference_page_label = tk.StringVar(value='1 / 1')

        # Le canevas garde la page utilisable si la fenêtre Windows est redimensionnée.
        canvas = tk.Canvas(page, bg='#edf5fd', highlightthickness=0)
        scroll = ttk.Scrollbar(page, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y'); canvas.pack(side='left', fill='both', expand=True)
        body = tk.Frame(canvas, bg='#edf5fd')
        win = canvas.create_window((0, 0), window=body, anchor='nw')
        body.bind('<Configure>', lambda _e: canvas.configure(scrollregion=canvas.bbox('all')))
        canvas.bind('<Configure>', lambda e: canvas.itemconfigure(win, width=e.width))

        heading = tk.Frame(body, bg='#eef6ff')
        heading.pack(fill='x', padx=12, pady=(8, 10))
        tk.Label(heading, text='Réservation de véhicule', bg='#eef6ff', fg='#142d51', font=('Segoe UI', 18, 'bold')).pack(side='left', padx=10, pady=5)
        tk.Label(heading, text=datetime.now().strftime('%d/%m/%Y  %H:%M'), bg='#eef6ff', fg='#546c86', font=('Segoe UI', 9)).pack(side='right', padx=12)
        self.reservation_web_sync_button=_reservation_action(
            heading,'Synchroniser site','sync','#167fcb',
            self.sync_public_website,170,side='right',background='#eef6ff')

        actions = tk.Frame(body, bg='#edf5fd');actions.pack(fill='x', padx=13, pady=(0, 10))
        for label, icon, color, callback, width in (
            ('Nouveau','new','#2db35f',self._reservation_reference_new,112),
            ('Enregistrer','save','#168ce7',lambda:self.save_business_record(name),133),
            ('Modifier','edit','#f0a02a',lambda:self.update_business_record(name),111),
            ('Supprimer','trash','#ea5261',lambda:self.delete_business_record(name),119),
            ('Annuler','cancel','#586d85',self._reservation_reference_cancel,105),
            ('Imprimer reçu','print','#e2f1ff',self.preview_reservation,148),
            ('Vers location','arrow','#e2f1ff',self.reservation_to_contract,142)):
            _reservation_action(actions,label,icon,color,callback,width,pale=color=='#e2f1ff')
        tk.Label(body,textvariable=self.web_sync_var,bg='#edf5fd',fg='#476b8c',
                 font=('Segoe UI',8),anchor='e').pack(fill='x',padx=20,pady=(0,4))

        stats = tk.Frame(body, bg='#edf5fd');stats.pack(fill='x', padx=13, pady=(0, 9))
        cards = (('total', 'Réservations totales', 'calendar', '#158ce5', '#dcefff'),
                 ('confirmed', 'Confirmées', 'check', '#28a85a', '#e1f7e9'),
                 ('pending', 'En attente', 'clock', '#ef9b1a', '#fff0da'),
                 ('cancelled', 'Annulées', 'cross', '#e64e59', '#fde9ed'),
                 ('available', 'Véhicules disponibles', 'car', '#207cbd', '#e7f4ff'))
        for i, (key, label, icon, color, soft) in enumerate(cards):
            stats.grid_columnconfigure(i, weight=1, uniform='reservation_stats')
            card = tk.Frame(stats, bg=soft, highlightbackground='#d6e7f5', highlightthickness=1)
            card.grid(row=0, column=i, sticky='nsew', padx=3)
            tile=tk.Canvas(card,width=47,height=47,bg=soft,highlightthickness=0)
            tile.pack(side='left',padx=8,pady=7)
            _reservation_round(tile,0,0,47,47,9,color)
            _reservation_icon(tile,icon,11,11,1,'white')
            labels = tk.Frame(card, bg=soft); labels.pack(side='left', fill='x', expand=True)
            tk.Label(labels, textvariable=self.reservation_reference_summary[key], bg=soft, fg=color, font=('Segoe UI', 15, 'bold'), anchor='w').pack(fill='x')
            tk.Label(labels, text=label, bg=soft, fg='#38506a', font=('Segoe UI', 8, 'bold'), anchor='w').pack(fill='x')

        upper = tk.Frame(body, bg='#edf5fd');upper.pack(fill='x', padx=13)
        upper.grid_columnconfigure(0, weight=7);upper.grid_columnconfigure(1, weight=3)
        form = tk.Frame(upper, bg='white', highlightbackground='#d7e5f3', highlightthickness=1)
        form.grid(row=0, column=0, sticky='nsew', padx=(0, 5))
        availability = tk.Frame(upper, bg='white', highlightbackground='#d7e5f3', highlightthickness=1)
        availability.grid(row=0, column=1, sticky='nsew', padx=(5, 0))
        self._reservation_reference_band(form, '▣  Informations de la réservation')
        fields_row = tk.Frame(form, bg='white');fields_row.pack(fill='both', expand=True, padx=9, pady=(8, 7))
        fields_row.grid_columnconfigure(0, weight=6);fields_row.grid_columnconfigure(1, weight=5)
        left = tk.Frame(fields_row, bg='white');left.grid(row=0, column=0, sticky='nsew', padx=(0, 9))
        right = tk.Frame(fields_row, bg='white');right.grid(row=0, column=1, sticky='nsew', padx=(9, 0))

        def line(parent, caption, icon, row, key, options=None, readonly=False):
            parent.grid_columnconfigure(1, weight=1)
            tile=tk.Canvas(parent,width=33,height=34,bg='white',highlightthickness=0)
            tile.grid(row=row,column=0,padx=(0,6),pady=5)
            _reservation_round(tile,0,0,33,34,6,'#168be0')
            _reservation_icon(tile,icon,6,6,.85,'white')
            area = tk.Frame(parent, bg='white');area.grid(row=row, column=1, sticky='ew', pady=3)
            tk.Label(area, text=caption, bg='white', fg='#293e58', font=('Segoe UI', 8, 'bold'), anchor='w').pack(fill='x')
            widget = ttk.Combobox(area, textvariable=v[key], values=options, style='GP.TCombobox', state='readonly' if readonly else 'normal') if options is not None else ttk.Entry(area, textvariable=v[key], style='GP.TEntry', state='readonly' if readonly else 'normal')
            widget.pack(fill='x', pady=(2, 0));return widget

        client = line(left, 'Client *', 'person', 0, 'client', self._reservation_client_choices())
        client.bind('<<ComboboxSelected>>', self._load_reservation_client)
        client.bind('<Return>', self._load_reservation_client)
        client.bind('<FocusOut>', self._load_reservation_client)
        client_extra=tk.Frame(left,bg='white');client_extra.grid(row=0,column=2,sticky='ew',padx=5)
        tk.Label(client_extra,text='Téléphone',bg='white',fg='#496078',font=('Segoe UI',7)).pack(anchor='w')
        tk.Label(client_extra,textvariable=v['phone'],bg='white',fg='#294a6b',font=('Segoe UI',8,'bold')).pack(side='left')
        tk.Button(client_extra,text='＋',command=lambda:self.show_page('clients'),bg='#31ae65',fg='white',font=('Segoe UI',9,'bold'),relief='flat').pack(side='right',padx=4)
        vehicle = line(left, 'Véhicule *', 'car', 1, 'vehicle', self._reservation_vehicle_choices())
        vehicle.bind('<<ComboboxSelected>>', self._load_reservation_vehicle)
        vehicle.bind('<Return>', self._load_reservation_vehicle)
        photo = tk.Frame(left, bg='#edf6ff', height=104);photo.grid(row=1, column=2, padx=5, sticky='ew');photo.grid_propagate(False)
        self.reservation_vehicle_photo = tk.Label(photo, bg='#edf6ff', fg='#536d89', text='🚘\nPhoto véhicule')
        self.reservation_vehicle_photo.pack(fill='both', expand=True)
        v['vehicle'].trace_add('write', lambda *_: (self._refresh_reservation_vehicle_photo(), self._reservation_reference_calendar()))
        for idx, (caption, icon, key, hour_key) in enumerate((('Date de départ *', 'calendar', 'start_date', 'start_time'), ('Date de retour *', 'calendar', 'end_date', 'end_time')), 2):
            date = line(left, caption, icon, idx, key)
            self._attach_date_picker(date, v[key])
            ttk.Combobox(left, textvariable=v[hour_key], values=[f'{h:02d}:{m:02d}' for h in range(24) for m in (0, 30)], width=8, style='GP.TCombobox').grid(row=idx, column=2, sticky='ew', padx=5)
        line(left, 'Durée (jours)', 'calendar', 4, 'duration', readonly=True)

        client_panel=tk.Frame(left,bg='#edf6ff',highlightbackground='#c9e1f5',highlightthickness=1)
        client_panel.grid(row=5,column=0,columnspan=3,sticky='ew',padx=(0,5),pady=(8,2))
        tk.Label(client_panel,text='INFORMATIONS DU CLIENT',bg='#edf6ff',fg='#154f82',
                 font=('Segoe UI',9,'bold')).pack(anchor='w',padx=11,pady=(7,3))
        self.reservation_client_identity=tk.StringVar(value='Sélectionnez un client')
        self.reservation_client_details=tk.StringVar(value='CIN · Téléphone · Ville · Adresse')
        tk.Label(client_panel,textvariable=self.reservation_client_identity,bg='#edf6ff',fg='#173b5d',
                 font=('Segoe UI',10,'bold'),anchor='w').pack(fill='x',padx=11)
        tk.Label(client_panel,textvariable=self.reservation_client_details,bg='#edf6ff',fg='#506e88',
                 font=('Segoe UI',8),anchor='w',wraplength=510,justify='left').pack(fill='x',padx=11,pady=(2,9))
        v['client'].trace_add('write',lambda *_:self._reservation_reference_client_details())

        kind = tk.Frame(right, bg='white');kind.pack(fill='x', pady=(5, 3))
        tk.Label(kind, text='Type de réservation', bg='white', fg='#243d5d', font=('Segoe UI', 9, 'bold')).pack(anchor='w')
        for caption in ('Avec acompte', 'Sans acompte'):
            tk.Radiobutton(kind, text=caption, value=caption, variable=self.reservation_reference_kind, command=self._reservation_reference_kind_changed, bg='white', fg='#354c66', selectcolor='white', font=('Segoe UI', 8)).pack(anchor='w')
        self.reservation_reference_payment = tk.Frame(right, bg='white');self.reservation_reference_payment.pack(fill='x')
        for caption, key, editable in (('Montant estimé (TTC)', 'total', False), ('Acompte', 'deposit', True), ('Reste à payer', 'balance', False)):
            row = tk.Frame(self.reservation_reference_payment, bg='white');row.pack(fill='x', pady=4)
            tk.Label(row, text=caption, bg='white', fg='#27405b', font=('Segoe UI', 8, 'bold'), width=19, anchor='w').pack(side='left')
            ttk.Entry(row, textvariable=v[key], state='normal' if editable else 'readonly', width=12, justify='right', style='GP.TEntry').pack(side='right')
            tk.Label(row, text='MAD', bg='white', fg='#60768e', font=('Segoe UI', 8)).pack(side='right', padx=5)
        price = tk.Frame(right, bg='white');price.pack(fill='x', pady=4)
        tk.Label(price, text='Prix / jour', bg='white', fg='#27405b', font=('Segoe UI', 8, 'bold')).pack(side='left')
        ttk.Entry(price, textvariable=v['daily_price'], width=12, style='GP.TEntry', justify='right').pack(side='right')
        status = tk.Frame(right, bg='white');status.pack(fill='x', pady=4)
        tk.Label(status, text='⚑  Statut', bg='white', fg='#27405b', font=('Segoe UI', 8, 'bold')).pack(side='left')
        ttk.Combobox(status, textvariable=v['status'], values=('EN ATTENTE', 'CONFIRMÉ', 'PAYÉ', 'TERMINÉ', 'ANNULÉ'), state='readonly', width=16, style='GP.TCombobox').pack(side='right')
        tk.Label(right, text='▤  Notes', bg='white', fg='#27405b', font=('Segoe UI', 8, 'bold')).pack(anchor='w', pady=(5, 2))
        ttk.Entry(right, textvariable=v['notes'], style='GP.TEntry').pack(fill='x')
        tk.Label(right, text='Référence', bg='white', fg='#60768e', font=('Segoe UI', 8)).pack(anchor='w', pady=(8, 0))
        ttk.Entry(right, textvariable=v['reference'], style='GP.TEntry').pack(fill='x')

        self._reservation_reference_band(availability, '♧  Vérifier la disponibilité')
        controls = tk.Frame(availability, bg='white');controls.pack(fill='x', padx=8, pady=6)
        tk.Button(controls, text='‹', command=lambda: self._reservation_reference_shift(-1), bg='white', fg='#163658', relief='flat', font=('Segoe UI', 18)).pack(side='left')
        self.reservation_reference_calendar_title = tk.StringVar()
        tk.Label(controls, textvariable=self.reservation_reference_calendar_title, bg='white', fg='#142d51', font=('Segoe UI', 10, 'bold')).pack(side='left', fill='x', expand=True)
        tk.Button(controls, text='›', command=lambda: self._reservation_reference_shift(1), bg='white', fg='#163658', relief='flat', font=('Segoe UI', 18)).pack(side='right')
        self.reservation_reference_calendar_body = tk.Frame(availability, bg='white');self.reservation_reference_calendar_body.pack(fill='x', padx=8)
        legend = tk.Frame(availability, bg='white');legend.pack(fill='x', padx=8, pady=9)
        for caption, color in (('Disponible', '#c6ebd4'), ('Réservé', '#f6c4ce'), ('En location', '#b3dcfb'), ('Indisponible', '#ef7c86')):
            tk.Label(legend, text='■ '+caption, bg='white', fg=color, font=('Segoe UI', 7, 'bold')).pack(side='left', padx=2)
        self._reservation_reference_calendar()

        history = tk.Frame(body, bg='white', highlightbackground='#d7e5f3', highlightthickness=1)
        history.pack(fill='both', expand=True, padx=13, pady=(0, 12))
        filters = tk.Frame(history, bg='#09619e');filters.pack(fill='x')
        tk.Label(filters, text='▣  Liste des réservations', bg='#09619e', fg='white', font=('Segoe UI', 10, 'bold')).pack(side='left', padx=9, pady=8)
        for var, options, width in ((self.reservation_reference_status, ('Tous les statuts', 'EN ATTENTE', 'CONFIRMÉ', 'PAYÉ', 'TERMINÉ', 'ANNULÉ'), 17), (self.reservation_reference_year, tuple(str(y) for y in range(datetime.now().year+2, datetime.now().year-8, -1)), 7), (self.reservation_reference_month, self.reservation_reference_months, 11)):
            comb = ttk.Combobox(filters, textvariable=var, values=options, state='readonly', width=width)
            comb.pack(side='right', padx=3);comb.bind('<<ComboboxSelected>>', lambda _e:self._reservation_reference_reset_page())
        query = ttk.Entry(filters, textvariable=self.reservation_search_var, width=32, style='GP.TEntry')
        query.pack(side='right', padx=5);query.bind('<KeyRelease>', lambda _e:self._reservation_reference_reset_page())
        tk.Label(filters, text='⌕', bg='#09619e', fg='white', font=('Segoe UI', 12)).pack(side='right')
        keys = tuple(key for _label, key in fields)
        columns = keys + ('booking_date', 'client_display', 'departure_display', 'return_display', 'actions')
        shown = ('reference', 'booking_date', 'client_display', 'phone', 'vehicle_model', 'plate', 'departure_display', 'return_display', 'duration', 'total', 'deposit', 'status', 'actions')
        table_box = tk.Frame(history, bg='white');table_box.pack(fill='both', expand=True, padx=5, pady=4)
        tree = ttk.Treeview(table_box, columns=columns, displaycolumns=shown, show='headings', height=9)
        heads = {'reference':'Référence','booking_date':'Date résa','client_display':'Client','phone':'Tél','vehicle_model':'Véhicule','plate':'Immatriculation','departure_display':'Départ','return_display':'Retour','duration':'Durée','total':'Montant','deposit':'Acompte','status':'Statut','actions':'Actions'}
        sizes = {'reference':112,'booking_date':95,'client_display':160,'phone':105,'vehicle_model':145,'plate':115,'departure_display':110,'return_display':110,'duration':62,'total':95,'deposit':90,'status':105,'actions':110}
        for key in columns:
            tree.heading(key, text=heads.get(key, key));tree.column(key, width=sizes.get(key, 80), anchor='center', stretch=key in ('client_display', 'vehicle_model'))
        tree.tag_configure('pending', background='#fff4df');tree.tag_configure('confirmed', background='#e9f8ef');tree.tag_configure('cancelled', background='#ffeded')
        ybar = ttk.Scrollbar(table_box, orient='vertical', command=tree.yview)
        xbar = ttk.Scrollbar(history, orient='horizontal', command=tree.xview)
        tree.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        tree.pack(side='left', fill='both', expand=True);ybar.pack(side='right', fill='y');xbar.pack(fill='x', padx=6)
        tree.bind('<<TreeviewSelect>>', lambda _e:self._reservation_reference_select())
        tree.bind('<ButtonRelease-1>', self._reservation_reference_table_action, add='+')
        tree.bind('<Double-1>', lambda _e:self.preview_reservation())
        self.module_trees[name] = self.reservation_reference_table = tree
        foot = tk.Frame(history, bg='#f0f7fd');foot.pack(fill='x')
        tk.Label(foot, textvariable=self.reservation_reference_count, bg='#f0f7fd', fg='#304b69', font=('Segoe UI', 8, 'bold')).pack(side='left', padx=12, pady=7)
        for caption, offset in (('»',100000),('›',1),('‹',-1),('«',-100000)):
            tk.Button(foot,text=caption,command=lambda step=offset:self._reservation_reference_go(step),bg='#e7f2fd',fg='#145693',relief='flat',font=('Segoe UI',9,'bold'),width=3).pack(side='right',padx=2,pady=4)
        tk.Label(foot,textvariable=self.reservation_reference_page_label,bg='#147fce',fg='white',font=('Segoe UI',8,'bold'),padx=10,pady=5).pack(side='right',padx=3)
        self._reservation_reference_new()
        for key in ('start_date','start_time','end_date','end_time','daily_price','deposit'):
            v[key].trace_add('write', lambda *_:self._calculate_reservation())
        self._refresh_reservation_reference()
        return page

    @staticmethod
    def _reservation_reference_band(parent, text):
        tk.Label(parent, text=text, bg='#08609f', fg='white', anchor='w', font=('Segoe UI', 10, 'bold'), padx=9, pady=8).pack(fill='x')

    def _reservation_reference_client_details(self):
        if not hasattr(self,'reservation_client_identity'):
            return
        code=self.module_vars['reservations']['client'].get().split('|',1)[0].strip()
        row=self.conn.execute('SELECT code,cin,nom,prenom,telephone,ville,adresse FROM clients WHERE code=? OR cin=? LIMIT 1',
                              (code,code)).fetchone() if code else None
        if not row:
            self.reservation_client_identity.set('Sélectionnez un client')
            self.reservation_client_details.set('CIN · Téléphone · Ville · Adresse')
            return
        self.reservation_client_identity.set(f"{row['prenom'] or ''} {row['nom'] or ''}  ·  Code {row['code']}".strip())
        details=[f"CIN : {row['cin'] or '—'}",f"Tél : {row['telephone'] or '—'}",
                 f"Ville : {row['ville'] or '—'}",f"Adresse : {row['adresse'] or '—'}"]
        self.reservation_client_details.set('   ·   '.join(details))

    def _reservation_reference_new(self):
        if hasattr(self,'reservation_mockup'):return self.reservation_mockup.new()
        self.new_business_record('reservations')
        self.reservation_reference_kind.set('Avec acompte')
        if hasattr(self,'reservation_reference_table'):
            self.reservation_reference_table.selection_remove(self.reservation_reference_table.selection())

    def _reservation_reference_kind_changed(self):
        if self.reservation_reference_kind.get() == 'Sans acompte':
            self.module_vars['reservations']['deposit'].set('0.00')

    def _reservation_reference_cancel(self):
        from reservation_actions import run
        run(self,'cancel')

    def _reservation_reference_reset_page(self):
        self.reservation_reference_page=1
        self._refresh_reservation_reference()

    def _reservation_reference_go(self, step):
        self.reservation_reference_page=max(1,min(self.reservation_reference_pages,self.reservation_reference_page+step))
        self._refresh_reservation_reference()

    def _reservation_reference_select(self):
        self.select_business_record('reservations')
        value=self.module_vars['reservations']['deposit'].get()
        self.reservation_reference_kind.set('Avec acompte' if self._number(value)>0 else 'Sans acompte')

    def _reservation_reference_shift(self, amount):
        dt=self.reservation_reference_calendar_month
        month=dt.month+amount
        self.reservation_reference_calendar_month=dt.replace(year=dt.year+(month-1)//12, month=(month-1)%12+1)
        self._reservation_reference_calendar()

    def _reservation_reference_calendar(self):
        if not hasattr(self,'reservation_reference_calendar_body'):return
        host=self.reservation_reference_calendar_body
        for child in host.winfo_children():child.destroy()
        date=self.reservation_reference_calendar_month
        months=('','Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
        self.reservation_reference_calendar_title.set(f'{months[date.month]} {date.year}')
        for col,label in enumerate(('Lun','Mar','Mer','Jeu','Ven','Sam','Dim')):
            host.grid_columnconfigure(col,weight=1)
            tk.Label(host,text=label,bg='#eaf3fd',fg='#385371',font=('Segoe UI',8,'bold')).grid(row=0,column=col,sticky='ew',padx=1,pady=1)
        v=self.module_vars.get('reservations',{})
        code=v['vehicle'].get().split('|')[0].strip() if v else ''
        reserved=set();rented=set()
        if code:
            for rec in self.conn.execute("SELECT payload FROM module_records WHERE module='reservations'"):
                try:p=json.loads(rec[0])
                except (ValueError,TypeError):continue
                if str(p.get('vehicle','')).split('|')[0].strip()!=code or str(p.get('status','')).upper() in ('ANNULÉ','ANNULE','TERMINÉ','TERMINE','CONVERTIE EN LOCATION'):continue
                self._reservation_reference_mark_dates(reserved,p.get('start_date'),p.get('end_date'),date)
            for rec in self.conn.execute('SELECT date_depart,date_retour FROM contracts WHERE vehicle_code=?',(code,)):
                self._reservation_reference_mark_dates(rented,rec[0],rec[1],date)
        begin=v['start_date'].get() if v else '';end=v['end_date'].get() if v else ''
        for row,week in enumerate(calendar.monthcalendar(date.year,date.month),1):
            for col,day in enumerate(week):
                if not day:continue
                iso=f'{date.year:04d}-{date.month:02d}-{day:02d}'
                pretty=f'{day:02d}/{date.month:02d}/{date.year}'
                color=('#b9defb' if iso in rented else '#f8cbd2' if iso in reserved else '#e4f7eb' if code else '#f2f6fa')
                if pretty==begin or pretty==end:color='#d5e9ff'
                tk.Button(host,text=str(day),bg=color,fg='#1c3957',relief='flat',font=('Segoe UI',8,'bold'),pady=6,command=lambda d=pretty:self._reservation_reference_pick_day(d)).grid(row=row,column=col,sticky='ew',padx=1,pady=1)

    def _reservation_reference_mark_dates(self, output, first, last, month):
        start=self._parse_french_date(first or '');end=self._parse_french_date(last or '')
        if not start or not end or end<start:return
        clip_start=max(start.date(), month.date());clip_end=min(end.date(), (month+timedelta(days=32)).replace(day=1).date()-timedelta(days=1))
        current=clip_start
        while current<=clip_end:
            output.add(current.isoformat());current+=timedelta(days=1)

    def _reservation_reference_pick_day(self, date):
        field='start_date' if self.reservation_reference_day_phase=='start' else 'end_date'
        self.module_vars['reservations'][field].set(date)
        self.reservation_reference_day_phase='end' if field=='start_date' else 'start'
        self._reservation_reference_calendar()

    def _reservation_reference_table_action(self, event):
        """Les icônes de la dernière colonne ouvrent, sélectionnent ou suppriment."""
        tree=self.reservation_reference_table
        if tree.identify_region(event.x,event.y)!='cell':return
        if tree.identify_column(event.x)!=f'#{len(tree["displaycolumns"])}':return
        iid=tree.identify_row(event.y)
        if not iid:return
        tree.selection_set(iid);self._reservation_reference_select()
        box=tree.bbox(iid, tree.identify_column(event.x))
        if not box:return
        third=(event.x-box[0])*3//max(1,box[2])
        if third==0:self.preview_reservation()
        elif third>=2:self.delete_business_record('reservations')

    def _refresh_reservation_reference(self, query=''):
        if hasattr(self,'reservation_mockup'):return self.reservation_mockup.refresh(query)
        tree=getattr(self,'reservation_reference_table',None)
        if tree is None:return
        tree.delete(*tree.get_children())
        keys=[key for _label,key in self.module_fields['reservations']]
        q=(query or self.reservation_search_var.get()).strip().casefold()
        selected_month=self.reservation_reference_month.get()
        month=f'{self.reservation_reference_months.index(selected_month)+1:02d}' if selected_month in self.reservation_reference_months else datetime.now().strftime('%m')
        year=self.reservation_reference_year.get()
        wanted=self.reservation_reference_status.get()
        total=confirmed=pending=cancelled=0
        matched=[]
        for rec in self.conn.execute("SELECT record_id,payload,created_at FROM module_records WHERE module='reservations' ORDER BY created_at DESC"):
            try:p=json.loads(rec['payload'])
            except (ValueError,TypeError):continue
            date=self._parse_french_date(p.get('start_date') or '')
            if not date or date.strftime('%m')!=month or str(date.year)!=year:continue
            total+=1
            state=str(p.get('status','')).upper()
            if state in ('ANNULÉ','ANNULE'):cancelled+=1
            elif state in ('CONFIRMÉ','CONFIRME','PAYÉ','PAYE'):confirmed+=1
            elif state=='EN ATTENTE':pending+=1
            if wanted!='Tous les statuts' and state!=wanted:continue
            search=' '.join(str(p.get(k,'')) for k in keys).casefold()
            if q and q not in search:continue
            try:registered=datetime.fromisoformat(str(rec['created_at'])).strftime('%d/%m/%Y')
            except ValueError:registered='—'
            vals=[p.get(k,'') for k in keys]+[registered,
                 f"{p.get('last_name','')} {p.get('first_name','')}".strip(),
                 f"{p.get('start_date','')} {p.get('start_time','')}",
                 f"{p.get('end_date','')} {p.get('end_time','')}", '◉   ✎   ▣']
            badge='cancelled' if state in ('ANNULÉ','ANNULE') else 'pending' if state=='EN ATTENTE' else 'confirmed'
            matched.append((rec['record_id'],vals,badge))
        self.reservation_reference_pages=max(1,(len(matched)+11)//12)
        self.reservation_reference_page=min(self.reservation_reference_page,self.reservation_reference_pages)
        self.reservation_reference_page_label.set(f'{self.reservation_reference_page} / {self.reservation_reference_pages}')
        start=(self.reservation_reference_page-1)*12
        for ref,vals,badge in matched[start:start+12]:
            tree.insert('','end',iid=f'reservations:{ref}',values=vals,tags=(badge,))
        for key,value in (('total',total),('confirmed',confirmed),('pending',pending),('cancelled',cancelled)):
            self.reservation_reference_summary[key].set(str(value))
        total_vehicles=self.conn.execute('SELECT COUNT(*) FROM vehicles WHERE service=1').fetchone()[0]
        active=self._currently_rented_vehicle_codes()
        self.reservation_reference_summary['available'].set(f"{max(0,total_vehicles-len(active))}/{total_vehicles}")
        self.reservation_reference_count.set(f'Total : {len(matched)} réservation(s)')
        self._reservation_reference_calendar()
