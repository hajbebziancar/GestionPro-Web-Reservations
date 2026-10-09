"""Fiche fournisseur HBZ : interface dédiée basée sur la maquette fournie."""
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


BLUE="#0785df"
DEEP="#075398"
PALE="#e6f4ff"
BG="#f2f9ff"
EDGE="#c9e0f2"
INK="#102b57"
GREEN="#12a95a"
AMBER="#ff9d10"
RED="#f23948"
PURPLE="#9339ec"


def _open_local(path):
    if sys.platform == "win32":os.startfile(str(path))
    elif sys.platform == "darwin":subprocess.Popen(["open",str(path)])
    else:webbrowser.open(path.as_uri())


class SupplierReferenceMixin:
    def _build_supplier_reference_page(self,name,title,fields):
        if not hasattr(self,"module_vars"):
            self.module_vars,self.module_trees,self.module_fields={},{},{}
        page=self._new_page(name)
        self.module_fields[name]=fields
        self.module_vars[name]={key:tk.StringVar(master=page) for _label,key in fields}
        variables=self.module_vars[name]
        self.supplier_image_label=None
        self.supplier_image_cache=None

        def button(parent,text,command,color=BLUE,**kw):
            return tk.Button(parent,text=text,command=command,bg=color,fg="white",activebackground=color,
                activeforeground="white",bd=0,relief="flat",font=("Segoe UI",9,"bold"),
                cursor="hand2",padx=10,pady=7,**kw)

        def section(parent,title,icon="▣"):
            outer=tk.Frame(parent,bg="white",highlightthickness=1,highlightbackground=EDGE)
            tk.Label(outer,text=f"{icon}   {title}",bg=BLUE,fg="white",anchor="w",padx=12,
                     font=("Segoe UI",10,"bold"),pady=8).pack(fill="x")
            inside=tk.Frame(outer,bg="white")
            inside.pack(fill="both",expand=True,padx=11,pady=8)
            return outer,inside

        def field(parent,label,key,row,col,kind="entry",choices=(),span=1):
            tk.Label(parent,text=label,bg="white",fg=INK,anchor="w",font=("Segoe UI",8,"bold")).grid(
                row=row*2,column=col,columnspan=span,sticky="ew",padx=4,pady=(2,1))
            if kind=="multiline":
                widget=tk.Text(parent,height=3,font=("Segoe UI",9),bg="#f7fbff",fg=INK,
                               wrap="word",relief="solid",bd=1)
                updating=[False]
                def from_variable(*_):
                    value=variables[key].get()
                    if widget.get("1.0","end-1c")==value:return
                    updating[0]=True;widget.delete("1.0","end");widget.insert("1.0",value);updating[0]=False
                def from_widget(_event=None):
                    if not updating[0]:variables[key].set(widget.get("1.0","end-1c"))
                variables[key].trace_add("write",from_variable)
                widget.bind("<KeyRelease>",from_widget)
                widget.bind("<FocusOut>",from_widget)
                from_variable()
            elif kind=="combo":
                widget=ttk.Combobox(parent,textvariable=variables[key],values=choices,
                                    state="readonly",style="GP.TCombobox")
            else:
                widget=ttk.Entry(parent,textvariable=variables[key],style="GP.TEntry")
            widget.grid(row=row*2+1,column=col,columnspan=span,sticky="ew",padx=4,pady=(1,5),ipady=2)
            if key=="registration_date":self._attach_date_picker(widget,variables[key])
            return widget

        def selected_code():return variables["reference"].get().strip()
        def stored_supplier():
            code=selected_code()
            row=self.conn.execute("SELECT payload FROM module_records WHERE module='suppliers' AND record_id=?",(code,)).fetchone()
            return bool(row)
        def require_saved():
            if stored_supplier():return True
            messagebox.showinfo("Fournisseur","Enregistrez ou sélectionnez d’abord le fournisseur.")
            return False
        def documents_dir():
            # Le code provient du fournisseur enregistré, jamais d'un chemin utilisateur.
            code=re.sub(r"[^A-Za-z0-9_-]","_",selected_code())
            return Path(__file__).resolve().parent/"assets"/"supplier_documents"/code
        def safe_filename(original):
            src=Path(original)
            stem="".join(c if c.isalnum() or c in "-_" else "_" for c in src.stem)[:70] or "document"
            return stem+src.suffix.lower()

        def redraw_photo(*_):
            label=self.supplier_image_label
            if label is None:return
            image_path=variables["photo_path"].get().strip()
            path=Path(image_path)
            if image_path and not path.is_absolute():path=Path(__file__).resolve().parent/path
            try:
                from PIL import Image,ImageTk
                with Image.open(path) as source:
                    picture=source.copy();picture.thumbnail((180,115),Image.Resampling.LANCZOS)
                self.supplier_image_cache=ImageTk.PhotoImage(picture)
                label.configure(image=self.supplier_image_cache,text="",compound="center")
            except (OSError,ImportError,ValueError):
                self.supplier_image_cache=None
                label.configure(image="",text="▣\nIMAGE DU FOURNISSEUR")

        def choose_photo():
            if not require_saved():return
            source=filedialog.askopenfilename(title="Image du fournisseur",filetypes=[("Images","*.png *.jpg *.jpeg *.webp"),("Tous les fichiers","*.*")])
            if not source:return
            target_dir=documents_dir();target_dir.mkdir(parents=True,exist_ok=True)
            target=target_dir/("fournisseur"+Path(source).suffix.lower())
            try:
                if Path(source).resolve()!=target.resolve():shutil.copy2(source,target)
                rel=str(target.relative_to(Path(__file__).resolve().parent))
                variables["photo_path"].set(rel)
                self.conn.execute("UPDATE module_records SET payload=json_set(payload,'$.photo_path',?) WHERE module='suppliers' AND record_id=?",(rel,selected_code()))
                self.conn.commit();redraw_photo()
            except (OSError,ValueError) as exc:messagebox.showerror("Image fournisseur",str(exc))

        def clear_photo():
            if not require_saved():return
            variables["photo_path"].set("")
            self.conn.execute("UPDATE module_records SET payload=json_set(payload,'$.photo_path','') WHERE module='suppliers' AND record_id=?",(selected_code(),))
            self.conn.commit();redraw_photo()

        def import_document():
            if not require_saved():return
            source=filedialog.askopenfilename(title="Importer un document fournisseur",filetypes=[("Documents","*.pdf *.png *.jpg *.jpeg *.docx"),("Tous les fichiers","*.*")])
            if not source:return
            folder=documents_dir();folder.mkdir(parents=True,exist_ok=True)
            target=folder/safe_filename(source)
            if target.exists() and Path(source).resolve()!=target.resolve():
                target=folder/(target.stem+"_"+datetime.now().strftime("%H%M%S")+target.suffix)
            try:
                if Path(source).resolve()!=target.resolve():shutil.copy2(source,target)
                refresh_documents()
            except OSError as exc:messagebox.showerror("Documents fournisseur",str(exc))

        def open_folder():
            if not require_saved():return
            folder=documents_dir();folder.mkdir(parents=True,exist_ok=True)
            _open_local(folder)

        def print_supplier():
            if not require_saved():return
            name_value=variables["company_name"].get()
            from html import escape
            labels=(("Code fournisseur","reference"),("Nom","company_name"),("Téléphone","phone"),
                    ("Adresse","address"),("Ville","city"),("Email","email"),("Banque","bank"),
                    ("RIB","bank_account"))
            rows="".join(f"<tr><th>{escape(label)}</th><td>{escape(variables[key].get())}</td></tr>" for label,key in labels)
            path=Path(__file__).resolve().parent/"exports"/("fiche_fournisseur_"+selected_code()+".html")
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("<html><meta charset='utf-8'><style>body{font-family:Arial;margin:45px;color:#102b57}h1{color:#0785df}td,th{padding:12px;border-bottom:1px solid #c9e0f2;text-align:left}</style>"+
                f"<h1>HBZ Rent Car — Fiche fournisseur</h1><h2>{escape(name_value)}</h2><table>{rows}</table><script>window.onload=()=>window.print()</script></html>",encoding="utf-8")
            webbrowser.open(path.as_uri())

        header=tk.Frame(page,bg="#e3f2ff",height=85)
        header.pack(fill="x",padx=10,pady=(6,4));header.pack_propagate(False)
        logo=tk.Label(header,text="HBZ Rent Car",fg=DEEP,bg="#e3f2ff",font=("Segoe UI",16,"bold"))
        logo.pack(side="left",padx=(12,15))
        try:
            from PIL import Image,ImageTk
            path=self._company_logo_path()
            with Image.open(path) as image:
                logo_image=image.copy();logo_image.thumbnail((170,65),Image.Resampling.LANCZOS)
            self.supplier_logo_image=ImageTk.PhotoImage(logo_image)
            logo.configure(image=self.supplier_logo_image,text="")
        except (OSError,ImportError,AttributeError):pass
        tk.Label(header,text="▣  Fiche fournisseur\nInformations, documents et historique des transactions",
                 bg="#e3f2ff",fg=INK,justify="left",font=("Segoe UI",13,"bold")).pack(side="left",fill="x",expand=True)
        code_box=tk.Frame(header,bg="white",highlightthickness=1,highlightbackground=EDGE)
        code_box.pack(side="left",padx=6)
        tk.Label(code_box,text="Code fournisseur",bg="white",fg=INK,font=("Segoe UI",8,"bold")).pack(padx=8)
        tk.Label(code_box,textvariable=variables["reference"],bg="#fff471",fg=INK,
                 font=("Segoe UI",15,"bold"),width=8).pack(padx=7,pady=(2,5))
        toolbar=tk.Frame(header,bg="#e3f2ff");toolbar.pack(side="right",padx=7)
        def write_action(method):
            method("suppliers")
            refresh_list();refresh_meta()
        for text,method,color in (("▣ Nouveau",self.new_business_record,BLUE),
                                  ("▣ Enregistrer",self.save_business_record,BLUE),
                                  ("✎ Modifier",self.update_business_record,AMBER),
                                  ("▤ Supprimer",self.delete_business_record,RED)):
            button(toolbar,text,lambda fun=method:write_action(fun),color).pack(side="left",padx=2)
        button(toolbar,"✕ Fermer",lambda:self.show_page("dashboard"),"#496887").pack(side="left",padx=2)

        body=tk.Frame(page,bg=BG);body.pack(fill="both",expand=True,padx=10,pady=4)
        body.grid_columnconfigure(0,weight=1,minsize=245)
        body.grid_columnconfigure(1,weight=3,minsize=620)
        body.grid_rowconfigure(0,weight=1)
        left,left_inner=section(body,"Liste des fournisseurs","▣")
        left.grid(row=0,column=0,sticky="nsew",padx=(0,6))
        left_inner.grid_columnconfigure(0,weight=1);left_inner.grid_rowconfigure(1,weight=1)
        query=tk.StringVar(master=page)
        search=ttk.Entry(left_inner,textvariable=query,style="GP.TEntry")
        search.grid(row=0,column=0,sticky="ew",pady=(0,5),ipady=3)
        button(left_inner,"⌕",lambda:self.refresh_business_records(name,query.get()),BLUE).grid(row=0,column=1,padx=(3,0),pady=(0,5))
        query.trace_add("write",lambda *_:self.refresh_business_records(name,query.get()))
        columns=tuple(key for _,key in fields)
        tree=ttk.Treeview(left_inner,columns=columns,displaycolumns=("reference","company_name","phone"),
                          show="headings",selectmode="browse",height=13)
        tree.heading("reference",text="Code");tree.heading("company_name",text="Nom du fournisseur");tree.heading("phone",text="Téléphone")
        tree.column("reference",width=70,minwidth=55,anchor="center")
        tree.column("company_name",width=170,minwidth=95,anchor="w")
        tree.column("phone",width=105,minwidth=85,anchor="center")
        tree.grid(row=1,column=0,sticky="nsew")
        yscroll=ttk.Scrollbar(left_inner,orient="vertical",command=tree.yview)
        yscroll.grid(row=1,column=1,sticky="ns");tree.configure(yscrollcommand=yscroll.set)
        total=tk.StringVar(master=page,value="Total : 0 fournisseur(s)")
        tk.Label(left_inner,textvariable=total,bg="white",fg=INK,font=("Segoe UI",9,"bold")).grid(
            row=2,column=0,sticky="w",pady=9)
        self.module_trees[name]=tree

        right=tk.Frame(body,bg=BG);right.grid(row=0,column=1,sticky="nsew")
        right.grid_columnconfigure(0,weight=1);right.grid_rowconfigure(1,weight=1)
        tabs=tk.Frame(right,bg=BG);tabs.grid(row=0,column=0,sticky="ew")
        panels=tk.Frame(right,bg=BG);panels.grid(row=1,column=0,sticky="nsew")
        panels.grid_rowconfigure(0,weight=1);panels.grid_columnconfigure(0,weight=1)
        tab_buttons=[];tab_pages=[]
        def show_tab(index):
            tab_pages[index].tkraise()
            for i,tab in enumerate(tab_buttons):
                tab.configure(bg=DEEP if i==index else PALE,fg="white" if i==index else INK)
            if index==1:refresh_purchases()
            if index==2:refresh_payments()
            if index==3:refresh_documents()
        for i,(icon,label) in enumerate((("▤","Fiche fournisseur"),("🛒","Historique des achats"),
                                          ("▤","Règlements"),("📁","Documents"))):
            tab=button(tabs,f"{icon}  {label}",lambda n=i:show_tab(n),PALE)
            tab.configure(fg=INK,font=("Segoe UI",9,"bold"),pady=9)
            tab.pack(side="left",fill="x",expand=True,padx=(0,3))
            tab_buttons.append(tab)
            pane=tk.Frame(panels,bg=BG);pane.grid(row=0,column=0,sticky="nsew");tab_pages.append(pane)

        fiche=tab_pages[0]
        fiche.grid_columnconfigure(0,weight=3);fiche.grid_columnconfigure(1,weight=2)
        info,info_body=section(fiche,"1. Informations générales","♟")
        info.grid(row=0,column=0,sticky="nsew",padx=(0,6),pady=(5,5))
        info_body.grid_columnconfigure(1,weight=1);info_body.grid_columnconfigure(2,weight=1)
        preview=tk.Label(info_body,text="▣\nIMAGE DU FOURNISSEUR",bg=BG,fg=INK,
                         font=("Segoe UI",11,"bold"),width=19,height=7)
        preview.grid(row=0,column=0,rowspan=7,sticky="nsew",padx=(0,9))
        self.supplier_image_label=preview
        photo_actions=tk.Frame(info_body,bg="white");photo_actions.grid(row=7,column=0,sticky="ew")
        button(photo_actions,"▣ Image",choose_photo,BLUE).pack(side="left",fill="x",expand=True)
        button(photo_actions,"✕",clear_photo,RED).pack(side="left",padx=(3,0))
        field(info_body,"Code fournisseur *","reference",0,1)
        field(info_body,"Téléphone *","phone",0,2)
        field(info_body,"Nom fournisseur *","company_name",1,1)
        field(info_body,"Email","email",1,2)
        field(info_body,"Contact","contact_name",2,1)
        field(info_body,"Site web","website",2,2)
        address,address_body=section(fiche,"2. Adresse","⌂")
        address.grid(row=0,column=1,sticky="nsew",pady=(5,5))
        for col in range(3):address_body.grid_columnconfigure(col,weight=1)
        field(address_body,"Adresse complète *","address",0,0,kind="multiline",span=3)
        field(address_body,"Ville","city",1,0)
        field(address_body,"Code postal","postal_code",1,1)
        field(address_body,"Pays","country",1,2,kind="combo",choices=("Maroc","France","Espagne","Autre"))
        more,more_body=section(fiche,"3. Informations complémentaires","▤")
        more.grid(row=1,column=0,columnspan=2,sticky="nsew",pady=5)
        for col in range(4):more_body.grid_columnconfigure(col,weight=1)
        field(more_body,"Type de fournisseur","supplier_type",0,0,kind="combo",choices=("Entretien","Pièces détachées","Carburant","Assurance","Nettoyage","Autre"))
        field(more_body,"Catégorie","category",0,1,kind="combo",choices=("PIÈCES DÉTACHÉES","ENTRETIEN / MÉCANIQUE","CARBURANT","ASSURANCE","NETTOYAGE","AUTRE"))
        field(more_body,"Notes","notes",0,2,kind="multiline")
        field(more_body,"Statut","status",0,3,kind="combo",choices=("ACTIF","INACTIF","BLOQUÉ"))
        field(more_body,"Mode de paiement","payment_method",1,0,kind="combo",choices=("ESPÈCES","CHÈQUE","TRAITE","VIREMENT","CARTE"))
        field(more_body,"Délai de paiement (jours)","payment_delay",1,1)
        field(more_body,"Contact secondaire","contact_secondary",1,2)
        field(more_body,"Date d'enregistrement","registration_date",1,3)
        field(more_body,"Téléphone secondaire","phone_secondary",2,0)
        field(more_body,"ICE / IF","tax_id",2,1)
        field(more_body,"RC","trade_register",2,2)
        balance=tk.StringVar(master=page,value="Solde actuel : 0,00 MAD")
        tk.Label(more_body,textvariable=balance,bg=PALE,fg=INK,font=("Segoe UI",10,"bold"),
                 padx=6,pady=7).grid(row=5,column=3,sticky="ew",padx=4)
        bank,bank_body=section(fiche,"4. Informations bancaires","▥")
        bank.grid(row=2,column=0,columnspan=2,sticky="ew",pady=(5,0))
        for col in range(4):bank_body.grid_columnconfigure(col,weight=1)
        field(bank_body,"Banque","bank",0,0)
        field(bank_body,"RIB","bank_account",0,1)
        field(bank_body,"Titulaire du compte","account_holder",0,2)
        field(bank_body,"SWIFT","swift",0,3)

        purchases,purchases_body=section(tab_pages[1],"Historique des achats du fournisseur","🛒")
        purchases.pack(fill="both",expand=True,pady=(5,0))
        button(purchases_body,"＋ Nouvel achat",self.open_supplier_purchases,GREEN).pack(anchor="w",pady=(0,8))
        purchase_tree=ttk.Treeview(purchases_body,columns=("reference","date","description","total","status"),show="headings")
        for key,text,width in (("reference","Référence",105),("date","Date",100),("description","Désignation",250),("total","Montant MAD",125),("status","Statut",110)):
            purchase_tree.heading(key,text=text);purchase_tree.column(key,width=width,anchor="center")
        purchase_tree.pack(fill="both",expand=True)

        payments,payments_body=section(tab_pages[2],"Règlements du fournisseur","▤")
        payments.pack(fill="both",expand=True,pady=(5,0))
        button(payments_body,"＋ Nouveau règlement",self.open_supplier_payment,BLUE).pack(anchor="w",pady=(0,8))
        pay_tree=ttk.Treeview(payments_body,columns=("reference","date","amount","mode"),show="headings")
        for key,text,width in (("reference","Référence",125),("date","Date",110),("amount","Montant MAD",150),("mode","Mode",120)):
            pay_tree.heading(key,text=text);pay_tree.column(key,width=width,anchor="center")
        pay_tree.pack(fill="both",expand=True)

        docs,docs_body=section(tab_pages[3],"Documents du fournisseur","📁")
        docs.pack(fill="both",expand=True,pady=(5,0))
        doc_actions=tk.Frame(docs_body,bg="white");doc_actions.pack(anchor="w",pady=(0,8))
        button(doc_actions,"⇧ Importer document",import_document,PURPLE).pack(side="left",padx=(0,5))
        button(doc_actions,"📁 Ouvrir dossier",open_folder,BLUE).pack(side="left")
        doc_tree=ttk.Treeview(docs_body,columns=("file","size"),show="headings")
        doc_tree.heading("file",text="Document");doc_tree.heading("size",text="Taille")
        doc_tree.column("file",width=430);doc_tree.column("size",width=100,anchor="center")
        doc_tree.pack(fill="both",expand=True)
        def open_doc(_=None):
            if not doc_tree.selection():return
            path=documents_dir()/doc_tree.item(doc_tree.selection()[0],"values")[0]
            if path.is_file():_open_local(path)
        doc_tree.bind("<Double-1>",open_doc)
        button(docs_body,"◉ Ouvrir le document sélectionné",open_doc,DEEP).pack(anchor="w",pady=(7,0))

        quick=tk.Frame(page,bg=BG);quick.pack(fill="x",padx=10,pady=(1,8))
        tk.Label(quick,text="⚙   Actions rapides",bg=DEEP,fg="white",anchor="w",padx=12,
                 font=("Segoe UI",10,"bold"),pady=6).pack(fill="x")
        row=tk.Frame(quick,bg=BG);row.pack(fill="x",pady=(5,0))
        for text,command,color in (("🛒  Nouvel achat",self.open_supplier_purchases,GREEN),
                                   ("▤  Nouveau règlement",self.open_supplier_payment,BLUE),
                                   ("◴  Voir historique",lambda:show_tab(1),AMBER),
                                   ("⇧  Importer document",import_document,PURPLE),
                                   ("📁  Ouvrir dossier",open_folder,BLUE),
                                   ("▣  Imprimer fiche",print_supplier,"#496887")):
            button(row,text,command,color).pack(side="left",fill="x",expand=True,padx=3)

        def refresh_purchases():
            purchase_tree.delete(*purchase_tree.get_children())
            for rid,raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='supplier_purchases' ORDER BY created_at DESC"):
                try:p=json.loads(raw)
                except (ValueError,TypeError):continue
                if str(p.get("supplier",""))!=selected_code():continue
                purchase_tree.insert("","end",values=(rid,p.get("date",""),p.get("description",""),p.get("total",p.get("amount","")),p.get("status","")))

        def refresh_payments():
            pay_tree.delete(*pay_tree.get_children())
            for rid,raw in self.conn.execute("SELECT record_id,payload FROM module_records WHERE module='supplier_payments' ORDER BY created_at DESC"):
                try:p=json.loads(raw)
                except (ValueError,TypeError):continue
                if str(p.get("supplier",""))!=selected_code():continue
                pay_tree.insert("","end",values=(rid,p.get("date",""),p.get("amount",""),p.get("mode","")))

        def refresh_documents():
            doc_tree.delete(*doc_tree.get_children())
            if not stored_supplier():return
            folder=documents_dir()
            if folder.exists():
                for path in sorted(folder.iterdir()):
                    if path.is_file():doc_tree.insert("","end",values=(path.name,f"{path.stat().st_size/1024:.0f} Ko"))

        def refresh_meta():
            code=selected_code();purchases_total=payments_total=0.0
            if code:
                for module in ("supplier_purchases","supplier_payments"):
                    for (raw,) in self.conn.execute("SELECT payload FROM module_records WHERE module=?",(module,)):
                        try:p=json.loads(raw)
                        except (ValueError,TypeError):continue
                        if str(p.get("supplier",""))!=code:continue
                        amount=self._number(p.get("total") or p.get("amount"))
                        if module=="supplier_purchases":purchases_total+=amount
                        else:payments_total+=amount
            balance.set(f"Solde actuel : {max(0,purchases_total-payments_total):,.2f} MAD".replace(","," "))
            redraw_photo()
            if doc_tree.winfo_exists():refresh_documents()

        def refresh_list():
            self.refresh_business_records(name,query.get())
            count=self.conn.execute("SELECT COUNT(*) FROM module_records WHERE module='suppliers'").fetchone()[0]
            total.set(f"Total : {count} fournisseur(s)")

        def select_record(_=None):
            if tree.selection():self.select_business_record(name);refresh_meta()

        tree.bind("<<TreeviewSelect>>",select_record)
        variables["photo_path"].trace_add("write",redraw_photo)
        self.new_business_record(name)
        refresh_list();redraw_photo();show_tab(0)

    def _next_supplier_reference(self):
        existing={row[0] for row in self.conn.execute("SELECT record_id FROM module_records WHERE module='suppliers'")}
        number=1
        while f"F{number:04d}" in existing:number+=1
        return f"F{number:04d}"
