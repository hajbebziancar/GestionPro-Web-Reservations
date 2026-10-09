"""Tabular transfers: filtered exports and additive validated contract imports."""
import sqlite3
from datetime import datetime
from tkinter import filedialog,messagebox
from contract_controls import IconButton
import tkinter as tk

def import_contract_rows(conn, rows, client_code=None):
    schema=list(conn.execute('PRAGMA table_info(contracts)'))
    allowed={r[1] for r in schema}; required={r[1] for r in schema if r[3] and r[4] is None}
    prepared=[]; skipped=0
    for raw in rows:
        row={str(k).strip().casefold():v for k,v in raw.items() if str(k).strip().casefold() in allowed}
        number=str(row.get('numero') or '').strip();row['numero']=number
        if not number:raise ValueError('Une ligne ne contient pas de numéro de contrat.')
        if conn.execute('SELECT 1 FROM contracts WHERE numero=?',(number,)).fetchone():skipped+=1;continue
        if required-set(row):raise ValueError('Colonnes obligatoires absentes : '+', '.join(sorted(required-set(row))))
        for col,table in (('client_code','clients'),('second_code','clients'),('vehicle_code','vehicles')):
            value=str(row.get(col) or '').strip();row[col]=value
            if (col!='second_code' or value) and not conn.execute('SELECT 1 FROM '+table+' WHERE code=?',(value,)).fetchone():raise ValueError('Code inconnu : '+col+' = '+value)
        if client_code and client_code not in (row['client_code'],row['second_code']):raise ValueError('Ce contrat ne concerne pas le client sélectionné.')
        for col in ('date_depart','date_retour'):
            datetime.strptime(str(row.get(col,'')),'%d/%m/%Y')
        for col in ('duree','prix','montant','reglement','reste','km_depart','km_retour'):
            if col in row:row[col]=float(str(row[col] or 0).replace(' ','').replace(',','.'))
        prepared.append(row)
    conn.execute('SAVEPOINT history_import')
    try:
        for row in prepared:
            if conn.execute('SELECT 1 FROM contracts WHERE numero=?',(row['numero'],)).fetchone():skipped+=1;continue
            columns=list(row);conn.execute('INSERT INTO contracts ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',[row[c] for c in columns])
        conn.execute('RELEASE history_import')
    except Exception:
        conn.execute('ROLLBACK TO history_import');conn.execute('RELEASE history_import');raise
    return len(prepared),skipped

def export_history(app, parent, tree):
    path=filedialog.asksaveasfilename(parent=parent,defaultextension='.xlsx',filetypes=app._tabular_filetypes(),initialfile='historique_locations.xlsx')
    if not path:return
    try:
        ids=list(dict.fromkeys(str(tree.item(i,'values')[0]) for i in tree.get_children() if 'passage' not in tree.item(i,'tags')))
        columns=[r[1] for r in app.conn.execute('PRAGMA table_info(contracts)')]
        rows=[app.conn.execute('SELECT * FROM contracts WHERE numero=?',(n,)).fetchone() for n in ids]
        app._write_tabular_file(path,columns,[r for r in rows if r is not None])
        messagebox.showinfo('Export',str(len(rows))+' contrat(s) exporté(s).',parent=parent)
    except (OSError,ValueError,RuntimeError,sqlite3.Error) as exc:messagebox.showerror('Export',str(exc),parent=parent)

def import_history(app,parent,refresh,client_code=None):
    path=filedialog.askopenfilename(parent=parent,filetypes=app._tabular_filetypes())
    if not path:return
    try:
        rows=[app._normalize_import_row('contracts',r) for r in app._read_tabular_file(path)]
        added,skipped=import_contract_rows(app.conn,rows,client_code)
        refresh();app.refresh_dashboard();app._load_search_values()
        messagebox.showinfo('Import',f'{added} contrat(s) ajouté(s), {skipped} déjà présent(s).',parent=parent)
    except Exception as exc:messagebox.showerror('Import',str(exc),parent=parent)

def install_page_transfers(app,page,name):
    if not page.winfo_exists():return
    def captions(w):
        text=getattr(w,'caption','')
        try:text+=' '+str(w.cget('text'))
        except tk.TclError:pass
        return [text]+[s for c in w.winfo_children() if c.winfo_manager() for s in captions(c)]
    texts=captions(page)
    known={'clients':(app.import_clients_csv,app.export_clients_csv),'vehicles':(app.import_vehicles_csv,app.export_vehicles_csv)}
    if name in known:imp,exp=known[name]
    elif name=='history':
        imp=lambda:import_history(app,page,app.refresh_history)
        exp=lambda:export_history(app,page,app.history_tree)
    elif name in getattr(app,'module_fields',{}):
        imp=lambda:app.import_business_records(name);exp=lambda:app.export_business_records(name)
    else:return
    missing=[(title,fn,icon,color) for title,fn,icon,color in (('Importer',imp,'document','#7153dc'),('Exporter',exp,'save','#0789ee')) if not any(title.casefold() in s.casefold() for s in texts)]
    if not missing:return
    bar=tk.Frame(page,bg='#eaf4ff');children=page.pack_slaves()
    bar.pack(fill='x',padx=16,pady=4,**({'before':children[0]} if children else {}))
    for title,fn,icon,color in missing:IconButton(bar,title,fn,color,icon=icon,width=130,height=34).pack(side='left',padx=4,pady=3)
