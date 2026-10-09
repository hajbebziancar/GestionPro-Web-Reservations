"""Fiche client HBZ, présentation compacte plein écran basée sur V240.12."""
import io
import json
import os
import re
import shutil
import subprocess
import sys
import webbrowser
from datetime import datetime
from pathlib import Path, PureWindowsPath
import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
from reference_widgets import image as ref_image, button as ref_button, section as ref_section, styles as ref_styles, entry as ref_entry, fit_page


BLUE="#005be5"
DARK="#0a3266"
BAR="#176aab"
BG="#eff7ff"
LINE="#c9e1f3"
GREEN="#008747"
ORANGE="#ed8200"
RED="#cd0035"
INK="#122b53"


def _index_existing_client_documents(app):
    """Associe les scans déjà présents aux clients de même code, sans doublons."""
    root=Path(app._client_documents_folder("_index",create=False)).parent
    if not root.is_dir():return 0
    known_codes={str(row[0]) for row in app.conn.execute("SELECT code FROM clients")}
    added=0;changed=False
    for folder in root.iterdir():
        if not folder.is_dir() or folder.name not in known_codes:continue
        existing={PureWindowsPath(row[1] or "").name.lower():row for row in app.conn.execute(
            "SELECT id,file_path FROM client_documents WHERE client_code=?",(folder.name,))}
        for path in folder.iterdir():
            if not path.is_file() or path.suffix.lower() not in (".pdf",".jpg",".jpeg",".png",".bmp",".tif",".tiff"):continue
            previous=existing.get(path.name.lower())
            if previous:
                if Path(previous[1] or "")!=path:
                    app.conn.execute("UPDATE client_documents SET file_path=? WHERE id=?",(str(path),previous[0]));changed=True
                continue
            stem=path.stem.upper()
            if stem.startswith("CIN_RECTO") or stem.startswith("CIN_1"):kind="CIN_RECTO"
            elif stem.startswith("CIN_VERSO") or stem.startswith("CIN_2"):kind="CIN_VERSO"
            elif stem.startswith("PERMIS_RECTO") or stem.startswith("PERMIS_1"):kind="PERMIS_RECTO"
            elif stem.startswith("PERMIS_VERSO") or stem.startswith("PERMIS_2"):kind="PERMIS_VERSO"
            elif stem.startswith("DOMICILE"):kind="DOMICILE"
            elif stem.startswith("PIECES_IDENTITE_FACES"):kind="AUTRE_FACES"
            else:kind="AUTRE"
            app.conn.execute("INSERT INTO client_documents(client_code,document_type,file_path,created_at) VALUES(?,?,?,?)",
                             (folder.name,kind,str(path),datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")))
            added+=1;changed=True
    if changed:app.conn.commit()
    return added


def _resolve_existing_client_document(app, client_code, raw_path):
    """Retrouve une pièce après déplacement ou réinstallation du dossier de l'app."""
    text=str(raw_path or "").strip()
    if not text:return None
    original=Path(text)
    if original.is_file():return original.resolve()
    candidate=app._client_documents_folder(client_code,create=False)/PureWindowsPath(text).name
    return candidate.resolve() if candidate.is_file() else None


def open_client_reference(app,on_select=None,container=None):
    _index_existing_client_documents(app)
    from client_mockup_ui import open_sheet
    return open_sheet(app,on_select,container)

    previous=getattr(app,"_client_reference_window",None)
    if previous is not None and previous.winfo_exists():
        previous._on_select=on_select
        if container is None:app.show_page("clients")
        return previous
    embedded=container is not None
    win=tk.Frame(container,bg=BG) if embedded else app._secondary_window(app.root)
    win._on_select=on_select
    app._client_reference_window=win
    win.configure(bg=BG)
    if embedded:
        win.pack(fill="both",expand=True)
    else:
        win.title("Fiche client HBZ Rent Car")
        width=max(760,min(1536,win.winfo_screenwidth()-28))
        height=max(560,min(960,win.winfo_screenheight()-65))
        win.geometry(f"{width}x{height}+{max(0,(win.winfo_screenwidth()-width)//2)}+{max(0,(win.winfo_screenheight()-height)//2)}")
        win.minsize(min(1040,width),min(650,height))
        win.transient(app.root)
        win.grab_set()
    win.grid_columnconfigure(0,weight=1)
    win.grid_rowconfigure(2,weight=1)
    values={k:tk.StringVar(master=win) for k in (
        "code cin nom prenom date_naissance age permis date_permis permis_age telephone adresse ville "
        "postal country email sexe profession workplace family references photo blocked date_enregistrement "
        "telephone2 cin_issued cin_place nationality emergency_name emergency_phone emergency_relation source").split()}
    _index_existing_client_documents(app)
    code=values["code"]
    selected_tab=tk.IntVar(master=win,value=0)
    photos={}
    preview_labels={}
    current_doc_ids={}
    other_document_rows=[]
    history_records={}

    ref_styles(win)
    profile_notes=[]
    def button(parent,title,command,color=BLUE,small=False):
        icons={"Nouveau":"new","Enregistrer":"save","Modifier":"edit","Supprimer":"delete","Fermer":"close","Scanner":"document","Importer":"document","Ajouter":"new"}
        icon=next((value for word,value in icons.items() if word in title),None)
        title=re.sub(r"^[^\wÀ-ÿ]+", "", title).strip() if re.search(r"[\wÀ-ÿ]",title) else title
        if title=="×":icon="delete"
        if title=="⌕":icon="search"
        if "photo" in title:icon="camera"
        return ref_button(parent,title,command,color,icon,small)

    def section(parent,title):
        clean=re.sub(r"^[^\wÀ-ÿ]+", "", title).strip()
        icon={"Liste des clients":"document","Informations générales":"client_general","Adresse et contact":"home","Informations complémentaires":"extra_section","Documents du client":"document"}.get(clean)
        return ref_section(parent,clean,icon,color=BAR)

    def field(parent,label,key,row,col,width=16):
        tk.Label(parent,text=label,bg="white",fg=INK,font=("Segoe UI",8,"bold"),anchor="w").grid(
            row=row*2,column=col,sticky="ew",padx=4,pady=(1,0) if embedded else (3,0))
        entry=tk.Entry(parent,textvariable=values[key],bg="white",fg=INK,relief="solid",bd=0,
                       highlightbackground=LINE,highlightthickness=1,font=("Segoe UI",10),width=width)
        entry.grid(row=row*2+1,column=col,sticky="ew",padx=4,pady=(1,2) if embedded else (2,5),ipady=2 if embedded else 5)
        if key in ("date_naissance","date_permis"):
            app._attach_date_picker(entry,values[key]);app._calendar_buttons[-1].configure(image=ref_image(win,"calendar",16),text="")
        return entry

    def close():
        if embedded:
            app.show_page("dashboard")
            return
        try:win.grab_release()
        except tk.TclError:pass
        win.destroy()
        app._client_reference_window=None
        if getattr(app,"current_page_name","")=="clients":app.show_page("dashboard")

    if not embedded:
        win.protocol("WM_DELETE_WINDOW",close)
        win.bind("<Escape>",lambda _event:close())

    # En-tête : logo réel, titre, code et actions, toujours visibles.
    header=tk.Frame(win,bg="#f2f9ff",height=72)
    header.grid(row=0,column=0,sticky="ew")
    header.grid_propagate(False)
    header.grid_columnconfigure(1,weight=1)
    logo=tk.Label(header,bg="#f2f9ff",image=ref_image(win,"client_title",54))
    logo.grid(row=0,column=0,padx=(12,10),pady=6)
    title=tk.Frame(header,bg="#f2f9ff");title.grid(row=0,column=1,sticky="ew")
    tk.Label(title,text="Fiche client",bg="#f2f9ff",fg="#112c65",anchor="w",
             font=("Segoe UI",19,"bold")).pack(anchor="w")
    tk.Label(title,text="Consultez et gérez les informations du client.",bg="#f2f9ff",fg=DARK,
             font=("Segoe UI",9)).pack(anchor="w")
    code_card=tk.Frame(header,bg="#fff0b3",highlightbackground=LINE,highlightthickness=1)
    code_card.grid(row=0,column=2,padx=8,pady=7)
    tk.Label(code_card,text="Code client",bg="#fff0b3",fg=INK,font=("Segoe UI",8,"bold")).pack(padx=9)
    tk.Label(code_card,textvariable=code,bg="#fff0b3",fg="#071e60",font=("Segoe UI",15,"bold"),
             width=7).pack(padx=7,pady=(1,5))
    top_actions=tk.Frame(header,bg="#f2f9ff");top_actions.grid(row=0,column=3,padx=(4,10))

    tabs=tk.Frame(win,bg=BG,height=39 if embedded else 55);tabs.grid(row=1,column=0,sticky="ew")
    tabs.grid_propagate(False)
    tab_buttons=[]
    content=tk.Frame(win,bg=BG);content.grid(row=2,column=0,sticky="nsew",padx=10,pady=(0,5))
    content.grid_columnconfigure(0,weight=1);content.grid_rowconfigure(0,weight=1)
    page_fiche=tk.Frame(content,bg=BG);page_fiche.grid(row=0,column=0,sticky="nsew")
    page_history=tk.Frame(content,bg=BG);page_history.grid(row=0,column=0,sticky="nsew")
    def show_tab(index):
        selected_tab.set(index)
        (page_history if index==1 else page_finance if index==2 else page_fiche).tkraise()
        if index==3: documents.focus_set()
        if index==4: note_tree.focus_set()
        if index==2: refresh_finance()
        for pos,tab in enumerate(tab_buttons):
            tab.configure(bg=BAR if pos==index else "#d8eafa",fg="white" if pos==index else DARK)
        if index==1:refresh_history()
    for index,label in enumerate(("Fiche client","Historique des locations","Historique financier","Documents","Notes")):
        tab=tk.Button(tabs,text=label,image=ref_image(win,("client_tab","history_tab","finance_tab","document","notes_tab")[index],18),compound="left",command=lambda i=index:show_tab(i),font=("Segoe UI",11,"bold"),
                      bd=0,relief="flat",cursor="hand2",padx=12 if embedded else 22,pady=4 if embedded else 9)
        tab.pack(side="left",padx=(12 if index==0 else 2,2),pady=(6,0))
        tab_buttons.append(tab)

    # Zone centrale sans Canvas : la fiche complète garde sa place à l'écran.
    list_width=180 if win.winfo_screenwidth()<1450 else 225
    page_fiche.grid_columnconfigure(0,weight=0,minsize=list_width)
    page_fiche.grid_columnconfigure(1,weight=1,minsize=0)
    page_fiche.grid_rowconfigure(0,weight=1)
    list_card,list_body=section(page_fiche,"▣   Liste des clients")
    list_card.configure(width=list_width)
    list_card.pack_propagate(False)
    list_card.grid(row=0,column=0,sticky="nsew",padx=(0,5))
    list_body.grid_columnconfigure(0,weight=1)
    list_body.grid_rowconfigure(1,weight=1)
    search=tk.StringVar(master=win)
    search_box=tk.Frame(list_body,bg="white")
    search_box.grid(row=0,column=0,sticky="ew",pady=(0,5))
    search_box.grid_columnconfigure(0,weight=1)
    search_entry=tk.Entry(search_box,textvariable=search,relief="solid",bd=1,font=("Segoe UI",9),fg=INK)
    search_entry.grid(row=0,column=0,sticky="ew",ipady=6)
    button(search_box,"⌕",lambda:refresh_list(),BLUE,True).grid(row=0,column=1,padx=(3,0))
    columns=("code","name")
    list_tree=ttk.Treeview(list_body,columns=columns,show="headings",selectmode="browse",height=9)
    for key,label,colw in (("code","Code",45),("name","Nom et prénom",158)):
        list_tree.heading(key,text=label);list_tree.column(key,width=colw,anchor="w",minwidth=colw,stretch=key=="name")
    list_tree.grid(row=1,column=0,sticky="nsew")
    list_scroll=ttk.Scrollbar(list_body,orient="vertical",command=list_tree.yview)
    list_scroll.grid(row=1,column=1,sticky="ns");list_tree.configure(yscrollcommand=list_scroll.set)
    list_tree.tag_configure("even",background="#ffffff",foreground=INK)
    list_tree.tag_configure("odd",background="#eaf4ff",foreground=INK)
    list_page=tk.IntVar(master=win,value=0)
    list_pages={"count":1,"total":0}
    list_count=tk.StringVar(master=win,value="0 client(s)")
    list_footer=tk.Frame(list_body,bg="white")
    list_footer.grid(row=2,column=0,sticky="ew",pady=(8,1))
    tk.Label(list_footer,textvariable=list_count,bg="white",fg=INK,font=("Segoe UI",8),anchor="center").pack(fill="x")
    pagination=tk.Frame(list_footer,bg='white');pagination.pack(fill='x',pady=3)
    def change_page(target):
        list_page.set(max(0,min(list_pages['count']-1,target)));refresh_list()
    for text,command in (('«',lambda:change_page(0)),('‹',lambda:change_page(list_page.get()-1)),('›',lambda:change_page(list_page.get()+1)),('»',lambda:change_page(list_pages['count']-1))):
        tk.Button(pagination,text=text,command=command,bg='#e4f2ff',fg=BLUE,font=('Segoe UI',10,'bold'),width=2,relief='flat').pack(side='left',fill='x',expand=True,padx=2)

    right=tk.Frame(page_fiche,bg=BG)
    right.grid(row=0,column=1,sticky="nsew")
    right.grid_columnconfigure(0,weight=1);right.grid_rowconfigure(0,weight=3);right.grid_rowconfigure(1,weight=2)
    upper=tk.Frame(right,bg=BG);upper.grid(row=0,column=0,sticky="nsew",pady=(0,5))
    upper.grid_columnconfigure(0,weight=64,uniform="upper");upper.grid_columnconfigure(1,weight=36,uniform="upper");upper.grid_rowconfigure(0,weight=1)
    lower=tk.Frame(right,bg=BG);lower.grid(row=1,column=0,sticky="nsew")
    lower.grid_columnconfigure(0,weight=29,uniform="lower");lower.grid_columnconfigure(1,weight=71,uniform="lower");lower.grid_rowconfigure(0,weight=1)
    identity,identity_body=section(upper,"Informations générales")
    identity.grid(row=0,column=0,sticky="nsew",padx=(0,5))
    identity_body.grid_columnconfigure(0,weight=24,uniform="identity_parts");identity_body.grid_columnconfigure(1,weight=76,uniform="identity_parts")
    identity_body.grid_rowconfigure(0,weight=1)
    photo_body=tk.Frame(identity_body,bg="#eaf4fd");photo_body.grid(row=0,column=0,sticky="nw",padx=4,pady=(18,3));photo_body.configure(width=165,height=230);photo_body.grid_propagate(False)
    photo_body.grid_columnconfigure(0,weight=1);photo_body.grid_rowconfigure(0,weight=1)
    photo_label=tk.Label(photo_body,bg="#eaf4fd",image=ref_image(win,"avatar",115),anchor="center")
    photo_label.grid(row=0,column=0,sticky="nsew",padx=3)
    photo_kind=tk.StringVar(master=win,value="CIN");cin_face=tk.StringVar(master=win,value="CIN");permis_face=tk.StringVar(master=win,value="PERMIS")
    photo_commands=tk.Frame(photo_body,bg="#eaf4fd");photo_commands.grid(row=1,column=0,sticky="ew",pady=4)
    photo_commands.grid_columnconfigure(0,weight=1);photo_commands.grid_columnconfigure(1,weight=0)
    photo_label.grid_remove()
    identity_previews={}
    for r,(kind,caption) in enumerate((('CIN','CIN · Recto'),('PERMIS','Permis · Recto'))):
        label=tk.Label(photo_body,text='Aucun recto',bg='#eaf4fd',fg=INK,width=1,height=3,cursor='hand2',anchor='n')
        label.grid(row=r,column=0,sticky='nsew',padx=3,pady=(0,8));photo_body.grid_rowconfigure(r,weight=1,uniform='identity_scans')
        label.bind('<Button-1>',lambda e,k=kind:open_document(k));identity_previews[kind]=label
    photo_commands.grid_remove()
    person=tk.Frame(identity_body,bg="white");person.grid(row=0,column=1,sticky="nsew")
    for col in range(3):person.grid_columnconfigure(col,weight=1,uniform="person")
    def person_field(label,key,row,col,span=1,readonly=False,tint="white"):
        frame=tk.Frame(person,bg="white");frame.grid(row=row,column=col,columnspan=span,sticky="ew",padx=3,pady=2)
        tk.Label(frame,text=label,bg="white",fg=INK,font=("Segoe UI",8),anchor="w").pack(fill="x")
        control=ref_entry(frame,values[key],readonly,tint);control.pack(fill="x",ipady=3)
        if key in ("date_naissance","cin_issued"):
            app._attach_date_picker(control,values[key]);app._calendar_buttons[-1].configure(image=ref_image(win,"calendar",16),text="")
        return control
    person_field("Code client *","code",0,0,readonly=True,tint="#fff0b3")
    person_field("CIN *","cin",0,1,2).bind('<FocusOut>',lambda e:sync_legacy_vars())
    person_field("Nom *","nom",1,0);person_field("Prénom *","prenom",1,1,2)
    person_field("Date de naissance","date_naissance",2,0);person_field("Âge","age",2,1,readonly=True,tint="#e9faf1")
    phone_control=person_field("Téléphone *","telephone",2,2)
    person_field("Deuxième téléphone","telephone2",3,0);person_field("Email","email",3,1,2)
    contacts=tk.Frame(person,bg="white");contacts.place(in_=phone_control,relx=1,rely=.5,anchor='e',width=48,height=20)
    ref_button(contacts,'',lambda:contact_action('phone'),"#e5f2fc",'phone',True).pack(side='left',padx=0)
    ref_button(contacts,'',lambda:contact_action('whatsapp'),"#008747",'whatsapp',True).pack(side='left',padx=0)
    person_field("Date d'enregistrement","date_enregistrement",4,0,readonly=True,tint="#eaf4ff")
    person_field("Date de délivrance CIN","cin_issued",4,1);person_field("Lieu de délivrance","cin_place",4,2)
    def ages(*_):
        values["age"].set(app._age_from_birth_date(values["date_naissance"].get()))
        values["permis_age"].set(app._age_from_birth_date(values["date_permis"].get()))
    values["date_naissance"].trace_add("write",ages);values["date_permis"].trace_add("write",ages)
    contact,contact_body=section(upper,"Adresse et contact");contact.grid(row=0,column=1,sticky="nsew")
    contact_body.grid_columnconfigure(0,weight=1);contact_body.grid_columnconfigure(1,weight=1)
    tk.Label(contact_body,text="Adresse complète",bg="white",fg=INK,font=("Segoe UI",8)).grid(row=0,column=0,columnspan=2,sticky="w",padx=4)
    address=tk.Text(contact_body,height=2,wrap="word",font=("Segoe UI",9),bg="white",highlightbackground=LINE,highlightthickness=1,relief="flat",bd=0)
    address.grid(row=1,column=0,columnspan=2,sticky="ew",padx=4,pady=4)
    field(contact_body,"Ville","ville",1,0);field(contact_body,"Code postal","postal",1,1)
    field(contact_body,"Profession","profession",2,1)
    for row,label,key,choices in ((2,"Pays","country",("Maroc","France","Espagne","Belgique","Autre")),(3,"Nationalité","nationality",("Marocaine","Française","Espagnole","Belge","Autre"))):
        tk.Label(contact_body,text=label,bg="white",fg=INK,font=("Segoe UI",8)).grid(row=row*2,column=0,sticky="w",padx=4)
        ttk.Combobox(contact_body,textvariable=values[key],values=choices,style="Reference.TCombobox",width=10).grid(row=row*2+1,column=0,sticky="ew",padx=4,pady=2)
    field(contact_body,"Genre","sexe",3,1)
    extra,extra_body=section(lower,"Informations complémentaires");extra.grid(row=0,column=0,sticky="nsew",padx=(0,5))
    for col in range(2):extra_body.grid_columnconfigure(col,weight=1)
    field(extra_body,"Permis de conduire *","permis",0,0);field(extra_body,"Date d'obtention *","date_permis",0,1)
    for row,label,key,choices in ((1,'Situation familiale','family',('Célibataire','Marié(e)','Autre')),(2,'Source du client','source',('Agence','Internet','Recommandation','Autre'))):
        tk.Label(extra_body,text=label,bg='white',fg=INK,font=('Segoe UI',8)).grid(row=row*2,column=0,columnspan=2,sticky='w',padx=4)
        ttk.Combobox(extra_body,textvariable=values[key],values=choices,style='Reference.TCombobox',state='normal',width=10).grid(row=row*2+1,column=0,columnspan=2,sticky='ew',padx=4,pady=2)
    tk.Label(extra_body,text="Remarques",bg="white",fg=INK,font=("Segoe UI",8)).grid(row=6,column=0,columnspan=2,sticky="w",padx=4)
    notes=tk.Text(extra_body,height=2,font=("Segoe UI",9),wrap="word",bg='white',highlightbackground=LINE,highlightthickness=1,relief='flat',bd=0)
    notes.grid(row=7,column=0,columnspan=2,sticky="nsew",padx=4,pady=3);extra_body.grid_rowconfigure(7,weight=1)
    documents,documents_body=section(lower,"Documents du client");documents.grid(row=0,column=1,sticky="nsew")
    for col in range(4):documents_body.grid_columnconfigure(col,weight=1,uniform="documents")
    documents_body.grid_rowconfigure(0,weight=1)
    document_names={}
    for col,kind,title_doc in ((0,"CIN","Carte nationale d'identité"),(1,"PERMIS","Permis de conduire"),(2,"DOMICILE","Justificatif de domicile"),(3,"AUTRE","Document PDF")):
        tile=tk.Frame(documents_body,bg="#eaf5fe");tile.grid(row=0,column=col,sticky="nsew",padx=3)
        tile.grid_columnconfigure(0,weight=1);tile.grid_rowconfigure(1,weight=1)
        tk.Label(tile,text=title_doc,bg="#eaf5fe",fg=INK,font=("Segoe UI",8),wraplength=150).grid(row=0,column=0,pady=3,sticky='ew')
        preview=tk.Label(tile,text="Aucun document",bg="#f3faff",fg="#70879c",font=("Segoe UI",8),width=1,height=3)
        preview.grid(row=1,column=0,sticky="nsew",padx=4,pady=3);preview_labels[kind]=preview
        preview.bind("<Button-1>",lambda _e,k=kind:open_document(k));preview.configure(cursor='hand2')
        document_names[kind]=tk.StringVar(master=win,value="Aucun document")
        tk.Label(tile,textvariable=document_names[kind],bg="#eaf5fe",fg='#587086',font=('Segoe UI',7),wraplength=145).grid(row=2,column=0,sticky='ew')
        if kind in ('CIN','PERMIS'):
            facebar=tk.Frame(tile,bg='#eaf5fe');facebar.grid(row=3,column=0,sticky='ew')
            for face,caption in ((kind,'Recto'),(kind+'_VERSO','Verso')):
                tk.Button(facebar,text=caption,command=lambda f=face:choose_cin_face(f),bg='#e4f1ff',fg=INK,relief='flat',bd=0,font=('Segoe UI',7),padx=1).pack(side='left',fill='x',expand=True)
        if kind=='AUTRE':
            other_list=tk.Listbox(tile,height=1,exportselection=False,font=('Segoe UI',7),bd=0)
            other_list.grid(row=3,column=0,sticky='ew',padx=4);other_list.bind('<<ListboxSelect>>',lambda e:select_other_document())
        controls=tk.Frame(tile,bg="#eaf5fe");controls.grid(row=4,column=0,sticky='ew',pady=4)
        get_kind=lambda k=kind:cin_face.get() if k=='CIN' else permis_face.get() if k=='PERMIS' else k
        for col2,(label,cmd,color) in enumerate((('Scanner',lambda get=get_kind:scan_document(get()),BLUE),('Importer',lambda get=get_kind:import_document(get()),BLUE),('×',lambda get=get_kind:delete_document(get()),RED))):
            controls.grid_columnconfigure(col2,weight=1);control=button(controls,label,cmd,color,True);control.configure(font=('Segoe UI',7,'bold'),padx=2);control.grid(row=0,column=col2,sticky='ew',padx=1)
        if kind=='AUTRE':
            def request_pdf_sync():
                request=getattr(app,'_request_mobile_sync',None)
                if request:
                    request()
                    document_names['AUTRE'].set('Synchronisation demandée…')
                else:messagebox.showinfo('Synchronisation','La synchronisation Android doit être configurée sur ce PC.',parent=win)
            button(tile,'Synchroniser PDF',request_pdf_sync,GREEN,True).grid(row=5,column=0,sticky='ew',padx=3)
    bottom_cards=tk.Frame(page_fiche,bg=BG);bottom_cards.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(6,0))
    for col,weight in enumerate((30,44,26)):bottom_cards.grid_columnconfigure(col,weight=weight,uniform='client_bottom')
    emergency,emergency_body=ref_section(bottom_cards,"Contacts d'urgence",'phone',soft='#e4f3fe');emergency.grid(row=0,column=0,sticky='nsew',padx=(0,5))
    emergency_body.grid_columnconfigure(0,weight=1);emergency_body.grid_columnconfigure(1,weight=1)
    field(emergency_body,'Nom','emergency_name',0,0);field(emergency_body,'Lien','emergency_relation',0,1);field(emergency_body,'Téléphone','emergency_phone',1,0)
    note_card,note_body=ref_section(bottom_cards,'Notes','notes_section',soft='#fff8df');note_card.grid(row=0,column=1,sticky='nsew',padx=(0,5))
    note_action=note_card.winfo_children()[0]
    button(note_action,'Ajouter',lambda:add_note(),BLUE,True).pack(side='right',padx=3)
    note_tree=ttk.Treeview(note_body,columns=('date','note','user'),show='headings',height=3,style='Reference.Treeview')
    for key,label,width in (('date','Date',80),('note','Note',210),('user','Utilisateur',80)):
        note_tree.heading(key,text=label);note_tree.column(key,width=width,minwidth=45,stretch=True)
    note_tree.pack(fill='both',expand=True)
    stat_card,stat_body=ref_section(bottom_cards,'Statistiques client','stats_section',soft='#f2ebff');stat_card.grid(row=0,column=2,sticky='nsew')
    client_stats={key:tk.StringVar(master=win,value='—') for key in ('count','paid','due','last')}
    for key,label,tint,fg in (('count','Nombre de locations','white',INK),('paid','Total payé','white',BLUE),('due','Solde dû','#ffe9ec',RED),('last','Dernière location','white',INK)):
        line=tk.Frame(stat_body,bg=tint);line.pack(fill='x',pady=3)
        tk.Label(line,text=label,bg=tint,fg=INK,font=('Segoe UI',8)).pack(side='left')
        tk.Label(line,textvariable=client_stats[key],bg=tint,fg=fg,font=('Segoe UI',9,'bold')).pack(side='right')
    page_finance=tk.Frame(content,bg=BG);page_finance.grid(row=0,column=0,sticky='nsew')
    tk.Label(page_finance,text='Historique financier du client',bg=BAR,fg='white',font=('Segoe UI',14,'bold'),pady=12).pack(fill='x')
    finance_tree=ttk.Treeview(page_finance,columns=('date','ref','contract','mode','amount'),show='headings',style='Reference.Treeview')
    for key,label in (('date','Date'),('ref','Référence'),('contract','Contrat'),('mode','Mode'),('amount','Montant MAD')):finance_tree.heading(key,text=label);finance_tree.column(key,width=120)
    finance_tree.pack(fill='both',expand=True,pady=10)
    ref_button(page_finance,'Nouveau règlement',lambda:app.show_page('receivables'),BLUE,'new').pack(anchor='e',pady=8)

    # Historique sur son propre onglet, sans réduire la largeur de la fiche.
    page_history.grid_columnconfigure(0,weight=1);page_history.grid_rowconfigure(2,weight=1)
    kpis=tk.Frame(page_history,bg=BG);kpis.grid(row=0,column=0,sticky="ew",pady=4)
    totals={key:tk.StringVar(master=win,value="—") for key in ("count","days","amount","last")}
    for index,(key,label,tint) in enumerate((("count","Locations","#e2f2ff"),("days","Jours","#e6f0ff"),
                                            ("amount","Montant total MAD","#e3f8e9"),("last","Dernière location","#fff0df"))):
        kpis.grid_columnconfigure(index,weight=1)
        card=tk.Frame(kpis,bg=tint,highlightbackground=LINE,highlightthickness=1)
        card.grid(row=0,column=index,sticky="ew",padx=4)
        tk.Label(card,text=label,bg=tint,fg=DARK,font=("Segoe UI",9,"bold")).pack(anchor="w",padx=13,pady=(8,0))
        tk.Label(card,textvariable=totals[key],bg=tint,fg=DARK,font=("Segoe UI",17,"bold")).pack(anchor="w",padx=13,pady=(0,8))
    history_search=tk.StringVar(master=win)
    tk.Entry(page_history,textvariable=history_search,font=("Segoe UI",10),relief="solid",bd=1).grid(
        row=1,column=0,sticky="ew",padx=5,pady=8,ipady=5)
    hist_card,hist_body=section(page_history,"▤   Historique des locations du client sélectionné")
    hist_card.grid(row=2,column=0,sticky="nsew",padx=4)
    hist_body.grid_columnconfigure(0,weight=1);hist_body.grid_rowconfigure(0,weight=1)
    hist_cols=("numero","vehicle","plate","start","end","days","total","due")
    hist_tree=ttk.Treeview(hist_body,columns=hist_cols,show="headings",selectmode="browse")
    for key,label,colw in zip(hist_cols,("Contrat","Véhicule","Immatriculation","Départ","Retour","Jours","Montant MAD","Solde MAD"),
                              (110,180,135,100,100,70,120,120)):
        hist_tree.heading(key,text=label);hist_tree.column(key,width=colw,minwidth=60,anchor="center",stretch=True)
    hist_tree.grid(row=0,column=0,sticky="nsew")
    hist_scroll=ttk.Scrollbar(hist_body,orient="vertical",command=hist_tree.yview)
    hist_scroll.grid(row=0,column=1,sticky="ns");hist_tree.configure(yscrollcommand=hist_scroll.set)
    detail=tk.Frame(page_history,bg="white",highlightbackground=LINE,highlightthickness=1)
    detail.grid(row=3,column=0,sticky="ew",padx=4,pady=5)
    history_photo=tk.Label(detail,text="Sélectionnez une location",bg="#eaf3fb",fg=DARK,width=24,height=5)
    history_photo.pack(side="left",padx=9,pady=7)
    detail_text=tk.StringVar(master=win,value="Aucun contrat sélectionné")
    tk.Label(detail,textvariable=detail_text,bg="white",fg=INK,justify="left",
             font=("Segoe UI",10,"bold")).pack(side="left",fill="x",expand=True)
    button(detail,"Ouvrir le contrat",lambda:open_contract(),BLUE,True).pack(side="right",padx=9)

    bottom=tk.Frame(win,bg=BG)
    shortcuts=tk.Frame(bottom,bg=BG)

    def valid_client():
        cid=code.get().strip()
        if not cid or not app.conn.execute("SELECT 1 FROM clients WHERE code=?",(cid,)).fetchone():
            messagebox.showwarning("Fiche client","Sélectionnez ou enregistrez un client.",parent=win)
            return ""
        return cid

    def sync_legacy_vars():
        values["adresse"].set(address.get("1.0","end-1c").strip())
        data={k:v.get() for k,v in values.items() if k in app.client_vars}
        data["observations"]=notes.get("1.0","end-1c").strip()
        for key,val in data.items():app.client_vars[key].set(val)
        if not app.client_vars["date_enregistrement"].get().strip() and not app.conn.execute(
                "SELECT 1 FROM clients WHERE code=?",(code.get().strip(),)).fetchone():
            app.client_vars["date_enregistrement"].set(datetime.now().strftime("%d/%m/%Y"))

    def load_profile(cid):
        row=app.conn.execute("SELECT payload FROM module_records WHERE module=? AND record_id=?",
                             ("client_profile",cid)).fetchone()
        try:data=json.loads(row[0]) if row else {}
        except (ValueError,TypeError):data={}
        for key in ("postal","country","workplace","family","references","blocked","telephone2","cin_issued","cin_place","nationality","emergency_name","emergency_phone","emergency_relation","source"):
            values[key].set(str(data.get(key,"")))

    def select_client(cid):
        row=app.conn.execute("SELECT * FROM clients WHERE code=?",(cid,)).fetchone()
        if not row:return
        for key,var in app.client_vars.items():
            if key in row.keys():var.set(str(row[key] or ""))
        for key,var in values.items():
            if key in row.keys():var.set(str(row[key] or ""))
        address.delete("1.0","end");address.insert("1.0",str(row["adresse"] or ""))
        notes.delete("1.0","end");notes.insert("1.0",str(row["observations"] or ""))
        load_profile(cid)
        profile_notes[:] = data_notes(cid)
        refresh_notes()
        display_photo()
        refresh_documents()
        refresh_history()
        if list_tree.exists(cid) and list_tree.selection()!=(cid,):
            list_tree.selection_set(cid);list_tree.see(cid)

    def refresh_list(*_):
        term=search.get().strip();pattern=f"%{term}%"
        rows=app.conn.execute("SELECT code,nom,prenom,telephone FROM clients WHERE "
                              "code LIKE ? OR cin LIKE ? OR nom LIKE ? OR prenom LIKE ? OR telephone LIKE ? "
                              "ORDER BY CASE WHEN code GLOB '[0-9]*' THEN CAST(code AS INTEGER) ELSE 2147483647 END,code",
                              (pattern,)*5).fetchall()
        list_tree.delete(*list_tree.get_children())
        list_pages["total"]=len(rows);list_pages["count"]=max(1,(len(rows)+14)//15)
        if list_page.get()>=list_pages["count"]:list_page.set(list_pages["count"]-1)
        for index,row in enumerate(rows[list_page.get()*15:(list_page.get()+1)*15]):
            list_tree.insert("","end",iid=str(row["code"]),values=(row["code"],
                             f"{row['nom'] or ''} {row['prenom'] or ''}"),
                             tags=("odd" if index%2 else "even",))
        list_count.set(f"{list_page.get()+1} / {list_pages['count']} · {len(rows)} clients")
        # La saisie positionne la liste sans charger la fiche avant Entrée.
        matches=list_tree.get_children()
        if term and matches:
            exact=next((item for item in matches if item.casefold()==term.casefold()),None)
            target=exact or matches[0]
            list_tree.selection_set(target)
            list_tree.focus(target)
            list_tree.see(target)

    def choose_list(_event=None):
        if search_entry.focus_get() is search_entry:return
        picked=list_tree.selection()
        if picked:select_client(picked[0])
    def accept_search(_event=None):
        picked=list_tree.selection()
        if not picked:picked=list_tree.get_children()[:1]
        if picked:
            cid=picked[0]
            list_tree.selection_set(cid)
            list_tree.focus(cid)
            list_tree.see(cid)
            select_client(cid)
        return "break"
    list_tree.bind("<<TreeviewSelect>>",choose_list)
    list_tree.bind("<Return>",accept_search)
    search_entry.bind("<Return>",accept_search)
    search.trace_add("write",lambda *_:(list_page.set(0),refresh_list()))

    def display_photo():
        for kind,label in identity_previews.items():
            row=app.conn.execute("SELECT file_path FROM client_documents WHERE client_code=? AND document_type IN (?,?) ORDER BY id DESC LIMIT 1",(code.get().strip(),kind,kind+'_RECTO')).fetchone()
            path=_resolve_existing_client_document(app,code.get().strip(),row[0]) if row else None
            if path:
                try:
                    photos['identity_'+kind]=preview_image(path,(max(100,label.winfo_width()-8),max(55,label.winfo_height()-8)))
                    label.configure(image=photos['identity_'+kind],text='')
                except Exception:label.configure(image='',text='Recto · cliquer pour ouvrir')
            else:label.configure(image='',text='Aucun recto')

    def photo_size():
        # L'image conserve ses proportions et occupe la place réellement disponible.
        return (max(100,photo_label.winfo_width()-12),max(100,photo_label.winfo_height()-12))

    def preview_image(path,size):
        """Aperçu image ou première page PDF, sans modifier le document original."""
        from PIL import Image,ImageTk,ImageOps
        if path.suffix.lower()==".pdf":
            try:
                import fitz
                with fitz.open(str(path)) as document:
                    if not document.page_count:raise ValueError("PDF vide")
                    pix=document[0].get_pixmap(matrix=fitz.Matrix(1.3,1.3),alpha=False)
                    picture=Image.frombytes("RGB",(pix.width,pix.height),pix.samples)
            except Exception:
                # Les scans PDF portent généralement une image pleine page.
                # Cette lecture reste disponible si la DLL de PyMuPDF manque.
                try:
                    from pypdf import PdfReader
                    with path.open("rb") as stream:
                        page=PdfReader(stream).pages[0]
                        if not page.images:raise ValueError("PDF sans image")
                        with Image.open(io.BytesIO(page.images[0].data)) as source:
                            picture=ImageOps.exif_transpose(source).copy()
                except Exception:
                    raise ValueError("PDF · double clic pour ouvrir") from None
        else:
            with Image.open(path) as source:picture=ImageOps.exif_transpose(source).copy()
        picture.thumbnail(size,Image.Resampling.LANCZOS)
        return ImageTk.PhotoImage(picture)

    def show_photo_kind(kind):
        photo_kind.set(kind)
        if kind=="PHOTO":display_photo();return
        item=current_doc_ids.get(kind)
        path=_resolve_existing_client_document(app,code.get().strip(),item[1]) if item else None
        if path is None:
            photo_label.configure(image="",text=f"{kind}\nAucun document");return
        try:
            photos["photo_document"]=preview_image(path,photo_size())
            photo_label.configure(image=photos["photo_document"],text="")
        except Exception:
            photo_label.configure(image="",text=f"{kind} · PDF\nDouble clic pour ouvrir\n{path.name}")

    def open_photo_document(_event=None):
        item=current_doc_ids.get(photo_kind.get())
        path=_resolve_existing_client_document(app,code.get().strip(),item[1] if item else values["photo"].get())
        if path:open_document_path(path)
    photo_label.bind("<Double-1>",open_photo_document)

    photo_resize={"job":None,"size":None}
    def resize_photo(event):
        size=(event.width,event.height)
        if size==photo_resize["size"]:return
        photo_resize["size"]=size
        if photo_resize["job"] is not None:win.after_cancel(photo_resize["job"])
        photo_resize["job"]=win.after(120,lambda:show_photo_kind(photo_kind.get()) if win.winfo_exists() else None)
    for label in identity_previews.values():label.bind("<Configure>",lambda e:display_photo())

    def choose_photo():
        path=filedialog.askopenfilename(parent=win,title="Choisir une photo",
                 filetypes=[("Images","*.png *.jpg *.jpeg *.bmp"),("Tous les fichiers","*.*")])
        if path:values["photo"].set(path);show_photo_kind("PHOTO")
    button(photo_commands,"Ajouter une photo",choose_photo,BLUE,True).grid(row=0,column=0,columnspan=2,sticky="ew",padx=2)
    photo_label.bind("<Button-3>",lambda e:(values["photo"].set(""),display_photo()))

    def refresh_documents():
        _index_existing_client_documents(app)
        photos.update({kind:None for kind in ("CIN","CIN_VERSO","PERMIS","PERMIS_VERSO","DOMICILE","AUTRE")})
        current_doc_ids.clear()
        cid=code.get().strip()
        other_document_rows.clear()
        other_list.delete(0,"end")
        if cid:
            other_document_rows.extend(app.conn.execute(
                "SELECT id,file_path,document_type FROM client_documents WHERE client_code=? "
                "AND LOWER(file_path) LIKE '%.pdf' ORDER BY id DESC",(cid,)).fetchall())
            for item in other_document_rows:
                other_list.insert("end",f"{item['document_type']} · {Path(item['file_path']).name}")
        for kind,label in preview_labels.items():
            if kind=="AUTRE":row=next((item for item in other_document_rows if str(item["document_type"]).startswith("AUTRE")),None)
            else:
                row=app.conn.execute(
                    "SELECT id,file_path FROM client_documents WHERE client_code=? AND document_type IN (?,?) ORDER BY id DESC LIMIT 1",
                    (cid,f"{kind}_RECTO",kind)).fetchone() if cid else None
            if not row:
                label.configure(image="",text="Aucun document");document_names[kind].set("Aucun document");continue
            current_doc_ids[kind]=(row["id"],str(row["file_path"] or ""))
            document_names[kind].set(Path(row["file_path"]).name)
            path=_resolve_existing_client_document(app,cid,row["file_path"])
            if path is None:label.configure(image="",text="Fichier indisponible");continue
            try:
                photos[kind]=preview_image(path,(110,100) if kind in ("CIN","CIN_VERSO","PERMIS","PERMIS_VERSO") else (232,100))
                label.configure(image=photos[kind],text="")
            except Exception:label.configure(image="",text=path.name[:25])
        for face in ("CIN_VERSO","PERMIS_VERSO"):
            item=app.conn.execute("SELECT id,file_path FROM client_documents WHERE client_code=? AND document_type=? ORDER BY id DESC LIMIT 1",(cid,face)).fetchone() if cid else None
            if item:current_doc_ids[face]=(item[0],item[1])
        choose_cin_face(cin_face.get(),update_photo=False)
        choose_cin_face(permis_face.get(),update_photo=False)
        if other_document_rows:
            preferred=current_doc_ids.get("AUTRE")
            index=next((i for i,item in enumerate(other_document_rows) if preferred and item["id"]==preferred[0]),0)
            other_list.selection_set(index)
            select_other_document()
        display_photo()

    def choose_cin_face(face,update_photo=True):
        base="PERMIS" if face.startswith("PERMIS") else "CIN"
        (permis_face if base=="PERMIS" else cin_face).set(face)
        if update_photo:
            show_photo_kind(face)
            item=current_doc_ids.get(face)
            if item:
                path=_resolve_existing_client_document(app,code.get().strip(),item[1])
                if path:
                    try:
                        photos[base]=preview_image(path,(145,110));preview_labels[base].configure(image=photos[base],text="");document_names[base].set(path.name)
                    except Exception:preview_labels[base].configure(image="",text=path.name)

    def update_faces_pdf(cid):
        """Sur Modifier, assemble les dernières faces du client dans Autres documents."""
        sources=[]
        for types in (("CIN_RECTO","CIN"),("CIN_VERSO",),("PERMIS_RECTO","PERMIS"),("PERMIS_VERSO",)):
            placeholders=",".join("?" for _ in types)
            row=app.conn.execute(f"SELECT file_path FROM client_documents WHERE client_code=? "
                                 f"AND document_type IN ({placeholders}) ORDER BY id DESC LIMIT 1",
                                 (cid,*types)).fetchone()
            if row and Path(row[0]).is_file():sources.append(Path(row[0]))
        if not sources:return False
        destination=app._client_documents_folder(cid)/"PIECES_IDENTITE_FACES.pdf"
        existing=app.conn.execute("SELECT id FROM client_documents WHERE client_code=? AND document_type='AUTRE_FACES' "
                                  "ORDER BY id DESC LIMIT 1",(cid,)).fetchone()
        if existing and destination.is_file() and destination.stat().st_mtime>=max(p.stat().st_mtime for p in sources):return True
        temporary=destination.with_name("_PIECES_IDENTITE_FACES.pdf")
        try:
            from PIL import Image,ImageOps
            from pypdf import PdfReader,PdfWriter
            writer=PdfWriter()
            for source in sources:
                if source.suffix.lower()==".pdf":
                    writer.append(str(source))
                else:
                    buffer=io.BytesIO()
                    with Image.open(source) as original:
                        ImageOps.exif_transpose(original).convert("RGB").save(buffer,"PDF",resolution=200)
                    buffer.seek(0)
                    writer.append(PdfReader(buffer))
            if not writer.pages:return False
            with temporary.open("wb") as stream:writer.write(stream)
            temporary.replace(destination)
            if not existing:
                app.conn.execute("INSERT INTO client_documents(client_code,document_type,file_path,created_at) VALUES(?,?,?,?)",
                                 (cid,"AUTRE_FACES",str(destination),datetime.now().isoformat(timespec="seconds")))
                app.conn.commit()
            return True
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    def select_other_document():
        selected=other_list.curselection()
        if not selected or selected[0]>=len(other_document_rows):return
        row=other_document_rows[selected[0]]
        current_doc_ids["AUTRE"]=(row["id"],str(row["file_path"] or ""))
        path=_resolve_existing_client_document(app,code.get().strip(),row["file_path"])
        if path is None:
            preview_labels["AUTRE"].configure(image="",text="Fichier indisponible")
            return
        try:
            photos["AUTRE"]=preview_image(path,(232,100))
            preview_labels["AUTRE"].configure(image=photos["AUTRE"],text="")
        except Exception:preview_labels["AUTRE"].configure(image="",text=path.name[:25])
        show_photo_kind("AUTRE")

    def open_document_path(path):
        try:
            if os.name=="nt":os.startfile(str(path))
            elif not webbrowser.open(path.as_uri()):raise OSError("Aucune application associée au document.")
        except (OSError,ValueError) as exc:
            messagebox.showerror("Document client",f"Impossible d'ouvrir {path.name} :\n{exc}",parent=win)

    def open_document(kind):
        if kind=="AUTRE" and other_list.curselection():
            row=other_document_rows[other_list.curselection()[0]]
            current_doc_ids["AUTRE"]=(row["id"],str(row["file_path"] or ""))
        item=current_doc_ids.get(kind)
        path=_resolve_existing_client_document(app,code.get().strip(),item[1]) if item else None
        if path:open_document_path(path)
        elif item:messagebox.showwarning("Document client","Le PDF enregistré pour ce client est introuvable. Relancez la synchronisation ou importez le fichier.",parent=win)
        else:messagebox.showinfo("Document PDF","Aucun PDF reçu pour ce client. Utilisez Synchroniser PDF après l’import depuis Android.",parent=win)

    def import_document(kind):
        cid=valid_client()
        if not cid:return
        source=filedialog.askopenfilename(parent=win,title=f"Importer {kind}",
                  filetypes=[("Images et PDF","*.png *.jpg *.jpeg *.bmp *.pdf"),("Tous les fichiers","*.*")])
        if not source:return
        path=Path(source)
        suffix=".pdf" if kind=="AUTRE" else path.suffix.lower()
        target=app._client_documents_folder(cid)/f"{kind}_{datetime.now():%Y%m%d_%H%M%S_%f}{suffix}"
        try:
            if kind=="AUTRE" and path.suffix.lower()!=".pdf":
                from PIL import Image,ImageOps
                with Image.open(path) as original:
                    ImageOps.exif_transpose(original).convert("RGB").save(target,"PDF",resolution=200)
            else:shutil.copy2(path,target)
            doc_type=f"{kind}_RECTO" if kind in ("CIN","PERMIS") else kind if kind in ("CIN_VERSO","PERMIS_VERSO") else kind if kind=="DOMICILE" else "AUTRE"
            app.conn.execute("INSERT INTO client_documents(client_code,document_type,file_path,created_at) VALUES(?,?,?,?)",
                             (cid,doc_type,str(target),datetime.now().isoformat(timespec="seconds")))
            if kind in ("CIN","PERMIS"):
                app.conn.execute("UPDATE clients SET photo=? WHERE code=?",(str(target),cid))
                values["photo"].set(str(target));show_photo_kind("PHOTO")
            app.conn.commit();refresh_documents()
        except Exception as exc:
            app.conn.rollback();target.unlink(missing_ok=True)
            messagebox.showerror("Importer document",str(exc),parent=win)

    def scan_document(kind):
        cid=valid_client()
        if not cid:return
        if kind in ("CIN","CIN_VERSO","PERMIS","PERMIS_VERSO"):
            app.scan_client_front_image(cid,kind.split("_",1)[0],
                on_complete=lambda _path:(refresh_documents(),select_client(cid)),face="VERSO" if kind.endswith("_VERSO") else "RECTO")
        else:
            source=app._client_documents_folder(cid)/f"_scan_autre_{datetime.now():%Y%m%d_%H%M%S_%f}.jpg"
            acquired=False
            if os.name=="nt":
                ps=('$d=New-Object -ComObject WIA.CommonDialog; '
                    '$i=$d.ShowAcquireImage(1,2,131072,"{B96B3CAE-0728-11D3-9D7B-0000F81EF32E}",$true,$true,$false); '
                    +f"if($i){{$i.SaveFile('{str(source).replace(chr(39),chr(39)*2)}')}}")
                try:
                    result=subprocess.run(["powershell.exe","-NoProfile","-STA","-Command",ps],
                                          capture_output=True,text=True,timeout=120)
                    acquired=result.returncode==0 and source.is_file()
                except (OSError,subprocess.TimeoutExpired):pass
            if not acquired:
                picked=filedialog.askopenfilename(parent=win,title="Importer un scan ou un PDF",
                           filetypes=[("Documents","*.pdf *.png *.jpg *.jpeg *.bmp *.tif *.tiff")])
                if not picked:return
                source=Path(picked)
            destination=app._client_documents_folder(cid)/f"{kind}_{datetime.now():%Y%m%d_%H%M%S_%f}.pdf"
            try:
                if source.suffix.lower()==".pdf":shutil.copy2(source,destination)
                else:
                    from PIL import Image,ImageOps
                    with Image.open(source) as original:
                        ImageOps.exif_transpose(original).convert("RGB").save(destination,"PDF",resolution=200)
                app.conn.execute("INSERT INTO client_documents(client_code,document_type,file_path,created_at) VALUES(?,?,?,?)",
                                 (cid,kind if kind=="DOMICILE" else "AUTRE",str(destination),datetime.now().isoformat(timespec="seconds")))
                app.conn.commit();refresh_documents();show_photo_kind(kind)
            except Exception as exc:
                destination.unlink(missing_ok=True)
                messagebox.showerror("Scan document",str(exc),parent=win)
            finally:
                if acquired:source.unlink(missing_ok=True)

    def delete_document(kind):
        item=current_doc_ids.get(kind)
        if not item:return
        if not messagebox.askyesno("Document client","Supprimer le document sélectionné ?",parent=win):return
        doc_id,path=item
        app.conn.execute("DELETE FROM client_documents WHERE id=?",(doc_id,))
        if kind=="CIN" and values["photo"].get()==path:
            app.conn.execute("UPDATE clients SET photo='' WHERE code=?",(code.get(),))
            values["photo"].set("");app.client_vars["photo"].set("");display_photo()
        app.conn.commit()
        try:Path(path).unlink(missing_ok=True)
        except OSError:pass
        refresh_documents()

    def refresh_history(*_):
        hist_tree.delete(*hist_tree.get_children());history_records.clear()
        cid=code.get().strip()
        if not cid or not app.conn.execute("SELECT 1 FROM clients WHERE code=?",(cid,)).fetchone():
            for item in list(totals.values())+list(client_stats.values()):item.set("—")
            return
        rows=app.conn.execute("SELECT c.*,v.modele,v.immatriculation,v.photo AS vehicle_photo "
                              "FROM contracts c LEFT JOIN vehicles v ON v.code=c.vehicle_code "
                              "WHERE c.client_code=? OR c.second_code=? ORDER BY substr(c.date_depart,7,4) DESC,"
                              "substr(c.date_depart,4,2) DESC,substr(c.date_depart,1,2) DESC",
                              (cid,cid)).fetchall()
        client_stats["count"].set(str(len(rows)))
        client_stats["paid"].set(f"{sum(float(r['reglement'] or 0) for r in rows):,.2f} MAD")
        client_stats["due"].set(f"{sum(float(r['reste'] or 0) for r in rows):,.2f} MAD")
        client_stats["last"].set(str(rows[0]["date_depart"] or "—") if rows else "—")
        totals["count"].set(str(len(rows)))
        totals["days"].set(str(sum(int(r["duree"] or 0) for r in rows)))
        totals["amount"].set(f"{sum(float(r['montant'] or 0) for r in rows):,.2f}")
        totals["last"].set(str(rows[0]["date_depart"] or "—") if rows else "—")
        needle=history_search.get().strip().casefold()
        for row in rows:
            number=str(row["numero"])
            if needle and needle not in " ".join(str(row[k] or "") for k in
                ("numero","vehicle_code","modele","immatriculation","date_depart")).casefold():continue
            history_records[number]=row
            hist_tree.insert("","end",iid=number,values=(number,row["modele"] or row["vehicle_code"] or "—",
                             row["immatriculation"] or "—",row["date_depart"] or "—",row["date_retour"] or "—",
                             row["duree"] or 0,f"{float(row['montant'] or 0):,.2f}",f"{float(row['reste'] or 0):,.2f}"))

    def select_history(_event=None):
        picked=hist_tree.selection()
        if not picked:return
        row=history_records.get(picked[0])
        if row is None:return
        detail_text.set(f"{row['numero']}  ·  {row['modele'] or row['vehicle_code'] or '—'}\n"
                        f"{row['date_depart'] or '—'} → {row['date_retour'] or '—'}    ·    "
                        f"{float(row['montant'] or 0):,.2f} MAD")
        path=app._vehicle_photo_path(str(row["vehicle_code"] or ""),str(row["vehicle_photo"] or ""))
        photos.pop("history",None)
        if path and Path(path).is_file():
            try:
                from PIL import Image,ImageTk,ImageOps
                with Image.open(path) as image:picture=ImageOps.exif_transpose(image).copy()
                picture.thumbnail((165,95),Image.Resampling.LANCZOS)
                photos["history"]=ImageTk.PhotoImage(picture)
                history_photo.configure(image=photos["history"],text="")
                return
            except Exception:pass
        history_photo.configure(image="",text="Photo indisponible")
    hist_tree.bind("<<TreeviewSelect>>",select_history)
    history_search.trace_add("write",refresh_history)

    def open_contract():
        picked=hist_tree.selection()
        if picked:app._dashboard_contract_document(picked[0],"preview")

    def new_client():
        for var in app.client_vars.values():var.set("")
        for var in values.values():var.set("")
        code.set(app._next_client_code())
        values["date_enregistrement"].set(datetime.now().strftime("%d/%m/%Y"))
        values["country"].set("Maroc")
        address.delete("1.0","end");notes.delete("1.0","end")
        if list_tree.selection():list_tree.selection_remove(list_tree.selection())
        profile_notes.clear();refresh_notes()
        display_photo();refresh_documents();refresh_history();show_tab(0)

    def save_client(update=False):
        cid=code.get().strip()
        if not cid:code.set(app._next_client_code());cid=code.get()
        if not values["nom"].get().strip():
            messagebox.showwarning("Fiche client","Le nom est obligatoire.",parent=win);return
        if not values["cin"].get().strip():
            messagebox.showwarning("Fiche client","Le CIN est obligatoire.",parent=win);return
        if update and not app.conn.execute("SELECT 1 FROM clients WHERE code=?",(cid,)).fetchone():
            messagebox.showwarning("Fiche client","Ce client n'est pas enregistré.",parent=win);return
        sync_legacy_vars()
        if not app._check_duplicate_client_cin(show_warning=True):return
        columns,data=app._client_values()
        exists=app.conn.execute("SELECT 1 FROM clients WHERE code=?",(cid,)).fetchone()
        try:
            if exists:
                assignments=",".join(f"{key}=?" for key in columns[1:])
                app.conn.execute(f"UPDATE clients SET {assignments} WHERE code=?",data[1:]+[cid])
            else:
                app.conn.execute(f"INSERT INTO clients({','.join(columns)}) VALUES({','.join('?' for _ in columns)})",data)
            extra={key:values[key].get().strip() for key in ("postal","country","workplace","family","references","blocked","telephone2","cin_issued","cin_place","nationality","emergency_name","emergency_phone","emergency_relation","source")}
            app.conn.execute("INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,?)",
                             ("client_profile",cid,json.dumps(extra,ensure_ascii=False),datetime.now().isoformat(timespec="seconds")))
            app.conn.commit()
            app._client_documents_folder(cid)
            app._audit("MODIFICATION" if exists else "CRÉATION","CLIENT",cid)
            pdf_error=None
            if update:
                try:update_faces_pdf(cid)
                except Exception as exc:pdf_error=exc
            app.refresh_clients();app._load_search_values();app.refresh_dashboard()
            refresh_list();select_client(cid)
            if pdf_error:messagebox.showwarning("Fiche client",f"Client {cid} enregistré, mais le PDF des faces n'a pas pu être créé :\n{pdf_error}",parent=win)
            else:messagebox.showinfo("Fiche client",f"Client {cid} enregistré.",parent=win)
        except Exception as exc:
            app.conn.rollback();messagebox.showerror("Fiche client",str(exc),parent=win)

    def delete_client():
        cid=valid_client()
        if not cid:return
        linked=app.conn.execute("SELECT COUNT(*) FROM contracts WHERE client_code=? OR second_code=?",(cid,cid)).fetchone()[0]
        if linked:messagebox.showwarning("Client","Ce client possède des contrats et ne peut pas être supprimé.",parent=win);return
        if not messagebox.askyesno("Supprimer","Supprimer le client sélectionné ?",parent=win):return
        app.conn.execute("DELETE FROM clients WHERE code=?",(cid,))
        app.conn.execute("DELETE FROM module_records WHERE module IN ('client_profile','client_notes') AND record_id=?",(cid,))
        app.conn.commit();app.refresh_clients();refresh_list();new_client()

    def quick_rental():
        cid=valid_client()
        if not cid:return
        if values["blocked"].get()=="1":
            messagebox.showwarning("Client bloqué","Ce client est marqué comme bloqué.",parent=win);return
        callback=win._on_select
        close()
        if callback:callback(cid)
        else:app.root.after(80,lambda:app.open_quick_contract_dialog(cid))

    def reservation():
        cid=valid_client()
        if not cid:return
        close();app.show_page("reservations")
        reservation_vars=getattr(app,"module_vars",{}).get("reservations",{})
        if "client" in reservation_vars:
            reservation_vars["client"].set(cid)
            app._load_reservation_client()

    def open_folder():
        cid=valid_client()
        if not cid:return
        folder=app._organize_client_documents(cid)
        if sys.platform.startswith("win"):os.startfile(str(folder))
        elif sys.platform=="darwin":subprocess.Popen(["open",str(folder)])
        else:subprocess.Popen(["xdg-open",str(folder)])

    def print_client():
        if not valid_client():return
        sync_legacy_vars();app.preview_client()

    def toggle_block():
        cid=valid_client()
        if not cid:return
        blocked=values["blocked"].get()=="1"
        values["blocked"].set("0" if blocked else "1")
        extra={key:values[key].get().strip() for key in ("postal","country","workplace","family","references","blocked","telephone2","cin_issued","cin_place","nationality","emergency_name","emergency_phone","emergency_relation","source")}
        app.conn.execute("INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,?)",
                         ("client_profile",cid,json.dumps(extra,ensure_ascii=False),datetime.now().isoformat(timespec="seconds")))
        app.conn.commit()
        messagebox.showinfo("Fiche client","Client débloqué." if blocked else "Client marqué comme bloqué.",parent=win)

    for title_text,command,color in (("Client rapide",lambda:app.open_quick_client_dialog(initial_client=code.get().strip()),BLUE),("Nouveau",new_client,"#005be5"),("Enregistrer",save_client,"#008747"),
                                     ("Modifier",lambda:save_client(True),"#ed8200"),("Supprimer",delete_client,"#cd0035"),("Fermer",close,"#e5f2fc")):
        button(top_actions,title_text,command,color,False).pack(side="left",padx=3)
    shortcuts_spec=(("ϟ","Client rapide","Formulaire client et contrat",GREEN,lambda:app.open_quick_client_dialog(initial_client=code.get().strip())),
                    ("▦","Nouvelle réservation","Faire une réservation",BLUE,reservation),
                    ("▤","Ouvrir dossier","Documents du client",ORANGE,open_folder),
                    ("▣","Scanner document","Scanner et enregistrer","#9548ea",lambda:scan_document("CIN")),
                    ("▤","Imprimer fiche","Imprimer la fiche client",BLUE,print_client),
                    ("⊘","Client bloqué","Bloquer / débloquer",RED,toggle_block))
    for col,(icon,label,description,color,command) in enumerate(shortcuts_spec):
        box=tk.Frame(shortcuts,bg="#f1f7fc",highlightbackground=LINE,highlightthickness=1)
        box.grid(row=0,column=col,sticky="ew",padx=3)
        button(box,icon,command,color).pack(side="left",padx=5,pady=4)
        caption=tk.Frame(box,bg="#f1f7fc");caption.pack(side="left",fill="x",expand=True)
        tk.Label(caption,text=label,bg="#f1f7fc",fg=INK,font=("Segoe UI",8,"bold"),
                 anchor="w").pack(anchor="w")
        if not embedded:
            tk.Label(caption,text=description,bg="#f1f7fc",fg="#54718d",font=("Segoe UI",7),
                     anchor="w").pack(anchor="w")
        box.bind("<Button-1>",lambda _event,c=command:c())

    def contact_action(kind):
        phone=re.sub(r'[^0-9+]','',values['telephone'].get())
        if not phone:messagebox.showwarning('Contact','Renseignez le téléphone du client.',parent=win);return
        if phone.startswith('0'):phone='212'+phone[1:]
        webbrowser.open('https://wa.me/'+phone.lstrip('+') if kind=='whatsapp' else 'tel:'+phone)
    def data_notes(cid):
        row=app.conn.execute("SELECT payload FROM module_records WHERE module='client_notes' AND record_id=?",(cid,)).fetchone()
        try:return json.loads(row[0]) if row else []
        except (ValueError,TypeError):return []
    def refresh_notes():
        note_tree.delete(*note_tree.get_children())
        for item in profile_notes:note_tree.insert('', 'end',values=(item.get('date',''),item.get('note',''),item.get('user','')))
    def add_note():
        cid=valid_client()
        if not cid:return
        text=simpledialog.askstring('Note client','Nouvelle note :',parent=win)
        if not text or not text.strip():return
        username=str(getattr(app,'current_user',{}) or '')
        if isinstance(getattr(app,'current_user',None),dict):username=app.current_user.get('username','ADMIN')
        profile_notes.insert(0,{'date':datetime.now().strftime('%d/%m/%Y'),'note':text.strip(),'user':username or 'ADMIN'})
        app.conn.execute("INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES('client_notes',?,?,?)",(cid,json.dumps(profile_notes,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')));app.conn.commit();refresh_notes()
    def refresh_finance():
        finance_tree.delete(*finance_tree.get_children());cid=code.get().strip()
        for ref,raw in app.conn.execute("SELECT record_id,payload FROM module_records WHERE module='payments' ORDER BY created_at DESC"):
            try:q=json.loads(raw)
            except (TypeError,ValueError):continue
            if str(q.get('client',''))==cid:finance_tree.insert('', 'end',values=(q.get('date',''),ref,q.get('contract',''),q.get('mode',''),q.get('amount','')))
    win._reference_values=values
    win._reference_select_client=select_client
    win._reference_save_client=save_client
    win._reference_new_client=new_client
    win._reference_tables={'clients':list_tree,'notes':note_tree,'finance':finance_tree,'history':hist_tree}
    style=ttk.Style(win)
    style.configure("HBZReference.Treeview",font=("Segoe UI",9),rowheight=27,
                    background="white",foreground=INK,fieldbackground="white")
    style.map("HBZReference.Treeview",background=[("selected","#bde4fb")],
              foreground=[("selected","#18284b")])
    style.configure("HBZReference.Treeview.Heading",font=("Segoe UI",9,"bold"),
                    background=BAR,foreground="white")
    list_tree.configure(style="HBZReference.Treeview")
    hist_tree.configure(style="HBZReference.Treeview")
    def refresh_synced_documents():
        if win.winfo_exists():refresh_documents()
    app._client_reference_refresh_documents=refresh_synced_documents
    refresh_list();new_client()
    fit_page(win)
    return win
