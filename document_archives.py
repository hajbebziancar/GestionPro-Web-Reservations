"""Numbered immutable PDF snapshots and multi-document selection."""
import html,json,os,re,tempfile,webbrowser,sqlite3,threading,queue,shutil,subprocess
from types import SimpleNamespace
from pathlib import Path
from datetime import datetime
import tkinter as tk
from tkinter import ttk,messagebox,filedialog
from contract_controls import IconButton
ROOT=Path(__file__).resolve().parent/'archives_documents'

def install(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS document_archives(id INTEGER PRIMARY KEY AUTOINCREMENT,kind TEXT NOT NULL,source_id TEXT NOT NULL,seq INTEGER NOT NULL,year INTEGER NOT NULL,amount REAL NOT NULL,customer TEXT,archived_at TEXT NOT NULL,pdf TEXT NOT NULL,UNIQUE(kind,source_id),UNIQUE(kind,year,seq))''');conn.commit()

def rows(conn,kind):
    install(conn);return [dict(r) for r in conn.execute('SELECT * FROM document_archives WHERE kind=? ORDER BY year,seq',(kind,))]

def total(conn,kind):return sum(r['amount'] for r in rows(conn,kind))

def merge_pdfs(paths,destination,recto_only=False):
    # Bundled pypdf is pure Python and does not depend on Windows DLLs.
    from pypdf import PdfReader,PdfWriter
    writer=PdfWriter()
    for path in paths:
        reader=PdfReader(str(path))
        for page in (reader.pages[:1] if recto_only else reader.pages):writer.add_page(page)
    if not writer.pages:raise ValueError('Aucun document à regrouper.')
    destination=Path(destination);temporary=destination.with_name(destination.name+'.tmp.pdf')
    try:
        with temporary.open('wb') as output:writer.write(output)
        os.replace(temporary,destination)
    finally:
        writer.close();temporary.unlink(missing_ok=True)

def archive(app,kind,source_id,content,amount,customer=''):
    install(app.conn);existing=app.conn.execute('SELECT * FROM document_archives WHERE kind=? AND source_id=?',(kind,str(source_id))).fetchone()
    if existing:return dict(existing)
    year=datetime.now().year;folder=ROOT/kind;folder.mkdir(parents=True,exist_ok=True)
    # Allocate under a write lock; failed PDF creation rolls back the number.
    app.conn.execute('BEGIN IMMEDIATE')
    dest=None
    try:
        app.conn.execute('CREATE TABLE IF NOT EXISTS archive_sequences(kind TEXT,year INTEGER,seq INTEGER,PRIMARY KEY(kind,year))')
        seq=app.conn.execute('SELECT MAX(value)+1 FROM (SELECT COALESCE(MAX(seq),0) AS value FROM document_archives WHERE kind=? AND year=? UNION ALL SELECT COALESCE(MAX(seq),0) FROM archive_sequences WHERE kind=? AND year=?)',(kind,year,kind,year)).fetchone()[0]
        display=f'{seq:06d}/{year}';filename=f'{seq:06d}-{year}.pdf';dest=folder/filename
        if kind=='contracts':
            # Replace the visible contract number in the archival copy, never mutate a signed source.
            escaped=html.escape(str(source_id))
            content=re.sub(r'>([^<>]*)<',lambda m:'>'+re.sub(r'(?<![\w/])'+re.escape(escaped)+r'(?![\w/])',display,m[1])+'<',content)
        with tempfile.TemporaryDirectory(prefix='gestpro_archive_') as tmp:
            hp=Path(tmp)/'document.html';hp.write_text(content,encoding='utf-8')
            if not app._create_pdf_preview(hp,dest,'Archivage PDF',contract_verso=False,single_page=(kind=='contracts'),open_result=False):raise ValueError('Le PDF n’a pas été créé ; aucun numéro d’archive attribué.')
        from pypdf import PdfReader
        pdf=PdfReader(str(dest))
        if not pdf.pages:raise ValueError('PDF vide.')
        if kind=='contracts' and len(pdf.pages)!=1:raise ValueError('Le contrat archivé doit contenir uniquement le recto.')
        app.conn.execute('INSERT INTO document_archives(kind,source_id,seq,year,amount,customer,archived_at,pdf) VALUES(?,?,?,?,?,?,?,?)',(kind,str(source_id),seq,year,float(amount),str(customer),datetime.now().isoformat(timespec='seconds'),str(dest.relative_to(ROOT))))
        app.conn.commit()
    except Exception:
        app.conn.rollback()
        if dest:dest.unlink(missing_ok=True)
        raise
    return dict(app.conn.execute('SELECT * FROM document_archives WHERE kind=? AND source_id=?',(kind,str(source_id))).fetchone())

def contract_content(app,number):
    from signed_contracts import signed_html,find_signed
    row=app.conn.execute('SELECT * FROM contracts WHERE numero=?',(number,)).fetchone()
    if not row:raise ValueError('Contrat introuvable.')
    record=find_signed(number)
    owners=record.get('client_codes',[]) if record else []
    path=signed_html(number,row['client_code']) if owners and str(owners[0])==str(row['client_code']) else None
    if path:return path.read_text(encoding='utf-8'),row
    app.contract_search_var.set(number);app.load_contract_lookup(check_conflict=False)
    return app._selected_contract_html(),row

def archive_contract(app,number):
    previous=getattr(app,'_archiving_documents',False)
    app._archiving_documents=True
    try:
        content,row=contract_content(app,number)
        client=app.conn.execute('SELECT nom,prenom FROM clients WHERE code=?',(row['client_code'],)).fetchone()
        return archive(app,'contracts',number,content,row['montant'] or 0,' '.join(str(x or '') for x in client) if client else row['client_code'])
    finally:
        app._archiving_documents=previous

def archive_invoice(app,record_id):
    row=app.conn.execute("SELECT payload FROM module_records WHERE module='invoices' AND record_id=?",(record_id,)).fetchone()
    if not row:raise ValueError('Facture introuvable.')
    p=json.loads(row[0]);return archive(app,'invoices',record_id,app._invoice_html(p),app._number(p.get('total')),p.get('customer_name',''))

def render_archive_pdf(html_path,pdf_path,title,contract_verso=False,single_page=False,open_result=False):
    """Worker-only renderer: no Tk calls and an isolated browser profile."""
    candidates=[]
    if os.name=='nt':
        for env in ('PROGRAMFILES','PROGRAMFILES(X86)','LOCALAPPDATA'):
            base=Path(os.environ.get(env,''))
            candidates.extend((base/'Google/Chrome/Application/chrome.exe',base/'Microsoft/Edge/Application/msedge.exe'))
    candidates.extend(Path(found) for name in ('chromium','chromium-browser','google-chrome','chrome','msedge') if (found:=shutil.which(name)))
    browser=next((str(p) for p in candidates if p.is_file()),None)
    if not browser:raise RuntimeError('Chrome ou Edge est nécessaire pour archiver en PDF.')
    with tempfile.TemporaryDirectory(prefix='gestpro_pdf_profile_') as profile:
        command=[browser,'--headless','--disable-gpu','--no-sandbox','--no-first-run','--disable-extensions',f'--user-data-dir={profile}',f'--print-to-pdf={pdf_path}','--no-pdf-header-footer',html_path.resolve().as_uri()]
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,creationflags=(0x08000000 if os.name=='nt' else 0))
        if result.returncode or not pdf_path.exists() or pdf_path.stat().st_size<1000:
            raise RuntimeError('Le navigateur n’a pas créé le PDF. '+result.stderr.decode(errors='ignore')[-300:])
    if single_page:
        from contract_print_details import ensure_single_recto_pdf
        ensure_single_recto_pdf(pdf_path)
    return True

def archive_batch(app,kind,ids,parent,done):
    """Prepare Tk-dependent HTML on the UI thread; render/commit off-thread."""
    if getattr(app,'_archive_batch_running',False):return
    database=app.conn.execute('PRAGMA database_list').fetchone()[2]
    if not database:raise ValueError('Archivage impossible : base de données sans fichier.')
    app._archive_batch_running=True
    win=tk.Toplevel(app.root);win.title('Archivage en cours');win.transient(app.root)
    label=tk.Label(win,text='Préparation…',font=('Segoe UI',12,'bold'),padx=28,pady=18);label.pack()
    progress=ttk.Progressbar(win,maximum=len(ids),length=350);progress.pack(padx=20,pady=8)
    stopped=[False];records=[];messages=queue.Queue()
    def cancel():stopped[0]=True;label.configure(text='Arrêt après le document en cours…')
    tk.Button(win,text='Arrêter',command=cancel).pack(pady=10);win.protocol('WM_DELETE_WINDOW',cancel)
    def finish(error=None):
        app._archive_batch_running=False;win.destroy()
        if error:messagebox.showerror('Archivage',str(error),parent=parent)
        else:done(records)
    def step(index=0):
        if stopped[0] or index==len(ids):finish();return
        source_id=ids[index];label.configure(text=f'Archivage {index+1} / {len(ids)} · {source_id}')
        try:
            existing=app.conn.execute('SELECT * FROM document_archives WHERE kind=? AND source_id=?',(kind,str(source_id))).fetchone()
            if existing:
                records.append(dict(existing));progress['value']=index+1;win.after(1,lambda:step(index+1));return
            previous=getattr(app,'_archiving_documents',False);app._archiving_documents=True
            try:
                if kind=='contracts':
                    content,row=contract_content(app,source_id)
                    client=app.conn.execute('SELECT nom,prenom FROM clients WHERE code=?',(row['client_code'],)).fetchone()
                    amount=row['montant'] or 0;customer=' '.join(str(x or '') for x in client) if client else row['client_code']
                else:
                    row=app.conn.execute("SELECT payload FROM module_records WHERE module='invoices' AND record_id=?",(source_id,)).fetchone()
                    if not row:raise ValueError('Facture introuvable.')
                    payload=json.loads(row[0]);content=app._invoice_html(payload);amount=app._number(payload.get('total'));customer=payload.get('customer_name','')
            finally:app._archiving_documents=previous
        except Exception as exc:finish(exc);return
        def work():
            conn=sqlite3.connect(database,timeout=5);conn.row_factory=sqlite3.Row
            try:
                proxy=SimpleNamespace(conn=conn,_create_pdf_preview=render_archive_pdf)
                messages.put((archive(proxy,kind,source_id,content,amount,customer),None))
            except Exception as exc:messages.put((None,str(exc)))
            finally:conn.close()
        threading.Thread(target=work,daemon=True).start()
        def poll():
            try:record,error=messages.get_nowait()
            except queue.Empty:win.after(75,poll);return
            if error:finish(error);return
            records.append(record);progress['value']=index+1;win.after(1,lambda:step(index+1))
        win.after(75,poll)
    win.after(1,step)

def open_archives(app,kind='contracts'):
    data=rows(app.conn,kind);win=app._secondary_window(app.root);win.title('Contrats archivés' if kind=='contracts' else 'Factures archivées');win.configure(bg='#f4faff');win.transient(app.root)
    width=min(1050,win.winfo_screenwidth()-60);height=min(650,win.winfo_screenheight()-100);win.geometry(f'{width}x{height}+{max(0,(win.winfo_screenwidth()-width)//2)}+{max(0,(win.winfo_screenheight()-height)//2)}')
    summary=tk.StringVar();tk.Label(win,textvariable=summary,bg='#e5f2ff',fg='#074575',font=('Segoe UI',13,'bold'),pady=16).pack(fill='x')
    filters=tk.Frame(win,bg='#f4faff');filters.pack(fill='x',padx=15,pady=6)
    date_from=tk.StringVar();date_to=tk.StringVar();date_basis=tk.StringVar(value='Date de départ' if kind=='contracts' else 'Date d’archivage');bounds=[None,None]
    tk.Label(filters,text='Période :',bg='#f4faff').pack(side='left',padx=4)
    ttk.Combobox(filters,textvariable=date_basis,values=['Date de départ','Date d’archivage'] if kind=='contracts' else ['Date d’archivage'],state='readonly',width=19).pack(side='left',padx=4)
    for caption,var in [('Du',date_from),('Au',date_to)]:
        tk.Label(filters,text=caption,bg='#f4faff').pack(side='left',padx=4)
        ttk.Entry(filters,textvariable=var,width=12,justify='center').pack(side='left',padx=4)
    tk.Label(filters,text='JJ/MM/AAAA',bg='#f4faff',fg='#63758b').pack(side='left',padx=4)
    contract_dates={str(r['numero']):r['date_depart'] for r in app.conn.execute('SELECT numero,date_depart FROM contracts')} if kind=='contracts' else {}
    def parsed(value):
        value=str(value or '').strip()[:10]
        for fmt in ('%d/%m/%Y','%Y-%m-%d'):
            try:return datetime.strptime(value,fmt).date()
            except ValueError:pass
        raise ValueError('Date invalide : utilisez JJ/MM/AAAA.')
    def visible_rows():
        if bounds==[None,None]:return list(data)
        result=[]
        for r in data:
            value=contract_dates.get(str(r['source_id']),r['archived_at']) if date_basis.get()=='Date de départ' else r['archived_at']
            try:day=parsed(value)
            except ValueError:continue
            if (bounds[0] is None or day>=bounds[0]) and (bounds[1] is None or day<=bounds[1]):result.append(r)
        return result
    def apply_filter():
        try:
            low=parsed(date_from.get()) if date_from.get().strip() else None
            high=parsed(date_to.get()) if date_to.get().strip() else None
            if low and high and low>high:raise ValueError('La date Du doit précéder la date Au.')
        except ValueError as exc:messagebox.showerror('Période',str(exc),parent=win);return
        bounds[:]=[low,high];refresh()
    def reset_filter():date_from.set('');date_to.set('');bounds[:]=[None,None];refresh()
    IconButton(filters,'Filtrer',apply_filter,icon='search',color='#087bea',width=95,height=32).pack(side='left',padx=4)
    IconButton(filters,'Réinitialiser',reset_filter,icon='eraser',color='#64748b',width=120,height=32).pack(side='left',padx=4)
    cols=('check','number','client','date','amount');tree=ttk.Treeview(win,columns=cols,show='headings')
    for c,t,w in zip(cols,('Choisir','N° archive','Client','Date d’archivage','Montant (DH)'),(60,140,260,180,130)):tree.heading(c,text=t);tree.column(c,width=w,anchor='center')
    tree.pack(fill='both',expand=True,padx=15,pady=12);chosen=set();by_id={str(r['id']):r for r in data}
    def refresh():
        visible=visible_rows();visible_ids={str(r['id']) for r in visible};chosen.intersection_update(visible_ids)
        for iid in tree.get_children():
            if iid not in visible_ids:tree.delete(iid)
        for r in visible:
            iid=str(r['id']);v=('☑' if iid in chosen else '☐',f"{r['seq']:06d}/{r['year']}",r['customer'],r['archived_at'][:10],f"{r['amount']:,.2f}")
            if tree.exists(iid):tree.item(iid,values=v)
            else:tree.insert('','end',iid=iid,values=v)
        summary.set(f"Total archivé : {sum(r['amount'] for r in data):,.2f} DH · Période : {sum(r['amount'] for r in visible):,.2f} DH · Sélection : {sum(by_id[i]['amount'] for i in chosen):,.2f} DH ({len(chosen)})")
    def toggle(e):
        iid=tree.identify_row(e.y)
        if iid and tree.identify_column(e.x)=='#1':
            chosen.remove(iid) if iid in chosen else chosen.add(iid);refresh();return 'break'
    def merge():
        if not chosen:messagebox.showinfo('PDF','Sélectionnez au moins un document.',parent=win);return
        folder=ROOT/kind/'PDF_regroupes';folder.mkdir(parents=True,exist_ok=True)
        period='_'.join(day.strftime('%d-%m-%Y') if day else 'Toutes_dates' for day in bounds)
        name=f'{kind}_{period}_{datetime.now():%Y%m%d_%H%M%S}.pdf'
        dest=filedialog.asksaveasfilename(parent=win,initialdir=str(folder),defaultextension='.pdf',filetypes=[('PDF','*.pdf')],initialfile=name)
        if not dest:return
        try:merge_pdfs([ROOT/r['pdf'] for r in data if str(r['id']) in chosen],dest,recto_only=(kind=='contracts'));webbrowser.open(Path(dest).resolve().as_uri())
        except Exception as exc:messagebox.showerror('PDF',str(exc),parent=win)
    def open_one(e):
        iid=tree.identify_row(e.y)
        if iid and tree.identify_column(e.x)!='#1':webbrowser.open((ROOT/by_id[iid]['pdf']).resolve().as_uri())
    def delete_selected():
        if not chosen:
            messagebox.showinfo('Archives','Sélectionnez au moins un document.',parent=win);return
        if not messagebox.askyesno('Supprimer la sélection',f'Supprimer {len(chosen)} archive(s) ? Les contrats et factures d’origine seront conservés.',parent=win):return
        selected_rows=[r for r in data if str(r['id']) in chosen]
        try:
            # Keep numbering monotonic even when the most recent archive is removed.
            with app.conn:
                app.conn.execute('CREATE TABLE IF NOT EXISTS archive_sequences(kind TEXT,year INTEGER,seq INTEGER,PRIMARY KEY(kind,year))')
                for r in selected_rows:
                    high=app.conn.execute('SELECT MAX(seq) FROM document_archives WHERE kind=? AND year=?',(kind,r['year'])).fetchone()[0]
                    app.conn.execute('INSERT INTO archive_sequences VALUES(?,?,?) ON CONFLICT(kind,year) DO UPDATE SET seq=MAX(seq,excluded.seq)',(kind,r['year'],high))
                    app.conn.execute('DELETE FROM document_archives WHERE id=? AND kind=?',(r['id'],kind))
            for r in selected_rows:
                tree.delete(str(r['id']));by_id.pop(str(r['id']),None);data.remove(r)
            chosen.clear();refresh()
        except Exception as exc:messagebox.showerror('Archives',str(exc),parent=win)
    def open_grouped_folder():
        folder=ROOT/kind/'PDF_regroupes';folder.mkdir(parents=True,exist_ok=True)
        if os.name=='nt':os.startfile(str(folder))
        else:webbrowser.open(folder.resolve().as_uri())
    def choose_all():chosen.update(str(r["id"]) for r in visible_rows());refresh()
    def clear():chosen.clear();refresh()
    tree.bind('<Button-1>',toggle);tree.bind('<Double-1>',open_one)
    bar=tk.Frame(win,bg='#f4faff');bar.pack(fill='x',padx=15,pady=6,before=tree)
    for text,fn,icon,color in [('Tout sélectionner',choose_all,'check','#087bea'),('Désélectionner',clear,'eraser','#64748b'),('Regrouper PDF',merge,'pdf','#8b42c5'),('Supprimer la sélection',delete_selected,'trash','#dc3545'),('PDF regroupés',open_grouped_folder,'document','#039c7b'),('Fermer',win.destroy,'cancel','#334155')]:IconButton(bar,text,fn,icon=icon,color=color,width=145,height=34).pack(side='left',padx=4)
    refresh();return win

def install_table_actions(app,parent,kind,tree,checkbox_column=None):
    install(app.conn);selected=set();summary=tk.StringVar();archived=tk.StringVar()
    # Place the controls before the table's direct container, never below it.
    table_box=tree
    while table_box.master is not parent:table_box=table_box.master
    bar=tk.Frame(parent,bg='#e5f2ff');bar.pack(fill='x',padx=12,pady=6,before=table_box)
    tk.Label(bar,textvariable=archived,bg='#e5f2ff',fg='#074575',font=('Segoe UI',11,'bold')).pack(side='left',padx=12)
    tk.Label(bar,textvariable=summary,bg='#e5f2ff',fg='#087a35',font=('Segoe UI',11,'bold')).pack(side='left',padx=10)
    buttons=tk.Frame(parent,bg='#f4faff');buttons.pack(fill='x',padx=12,pady=(0,5),before=table_box)
    def record(iid):return iid.split(':',1)[1] if kind=='invoices' else str(tree.item(iid,'values')[0])
    def eligible(iid):return 'passage' not in tree.item(iid,'tags')
    def refresh():
        archived.set(f"Montant {'factures' if kind=='invoices' else 'contrats'} archivés : {total(app.conn,kind):,.2f} DH")
        present={record(i) for i in tree.get_children() if eligible(i)}
        selected.intersection_update(present)
        amount=0
        for source_id in selected:
            if kind=='invoices':
                row=app.conn.execute("SELECT payload FROM module_records WHERE module='invoices' AND record_id=?",(source_id,)).fetchone()
                if row:amount+=app._number(json.loads(row[0]).get('total'))
            else:
                row=app.conn.execute('SELECT montant FROM contracts WHERE numero=?',(source_id,)).fetchone()
                if row:amount+=float(row[0] or 0)
        summary.set(f'Sélection : {len(selected)} · {amount:,.2f} DH')
        for iid in tree.get_children():
            mark=('☑' if record(iid) in selected else '☐') if eligible(iid) else ''
            if checkbox_column:tree.set(iid,checkbox_column,mark)
            else:tree.item(iid,text=mark)
    tree.configure(show='tree headings')
    if checkbox_column:
        columns=list(tree['columns'])
        if checkbox_column not in columns:tree.configure(columns=columns+[checkbox_column])
        tree.heading(checkbox_column,text='Choisir');tree.column(checkbox_column,width=50,minwidth=40,anchor='center',stretch=False)
        tree.configure(displaycolumns=(checkbox_column,*columns))
    else:
        tree.heading('#0',text='Choisir');tree.column('#0',width=85,minwidth=55,stretch=False)
    def clicked(e):
        iid=tree.identify_row(e.y)
        if iid and tree.identify_column(e.x)==('#1' if checkbox_column else '#0'):
            if eligible(iid):
                source_id=record(iid)
                selected.remove(source_id) if source_id in selected else selected.add(source_id)
                refresh()
            return 'break'
    tree.bind('<Button-1>',clicked,add='+')
    def selected_records():
        return list(dict.fromkeys(record(i) for i in tree.get_children() if eligible(i) and record(i) in selected))
    def archive_selected():
        ids=selected_records()
        if not ids:messagebox.showinfo('Archivage','Cochez les documents à archiver.',parent=parent);return
        def completed(records):refresh();open_archives(app,kind)
        archive_batch(app,kind,ids,parent,completed)
    def merge_selected():
        ids=selected_records()
        if not ids:messagebox.showinfo('PDF','Cochez les documents à regrouper.',parent=parent);return
        dest=filedialog.asksaveasfilename(parent=parent,defaultextension='.pdf',filetypes=[('PDF','*.pdf')],initialfile='Documents_selectionnes.pdf')
        if not dest:return
        def completed(records):
            refresh()
            if not records:return
            try:merge_pdfs([ROOT/r['pdf'] for r in records],dest,recto_only=(kind=='contracts'));webbrowser.open(Path(dest).resolve().as_uri())
            except Exception as exc:messagebox.showerror('PDF',str(exc),parent=parent)
        archive_batch(app,kind,ids,parent,completed)
    def all_selected():selected.update(record(i) for i in tree.get_children() if eligible(i));refresh()
    def none_selected():selected.clear();refresh()
    actions=[('Archiver la sélection',archive_selected,'save'),('Contrats archivés',lambda:open_archives(app,'contracts'),'document'),('Regrouper PDF',merge_selected,'pdf'),('Tout',all_selected,'check'),('Aucun',none_selected,'eraser')]
    if kind=='invoices':actions.insert(2,('Factures archivées',lambda:open_archives(app,'invoices'),'document'))
    colors={'Archiver la sélection':'#16864b','Contrats archivés':'#087f82','Factures archivées':'#7153dc','Regrouper PDF':'#c83248','Tout':'#0789ee','Aucun':'#60788a'}
    widgets=[]
    for text,fn,icon in reversed(actions):
        width=158 if text=='Archiver la sélection' else 140 if 'archivés' in text or 'archivées' in text else 125 if text=='Regrouper PDF' else 70
        widgets.append(IconButton(buttons,text,fn,color=colors[text],icon=icon,width=width,height=32))
    def arrange(event=None):
        available=max(1,buttons.winfo_width()-8);x=0;row=0;col=0
        for widget in widgets:
            width=int(widget.cget('width'))+6
            if x and x+width>available:row+=1;col=0;x=0
            widget.grid(row=row,column=col,padx=3,pady=2,sticky='w');x+=width;col+=1
    buttons.bind('<Configure>',arrange);arrange()
    refresh();return refresh
