"""Centre financier HBZ : tableau mensuel dans le style de la maquette."""
import csv
import json
from collections import defaultdict
from datetime import datetime,timedelta
import tkinter as tk
from tkinter import filedialog,ttk,messagebox

BG="#edf7ff"
CARD="#ffffff"
DEEP="#07549b"
BLUE="#0787f2"
GREEN="#08ad50"
ORANGE="#ff9910"
RED="#f3384e"
PURPLE="#8831e8"
TEXT="#0d2855"
EDGE="#cadff2"
MONTHS=("Janvier","Février","Mars","Avril","Mai","Juin","Juillet","Août","Septembre","Octobre","Novembre","Décembre")


def money(value):
    return f"{value:,.2f}".replace(","," ").replace(".",",")


class FinancialCenterMixin:
    def _build_financial_center(self):
        page=self._new_page("financial_center")
        now=datetime.now()
        self.financial_center_month=tk.StringVar(master=page,value=MONTHS[now.month-1])
        self.financial_center_year=tk.StringVar(master=page,value=str(now.year))
        self.financial_center_cards={}
        self.financial_center_tables={}
        self.financial_center_tab="Aperçu général"
        self.financial_center_buttons={}
        self.financial_center_selected=tk.StringVar(master=page)

        def action(parent,label,command,color=BLUE):
            return tk.Button(parent,text=label,command=command,bg=color,fg="white",activebackground=color,
                activeforeground="white",relief="flat",bd=0,cursor="hand2",padx=9,pady=7,
                font=("Segoe UI",9,"bold"))
        def panel(parent,title,icon="▣"):
            box=tk.Frame(parent,bg=CARD,highlightbackground=EDGE,highlightthickness=1)
            tk.Label(box,text=f"{icon}   {title}",bg=DEEP,fg="white",anchor="w",padx=11,pady=7,
                font=("Segoe UI",9,"bold")).pack(fill="x")
            inner=tk.Frame(box,bg=CARD)
            inner.pack(fill="both",expand=True,padx=6,pady=6)
            return box,inner
        def tree_for(parent,key,columns,height=5):
            frame=tk.Frame(parent,bg=CARD);frame.pack(fill="both",expand=True)
            keys=tuple(name for name,_ in columns)
            tree=ttk.Treeview(frame,columns=keys,show="headings",height=height,selectmode="browse")
            for name,label in columns:
                tree.heading(name,text=label)
                tree.column(name,width=85 if name in ("date","amount") else 120,anchor="center",minwidth=65,stretch=True)
            ybar=ttk.Scrollbar(frame,orient="vertical",command=tree.yview)
            tree.configure(yscrollcommand=ybar.set)
            tree.pack(side="left",fill="both",expand=True)
            ybar.pack(side="right",fill="y")
            self.financial_center_tables[key]=tree
            return tree

        header=tk.Frame(page,bg="#e7f4ff");header.pack(fill="x",padx=9,pady=(6,5))
        tk.Label(header,text="▥",bg=BLUE,fg="white",font=("Segoe UI Symbol",24,"bold"),
                 width=2,pady=5).pack(side="left",padx=(9,10),pady=5)
        title=tk.Frame(header,bg="#e7f4ff");title.pack(side="left",fill="x",expand=True)
        tk.Label(title,text="Centre financier",bg="#e7f4ff",fg=TEXT,font=("Segoe UI",19,"bold")).pack(anchor="w")
        tk.Label(title,text="Suivi de la trésorerie, charges, créances et échéances",bg="#e7f4ff",
                 fg=TEXT,font=("Segoe UI",8)).pack(anchor="w")
        filters=tk.Frame(header,bg="#e7f4ff");filters.pack(side="left",padx=6)
        for label,var,choices,width in (("Mois",self.financial_center_month,MONTHS,12),
                                        ("Année",self.financial_center_year,tuple(str(y) for y in range(now.year+2,now.year-10,-1)),6)):
            slot=tk.Frame(filters,bg="#e7f4ff");slot.pack(side="left",padx=4)
            tk.Label(slot,text=label,bg="#e7f4ff",fg=TEXT,font=("Segoe UI",8,"bold")).pack(anchor="w")
            combo=ttk.Combobox(slot,textvariable=var,values=choices,state="readonly",width=width,style="GP.TCombobox")
            combo.pack();combo.bind("<<ComboboxSelected>>",lambda _e:self._refresh_financial_center())
        for label,command,color in (("↻  Actualiser",self._refresh_financial_center,BLUE),
                                    ("▣  Export Excel",self._export_financial_center,GREEN),
                                    ("▣  Imprimer",self._print_financial_center,BLUE),
                                    ("▥  Statistiques",lambda:self._select_financial_center_tab("Aperçu général"),PURPLE)):
            action(header,label,command,color).pack(side="left",padx=3)

        cards=tk.Frame(page,bg=BG);cards.pack(fill="x",padx=8,pady=3)
        specs=(("revenue","Chiffre d’affaires du mois","▦",BLUE,"#e7f4ff"),
               ("cash","Caisse","▣",GREEN,"#e2f8ed"),
               ("bank","Banque","▥",BLUE,"#e2f1ff"),
               ("receivables","Créances clients","♟",ORANGE,"#fff0e3"),
               ("expenses","Charges du mois","▰",RED,"#ffe4e9"),
               ("drafts","Traites à venir","▤",PURPLE,"#efe6ff"),
               ("savings","Vision épargne","◷","#a36b08","#fff1ae"),
               ("cash_funding","Alimentation de caisse","＋",GREEN,"#e2f8ed"))
        for i,(key,label,icon,color,soft) in enumerate(specs):
            cards.grid_columnconfigure(i%4,weight=1,uniform="fin_cards")
            box=tk.Frame(cards,bg=soft,highlightbackground=EDGE,highlightthickness=1)
            box.grid(row=i//4,column=i%4,sticky="nsew",padx=3,pady=2)
            icon_box=tk.Label(box,text=icon,bg=color,fg="white",font=("Segoe UI Symbol",19,"bold"),width=3)
            icon_box.pack(side="left",padx=(8,5),pady=11)
            info=tk.Frame(box,bg=soft);info.pack(side="left",fill="both",expand=True,pady=7)
            title_label=tk.Label(info,text=label,bg=soft,fg=TEXT,anchor="w",font=("Segoe UI",8,"bold"))
            title_label.pack(fill="x")
            amount=tk.StringVar(master=page,value="0,00 MAD")
            amount_label=tk.Label(info,textvariable=amount,bg=soft,fg=TEXT,anchor="w",font=("Segoe UI",12,"bold"))
            amount_label.pack(fill="x")
            detail=tk.StringVar(master=page,value="—")
            detail_label=tk.Label(info,textvariable=detail,bg=soft,fg=TEXT,anchor="w",font=("Segoe UI",8),wraplength=170)
            detail_label.pack(fill="x")
            for widget in (box,icon_box,info,title_label,amount_label,detail_label):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>",lambda _event,card=key:self._open_center_card_sources(card))
            self.financial_center_cards[key]=(amount,detail)

        tabs=tk.Frame(page,bg=BG);tabs.pack(fill="x",padx=10,pady=(5,5))
        tab_specs=(("Aperçu général","▥"),("Caisse","▣"),("Banque","▥"),
                   ("Créances clients","♟"),("Produits & charges","▰"),
                   ("Chèques / Traites","▤"),("Crédit / Échéance","▦"),("Bilan global","◕"))
        for index,(label,icon) in enumerate(tab_specs):
            tabs.grid_columnconfigure(index,weight=1,uniform="finance_tabs")
            control=tk.Button(tabs,text=f"{icon}  {label}",bg="#e6f2ff",fg=TEXT,
                font=("Segoe UI",8,"bold"),bd=0,padx=4,pady=10,cursor="hand2",
                command=lambda tab=label:self._select_financial_center_tab(tab))
            control.grid(row=0,column=index,sticky="ew",padx=1)
            self.financial_center_buttons[label]=control
        content=tk.Frame(page,bg=BG);content.pack(fill="both",expand=True,padx=8)
        content.grid_columnconfigure(0,weight=1);content.grid_rowconfigure(0,weight=1)
        overview=tk.Frame(content,bg=BG);overview.grid(row=0,column=0,sticky="nsew")
        detail=tk.Frame(content,bg=BG);detail.grid(row=0,column=0,sticky="nsew")
        self.financial_center_panels=(overview,detail)
        overview.grid_columnconfigure(0,weight=5);overview.grid_columnconfigure(1,weight=4)
        overview.grid_columnconfigure(2,weight=2)
        chart,chart_content=panel(overview,"Évolution de la trésorerie","▥")
        chart.grid(row=0,column=0,sticky="nsew",padx=3,pady=3)
        self.financial_center_chart=tk.Canvas(chart_content,bg=CARD,highlightthickness=0,height=204)
        self.financial_center_chart.pack(fill="both",expand=True)
        self.financial_center_chart.bind("<Configure>",lambda _e:self._draw_financial_center_charts())
        share,share_content=panel(overview,"Répartition des charges (mois sélectionné)","◕")
        share.grid(row=0,column=1,sticky="nsew",padx=3,pady=3)
        self.financial_center_donut=tk.Canvas(share_content,bg=CARD,highlightthickness=0,height=204)
        self.financial_center_donut.pack(fill="both",expand=True)
        self.financial_center_donut.bind("<Configure>",lambda _e:self._draw_financial_center_charts())
        top,top_content=panel(overview,"Top 5 charges du mois","▥")
        top.grid(row=0,column=2,sticky="nsew",padx=3,pady=3)
        self.financial_center_top=top_content
        next_due,next_content=panel(overview,"Prochaines échéances (< 10 jours)","♧")
        next_due.grid(row=1,column=0,sticky="nsew",padx=3,pady=3)
        tree_for(next_content,"due",(("date","Date"),("type","Type"),("reference","Référence"),
                                     ("amount","Montant"),("status","Statut")))
        recent,recent_content=panel(overview,"Dernières opérations","◷")
        recent.grid(row=1,column=1,sticky="nsew",padx=3,pady=3)
        tree_for(recent_content,"recent",(("date","Date"),("description","Libellé"),
                                         ("type","Type"),("amount","Montant"),("mode","Mode")))
        status,status_content=panel(overview,"Statut des clients","♟")
        status.grid(row=1,column=2,sticky="nsew",padx=3,pady=3)
        self.financial_center_status=status_content
        accounts,accounts_content=panel(overview,"Situation des comptes (détail)","▤")
        accounts.grid(row=2,column=0,sticky="nsew",padx=3,pady=3)
        tree_for(accounts_content,"accounts",(("account","Compte"),("in","Entrées"),
                                             ("out","Sorties"),("balance","Solde période")),height=3)
        summary,summary_content=panel(overview,"Synthèse du mois","◕")
        summary.grid(row=2,column=1,sticky="nsew",padx=3,pady=3)
        tree_for(summary_content,"summary",(("rubric","Rubrique"),("amount","Montant")),height=5)
        fast,fast_content=panel(overview,"Actions rapides","ϟ")
        fast.grid(row=2,column=2,sticky="nsew",padx=3,pady=3)
        for i,(label,cmd,color) in enumerate((("Nouvelle charge",self.open_new_charge_form,GREEN),
                      ("Nouveau règlement",lambda:self.show_page("receivables"),BLUE),
                      ("Saisir une créance",lambda:self.show_page("receivables"),ORANGE),
                      ("Saisir une traite",lambda:self.show_page("checks"),PURPLE),
                      ("Transfert banque → caisse",lambda:self._open_center_expenses("BANQUE"),BLUE),
                      ("Imprimer rapport",self._print_financial_center,"#546c83"))):
            fast_content.grid_columnconfigure(i%2,weight=1)
            action(fast_content,label,cmd,color).grid(row=i//2,column=i%2,sticky="ew",padx=2,pady=3)
        detail_box,detail_content=panel(detail,"Détail de la période","▤")
        detail_box.pack(fill="both",expand=True,padx=3,pady=3)
        self.financial_center_detail_title=detail_box.winfo_children()[0]
        self.financial_center_detail_content=detail_content
        self.financial_center_bank_actions=tk.Frame(detail_content,bg="#e8f3ff")
        action(self.financial_center_bank_actions,"＋  Versement · caisse → banque",
               lambda:self.open_versements("VERSEMENT BANQUE"),GREEN).pack(side="left",padx=5,pady=5)
        action(self.financial_center_bank_actions,"−  Retrait · banque → caisse",
               lambda:self.open_versements("RETRAIT BANQUE"),RED).pack(side="left",padx=5,pady=5)
        action(self.financial_center_bank_actions,"↻  Actualiser",self._refresh_financial_center,BLUE).pack(side="right",padx=5,pady=5)
        self.financial_center_detail_tree=tree_for(detail_content,"detail",(("date","Date"),("reference","Référence"),
                                          ("name","Libellé / client"),("type","Type"),
                                          ("amount","Montant MAD"),("status","Statut / mode")),height=18)
        self.financial_center_balance=tk.Frame(detail_content,bg=BG)
        tk.Button(self.financial_center_balance,text="▤  Détail de la production par contrat",
                  command=self._open_center_production_detail,bg=BLUE,fg="white",bd=0,
                  font=("Segoe UI",9,"bold"),pady=6).pack(anchor="e",padx=7,pady=(4,0))
        self.financial_center_balance_rows={}
        columns=tk.Frame(self.financial_center_balance,bg=BG)
        columns.pack(fill="x")
        for side,title,color,labels in (("debit","DÉBIT",BLUE,("Banque","Caisse","Créances clients","Charges","Chèques reçus à venir","TOTAL DÉBIT")),
                                        ("credit","CRÉDIT",PURPLE,("Chiffre d’affaires","Alimentation de caisse","Traites / échéances à venir","TOTAL CRÉDIT"))):
            block=tk.Frame(columns,bg="white",highlightbackground=EDGE,highlightthickness=1)
            block.pack(side="left",fill="both",expand=True,padx=4,pady=5)
            tk.Label(block,text=title,bg=color,fg="white",font=("Segoe UI",13,"bold"),pady=9).pack(fill="x")
            for label in labels:
                informative=label in ("Traites / échéances à venir","Chèques reçus à venir")
                line=tk.Frame(block,bg="#fff1ae" if informative else "#e8f3ff" if label.startswith("TOTAL") else "white")
                line.pack(fill="x",padx=9,pady=3)
                tk.Label(line,text=label,bg=line.cget("bg"),fg="#865b08" if informative else TEXT,
                         font=("Segoe UI",10,"bold" if informative or label.startswith("TOTAL") else "normal"),anchor="w").pack(side="left",padx=7,pady=5)
                value=tk.StringVar(master=page,value="0,00 MAD")
                tk.Label(line,textvariable=value,bg=line.cget("bg"),fg="#865b08" if informative else color,
                         font=("Segoe UI",10,"bold"),anchor="e").pack(side="right",padx=7)
                self.financial_center_balance_rows[label]=value
        self.financial_center_result=tk.StringVar(master=page)
        self.financial_center_result_label=tk.Label(self.financial_center_balance,textvariable=self.financial_center_result,bg="#e6faef",fg=GREEN,font=("Segoe UI",11,"bold"),pady=12)
        self.financial_center_result_label.pack(fill="x",padx=5,pady=5)
        self.financial_center_savings=tk.StringVar(master=page,value="VISION ÉPARGNE : journée de passage · hors production")
        tk.Label(self.financial_center_balance,textvariable=self.financial_center_savings,bg="#fff1ae",fg="#805500",
                 font=("Segoe UI",10,"bold"),anchor="w",padx=12,pady=8).pack(fill="x",padx=5,pady=3)
        self.financial_center_balance_indicators={}
        indicators=tk.Frame(self.financial_center_balance,bg=BG)
        indicators.pack(fill="x",padx=4,pady=3)
        for index,(key,title) in enumerate((("supplier_payable","Dettes fournisseurs"),("versements","Versements nets"),
                                             ("client_cheques","Règlements par chèque"),("charge_cash","Charges espèces"),
                                             ("charge_cheques","Charges banque / chèques"),("credit_j10","Échéances ≤ 10 jours"))):
            row,column=divmod(index,3)
            indicators.grid_columnconfigure(column,weight=1,uniform="balance_info")
            box=tk.Frame(indicators,bg="#edf3ff",highlightbackground=EDGE,highlightthickness=1)
            box.grid(row=row,column=column,sticky="ew",padx=3,pady=2)
            tk.Label(box,text=title,bg="#edf3ff",fg=TEXT,font=("Segoe UI",8,"bold"),anchor="w").pack(fill="x",padx=8,pady=(7,1))
            variable=tk.StringVar(master=page,value="0,00 MAD")
            tk.Label(box,textvariable=variable,bg="#edf3ff",fg=PURPLE,font=("Segoe UI",11,"bold"),anchor="w").pack(fill="x",padx=8,pady=(0,7))
            self.financial_center_balance_indicators[key]=variable
        self.financial_center_pending_title=tk.StringVar(master=page,value="TRAITES ET ÉCHÉANCES EN ATTENTE · informatif, hors solde")
        tk.Label(self.financial_center_balance,textvariable=self.financial_center_pending_title,bg="#fff0db",fg="#8b5310",
                 font=("Segoe UI",10,"bold"),anchor="w",padx=12,pady=7).pack(fill="x",padx=5,pady=(7,2))
        pending_area=tk.Frame(self.financial_center_balance,bg=BG)
        pending_area.pack(fill="both",expand=True,padx=5,pady=(0,5))
        self.financial_center_pending_tree=ttk.Treeview(pending_area,columns=("date","reference","nature","amount","status"),
                                                        show="headings",height=5)
        for key,label,width in (("date","Date prévue",105),("reference","Référence",115),
                                ("nature","Traite / échéance",265),("amount","Montant MAD",130),
                                ("status","Statut",170)):
            self.financial_center_pending_tree.heading(key,text=label)
            self.financial_center_pending_tree.column(key,width=width,minwidth=85,stretch=True,anchor="w")
        pending_scroll=ttk.Scrollbar(pending_area,orient="vertical",command=self.financial_center_pending_tree.yview)
        self.financial_center_pending_tree.configure(yscrollcommand=pending_scroll.set)
        self.financial_center_pending_tree.pack(side="left",fill="both",expand=True)
        pending_scroll.pack(side="right",fill="y")
        self._select_financial_center_tab("Aperçu général")
        from financial_reference_ui import build
        return build(self)

    def _select_financial_center_tab(self,tab):
        if getattr(self,"financial_reference_enabled",False):
            from financial_reference_ui import select
            return select(self,{"Aperçu général":"Vue globale","Bilan global":"Vue globale","Crédit / Échéance":"Crédits / Échéances"}.get(tab,tab))
        self.financial_center_tab=tab
        if tab=="Banque":self.financial_center_bank_actions.pack(fill="x",before=self.financial_center_detail_tree.master)
        else:self.financial_center_bank_actions.pack_forget()
        for label,control in self.financial_center_buttons.items():
            control.configure(bg=BLUE if label==tab else "#e6f2ff",fg="white" if label==tab else TEXT)
        self.financial_center_panels[0 if tab=="Aperçu général" else 1].tkraise()
        if tab!="Aperçu général":
            self.financial_center_detail_title.configure(text=f"▤   {tab} · {self.financial_center_month.get()} {self.financial_center_year.get()}")
            if tab=="Bilan global":
                self.financial_center_detail_tree.master.pack_forget()
                self.financial_center_balance.pack(fill="both",expand=True)
            else:
                self.financial_center_balance.pack_forget()
                self.financial_center_detail_tree.master.pack(fill="both",expand=True)
            self._refresh_financial_center_detail()

    def _open_center_expenses(self,tab):
        self.show_page("expenses")
        if hasattr(self,"expense_finance_tab"):self._expense_reference_select(tab)

    def _open_center_production_detail(self):
        start,end=self._center_period()
        win=self._secondary_window(self.root)
        win.title(f"Production des contrats · {self.financial_center_month.get()} {self.financial_center_year.get()}")
        win.geometry("1050x560");win.configure(bg=BG)
        tk.Label(win,text="CHIFFRE D’AFFAIRES RÉPARTI PAR JOUR DE LOCATION",bg=DEEP,fg="white",
                 font=("Segoe UI",13,"bold"),pady=12).pack(fill="x")
        columns=("contract","departure","return","days","production")
        tree=ttk.Treeview(win,columns=columns,show="headings")
        for key,label,width in (("contract","Contrat",130),("departure","Départ",120),
                                ("return","Retour",120),("days","Jours du mois",130),
                                ("production","CA du mois (MAD)",190)):
            tree.heading(key,text=label);tree.column(key,width=width,stretch=True,anchor="center")
        tree.pack(fill="both",expand=True,padx=13,pady=12)
        total=0.0;savings_total=0.0
        for row in self.conn.execute("SELECT numero,date_depart,date_retour,duree,montant FROM contracts"):
            share=self._contract_period_share(row[1],row[2],row[3],start,end)
            gap=self._contract_boundary_share(row[1],row[2],row[3],end)
            if share<=0 and gap<=0:continue
            first=self._parse_french_date(row[1]);last=self._parse_french_date(row[2])
            days=max(1,(last.date()-first.date()).days) if first and last and last>first else max(1,int(row[3] or 1))
            if share:
                amount=self._number(row[4])*share;total+=amount
                tree.insert("","end",values=(row[0],row[1],row[2],f"{round(share*days)} / {days}",money(amount)))
            if gap:
                saved=self._number(row[4])*gap;savings_total+=saved
                tree.insert("","end",values=(row[0],"Vision épargne",(end+timedelta(days=1)).strftime("%d/%m/%Y"),
                                              f"1 / {days} · hors CA",money(saved)))
        tk.Label(win,text=f"PRODUCTION DU MOIS : {money(total)} MAD",bg="#e6faef",fg=GREEN,
                 font=("Segoe UI",12,"bold"),anchor="e",padx=16,pady=10).pack(fill="x",padx=13,pady=(0,12))
        tk.Label(win,text=f"VISION ÉPARGNE · HORS PRODUCTION : {money(savings_total)} MAD",bg="#fff1ae",fg="#805500",
                 font=("Segoe UI",10,"bold"),anchor="e",padx=16,pady=5).pack(fill="x",padx=13,pady=(0,8))

    def _center_period(self):
        year=int(self.financial_center_year.get())
        month=MONTHS.index(self.financial_center_month.get())+1
        start=datetime(year,month,1)
        end=(datetime(year+1,1,1) if month==12 else datetime(year,month+1,1))-timedelta(microseconds=1)
        return start,end

    def _open_center_card_sources(self, key):
        """Écritures détaillées qui alimentent les six cartes du mois choisi."""
        start,end=self._center_period()
        titles={"revenue":"Chiffre d’affaires du mois","cash":"Caisse","bank":"Banque","receivables":"Créances clients",
                "expenses":"Charges du mois","drafts":"Traites à venir","savings":"Vision épargne"}
        if key=="cash_funding":
            from cash_funding import open_funding
            open_funding(self);return
        if key not in titles:return
        if key=='drafts':
            self._sync_pending_drafts();self._sync_hbz_credit_monthly_bank()
            upcoming=self._draft_period_info_rows(start,end)
            entries=[(date,ref,"Traite / échéance · "+str(party),label,float(amount))
                     for date,ref,party,label,amount,status in upcoming]
            self._center_card_dialog(key,titles[key],entries)
            return
        entries=[]
        def add(date,reference,source,description,value):
            if abs(value)>0.00001:entries.append((str(date),str(reference),str(source),str(description),float(value)))
        if key in ("revenue","cash","bank","receivables","savings"):
            modes,payments=self._contract_payment_parts()
            for row in self.conn.execute("SELECT numero,client_code,date_depart,date_retour,duree,montant,reglement FROM contracts"):
                ref,client,departure,arrival,duration=row[:5]
                amount=max(0,self._number(row[5]));paid=min(amount,max(0,self._number(row[6])))
                cash,bank=payments.get(str(ref),(0.0,0.0));detail=cash+bank
                if detail>paid and detail:cash*=paid/detail;bank*=paid/detail
                initial=max(0,paid-cash-bank)
                mode=modes.get(str(ref),"ESPÈCES")
                if any(token in mode for token in ("CHÈQUE","CHEQUE","BANQUE","VIREMENT","CARTE")):bank+=initial
                else:cash+=initial
                allocated=self._contract_allocated_parts(departure,arrival,duration,amount,cash,bank,start,end,
                                                         savings=key=="savings")
                portion=dict(zip(("savings" if key=="savings" else "revenue","cash","bank","receivables"),allocated))[key]
                date=(end+timedelta(days=1)).strftime("%d/%m/%Y") if key=="savings" else departure
                client_row=self.conn.execute("SELECT nom,prenom FROM clients WHERE code=?",(client,)).fetchone()
                client_name=" ".join(str(x or "") for x in client_row) if client_row else str(client)
                add(date,ref,f"Contrat · {client_name} · client {client}","Journée épargne · hors chiffre d’affaires" if key=="savings" else "Production répartie sur le mois",portion)
        if key in ("cash","bank","expenses","drafts"):
            for ref,payload,_ in (self._center_charge_rows(start,end) if key=="expenses" else self._center_bank_rows(start,end)):
                amount=self._number(payload.get("amount"));status=str(payload.get("status","")).upper()
                category=str(payload.get("category","")).upper()
                source=payload.get("party") or category or "Produits & charges"
                description=payload.get("description") or category
                if key=="drafts" and status=="EN ATTENTE" and category in ("TRAITE BANCAIRE","CRÉDIT HBZ / ÉCHÉANCE"):
                    add(payload.get("date"),ref,source,description+" · en attente",amount)
                if status in ("EN ATTENTE","ANNULÉ","ANNULE","REJETÉ","REJETE"):continue
                received=str(payload.get("direction","")).upper() in ("REÇU","RECU")
                if received and payload.get("source_check"):
                    if key=="bank":add(payload.get("date"),ref,source,description,amount)
                    continue
                if str(payload.get("type","")).upper()!="CHARGE":continue
                if self._is_production_draft(payload):
                    due=self._parse_french_date(payload.get("date",""))
                    if due is None or due.date()>datetime.now().date():continue
                if key=="expenses" and category not in ("RÈGLEMENT FOURNISSEUR","CRÉDIT HBZ / MENSUALITÉ"):
                    add(payload.get("date"),ref,source,description,amount)
                mode=str(payload.get("payment_method","")).upper()
                if key=="cash" and "ESP" in mode:add(payload.get("date"),ref,source,description,-amount)
                if key=="bank" and any(x in mode for x in ("CHÈQUE","CHEQUE","BANQUE")):
                    add(payload.get("date"),ref,source,description,-amount)
            if key in ("cash","bank","expenses"):
                for ref,payload,_ in self._center_rows("maintenance",start,end):
                    amount=max(0,self._number(payload.get("amount")))
                    mode=str(payload.get("payment_method","")).upper()
                    if key=="expenses" or key=="cash" and "ESP" in mode or key=="bank" and ("CHÈQUE" in mode or "CHEQUE" in mode):
                        add(payload.get("date"),ref,"Entretien véhicule",payload.get("description") or payload.get("type") or "Intervention",amount if key=="expenses" else -amount)
            if key in ("cash","bank"):
                for ref,payload,_ in self._center_rows("transfers",start,end):
                    amount=self._number(payload.get("amount"));withdraw="RETRAIT" in str(payload.get("mode","")).upper()
                    sign=(1 if withdraw else -1) if key=="cash" else (-1 if withdraw else 1)
                    add(payload.get("date"),ref,"Transfert interne",payload.get("mode") or "Versement",sign*amount)
        if key=="cash":
            from cash_funding import rows as funding_rows
            for ref,q,d in funding_rows(self,start,end):add(q['date'],ref,q['source'],'Alimentation de caisse · hors production',float(q['amount']))
        if key=="expenses":self._center_charge_categories(entries)
        else:self._center_card_dialog(key,titles[key],entries)

    def _center_charge_categories(self,entries):
        groups=defaultdict(list)
        for entry in entries:
            record=self._center_source_record("expenses",entry)
            category=str(record["payload"].get("category") or ("Entretien" if record["module"]=="maintenance" else entry[2]) or "Autres").strip()
            aliases={"PERSONNEL":"Personnel","SALAIRE":"Personnel","SALAIRES":"Personnel","ENTRETIEN":"Entretien","ENTRETIEN VÉHICULE":"Entretien","ASSURANCE":"Assurance","EXPLOITATION":"Exploitation","AUTRES":"Autres","DIVERS":"Autres"}
            category=aliases.get(category.upper(),category)
            groups[category].append(entry)
        win=self._secondary_window(self.root);win.title("Charges détaillées par rubrique");win.geometry("850x580");win.minsize(650,440);win.configure(bg=BG)
        tk.Label(win,text="▧  CHARGES PAR RUBRIQUE",bg=DEEP,fg="white",font=("Segoe UI",17,"bold"),padx=18,pady=16,anchor="w").pack(fill="x")
        tk.Label(win,text=f"{self.financial_center_month.get()} {self.financial_center_year.get()} · Charges exécutées uniquement",bg=BG,fg=TEXT,font=("Segoe UI",10),pady=10).pack(fill="x")
        footer=tk.Frame(win,bg=BG);footer.pack(side="bottom",fill="x",padx=14,pady=12)
        tk.Label(win,text="TOTAL CHARGES : "+money(sum(entry[4] for entry in entries))+" MAD",bg="#e8f3fc",fg=DEEP,font=("Segoe UI",12,"bold"),pady=10).pack(side="bottom",fill="x")
        table=ttk.Treeview(win,columns=("category","count","amount"),show="headings",selectmode="browse")
        for key,title,width in (("category","Rubrique",400),("count","Nombre",90),("amount","Montant MAD",180)):
            table.heading(key,text=title);table.column(key,width=width,anchor="w" if key=="category" else "e")
        table.pack(fill="both",expand=True,padx=14,pady=8)
        order=sorted(groups,key=str.casefold)
        for index,category in enumerate(order):table.insert("","end",iid=str(index),values=(category,len(groups[category]),money(sum(e[4] for e in groups[category]))))
        def detail():
            selection=table.selection()
            if selection:
                category=order[int(selection[0])];self._center_card_dialog("expenses","Charges · "+category,groups[category])
        detail_button=self._center_action_button(footer,"▤  Voir le détail",detail,BLUE);detail_button.pack(side="left",padx=4);detail_button.configure(state="disabled")
        table.bind("<<TreeviewSelect>>",lambda event:detail_button.configure(state="normal" if table.selection() else "disabled"))
        table.bind("<Double-1>",lambda event:detail())
        self._center_action_button(footer,"＋  Ajout charge",lambda:self.show_page("add_charge"),GREEN).pack(side="left",padx=4)
        self._center_action_button(footer,"×  Fermer",win.destroy,"#64748b").pack(side="right")

    def _center_source_record(self, key, entry):
        date,ref,source,description,amount=entry
        record={"date":date,"reference":ref,"source":source,"description":description,
                "amount":amount,"party":"—","module":None,"payload":{},"remaining":0.0}
        contract=self.conn.execute("SELECT client_code,montant,reglement FROM contracts WHERE numero=?",(ref,)).fetchone()
        if contract and source.startswith("Contrat"):
            record["module"]="contract"
            code=str(contract[0] or "")
            client=self.conn.execute("SELECT nom,prenom FROM clients WHERE code=?",(code,)).fetchone()
            name=" ".join(str(v or "").strip() for v in client).strip() if client else ""
            record["party"]=(name+" · "+code) if name else "Client "+code
            record["source"]="Contrat de location"
            record["remaining"]=max(0,self._number(contract[1])-self._number(contract[2]))
        else:
            row=self.conn.execute("SELECT module,payload FROM module_records WHERE record_id=?",(ref,)).fetchone()
            if key=="drafts" and "Traite —" in description:
                matches=[]
                for rid,raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='checks'"):
                    try:q=json.loads(raw)
                    except (ValueError,TypeError):continue
                    if str(q.get("number") or rid)==ref and str(q.get("due_date"))==date:
                        matches.append((rid,raw))
                if len(matches)==1:
                    record["reference"]=matches[0][0];row=("checks",matches[0][1])
                else:row=None
            elif key=="drafts" and "HBZ Crédit" in description:
                row=None;record["module"]="hbz_credit"
            if row:
                try:payload=json.loads(row[1])
                except (ValueError,TypeError):payload={}
                record["module"],record["payload"]=row[0],payload
                party=payload.get("party") or payload.get("supplier") or payload.get("client") or payload.get("customer_name") or "—"
                client=self.conn.execute("SELECT nom,prenom FROM clients WHERE code=?",(str(party),)).fetchone()
                record["party"]=" ".join(str(v or "") for v in client).strip()+" · "+str(party) if client else str(party)
                record["source"]={"expenses":"Produits & charges","maintenance":"Entretien véhicule","transfers":"Transfert interne","checks":"Chèque / traite"}.get(row[0],source)
            elif key=="drafts":
                record["party"]=source.removeprefix("Traite / échéance · ")
                record["source"]="Crédit / échéance"
        record["status"]="À venir · informatif, hors solde" if key=="drafts" else (
            "Hors production" if key=="savings" else record["payload"].get("status") or ("Reste à régler" if key=="receivables" else "Comptabilisé"))
        return record

    def _center_open_source(self, record):
        module=record["module"];ref=record["reference"];payload=record["payload"]
        if module=="hbz_credit":
            self._open_hbz_credit_target("credits",ref);return
        if module=="contract":
            self.open_quick_contract_dialog(contract_number=ref);return
        # Les écritures automatiques se modifient depuis leur origine.
        if payload.get("source_check"):
            module="checks";ref=str(payload["source_check"])
            row=self.conn.execute("SELECT payload FROM module_records WHERE module=? AND record_id=?",(module,ref)).fetchone()
            if not row:return
            payload=json.loads(row[0])
        elif str(payload.get("category","")).upper().startswith("CRÉDIT HBZ"):
            self._open_hbz_credit_target("credits");return
        elif payload.get("source_recurring_charge"):
            self.open_recurring_charges();return
        if module not in getattr(self,"module_vars",{}):return
        self.show_page(module)
        for label,field in self.module_fields[module]:
            self.module_vars[module][field].set(payload.get(field,""))
        first=self.module_fields[module][0][1]
        self.module_vars[module][first].set(ref)

    def _center_action_button(self,parent,text,command,color):
        button=tk.Button(parent,text=text,command=command,bg=color,fg="white",
                         activebackground=DEEP,activeforeground="white",disabledforeground="#e0e7ef",
                         relief="flat",bd=0,font=("Segoe UI",10,"bold"),padx=14,pady=10,cursor="hand2")
        return button

    def _center_export_visible(self,win,tree,headers,title):
        path=filedialog.asksaveasfilename(parent=win,title="Exporter les lignes affichées",defaultextension=".csv",
                                         filetypes=(("Tableau CSV · Excel","*.csv"),))
        if not path:return
        try:
            with open(path,"w",encoding="utf-8-sig",newline="") as output:
                writer=csv.writer(output,delimiter=";");writer.writerow(headers)
                for item in tree.get_children():writer.writerow(tree.item(item,"values"))
        except OSError as error:
            messagebox.showerror("Export impossible",str(error),parent=win);return
        messagebox.showinfo("Export terminé","Les lignes affichées ont été exportées.",parent=win)

    def _center_card_dialog(self,key,title,entries):
        records=[self._center_source_record(key,entry) for entry in entries]
        win=self._secondary_window(self.root);win.title("Origine des données — "+title)
        win.update_idletasks()
        width=min(1240,max(680,win.winfo_screenwidth()-80))
        height=min(720,max(500,win.winfo_screenheight()-110))
        win.geometry(f"{width}x{height}");win.minsize(min(760,width),min(560,height));win.configure(bg=BG)
        win.columnconfigure(0,weight=1)
        win.rowconfigure(4,weight=1)
        # Seul le tableau s'étire : le pied d'actions garde sa place.

        accent={"revenue":BLUE,"cash":GREEN,"bank":BLUE,"receivables":ORANGE,"expenses":RED,"drafts":PURPLE,"savings":"#aa7a17"}.get(key,BLUE)
        icons={"revenue":"▥","cash":"▣","bank":"▤","receivables":"♟","expenses":"▧","drafts":"◷","savings":"◇"}
        header=tk.Frame(win,bg=DEEP);header.grid(row=0,column=0,sticky="ew")
        tk.Label(header,text=icons.get(key,"▤"),bg=accent,fg="white",font=("Segoe UI",25,"bold"),width=3,pady=10).pack(side="left",padx=(18,10),pady=14)
        heading=tk.Frame(header,bg=DEEP);heading.pack(side="left",fill="x",expand=True)
        tk.Label(heading,text=title,bg=DEEP,fg="white",font=("Segoe UI",18,"bold"),anchor="w").pack(fill="x")
        tk.Label(heading,text=f"Centre financier  /  {self.financial_center_month.get()} {self.financial_center_year.get()}",bg=DEEP,fg="#c6ddf4",font=("Segoe UI",10),anchor="w").pack(fill="x",pady=3)
        metrics=tk.Frame(win,bg=BG);metrics.grid(row=1,column=0,sticky="ew",padx=12,pady=(8,3))
        for label,value in (("TOTAL DES ÉCRITURES",money(sum(r["amount"] for r in records))+" MAD"),("NOMBRE DE LIGNES",str(len(records))),("PÉRIMÈTRE","Informatif · hors solde" if key=="drafts" else "Hors production" if key=="savings" else "Mois sélectionné")):
            card=tk.Frame(metrics,bg=CARD,highlightbackground=EDGE,highlightthickness=1);card.pack(side="left",fill="x",expand=True,padx=4)
            tk.Label(card,text=label,bg=CARD,fg=TEXT,font=("Segoe UI",8),anchor="w").pack(fill="x",padx=12,pady=(9,3))
            tk.Label(card,text=value,bg=CARD,fg=accent,font=("Segoe UI",12,"bold"),anchor="w").pack(fill="x",padx=12,pady=(0,10))
        tk.Label(win,text="Échéances à venir : information uniquement, aucun débit avant exécution." if key=="drafts" else
                 "Vision épargne : hors production du mois." if key=="savings" else "Origine des écritures comprises dans la carte · sélectionnez une ligne pour agir",
                 bg=BG,fg=TEXT,anchor="w",padx=16,pady=4,wraplength=660).grid(row=2,column=0,sticky="ew")
        toolbar=tk.Frame(win,bg=BG);toolbar.grid(row=3,column=0,sticky="ew",padx=12,pady=4)
        tk.Label(toolbar,text="⌕  Rechercher :",bg=BG,fg=TEXT).pack(side="left")
        query=tk.StringVar();ttk.Entry(toolbar,textvariable=query,width=25).pack(side="left",fill="x",expand=True,padx=8)
        box=tk.Frame(win,bg=BG);box.grid(row=4,column=0,sticky="nsew",padx=12,pady=6)
        columns=("date","reference","source","party","description","amount","status")
        style=ttk.Style(win)
        style.configure("FinanceDetail.Treeview",rowheight=32,font=("Segoe UI",10),background=CARD,fieldbackground=CARD,foreground=TEXT,borderwidth=0)
        style.configure("FinanceDetail.Treeview.Heading",font=("Segoe UI",10,"bold"),padding=(8,10))
        style.map("FinanceDetail.Treeview",background=[("selected",DEEP)],foreground=[("selected","white")])
        tree=ttk.Treeview(box,columns=columns,show="headings",selectmode="browse",style="FinanceDetail.Treeview")
        tree.tag_configure("even",background="#f0f6fc");tree.tag_configure("odd",background=CARD)
        for column,label,width in zip(columns,("Date","Référence","Source","Client / organisme","Détail","Montant MAD","Statut"),(105,115,160,210,250,130,200)):
            tree.heading(column,text=label);tree.column(column,width=width,minwidth=80,anchor="e" if column=="amount" else "w",stretch=False)
        vertical=ttk.Scrollbar(box,orient="vertical",command=tree.yview)
        horizontal=ttk.Scrollbar(box,orient="horizontal",command=tree.xview)
        tree.configure(yscrollcommand=vertical.set,xscrollcommand=horizontal.set)
        tree.grid(row=0,column=0,sticky="nsew");vertical.grid(row=0,column=1,sticky="ns");horizontal.grid(row=1,column=0,sticky="ew")
        box.rowconfigure(0,weight=1);box.columnconfigure(0,weight=1)
        summary=tk.StringVar()
        tk.Label(win,textvariable=summary,bg="#e8f3fc",fg=DEEP,font=("Segoe UI",11,"bold"),anchor="e",padx=12,pady=6,wraplength=660).grid(row=5,column=0,sticky="ew",padx=12)
        actions=tk.Frame(win,bg=BG);actions.grid(row=7,column=0,sticky="ew",padx=12,pady=(4,10))
        for column in range(3):actions.columnconfigure(column,weight=1,uniform="finance_actions")
        def selected():
            ids=tree.selection()
            return records[int(ids[0])] if ids else None
        def open_source():
            record=selected()
            if record:self._center_open_source(record)
        def pay():
            record=selected()
            if record and record["module"]=="contract" and record["remaining"]>.005:
                self.open_receivable_payment(contract_number=record["reference"],on_saved=refresh)
        edit=self._center_action_button(actions,"✎  Ouvrir / modifier",open_source,ORANGE);edit.grid(row=0,column=0,sticky="ew",padx=4,pady=3)
        payment=self._center_action_button(actions,"＋  Règlement client",pay,GREEN);payment.grid(row=0,column=1,sticky="ew",padx=4,pady=3)
        selection_text=tk.StringVar(value="Sélectionnez une ligne pour ouvrir son origine ou enregistrer un règlement.")
        tk.Label(win,textvariable=selection_text,bg=BG,fg=TEXT,font=("Segoe UI",9),anchor="w",padx=16,pady=4,wraplength=660).grid(row=6,column=0,sticky="ew")
        def selection_changed(*_):
            record=selected()
            edit.configure(state="normal" if record and record["module"] else "disabled")
            payment.configure(state="normal" if record and record["module"]=="contract" and record["remaining"]>.005 else "disabled")
            selection_text.set(f"Sélection : {record['reference']} · {record['party']} · {money(record['amount'])} MAD" if record else "Sélectionnez une ligne pour activer les actions disponibles.")
        def populate(*_):
            tree.delete(*tree.get_children());needle=query.get().casefold().strip();visible=[]
            for index,record in enumerate(records):
                if needle and needle not in " ".join(str(record[c]) for c in columns).casefold():continue
                visible.append(record)
                tree.insert("","end",iid=str(index),tags=("even" if len(visible)%2==0 else "odd",),values=tuple(money(record[c])+" MAD" if c=="amount" else record[c] for c in columns))
            summary.set(f"{len(visible)} ligne(s) · Total affiché : {money(sum(r['amount'] for r in visible))} MAD · Total de la liste : {money(sum(r['amount'] for r in records))} MAD")
            selection_changed()
        def refresh():
            self._refresh_financial_center()
            win.destroy();self._open_center_card_sources(key)
        self._center_action_button(actions,"×  Fermer",win.destroy,"#64748b").grid(row=1,column=2,sticky="ew",padx=4,pady=3)
        self._center_action_button(actions,"↻  Actualiser",refresh,BLUE).grid(row=1,column=0,sticky="ew",padx=4,pady=3)
        self._center_action_button(actions,"▥  Exporter CSV",lambda:self._center_export_visible(win,tree,("Date","Référence","Source","Client / organisme","Détail","Montant MAD","Statut"),title),PURPLE).grid(row=1,column=1,sticky="ew",padx=4,pady=3)
        self._center_action_button(toolbar,"×  Effacer",lambda:query.set(""),"#64748b").pack(side="left",padx=6)
        tree.bind("<<TreeviewSelect>>",selection_changed);tree.bind("<Double-1>",lambda event:open_source())
        query.trace_add("write",populate);populate()

    def _center_rows(self,module,start,end):
        result=[]
        for reference,raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module=? ORDER BY created_at DESC",(module,)):
            try:payload=json.loads(raw)
            except (ValueError,TypeError):continue
            stamp=self._parse_french_date(payload.get("date") or payload.get("due_date") or "")
            if stamp and start<=stamp<=end:result.append((reference,payload,stamp))
        return result

    def _center_bank_rows(self,start,end):
        rows=[]
        for ref,raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='expenses' ORDER BY created_at DESC"):
            try:payload=json.loads(raw)
            except (ValueError,TypeError):continue
            if self._expense_bank_in_period(payload,start,end):
                rows.append((ref,payload,self._parse_french_date(payload.get('date','')) or start))
        return rows

    def _center_charge_rows(self,start,end):
        rows=[]
        for ref,raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='expenses' ORDER BY created_at DESC"):
            try:p=json.loads(raw)
            except (ValueError,TypeError):continue
            if self._expense_charge_in_period(p,start,end):
                rows.append((ref,p,self._parse_french_date(p.get('date','')) or start))
        return rows

    def _refresh_financial_center(self):
        if not hasattr(self,"financial_center_cards"):return
        self._sync_pending_drafts()
        self._sync_hbz_credit_monthly_bank()
        start,end=self._center_period()
        totals=self._financial_totals(start,end)
        expenses=self._center_charge_rows(start,end)
        checks=self._center_rows("checks",start,end)
        payments=self._center_rows("payments",start,end)
        transfers=self._center_rows("transfers",start,end)
        charges=[(rid,p,d) for rid,p,d in expenses if p.get("type","").upper()=="CHARGE" and p.get("status","").upper()!="EN ATTENTE" and p.get("category","").upper() not in ("RÈGLEMENT FOURNISSEUR","CRÉDIT HBZ / MENSUALITÉ")]
        maintenance=self._center_rows("maintenance",start,end)
        # Même source que Produits & charges : les effets et crédits restent
        # informatifs jusqu'à leur vraie date d'exécution.
        pending=[(ref,{'amount':amount},self._parse_french_date(date))
                 for date,ref,party,label,amount,status in self._draft_period_info_rows(start,end)]
        set_card=lambda key,val,subtitle:(self.financial_center_cards[key][0].set(f"{money(val)} MAD"),self.financial_center_cards[key][1].set(subtitle))
        set_card("revenue",totals["revenue"],"Contrats · production du mois sélectionné")
        set_card("cash",totals["cash"],f"Entrées du mois : {money(totals['cash']+totals['charge_cash']+max(0,totals['versements']))}")
        set_card("cash_funding",totals["cash_funding"],"Apports hors production · cliquez pour saisir")
        set_card("bank",totals["bank"],f"Versements : {money(totals['versements'])} MAD")
        receivables=[r for r in self.conn.execute("SELECT montant,reglement,date_depart,date_retour,duree FROM contracts")
                     if self._number(r[0])-self._number(r[1])>0.005
                     and self._contract_period_share(r[2],r[3],r[4],start,end)>0]
        set_card("receivables",totals["receivables"],f"Non réglées : {len(receivables)}")
        set_card("expenses",totals["expenses"],f"Nombre : {len(charges)+len(maintenance)}")
        set_card("drafts",sum(max(0,self._number(p.get("amount"))) for _,p,_ in pending),f"Nombre : {len(pending)} · informatif")
        set_card("savings",totals["savings_future"],
                 f"Caisse {money(totals['savings_cash'])} · Banque {money(totals['savings_bank'])} · Créances {money(totals['savings_receivables'])}")
        self.financial_center_chart_data=[]
        for month in range(1,13):
            first=datetime(start.year,month,1)
            last=(datetime(start.year+1,1,1) if month==12 else datetime(start.year,month+1,1))-timedelta(microseconds=1)
            monthly=self._financial_totals(first,last)
            self.financial_center_chart_data.append((monthly["cash"],monthly["bank"],monthly["receivables"]))
        categories=defaultdict(float)
        for rid,p,d in charges:categories[str(p.get("category") or "Autres")]+=self._number(p.get("amount"))
        for rid,p,d in maintenance:
            categories["Entretien véhicule"]+=self._number(p.get("amount"))
        self.financial_center_categories=sorted(categories.items(),key=lambda item:item[1],reverse=True)
        self._draw_financial_center_charts()
        self._center_draw_top()
        self._center_draw_status(start,end)
        self._center_fill_tree("accounts",[("Caisse",money(totals["cash"]+totals["charge_cash"]),money(totals["charge_cash"]),money(totals["cash"])),
                                          ("Banque",money(totals["bank"]+totals["charge_cheques"]),money(totals["charge_cheques"]),money(totals["bank"])),
                                          ("Créances clients",money(totals["revenue"]),money(totals["revenue"]-totals["receivables"]),money(totals["receivables"]))])
        self._center_fill_tree("summary",[("Chiffre d’affaires",money(totals["revenue"])),
                                         ("Charges",money(totals["expenses"])),
                                         ("Résultat du mois",money(totals["result"]))])
        today=datetime.now().date();due=[]
        for rid,raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='checks'"):
            try:p=json.loads(raw)
            except (ValueError,TypeError):continue
            date=self._parse_french_date(p.get("due_date",""))
            if not date or not today<date.date()<=today+timedelta(days=10) or p.get("status","").upper()!="EN ATTENTE":continue
            if p.get("type","").upper() in ("CHÈQUE","CHEQUE") and date.date()>today+timedelta(days=3):continue
            due.append((date.strftime("%d/%m/%Y"),p.get("type",""),rid,money(self._number(p.get("amount"))),"En attente"))
        for rid,raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='expenses'"):
            try:p=json.loads(raw)
            except (ValueError,TypeError):continue
            if p.get("category","").upper()!="CRÉDIT HBZ / ÉCHÉANCE" or p.get("status","").upper()!="EN ATTENTE":continue
            date=self._parse_french_date(p.get("date",""))
            if date and today<date.date()<=today+timedelta(days=10)  :
                due.append((date.strftime("%d/%m/%Y"),"Crédit",rid,money(self._number(p.get("amount"))),"En attente"))
        for number,return_date,amount,paid in self.conn.execute("SELECT numero,date_retour,montant,reglement FROM contracts"):
            date=self._parse_french_date(return_date or "")
            remaining=max(0,self._number(amount)-self._number(paid))
            if date and today<=date.date()<=today+timedelta(days=10) and remaining>0.005:
                due.append((date.strftime("%d/%m/%Y"),"Créance client",number,money(remaining),"À relancer"))
        self._center_fill_tree("due",sorted(due,key=lambda r:datetime.strptime(r[0],"%d/%m/%Y"))[:5])
        recent=[]
        for rid,p,d in charges:recent.append((d.strftime("%d/%m/%Y"),p.get("description") or p.get("category") or rid,"Charge","−"+money(self._number(p.get("amount"))),p.get("payment_method","")))
        for rid,p,d in payments:recent.append((d.strftime("%d/%m/%Y"),p.get("customer_name") or "Règlement client","Créance","+"+money(self._number(p.get("amount"))),p.get("mode","")))
        for rid,p,d in transfers:recent.append((d.strftime("%d/%m/%Y"),p.get("mode") or "Transfert","Banque",money(self._number(p.get("amount"))),"Transfert"))
        recent.sort(key=lambda r:datetime.strptime(r[0],"%d/%m/%Y"),reverse=True)
        self._center_fill_tree("recent",recent[:5])
        self._refresh_financial_center_detail()
        from financial_reference_ui import refresh
        refresh(self,totals)

    def _center_fill_tree(self,key,rows):
        tree=self.financial_center_tables[key]
        tree.delete(*tree.get_children())
        for row in rows:tree.insert("","end",values=row)

    def _center_draw_top(self):
        area=self.financial_center_top
        for child in area.winfo_children():child.destroy()
        colors=(GREEN,ORANGE,"#43bc4e",RED,PURPLE)
        for i,(name,amount) in enumerate(self.financial_center_categories[:5]):
            row=tk.Frame(area,bg=CARD);row.pack(fill="x",pady=3)
            widgets=(tk.Label(row,text=str(i+1),bg=colors[i],fg="white",font=("Segoe UI",9,"bold"),width=3,pady=4),
                     tk.Label(row,text=name,bg=CARD,fg=TEXT,font=("Segoe UI",8),anchor="w",wraplength=120),
                     tk.Label(row,text=money(amount),bg=CARD,fg=TEXT,font=("Segoe UI",8,"bold")))
            widgets[0].pack(side="left",padx=3)
            widgets[1].pack(side="left",fill="x",expand=True)
            widgets[2].pack(side="right",padx=4)
            for widget in (row,)+widgets:
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>",lambda _event,category=name:self._open_center_top_charge(category))
        if not self.financial_center_categories:tk.Label(area,text="Aucune charge pour la période",bg=CARD,fg=TEXT).pack(pady=19)

    def _center_draw_status(self,start,end):
        area=self.financial_center_status
        for child in area.winfo_children():child.destroy()
        rows=self._receivable_rows(status="TOUS",month=MONTHS[start.month-1],year=str(start.year))
        rows+=self._receivable_rows(status="TOUS",month=MONTHS[start.month-1],year=str(start.year),only_insolvent=True)
        grouped=defaultdict(list)
        for record in rows:grouped[str(record["client"])].append(record)
        today=datetime.now().date()
        groups={"Clients à jour":[],"En retard (< 30 j)":[],"En retard (≥ 30 j)":[]}
        for client,contracts in grouped.items():
            unpaid=[record for record in contracts if record["balance"]>.005]
            delays=[(today-self._parse_french_date(record["end"]).date()).days for record in unpaid
                    if self._parse_french_date(record["end"])]
            category="En retard (≥ 30 j)" if any(delay>=30 for delay in delays) else (
                "En retard (< 30 j)" if any(delay>0 for delay in delays) else "Clients à jour")
            groups[category].extend(contracts)
        self.financial_center_client_groups=groups
        for title,color,soft in (("Clients à jour",GREEN,"#e7f9ef"),
                                 ("En retard (< 30 j)",ORANGE,"#fff2e1"),
                                 ("En retard (≥ 30 j)",RED,"#ffe7eb")):
            row=tk.Frame(area,bg=soft);row.pack(fill="x",pady=4)
            count=tk.Label(row,text=str(len({record['client'] for record in groups[title]})),bg=color,fg="white",font=("Segoe UI",15,"bold"),width=3,pady=4)
            label=tk.Label(row,text=title,bg=soft,fg=TEXT,font=("Segoe UI",8),wraplength=125)
            count.pack(side="left",padx=5);label.pack(side="left",fill="x",expand=True)
            for widget in (row,count,label):
                widget.configure(cursor="hand2")
                widget.bind("<Button-1>",lambda _event,group=title:self._open_center_client_status(group))

    def _open_center_source_list(self,title,headers,entries):
        win=self._secondary_window(self.root);win.title(title);win.geometry("980x560");win.minsize(720,400)
        tk.Label(win,text=title,bg=DEEP,fg="white",font=("Segoe UI",14,"bold"),padx=16,pady=11,anchor="w").pack(fill="x")
        actions=tk.Frame(win,bg=BG);actions.pack(side="bottom",fill="x",padx=12,pady=(0,12))
        box=tk.Frame(win,bg=CARD);box.pack(fill="both",expand=True,padx=12,pady=12)
        columns=tuple(str(i) for i in range(len(headers)))
        tree=ttk.Treeview(box,columns=columns,show="headings")
        for key,label in zip(columns,headers):tree.heading(key,text=label);tree.column(key,width=145,anchor="w")
        bar=ttk.Scrollbar(box,orient="vertical",command=tree.yview)
        tree.configure(yscrollcommand=bar.set);tree.pack(side="left",fill="both",expand=True);bar.pack(side="right",fill="y")
        tree.tag_configure("alternate",background="#eef5fc")
        for i,entry in enumerate(entries):tree.insert("","end",values=entry,tags=("alternate",) if i%2 else ())
        if not entries:tree.insert("","end",values=("Aucune donnée pour ce mois",)+("",)*(len(headers)-1))

        self._center_action_button(actions,"×  Fermer",win.destroy,"#64748b").pack(side="right")
        self._center_action_button(actions,"▥  Exporter CSV",lambda:self._center_export_visible(win,tree,headers,title),PURPLE).pack(side="right",padx=8)

    def _open_center_top_charge(self,category):
        start,end=self._center_period();entries=[]
        for ref,p,date in self._center_charge_rows(start,end):
            if (str(p.get("type","")).upper()!="CHARGE" or str(p.get("status","")).upper()=="EN ATTENTE"
                    or str(p.get("category") or "Autres")!=category):continue
            entries.append((date.strftime("%d/%m/%Y"),ref,p.get("party") or "—",p.get("description") or category,
                            f"{money(self._number(p.get('amount')))} MAD"))
        if category=="Entretien véhicule":
            for ref,p,date in self._center_rows("maintenance",start,end):
                entries.append((date.strftime("%d/%m/%Y"),ref,p.get("supplier") or p.get("vehicle") or "—",
                                p.get("description") or "Entretien",f"{money(self._number(p.get('amount')))} MAD"))
        self._open_center_source_list(f"Charges · {category} · {self.financial_center_month.get()} {self.financial_center_year.get()}",
                                      ("Date","Référence","Fournisseur / source","Description","Montant"),entries)

    def _open_center_client_status(self,category):
        entries=[(row.get("end",row.get("period","")),str(row["contract"]),"Contrat de location",
                  "Créance client · "+str(row.get("period","")),float(row["balance"]))
                 for row in self.financial_center_client_groups.get(category,[])]
        self._center_card_dialog("receivables",category,entries)

    def _draw_financial_center_charts(self):
        if not hasattr(self,"financial_center_chart_data"):return
        canvas=self.financial_center_chart
        if not canvas.winfo_exists():return
        canvas.delete("all")
        width=max(320,canvas.winfo_width());height=max(175,canvas.winfo_height())
        left,right,top,bottom=45,width-12,30,height-28
        for index,(label,color) in enumerate((("Caisse",GREEN),("Banque",BLUE),("Créances",ORANGE))):
            x=left+index*105
            canvas.create_rectangle(x,6,x+12,18,fill=color,outline="")
            canvas.create_text(x+17,12,text=label,anchor="w",fill=TEXT,font=("Segoe UI",8))
        series=self.financial_center_chart_data
        maximum=max(1.0,*(max(0,v) for row in series for v in row))*1.12
        for i in range(5):
            y=bottom-(bottom-top)*i/4
            canvas.create_line(left,y,right,y,fill="#d7e6f4")
            canvas.create_text(left-5,y,text=f"{maximum*i/4:,.0f}".replace(","," "),anchor="e",fill=TEXT,font=("Segoe UI",7))
        for i in range(12):
            x=left+(right-left)*i/11
            canvas.create_line(x,top,x,bottom,fill="#e8f0f8")
            canvas.create_text(x,bottom+12,text=MONTHS[i][:3],fill=TEXT,font=("Segoe UI",7))
        for index,color in enumerate((GREEN,BLUE,ORANGE)):
            points=[]
            for i,values in enumerate(series):
                x=left+(right-left)*i/11;y=bottom-max(0,values[index])/maximum*(bottom-top)
                points.extend((x,y))
                canvas.create_oval(x-3,y-3,x+3,y+3,fill=color,outline=color)
            canvas.create_line(*points,fill=color,width=2,smooth=True)
        donut=self.financial_center_donut
        if not donut.winfo_exists():return
        donut.delete("all")
        w=max(250,donut.winfo_width());h=max(175,donut.winfo_height())
        size=min(h-28,w*.53);x=8;y=(h-size)/2
        total=sum(value for _,value in self.financial_center_categories)
        palette=(BLUE,ORANGE,GREEN,RED,PURPLE,"#859ab3")
        if total>0:
            angle=90
            for i,(name,value) in enumerate(self.financial_center_categories):
                extent=360*value/total
                donut.create_arc(x,y,x+size,y+size,start=angle,extent=extent,fill=palette[i%len(palette)],outline=CARD,width=2)
                angle+=extent
            inset=size*.27
            donut.create_oval(x+inset,y+inset,x+size-inset,y+size-inset,fill=CARD,outline=CARD)
        else:donut.create_oval(x,y,x+size,y+size,fill="#e8f0f8",outline="")
        donut.create_text(x+size/2,y+size/2,text=f"{money(total)}\nMAD",fill=TEXT,font=("Segoe UI",10,"bold"),justify="center")
        for i,(name,value) in enumerate(self.financial_center_categories[:6]):
            yy=24+i*25
            donut.create_oval(size+21,yy-4,size+31,yy+6,fill=palette[i%len(palette)],outline="")
            donut.create_text(size+37,yy,text=name[:19],anchor="w",fill=TEXT,font=("Segoe UI",7))
            donut.create_text(w-7,yy,text=f"{value/total:.0%}",anchor="e",fill=TEXT,font=("Segoe UI",7,"bold"))

    def _refresh_financial_center_detail(self):
        if not hasattr(self,"financial_center_tab"):return
        tab=self.financial_center_tab
        if tab=="Aperçu général":return
        start,end=self._center_period()
        self._sync_pending_drafts()
        self._sync_hbz_credit_monthly_bank()
        rows=[]
        target={"Caisse":("payments","transfers","cash_funding"),"Banque":("payments","transfers","expenses"),
                "Créances clients":(),"Produits & charges":("expenses","maintenance"),
                "Chèques / Traites":("checks",),"Crédit / Échéance":("expenses",),
                "Bilan global":()}.get(tab,())
        if tab=="Créances clients":
            for record in self.conn.execute("SELECT numero,client_code,date_depart,date_retour,duree,montant,reglement FROM contracts"):
                amount=max(0,self._number(record[5]))
                paid=min(amount,max(0,self._number(record[6])))
                production,settled,_,due=self._contract_allocated_parts(
                    record[2],record[3],record[4],amount,paid,0,start,end)
                if due>0.005:
                    departure=self._parse_french_date(record[2])
                    period_date=max(start.date(),departure.date()) if departure else start.date()
                    rows.append((period_date.strftime("%d/%m/%Y"),record[0],record[1],
                                 f"Créance du mois · CA {money(production)} · réglé {money(settled)}",
                                 money(due),"À régler"))
        for module in target:
            for rid,p,date in (self._center_charge_rows(start,end) if module=="expenses" and tab=="Produits & charges" else self._center_rows(module,start,end)):
                kind=str(p.get("type") or p.get("category") or module)
                if tab=="Crédit / Échéance" and "CRÉDIT" not in kind.upper() and "ÉCHÉANCE" not in str(p.get("category","")).upper():continue
                if tab=="Banque" and module=="expenses" and "ESP" in str(p.get("payment_method","")).upper():continue
                if tab=="Caisse" and module=="payments" and "CHÈQUE" in str(p.get("mode","")).upper():continue
                status=p.get("status") or p.get("payment_method") or p.get("mode") or "—"
                if module=="expenses" and str(status).upper()=="EN ATTENTE":status="En attente · informatif"
                rows.append((date.strftime("%d/%m/%Y"),rid,p.get("description") or p.get("client") or p.get("party") or p.get("supplier_name") or p.get("mode") or "—",kind,money(self._number(p.get("amount") or p.get("total"))),status))
        if tab=="Bilan global":
            totals=self._financial_totals(start,end)
            self.financial_center_savings.set(
                f"VISION ÉPARGNE : {money(totals['savings_future'])} MAD · journée de passage, hors production  |  "
                f"Caisse : {money(totals['savings_cash'])}  ·  Banque : {money(totals['savings_bank'])}  ·  "
                f"Créances : {money(totals['savings_receivables'])}")
            self.financial_center_balance_indicators["credit_j10"].set(f"{money(self._hbz_credit_due_10d_total())} MAD")
            for key in ("supplier_payable","versements","client_cheques","charge_cash","charge_cheques"):
                self.financial_center_balance_indicators[key].set(f"{money(totals[key])} MAD")
            # J−3 à la veille : information du cycle 6→5, sans débit anticipé.
            waiting=[(self._parse_french_date(date),reference,
                      {'amount':amount,'description':f'{label} — {party}'})
                     for date,reference,party,label,amount,status in self._draft_period_info_rows(start,end)]
            received_info=self._draft_period_info_rows(start,end,received_checks=True)
            self.financial_center_balance_rows['Chèques reçus à venir'].set(f"{money(sum(r[4] for r in received_info))} MAD · informatif")
            emitted_total=sum(self._number(p.get('amount')) for _,_,p in waiting)
            waiting.extend((self._parse_french_date(d),ref,{'amount':amount,'description':f'{label} — {party} · DÉBIT INFORMATIF'}) for d,ref,party,label,amount,status in received_info)
            waiting.sort(key=lambda item:item[0])
            self.financial_center_balance_rows["Traites / échéances à venir"].set(
                f"{money(emitted_total)} MAD · informatif")
            self.financial_center_pending_tree.delete(*self.financial_center_pending_tree.get_children())
            for date,reference,p in waiting:
                days=(date.date()-datetime.now().date()).days
                status="Prête à exécuter · hors solde" if 0<days<=3 else (
                    "En attente · date dépassée" if days<0 else "En attente · hors solde")
                self.financial_center_pending_tree.insert("","end",values=(date.strftime("%d/%m/%Y"),reference,
                    p.get("description") or p.get("category") or "Échéance",money(self._number(p.get("amount"))),
                    status))
            self.financial_center_pending_title.set(
                f"TRAITES ET ÉCHÉANCES EN ATTENTE · {len(waiting)} effet(s) · "
                f"{money(sum(self._number(p.get('amount')) for _,_,p in waiting))} MAD · informatif, hors solde")
            for label,key in (("Banque","bank"),("Caisse","cash"),("Créances clients","receivables"),
                              ("Charges","expenses"),("TOTAL DÉBIT","debit"),
                              ("Chiffre d’affaires","revenue"),("Alimentation de caisse","cash_funding"),("TOTAL CRÉDIT","credit")):
                self.financial_center_balance_rows[label].set(f"{money(totals[key])} MAD")
            self.financial_center_result_label.configure(fg=RED if totals["result"]<0 else GREEN,bg="#ffe4e9" if totals["result"]<0 else "#e6faef")
            self.financial_center_result.set(
                f"RÉSULTAT : CA − CHARGES = {money(totals['result'])} MAD    ·    ÉCART DÉBIT / CRÉDIT : {money(totals['balance_gap'])} MAD\nDÉFICIT RESTANT À COUVRIR APRÈS ALIMENTATION : {money(totals['deficit_remaining'])} MAD")
            # Reprendre les mêmes montants que la synthèse Produits & charges.
            rows=[("", "CA", "Chiffre d’affaires", "Crédit",money(totals["revenue"]),"Comptabilisé"),
                  ("", "BANQUE", "Solde bancaire de la période", "Débit",money(totals["bank"]),"Comptabilisé"),
                  ("", "CAISSE", "Solde de caisse de la période", "Débit",money(totals["cash"]),"Comptabilisé"),
                  ("", "CRÉANCES", "Reste à encaisser", "Débit",money(totals["receivables"]),"Comptabilisé"),
                  ("", "CHARGES", "Charges exécutées", "Débit",money(totals["expenses"]),"Comptabilisé"),
                  ("", "TOTAL DÉBIT", "Banque + caisse + créances + charges", "Synthèse",money(totals["debit"]),"Comptabilisé"),
                  ("", "ALIMENTATION", "Apports hors production", "Crédit",money(totals["cash_funding"]),"Comptabilisé"),
                  ("", "TOTAL CRÉDIT", "Chiffre d’affaires + alimentation", "Synthèse",money(totals["credit"]),"Comptabilisé"),
                  ("", "RÉSULTAT", "CA − charges", "Synthèse",money(totals["result"]),"Comptabilisé"),
                  ("", "TRAITES À VENIR", "Effets du cycle 6→5 visibles dès J−3", "Prévision",money(emitted_total),"Informatif · crédit · hors solde"),
                  ("", "ÉCHÉANCES ≤ 10 J", "Échéances proches", "Prévision",
                   money(self._pending_drafts_total(10)),"Informatif · hors solde")]
        if tab=='Bilan global':
            rows.extend((d,ref,label+' — '+party,'Débit',money(amount),'Informatif · hors solde') for d,ref,party,label,amount,status in received_info)
        rows.sort(key=lambda r:self._parse_french_date(r[0]) or datetime.min,reverse=True)
        self._center_fill_tree("detail",rows)

    def _print_financial_center(self):
        start,end=self._center_period()
        self._print_financial_summary(self._financial_totals(start,end),start.strftime("%d/%m/%Y"),end.strftime("%d/%m/%Y"))

    def _export_financial_center(self):
        self._sync_pending_drafts()
        self._sync_hbz_credit_monthly_bank()
        start,end=self._center_period()
        totals=self._financial_totals(start,end)
        path=filedialog.asksaveasfilename(defaultextension=".xlsx",initialfile=f"centre_financier_{start:%Y_%m}.xlsx",
                filetypes=[("Excel","*.xlsx"),("CSV","*.csv")])
        if not path:return
        rows=[("Caisse",totals["cash"]),("Banque",totals["bank"]),("Créances clients",totals["receivables"]),
              ("Charges",totals["expenses"]),("Produits / CA",totals["revenue"]),
              ("Résultat",totals["result"]),("Traites et crédits à venir (informatif)",sum(max(0,self._number(p.get("amount")))
                for _,p,_ in self._center_rows("expenses",start,end) if p.get("category","").upper() in ("TRAITE BANCAIRE","CRÉDIT HBZ / ÉCHÉANCE") and p.get("status","").upper()=="EN ATTENTE"))]
        self._write_tabular_file(path,["Rubrique",f"Montant ({start:%m/%Y})"],rows)
