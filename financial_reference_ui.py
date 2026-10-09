"""Financial reference layout backed by the established accounting engine."""
import json
import sqlite3
import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime,timedelta
import tkinter as tk
from tkinter import ttk,messagebox
from reference_widgets import image,button,section,styles,BG,BLUE,GREEN,RED,PURPLE,INK,LINE,fit_page
MONTHS=('Janvier','Février','Mars','Avril','Mai','Juin','Juillet','Août','Septembre','Octobre','Novembre','Décembre')
def money(value):return f'{float(value):,.2f}'.replace(',',' ').replace('.',',')+' MAD'
def build(app):
    page=app.pages['financial_center'];styles(page)
    for child in page.winfo_children():child.pack_forget()
    shell=tk.Frame(page,bg=BG);shell.pack(fill='both',expand=True,padx=10,pady=5)
    shell.grid_columnconfigure(0,weight=1);shell.grid_rowconfigure(3,weight=1)
    app.financial_reference_shell=shell
    header=tk.Frame(shell,bg=BG);header.grid(row=0,column=0,sticky='ew',pady=(0,8));header.grid_columnconfigure(1,weight=1)
    tk.Label(header,image=image(shell,'finance_title',36),bg=BG).grid(row=0,column=0,rowspan=2,padx=(0,12))
    tk.Label(header,text='Centre financier',bg=BG,fg=INK,font=('Segoe UI',22,'bold'),anchor='w').grid(row=0,column=1,sticky='ew')
    tk.Label(header,text='Suivi de la trésorerie, charges, revenus et échéances.',bg=BG,fg=INK,font=('Segoe UI',9),anchor='w').grid(row=1,column=1,sticky='ew')
    controls=tk.Frame(header,bg=BG);controls.grid(row=0,column=2,rowspan=2)
    for i,(label,var,vals,width) in enumerate((('Mois',app.financial_center_month,MONTHS,12),('Année',app.financial_center_year,tuple(str(n) for n in range(datetime.now().year-10,datetime.now().year+3)),5))):
        box=tk.Frame(controls,bg=BG);box.pack(side='left',padx=4)
        tk.Label(box,text=label,bg=BG,fg=INK,font=('Segoe UI',8)).pack(anchor='w')
        control=ttk.Combobox(box,textvariable=var,values=vals,width=width,state='readonly',style='Reference.TCombobox');control.pack();control.bind('<<ComboboxSelected>>',lambda e:app._refresh_financial_center())
    for title,command,color,icon in (('Actualiser',app._refresh_financial_center,BLUE,'refresh'),('Exporter Excel',app._export_financial_center,GREEN,'excel'),('Imprimer',app._print_financial_center,RED,'print'),('Paramètres',lambda:app.show_page('settings'),PURPLE,'settings')):
        button(controls,title,command,color,icon,True).pack(side='left',padx=3,pady=10)
    cards=tk.Frame(shell,bg=BG);cards.grid(row=1,column=0,sticky='ew')
    definitions=(('revenue',"Chiffre d’affaires (CA)",'ca','#e0f2fe','#0059d8'),('cash','Caisse','cash','#def8eb','#087546'),('bank','Banque','bank','#e5eaff','#0925a5'),('receivables','Créances clients','clients','#fff0df','#bb2800'),('supplier_payable','Dettes fournisseurs','supplier','#ffe8ec','#b20b37'),('expenses','Total des charges','expenses','#ede7ff','#6525d9'),('result','Résultat du mois','result','#fff5c9','#8f6104'),('cash_funding','Alimentation de caisse','funding','#e0f8ed','#087546'))
    app.financial_reference_card_labels={}
    for i,(key,title,icon,soft,color) in enumerate(definitions):
        cards.grid_columnconfigure(i%4,weight=1,uniform='ref_fin_cards')
        card=tk.Frame(cards,bg=soft,highlightbackground=LINE,highlightthickness=1);card.grid(row=i//4,column=i%4,sticky='nsew',padx=3,pady=4)
        tk.Label(card,image=image(card,icon,43),bg=soft).pack(side='left',padx=9,pady=14)
        graphic='clock' if key=='receivables' else 'clock_red' if key=='supplier_payable' else 'trend_arrow' if key in ('result','cash_funding') else 'trend'
        trend=tk.Label(card,image=image(card,graphic,22),bg=soft);trend.pack(side='right',padx=6)
        body=tk.Frame(card,bg=soft);body.pack(side='left',fill='both',expand=True,pady=9)
        tk.Label(body,text=title,bg=soft,fg=color,font=('Segoe UI',9,'bold'),anchor='w').pack(fill='x')
        if key not in app.financial_center_cards:app.financial_center_cards[key]=(tk.StringVar(master=page,value=money(0)),tk.StringVar(master=page))
        amount,subtitle=app.financial_center_cards[key]
        amount_label=tk.Label(body,textvariable=amount,bg=soft,fg=color,font=('Segoe UI',14,'bold'),anchor='w');amount_label.pack(fill='x')
        tk.Label(body,textvariable=subtitle,bg=soft,fg='#526b84',font=('Segoe UI',8),anchor='w',wraplength=220).pack(fill='x')
        app.financial_reference_card_labels[key]=amount_label
        command=(lambda k=key:app._open_center_card_sources(k)) if key not in ('result','supplier_payable') else (lambda:select(app,'Dettes fournisseurs')) if key=='supplier_payable' else (lambda:select(app,'Vue globale'))
        for widget in (card,*card.winfo_children(),*body.winfo_children()):widget.configure(cursor='hand2');widget.bind('<Button-1>',lambda e,c=command:c())
    tabs=tk.Frame(shell,bg=BG);tabs.grid(row=2,column=0,sticky='ew',pady=6)
    labels=('Vue globale','Entrées / Sorties','Banque','Caisse','Créances clients','Dettes fournisseurs','Produits & charges','Crédits / Échéances','Détail par véhicule')
    app.financial_reference_tab_buttons={}
    for i,title in enumerate(labels):
        tabs.grid_columnconfigure(i,weight=1)
        btn=tk.Button(tabs,text=title,image=image(tabs,('tab_overview','tab_flow','tab_bank','tab_cash','tab_due','tab_supplier','tab_charge','tab_credit','tab_vehicle')[i],14),compound='left',command=lambda t=title:select(app,t),bg=BG,fg=INK,font=('Segoe UI',8,'bold'),relief='flat',bd=0,pady=7,cursor='hand2');btn.grid(row=0,column=i,sticky='ew');app.financial_reference_tab_buttons[title]=btn
    content=tk.Frame(shell,bg=BG);content.grid(row=3,column=0,sticky='nsew');content.grid_columnconfigure(0,weight=1);content.grid_rowconfigure(0,weight=1)
    overview=tk.Frame(content,bg=BG);overview.grid(row=0,column=0,sticky='nsew');overview.grid_columnconfigure(0,weight=1);overview.grid_rowconfigure(3,weight=1)
    app.financial_reference_overview=overview
    detail=tk.Frame(content,bg=BG);detail.grid(row=0,column=0,sticky='nsew');app.financial_reference_detail=detail
    tk.Label(detail,text='Détail de la période',bg='#154c7b',fg='white',font=('Segoe UI',13,'bold'),pady=8).pack(fill='x')
    toolbar=tk.Frame(detail,bg=BG);toolbar.pack(fill='x',pady=5);app.financial_reference_detail_toolbar=toolbar
    button(toolbar,'Nouvelle charge',app.open_new_charge_form,GREEN,'new',True).pack(side='left',padx=3)
    button(toolbar,'Nouveau règlement',lambda:app.show_page('receivables'),BLUE,'new',True).pack(side='left',padx=3)
    button(toolbar,'Versement caisse → banque',lambda:app.open_versements('VERSEMENT BANQUE'),BLUE,'bank',True).pack(side='left',padx=3)
    button(toolbar,'Retrait banque → caisse',lambda:app.open_versements('RETRAIT BANQUE'),RED,'cash',True).pack(side='left',padx=3)
    cols=('date','ref','source','type','amount','status')
    detailtree=ttk.Treeview(detail,columns=cols,show='headings',style='Reference.Treeview')
    for key,label in zip(cols,('Date','Référence','Source / client','Nature / rubrique','Montant MAD','Statut / mode')):detailtree.heading(key,text=label);detailtree.column(key,width=140,minwidth=65)
    detailtree.pack(fill='both',expand=True);app.financial_reference_detail_tree=detailtree
    balance=tk.Frame(overview,bg=BG);balance.grid(row=0,column=0,sticky='ew');balance.grid_columnconfigure(0,weight=1,uniform='bal');balance.grid_columnconfigure(1,weight=1,uniform='bal')
    for side,title,color,labels in (('debit','DÉBIT',BLUE,('Banque','Caisse','Créances clients','Charges','TOTAL DÉBIT')),('credit','CRÉDIT',PURPLE,('Chiffre d’affaires','Alimentation de caisse','Traites / échéances à venir','TOTAL CRÉDIT'))):
        box,body=section(balance,title,color=color);box.grid(row=0,column=0 if side=='debit' else 1,sticky='nsew',padx=3)
        box.winfo_children()[0].configure(anchor='center')
        for label in labels:
            informative=label=='Traites / échéances à venir';total=label.startswith('TOTAL');tint='#fff0ad' if informative else '#e7f3ff' if total else 'white'
            line=tk.Frame(body,bg=tint);line.pack(fill='x',pady=1)
            caption='Crédits / échéances à venir · informatif' if informative else label
            tk.Label(line,text=caption,bg=tint,fg=INK,font=('Segoe UI',9,'bold' if total else 'normal'),anchor='w').pack(side='left',padx=8,pady=5)
            tk.Label(line,textvariable=app.financial_center_balance_rows[label],bg=tint,fg='#8d6609' if informative else '#074fc3',font=('Segoe UI',9,'bold')).pack(side='right',padx=8)
        if side=='credit':tk.Label(body,text='Les échéances à venir sont exclues du total crédit.',bg='white',fg='#8b6407',font=('Segoe UI',8),anchor='w').pack(fill='x',padx=6,pady=2)
    result=tk.Frame(overview,bg='#e0f7eb');result.grid(row=1,column=0,sticky='ew',padx=3,pady=7)
    app.financial_reference_result_label=tk.Label(result,textvariable=app.financial_center_result,bg='#e0f7eb',fg=GREEN,font=('Segoe UI',10,'bold'),justify='left',anchor='w');app.financial_reference_result_label.configure(wraplength=850)
    app.financial_reference_result_label.pack(side='left',fill='x',expand=True,padx=10,pady=8)
    from cash_funding import open_funding
    button(result,'Ajouter une alimentation de caisse',lambda:open_funding(app),RED,'new',True).pack(side='right',padx=6,pady=8)
    summaries=tk.Frame(overview,bg=BG);summaries.grid(row=2,column=0,sticky='ew');app.financial_reference_indicators={}
    for i,(title,soft,rows) in enumerate((('SITUATION TRÉSORERIE','#fff0b8',(('cash','Solde caisse'),('bank','Solde banque'),('available','Total disponible'))),('CRÉANCES & DETTES','#eae0ff',(('receivables','Créances clients'),('supplier_payable','Dettes fournisseurs'),('net_due','Solde net'))),('CRÉDITS','#d6ebff',(('month_due','Échéances du cycle 6 → 5'),('upcoming','Échéances à venir'),('capital','Capital restant global'))))):
        summaries.grid_columnconfigure(i,weight=1,uniform='sum');box,body=section(summaries,title,('treasury','summary_due','summary_credit')[i],soft=soft);box.grid(row=0,column=i,sticky='nsew',padx=3,pady=2)
        for key,label in rows:
            var=tk.StringVar(master=page,value=money(0));app.financial_reference_indicators[key]=var
            line=tk.Frame(body,bg='white');line.pack(fill='x',pady=2)
            tk.Label(line,text=label,bg='white',fg=INK,font=('Segoe UI',8)).pack(side='left')
            tk.Label(line,textvariable=var,bg='white',fg='#0956c6',font=('Segoe UI',9,'bold')).pack(side='right')
    duebox=tk.Frame(overview,bg='white',highlightbackground=LINE,highlightthickness=1);duebox.grid(row=3,column=0,sticky='nsew',padx=3,pady=(6,0))
    duehead=tk.Frame(duebox,bg='white');duehead.pack(fill='x',padx=7,pady=5)
    tk.Label(duehead,text='PROCHAINES ÉCHÉANCES DE CRÉDITS',image=image(duehead,'calendar',20),compound='left',bg='white',fg='#063ea8',font=('Segoe UI',11,'bold')).pack(side='left')
    button(duehead,'Voir toutes les échéances',app.open_hbz_credit_app,BLUE,'view',True).pack(side='right')
    cols=('date','reference','organism','amount','capital','status','action')
    tree=ttk.Treeview(duebox,columns=cols,show='headings',height=4,style='Reference.Treeview')
    for key,label,width in zip(cols,('Date échéance','Référence','Organisme','Montant (MAD)','Capital restant (MAD)','Statut','Action'),(115,145,190,130,160,110,105)):
        tree.heading(key,text=label);tree.column(key,width=width,minwidth=65,stretch=key!='action')
    tree.tag_configure('odd',background='#edf6ff');tree.pack(side='left',fill='both',expand=True,padx=(7,0),pady=(0,7))
    bar=ttk.Scrollbar(duebox,orient='vertical',command=tree.yview);bar.pack(side='right',fill='y',pady=(0,7));tree.configure(yscrollcommand=bar.set)
    app.financial_reference_credit_tree=tree;app.financial_reference_credit_records={}
    tree.bind('<Double-1>',lambda e:credit_action(app,'view',tree.identify_row(e.y)))
    app.financial_reference_action_frames=[]
    def render_actions(*_):
        for frame in app.financial_reference_action_frames:frame.destroy()
        app.financial_reference_action_frames.clear()
        for iid in tree.get_children():
            bbox=tree.bbox(iid,'action')
            if not bbox:continue
            statusbox=tree.bbox(iid,'status')
            if statusbox:
                sx,sy,sw,sh=statusbox
                badge=tk.Label(tree,text='En cours',bg='#008747',fg='white',font=('Segoe UI',8,'bold'));badge.place(x=sx+8,y=sy+3,width=max(35,sw-16),height=max(15,sh-6));app.financial_reference_action_frames.append(badge)
            x,y,w,h=bbox;frame=tk.Frame(tree,bg='white');frame.place(x=x+2,y=y+1,width=w-4,height=h-2);app.financial_reference_action_frames.append(frame)
            for icon,action,color in (('view','view','#dcf0ff'),('edit','edit','#fff0bc'),('delete','delete','#ffe1e7')):
                b=tk.Button(frame,image=image(frame,icon,14),command=lambda a=action,k=iid:credit_action(app,a,k),bg=color,relief='flat',bd=0,cursor='hand2');b.pack(side='left',fill='both',expand=True,padx=1)
    tree.bind('<Configure>',lambda e:tree.after_idle(render_actions));tree.configure(yscrollcommand=lambda a,b:(bar.set(a,b),tree.after_idle(render_actions)))
    app.financial_reference_render_actions=render_actions
    fit_page(shell)
    app.financial_reference_enabled=True;select(app,'Vue globale');app._refresh_financial_center()
    return page

def upcoming(app):
    path=app._hbz_credit_db_path()
    if not path.exists():return []
    with sqlite3.connect(f'file:{Path(path).resolve().as_posix()}?mode=ro',uri=True) as con:
        return con.execute("SELECT id,date_ech,ref,COALESCE(organisme,''),COALESCE(echeance,0),COALESCE(capital_restant,0) FROM echeances WHERE date(date_ech)>=? ORDER BY date(date_ech),ref,id",(datetime.now().date().isoformat(),)).fetchall()

def refresh(app,totals):
    if not getattr(app,'financial_reference_enabled',False):return
    app._financial_reference_totals=totals
    def setcard(key,value,subtitle):app.financial_center_cards[key][0].set(money(value));app.financial_center_cards[key][1].set(subtitle)
    setcard('supplier_payable',totals['supplier_payable'],'Total des dettes')
    setcard('result',totals['result'],'Bénéfice après charges' if totals['result']>=0 else 'Déficit de la société')
    setcard('cash',totals['cash'],'Solde de caisse de la période');setcard('bank',totals['bank'],'Solde bancaire de la période')
    app.financial_reference_card_labels['result'].configure(fg=GREEN if totals['result']>=0 else RED)
    app.financial_reference_result_label.configure(fg=GREEN if totals['result']>=0 else RED,wraplength=max(300,app.financial_reference_shell.winfo_width()-320))
    credit=upcoming(app);snapshot=app._hbz_credit_snapshot()
    start,end=app._center_period()
    cycle_start=start.replace(day=6);cycle_end=(end.replace(hour=0,minute=0,second=0,microsecond=0)+timedelta(days=5))
    month_due=sum(float(row[4]) for row in credit if (app._parse_french_date(row[1]) and cycle_start<=app._parse_french_date(row[1])<=cycle_end))
    values=dict(totals,available=totals['cash']+totals['bank'],net_due=totals['receivables']-totals['supplier_payable'],month_due=month_due,upcoming=sum(float(row[4]) for row in credit),capital=snapshot['remaining'])
    for key,var in app.financial_reference_indicators.items():var.set(money(values[key]))
    tree=app.financial_reference_credit_tree;tree.delete(*tree.get_children());app.financial_reference_credit_records={}
    for i,row in enumerate(credit):
        iid=str(row[0]);app.financial_reference_credit_records[iid]=row
        date=app._parse_french_date(row[1]);tree.insert('', 'end',iid=iid,values=(date.strftime('%d/%m/%Y') if date else row[1],row[2],row[3],money(row[4]),money(row[5]),'En cours',''),tags=('odd',) if i%2 else ())
    tree.after_idle(app.financial_reference_render_actions)
    select(app,getattr(app,'financial_reference_tab','Vue globale'),refresh_only=True)

def select(app,title,refresh_only=False):
    app.financial_reference_tab=title
    for label,btn in app.financial_reference_tab_buttons.items():btn.configure(bg='#e3f1ff' if label==title else BG,fg=BLUE if label==title else INK)
    if title=='Vue globale':
        app.financial_center_tab='Bilan global';app.financial_reference_overview.tkraise();app._refresh_financial_center_detail();return
    app.financial_reference_detail.tkraise()
    mapping={'Crédits / Échéances':'Crédit / Échéance','Entrées / Sorties':'Caisse','Détail par véhicule':'Produits & charges'}
    app.financial_center_tab=mapping.get(title,title)
    if title=='Dettes fournisseurs':
        start,end=app._center_period();records=[]
        for ref,q,date in app._center_rows('maintenance',start,end):
            if any(x in str(q.get('payment_method','')).upper() for x in ('CRÉDIT','CREDIT')):records.append((date.strftime('%d/%m/%Y'),ref,q.get('supplier',''),q.get('service','Entretien'),money(app._number(q.get('amount'))),'À régler'))
    elif title=='Détail par véhicule':
        start,end=app._center_period();records=[]
        for code,model in app.conn.execute('SELECT code,modele FROM vehicles ORDER BY modele'):
            amount=0
            for r in app.conn.execute('SELECT date_depart,date_retour,duree,montant,reglement FROM contracts WHERE vehicle_code=?',(code,)):
                amount+=app._contract_allocated_parts(r[0],r[1],r[2],app._number(r[3]),app._number(r[4]),0,start,end)[0]
            if amount:records.append(('',code,model,'Production du mois',money(amount),'CA'))
    else:
        app._refresh_financial_center_detail();records=[app.financial_center_detail_tree.item(i,'values') for i in app.financial_center_detail_tree.get_children()]
        if title=='Entrées / Sorties':
            start,end=app._center_period()
            for ref,q,date in app._center_rows('expenses',start,end):records.append((date.strftime('%d/%m/%Y'),ref,q.get('party',''),q.get('category',''),money(app._number(q.get('amount'))),q.get('status','')))
    tree=app.financial_reference_detail_tree;tree.delete(*tree.get_children())
    for i,row in enumerate(records):
        row=list(row)
        if len(row)>2:
            client=app.conn.execute('SELECT nom,prenom FROM clients WHERE code=?',(str(row[2]),)).fetchone()
            if client:row[2]=' '.join(str(x or '') for x in client)
        tree.insert('', 'end',values=row,tags=('odd',) if i%2 else ())

def credit_action(app,action,iid):
    row=app.financial_reference_credit_records.get(iid)
    if row is None:return
    if action=='view':
        messagebox.showinfo('Échéance de crédit',f'Crédit : {row[2]}\nOrganisme : {row[3]}\nDate : {row[1]}\nMontant : {money(row[4])}\nCapital restant : {money(row[5])}',parent=app.root);return
    # Financial editing remains in the existing dedicated credit application,
    # where capital schedules and generated entries are managed together.
    if getattr(app,"_authenticated",False) and not app._require_permission("Finance"):return
    folder=Path(app._hbz_credit_db_path()).parent
    executable=Path(sys.executable)
    if os.name=="nt" and executable.with_name("pythonw.exe").exists():executable=executable.with_name("pythonw.exe")
    subprocess.Popen([str(executable),str(folder/"app.py"),"--due-id",str(row[0]),"--due-action",action],cwd=str(folder))
