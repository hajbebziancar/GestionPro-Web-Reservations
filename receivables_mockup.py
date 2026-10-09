"""Two-tab receivables workspace, with the supplied three-column reference layout."""
import tkinter as tk
from tkinter import ttk,messagebox
from datetime import datetime
import json,html,webbrowser
from pathlib import Path
BG='#f3f8fd';INK='#12385c';BLUE='#0877ee';GREEN='#12944e';LINE='#d8e5ef'

def build(app):
    host=app._new_page('receivables');tabs=tk.Frame(host,bg=BG);tabs.pack(fill='x',padx=8,pady=4)
    book=app.receivable_workspace=ttk.Notebook(host);style=ttk.Style(host);style.layout('ReceivableWorkspace.TNotebook.Tab',[]);book.configure(style='ReceivableWorkspace.TNotebook');book.pack(fill='both',expand=True)
    page=tk.Frame(book,bg=BG);statement=app.receivable_statement_page=tk.Frame(book,bg=BG)
    book.add(page,text='Gestion des créances');book.add(statement,text='Situation client')
    for label,cmd,color in [('Gestion des créances',lambda:book.select(0),BLUE),('Situation client',app.open_client_statement,'#7953b8')]:
        tk.Button(tabs,text=label,command=cmd,bg=color,fg='white',relief='flat',font=('Segoe UI',9,'bold'),padx=15,pady=5).pack(side='left',padx=3)
    tk.Label(statement,text='Sélectionnez une créance pour ouvrir la situation du client.',bg=BG,fg=INK).pack(pady=30)
    app.receivables_mockup=View(app,page)
    return host

