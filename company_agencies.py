"""Agences de la société et coordonnées, partagées par les contrats."""
import tkinter as tk
from tkinter import ttk,messagebox
import re

class AgencyStore:
    def __init__(self,conn):
        self.conn=conn
        conn.execute('CREATE TABLE IF NOT EXISTS company_agencies(id INTEGER PRIMARY KEY,name TEXT UNIQUE NOT NULL,address TEXT NOT NULL DEFAULT "",email TEXT NOT NULL DEFAULT "",phone TEXT NOT NULL DEFAULT "")')
        conn.commit()
    def list(self):return self.conn.execute('SELECT * FROM company_agencies ORDER BY name').fetchall()
    def save(self,name,address,email,phone,record_id=None):
        name=name.strip();email=email.strip()
        if not name:raise ValueError('Indiquez le nom de l’agence.')
        if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email):raise ValueError('Adresse email invalide.')
        with self.conn:
            if record_id:self.conn.execute('UPDATE company_agencies SET name=?,address=?,email=?,phone=? WHERE id=?',(name,address.strip(),email,phone.strip(),record_id))
            else:self.conn.execute('INSERT INTO company_agencies(name,address,email,phone) VALUES(?,?,?,?)',(name,address.strip(),email,phone.strip()))

def open_agencies(parent,store,on_change=lambda:None):
    win=tk.Toplevel(parent);win.title('Agences de la société — email et coordonnées');win.geometry('780x520');win.transient(parent.winfo_toplevel())
    tk.Label(win,text='AGENCES DE LA SOCIÉTÉ',bg='#0065ef',fg='white',font=('Segoe UI',15,'bold'),pady=14).pack(fill='x')
    fields={key:tk.StringVar() for key in ('name','address','email','phone')};current=[None]
    form=tk.Frame(win);form.pack(fill='x',padx=18,pady=12)
    for i,(key,title) in enumerate((('name','Nom de l’agence *'),('address','Adresse'),('email','Email de l’agence'),('phone','Téléphone'))):
        tk.Label(form,text=title).grid(row=i,column=0,sticky='w',pady=5)
        ttk.Entry(form,textvariable=fields[key],width=65).grid(row=i,column=1,sticky='ew',padx=10,pady=5)
    form.columnconfigure(1,weight=1)
    tree=ttk.Treeview(win,columns=('name','email','phone'),show='headings')
    for key,title in [('name','Agence'),('email','Email'),('phone','Téléphone')]:tree.heading(key,text=title)
    tree.pack(fill='both',expand=True,padx=18)
    def refresh():
        tree.delete(*tree.get_children())
        for row in store.list():tree.insert('','end',iid=str(row['id']),values=(row['name'],row['email'],row['phone']))
    def selected(_):
        if not tree.selection():return
        current[0]=int(tree.selection()[0]);row=next(r for r in store.list() if r['id']==current[0])
        for key,var in fields.items():var.set(row[key])
    tree.bind('<<TreeviewSelect>>',selected)
    def new():
        current[0]=None
        for var in fields.values():var.set('')
    def save():
        try:store.save(*(fields[k].get() for k in ('name','address','email','phone')),record_id=current[0])
        except Exception as exc:messagebox.showerror('Agence',str(exc),parent=win);return
        refresh();on_change();new()
    bar=tk.Frame(win);bar.pack(fill='x',padx=18,pady=12)
    for title,command,color in [('Nouvelle agence',new,'#0065ef'),('Enregistrer',save,'#009642'),('Fermer',win.destroy,'#64748b')]:tk.Button(bar,text=title,command=command,bg=color,fg='white',relief='flat',padx=18,pady=8).pack(side='left',padx=4)
    refresh();return win