class View:
    def __init__(self,app,page):
        self.app,self.page=app,page;self.pageno=0;self.chosen=set();self.rows=[];self.category='Toutes';self.last_payment=None;self.ready=False
        for col,weight in enumerate((43,38,27)):page.grid_columnconfigure(col,weight=weight,uniform='main')
        page.grid_rowconfigure(2,weight=3);page.grid_rowconfigure(3,weight=2)
        app.receivable_search=tk.StringVar();app.receivable_status=tk.StringVar(value='TOUS');app.receivable_month=tk.StringVar(value='Tous les mois');app.receivable_year=tk.StringVar(value='Toutes les années');app.receivable_date_from=tk.StringVar();app.receivable_date_to=tk.StringVar()
        self.vehicle=tk.StringVar(value='Tous les véhicules');self.limit=tk.StringVar(value='10');self.caption=tk.StringVar()
        head=tk.Frame(page,bg='#073563');head.grid(row=0,column=0,columnspan=3,sticky='ew',padx=5,pady=3)
        tk.Label(head,text='▤  Gestion des Créances',bg='#073563',fg='white',font=('Segoe UI',16,'bold')).pack(side='left',padx=8,pady=8)
        for text,cmd in [('＋ Nouvelle Créance',app.open_receivable_payment),('▤ Exporter',app.export_receivables),('▣ Imprimer',app.open_client_statement)]:self.button(head,text,cmd,BLUE).pack(side='right',padx=4,pady=5)
        self.period=tk.StringVar(value='Toutes les périodes')
        months=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
        years=range(datetime.now().year-2,datetime.now().year+2)
        ttk.Combobox(head,textvariable=self.period,values=('Toutes les périodes',)+tuple(f'{m} {y}' for y in years for m in months),state='readonly',width=17).pack(side='right',padx=4,pady=5)
        def period_changed(*_):
            parts=self.period.get().rsplit(' ',1)
            app.receivable_month.set(parts[0] if len(parts)==2 and parts[1].isdigit() else 'Tous les mois')
            app.receivable_year.set(parts[1] if len(parts)==2 and parts[1].isdigit() else 'Toutes les années')
            self.pageno=0;self.refresh()
        self.period.trace_add('write',period_changed)
        ttk.Entry(head,textvariable=app.receivable_search,width=22).pack(side='right',padx=4,pady=5)
        metrics=tk.Frame(page,bg=BG);metrics.grid(row=1,column=0,columnspan=3,sticky='ew',padx=5,pady=4)
        app.receivable_metric_vars={k:tk.StringVar(value='0,00 DH') for k in ('total','paid','balance','overdue','upcoming')};self.counts={}
        palette=[('#e7f1ff','#246ab0'),('#e9f7ed','#25814d'),('#fff2dd','#a96a1b'),('#fde9ed','#b34459'),('#f0eafb','#7953b8')]
        for i,(label,key) in enumerate([('Total Créances','total'),('Créances réglées','paid'),('Créances en cours','balance'),('Créances en retard','overdue'),('Échéances à venir','upcoming')]):
            soft,color=palette[i];box=tk.Frame(metrics,bg=soft,highlightbackground=LINE,highlightthickness=1);box.grid(row=0,column=i,sticky='nsew',padx=3);metrics.grid_columnconfigure(i,weight=1,uniform='metrics')
            tk.Label(box,text=label,bg=soft,fg=color,font=('Segoe UI',9,'bold')).pack(anchor='w',padx=10,pady=(6,1));tk.Label(box,textvariable=app.receivable_metric_vars[key],bg=soft,fg=color,font=('Segoe UI',15,'bold')).pack(anchor='w',padx=10)
            self.counts[key]=tk.StringVar();tk.Label(box,textvariable=self.counts[key],bg=soft,fg=color,font=('Segoe UI',8)).pack(anchor='w',padx=10,pady=(1,6))
        listing,body=self.section(page,'▤  Liste des créances');listing.grid(row=2,column=0,columnspan=2,sticky='nsew',padx=5,pady=4)
        categories=tk.Frame(body,bg='white');categories.pack(fill='x');self.tabs={}
        for label in ('Toutes','En cours','En retard','À venir','Réglées'):
            b=self.button(categories,label,lambda l=label:self.choose(l),BLUE if label=='Toutes' else '#65809b');b.pack(side='left',expand=True,fill='x',padx=2);self.tabs[label]=b
        filters=tk.Frame(body,bg='white');filters.pack(fill='x',pady=4)
        for col,(var,values,width) in enumerate([(app.receivable_search,None,24),(app.receivable_status,('TOUS','RESTE À PAYER','NON RÉGLÉ','PARTIEL','RÉGLÉ','ÉCHUE'),14),(self.vehicle,('Tous les véhicules',),18),(app.receivable_date_from,None,11),(app.receivable_date_to,None,11)]):
            cell=tk.Frame(filters,bg='white');cell.grid(row=col//3,column=col%3,sticky='ew',padx=2,pady=2);filters.grid_columnconfigure(col%3,weight=1)
            if col>=3:tk.Label(cell,text='Du' if col==3 else 'Au',bg='white',fg=INK,font=('Segoe UI',8)).pack(side='left')
            w=ttk.Combobox(cell,textvariable=var,values=values,state='readonly',width=width) if values else ttk.Entry(cell,textvariable=var,width=width);w.pack(fill='x',expand=True)
            if col>=3:app._attach_date_picker(w,var)
            if col==2:self.vehicle_combo=w
        self.button(filters,'⌕ Rechercher',self.refresh,BLUE).grid(row=1,column=2,sticky='ew',padx=2)
        columns=('reference','choose','code','client','phone','vehicle','contract','total','paid','balance','due','status','actions')
        app.receivables_tree=self.tree(body,columns,[('choose','☐',32),('code','Code',55),('client','Client',115),('phone','Téléphone',80),('vehicle','Véhicule',95),('contract','Contrat N°',90),('total','Montant (DH)',80),('paid','Réglé (DH)',75),('balance','Reste (DH)',75),('due','Échéance',80),('status','Statut',75),('actions','Action',55)])
        app.receivables_tree.configure(displaycolumns=columns[1:]);app.receivable_active_tree=app.receivables_tree
        from history_layout import blue_history_headings
        blue_history_headings(ttk.Style(page),'Receivables3D.Treeview')
        for tag,soft in [('Réglée','#eff9f2'),('En cours','#fff8ea'),('En retard','#fff0f2'),('À venir','#f5f0fc')]:app.receivables_tree.tag_configure(tag,background=soft)
        app.receivables_tree.bind('<<TreeviewSelect>>',self.selection);app.receivables_tree.bind('<Button-1>',self.click,add='+');app.receivables_tree.bind('<Double-1>',lambda e:app.open_receivable_payment())
        footer=tk.Frame(body,bg='white');footer.pack(fill='x');tk.Label(footer,textvariable=self.caption,bg='white',fg=INK,font=('Segoe UI',8)).pack(side='left')
        for label,cmd in [('‹',lambda:self.move(-1)),('›',lambda:self.move(1))]:self.button(footer,label,cmd,BLUE).pack(side='right',padx=2)
        ttk.Combobox(footer,textvariable=self.limit,values=('10','20','50'),state='readonly',width=4).pack(side='right',padx=3)
        right=tk.Frame(page,bg=BG);right.grid(row=2,column=2,sticky='nsew',padx=5,pady=4)
        self.details={};self.photo=None
        for title,fields in [('▤  Détails de la créance',[('Code client','client'),('Nom','name'),('CIN','cin'),('Téléphone','phone'),('Adresse','address')]),('▤  Détails contrat',[('N° Contrat','contract'),('Véhicule','vehicle'),('Date début','start'),('Date fin','end'),('Montant total','total')]),('▤  Situation de la créance',[('Montant total','total2'),('Déjà réglé','paid'),('Reste à payer','balance'),('Échéance','deadline'),('Statut','status')])]:
            box,b=self.section(right,title);box.pack(fill='both',expand=True,pady=2)
            for i,(label,key) in enumerate(fields):
                var=self.details[key]=tk.StringVar(value='—');tk.Label(b,text=label+' :',bg='white',fg=INK,font=('Segoe UI',8)).grid(row=i,column=0,sticky='w',padx=2)
                tk.Label(b,textvariable=var,bg='white',fg='#b34459' if key=='balance' else INK,font=('Segoe UI',8,'bold'),anchor='w').grid(row=i,column=1,sticky='ew',padx=3);b.grid_columnconfigure(1,weight=1)
            if 'contrat' in title:self.photo=tk.Label(b,bg='white');self.photo.grid(row=0,column=2,rowspan=5)
        history,hbody=self.section(page,'▤  Historique des paiements','#e5f4ea');history.grid(row=3,column=0,sticky='nsew',padx=5,pady=4)
        app.receivable_payments_tree=self.tree(hbody,('date','mode','reference','amount','notes','user'),[(k,l,w) for k,l,w in [('date','Date',70),('mode','Mode',70),('reference','Référence',80),('amount','Montant (DH)',85),('notes','Observations',110),('user','Utilisateur',60)]])
        payment,pbody=self.section(page,'⊕  Ajouter un paiement');payment.grid(row=3,column=1,sticky='nsew',padx=5,pady=4)
        self.pay={k:tk.StringVar(value=datetime.now().strftime('%d/%m/%Y') if k=='date' else 'ESPÈCES' if k=='mode' else '0,00' if k=='amount' else '') for k in ('date','mode','amount','reference','notes')}
        for i,(label,key) in enumerate([('Date paiement','date'),('Mode paiement','mode'),('Montant (DH)','amount'),('Référence','reference'),('Observations','notes')]):
            row,col=divmod(i,3);cell=tk.Frame(pbody,bg='white');cell.grid(row=row,column=col,sticky='ew',padx=3,pady=3);pbody.grid_columnconfigure(col,weight=1,uniform='pay')
            tk.Label(cell,text=label,bg='white',fg=INK,font=('Segoe UI',8)).pack(anchor='w')
            widget=ttk.Combobox(cell,textvariable=self.pay[key],values=('ESPÈCES','CHÈQUE','VIREMENT','CARTE'),state='readonly',width=10) if key=='mode' else ttk.Entry(cell,textvariable=self.pay[key],width=10);widget.pack(fill='x')
            if key=='date':app._attach_date_picker(widget,self.pay[key])
        controls=tk.Frame(pbody,bg='white');controls.grid(row=2,column=0,columnspan=3,sticky='ew',pady=3)
        for text,cmd,color in [('▣ Enregistrer',self.save_payment,GREEN),('▣ Imprimer reçu',self.receipt,BLUE),('Annuler',self.reset,'#65809b')]:self.button(controls,text,cmd,color).pack(side='left',expand=True,fill='x',padx=2)
        quick,qbody=self.section(page,'⚙  Actions rapides','#f0eafb');quick.grid(row=3,column=2,sticky='nsew',padx=5,pady=4)
        for text,cmd,color in [('▣ Enregistrer un paiement',self.save_payment,GREEN),('▤ Imprimer l’état du compte',app.open_client_statement,BLUE),('✉ Envoyer un rappel au client',self.reminder,'#e58b23'),('! Marquer comme en retard',self.mark_late,'#d54660'),('▤ Voir le contrat',self.contract,'#65809b')]:self.button(qbody,text,cmd,color).pack(fill='x',pady=2)
        # Compatibility with the existing financial selection APIs.
        app.receivable_detail_vars={};app.receivable_schedule_tree=ttk.Treeview(page)
        for var in (app.receivable_search,app.receivable_status,app.receivable_date_from,app.receivable_date_to,self.vehicle,self.limit):var.trace_add('write',lambda *_:self.refresh())
        self.ready=True;self.refresh();page.bind('<Configure>',self.resize,add='+')
        from reference_widgets import fit_page
        fit_page(page)
    def button(self,parent,text,cmd,color):return tk.Button(parent,text=text,command=cmd,bg=color,fg='white',relief='flat',font=('Segoe UI',8,'bold'),padx=5,pady=5,cursor='hand2')
    def section(self,parent,title,soft='#e2f0fc'):
        box=tk.Frame(parent,bg='white',highlightbackground=LINE,highlightthickness=1);tk.Label(box,text=title,bg=soft,fg=INK,font=('Segoe UI',10,'bold'),anchor='w',padx=7,pady=5).pack(fill='x');body=tk.Frame(box,bg='white');body.pack(fill='both',expand=True,padx=4,pady=3);return box,body
    def tree(self,parent,columns,defs):
        box=tk.Frame(parent,bg='white');box.pack(fill='both',expand=True)
        tree=ttk.Treeview(box,columns=columns,show='headings',height=3,style='Receivables3D.Treeview')
        for key,label,width in defs:tree.heading(key,text=label);tree.column(key,width=width,anchor='center',minwidth=1)
        tree.pack(side='left',fill='both',expand=True);bar=ttk.Scrollbar(box,command=tree.yview);bar.pack(side='right',fill='y');tree.configure(yscrollcommand=bar.set);return tree
    def choose(self,label):self.category=label;self.pageno=0;self.refresh()
    def move(self,offset):self.pageno=max(0,self.pageno+offset);self.refresh()
    def refresh(self):
        if not self.ready:return
        app=self.app;rows=app._receivable_rows(app.receivable_search.get(),app.receivable_status.get(),app.receivable_month.get(),app.receivable_year.get())+app._receivable_rows(app.receivable_search.get(),app.receivable_status.get(),app.receivable_month.get(),app.receivable_year.get(),True)
        manual={str(r[0]) for r in app.conn.execute("SELECT record_id FROM module_records WHERE module='receivable_late_flags'")}
        for row in rows:
            row['insolvent']=row['insolvent'] or str(row['contract']) in manual
            row['view_state']='Réglée' if row['balance']<=.005 else 'En retard' if row['insolvent'] else 'À venir' if (app._parse_french_date(row['deadline']) or datetime.min).date()>datetime.now().date() else 'En cours'
        low=app._parse_french_date(app.receivable_date_from.get());high=app._parse_french_date(app.receivable_date_to.get())
        rows=[r for r in rows if (not low or (app._parse_french_date(r['start']) or datetime.min)>=low) and (not high or (app._parse_french_date(r['start']) or datetime.max)<=high)]
        options=tuple(sorted({r['vehicle'] for r in rows}));self.vehicle_combo.configure(values=('Tous les véhicules',)+options)
        if self.vehicle.get()!='Tous les véhicules':rows=[r for r in rows if r['vehicle']==self.vehicle.get()]
        groups={'total':rows,'paid':[r for r in rows if r['view_state']=='Réglée'],'balance':[r for r in rows if r['view_state']=='En cours'],'overdue':[r for r in rows if r['view_state']=='En retard'],'upcoming':[r for r in rows if r['view_state']=='À venir']}
        for key,group in groups.items():
            amount=sum(r['total'] if key=='total' else r['paid'] if key=='paid' else r['balance'] for r in group);app.receivable_metric_vars[key].set(f'{amount:,.2f} DH'.replace(',',' '));self.counts[key].set(f"{len({r['client'] for r in group})} clients")
        cats={'Toutes':rows,'En cours':groups['balance'],'En retard':groups['overdue'],'À venir':groups['upcoming'],'Réglées':groups['paid']}
        for label,b in self.tabs.items():b.configure(text=f'{label} ({len(cats[label])})',bg=BLUE if label==self.category else '#65809b')
        self.rows=cats[self.category];app._receivable_display_rows=self.rows;limit=int(self.limit.get());self.pageno=min(self.pageno,max(0,(len(self.rows)-1)//limit));start=self.pageno*limit
        selected=app.receivables_tree.selection();old=selected[0] if selected else None;app.receivables_tree.delete(*app.receivables_tree.get_children())
        self.map={}
        for r in self.rows[start:start+limit]:
            iid=f"receivable:{r['contract']}:{r['period']}";self.map[iid]=r
            vals=(r['contract'],'☑' if iid in self.chosen else '☐',r['client'],r['name'],r['phone'],r['vehicle'].split('|')[-1].strip(),r['contract'],f"{r['total']:.2f}",f"{r['paid']:.2f}",f"{r['balance']:.2f}",r['deadline'],r['view_state'],'◉  ✎')
            app.receivables_tree.insert('','end',iid=iid,values=vals,tags=(r['view_state'],))
        self.caption.set(f'Affichage de {start+1 if self.rows else 0} à {min(start+limit,len(self.rows))} sur {len(self.rows)} créances')
        if self.map:app.receivables_tree.selection_set(old if old in self.map else next(iter(self.map)));self.selection()
        else:
            for var in self.details.values():var.set('—')
            app.receivable_payments_tree.delete(*app.receivable_payments_tree.get_children());self.photo.configure(image='')
    def selection(self,event=None):
        sel=self.app.receivables_tree.selection()
        if not sel or sel[0] not in self.map:return
        row=self.map[sel[0]];values=dict(row,total2=row['total']);client=self.app.conn.execute('SELECT adresse FROM clients WHERE code=?',(row['client'],)).fetchone();values['address']=client[0] if client else '—';values['status']=row['view_state']
        for key,var in self.details.items():var.set(f'{values[key]:,.2f} DH' if key in ('total','total2','paid','balance') else values.get(key,'—'))
        tree=self.app.receivable_payments_tree;tree.delete(*tree.get_children())
        for rid,raw in self.app.conn.execute("SELECT record_id,payload FROM module_records WHERE module='payments' ORDER BY created_at DESC"):
            try:p=json.loads(raw)
            except (ValueError,TypeError):continue
            if str(p.get('contract',''))==str(row['contract']):tree.insert('','end',values=(p.get('date',''),p.get('mode',''),p.get('document',rid),p.get('amount',''),p.get('notes',''),p.get('user','')))
        try:
            from PIL import Image,ImageTk
            path=self.app._vehicle_photo_path(row['vehicle'].split('|')[0].strip());self.photo.configure(image='')
            if path:
                image=Image.open(path);image.thumbnail((90,70));self.photo._image=ImageTk.PhotoImage(image,master=self.photo);self.photo.configure(image=self.photo._image)
        except (OSError,ValueError,TypeError):self.photo.configure(image='')
    def click(self,event):
        tree=self.app.receivables_tree;iid=tree.identify_row(event.y);col=tree.identify_column(event.x)
        if iid and col=='#1':
            if iid in self.chosen:self.chosen.remove(iid)
            else:self.chosen.add(iid)
            vals=list(tree.item(iid,'values'));vals[1]='☑' if iid in self.chosen else '☐';tree.item(iid,values=vals)
        elif iid and col=='#12':tree.selection_set(iid);self.app.open_receivable_payment()
    def resize(self,event=None):
        width=self.app.receivables_tree.winfo_width()-4
        cols=self.app.receivables_tree['displaycolumns'];weights=[32,55,110,80,95,90,80,75,75,80,75,55]
        for key,w in zip(cols,weights):self.app.receivables_tree.column(key,width=max(1,int(width*w/sum(weights))),minwidth=1)
    def reset(self):self.pay['amount'].set('0,00');self.pay['reference'].set('');self.pay['notes'].set('')
    def save_payment(self):
        app=self.app;row=app._selected_receivable()
        if row is None:return
        try:amount=float(self.pay['amount'].get().replace(' ','').replace(',','.'))
        except ValueError:messagebox.showwarning('Paiement','Montant invalide.');return
        date=app._parse_french_date(self.pay['date'].get());total=max(0,float(row['montant'] or 0));paid=min(total,max(0,float(row['reglement'] or 0)));remaining=total-paid;mode=self.pay['mode'].get()
        if not date or amount<=0 or amount>remaining+.005:messagebox.showwarning('Paiement',f'Date valide et montant entre 0 et {remaining:.2f} DH requis.');return
        if not app._receivable_payment_dialog(app.root,False,row,total,paid,amount,max(0,remaining-amount),mode):return
        rid=f"REG-{row['numero']}-{datetime.now():%Y%m%d%H%M%S%f}";payload=dict(reference=rid,contract=row['numero'],client=row['client_code'],customer_name=f"{row['nom']} {row['prenom']}",amount=f'{amount:.2f}',cash_amount=f'{amount:.2f}' if mode=='ESPÈCES' else '0.00',bank_amount='0.00' if mode=='ESPÈCES' else f'{amount:.2f}',mode=mode,document=self.pay['reference'].get(),notes=self.pay['notes'].get(),date=date.strftime('%d/%m/%Y'),status='ENCAISSÉ')
        try:
            app.conn.execute('UPDATE contracts SET reglement=?,reste=? WHERE numero=?',(paid+amount,max(0,remaining-amount),row['numero']))
            app.conn.execute('INSERT INTO module_records VALUES(?,?,?,?)',('payments',rid,json.dumps(payload,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')));app._audit('RÈGLEMENT','CRÉANCE',row['numero'],f'{amount:.2f} MAD — {mode}');app.conn.commit()
        except Exception as exc:
            app.conn.rollback();messagebox.showerror('Paiement',f'Enregistrement impossible : {exc}');return
        self.last_payment=payload;self.reset();self.refresh();app.refresh_dashboard();app.schedule_web_sync()
    def receipt(self):
        if not self.last_payment:messagebox.showinfo('Reçu','Enregistrez un paiement pour imprimer son reçu.');return
        p=self.last_payment;doc=f"<html><head><meta charset='utf-8'></head><body><h1>HBZ RENT CAR — Reçu de paiement</h1><p>Contrat : {html.escape(str(p['contract']))}</p><p>Client : {html.escape(p['customer_name'])}</p><p>Date : {p['date']} · Montant : {p['amount']} DH · {p['mode']}</p><p>Référence : {html.escape(p['document'])}</p></body></html>";path=Path(__file__).parent/'exports'/f"{p['reference']}.html";path.parent.mkdir(exist_ok=True);path.write_text(self.app._make_html_directly_printable(doc),encoding='utf-8');webbrowser.open(path.as_uri())
    def contract(self):
        row=self.app._selected_receivable()
        if row is None:return
        self.app.contract_search_var.set(row['numero']);self.app.load_contract_lookup(check_conflict=False);self.app.show_page('contract')
    def reminder(self):
        row=self.app._selected_receivable()
        if row is None:return
        from urllib.parse import quote
        phone=''.join(c for c in str(row['telephone']) if c.isdigit())
        if phone.startswith('0'):phone='212'+phone[1:]
        if not phone:messagebox.showwarning('Rappel','Le client n’a pas de téléphone.');return
        webbrowser.open('https://wa.me/'+phone+'?text='+quote(f"Bonjour, rappel de règlement pour le contrat {row['numero']}. Reste : {max(0,float(row['montant'] or 0)-float(row['reglement'] or 0)):.2f} DH."))
    def mark_late(self):
        row=self.app._selected_receivable()
        if row is None:return
        if float(row['montant'] or 0)-float(row['reglement'] or 0)<=.005:
            messagebox.showinfo('Retard','Cette créance est déjà réglée.');return
        if not messagebox.askyesno('Retard','Marquer cette créance comme en retard ? Les montants restent inchangés.') :return
        self.app.conn.execute('INSERT OR REPLACE INTO module_records VALUES(?,?,?,?)',('receivable_late_flags',str(row['numero']),json.dumps({'manual':True}),datetime.now().isoformat(timespec='seconds')))
        self.app.conn.commit();self.choose('En retard')
