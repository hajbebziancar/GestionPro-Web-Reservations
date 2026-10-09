"""Unconditional local reservation cancellation/deletion, independent of booking validation."""
import json
from datetime import datetime
import tkinter as tk
from tkinter import messagebox

def apply_action(conn,reference,action):
    if action not in ('cancel','delete'):raise ValueError('Action inconnue')
    row=conn.execute("SELECT payload FROM module_records WHERE module='reservations' AND record_id=?",(reference,)).fetchone()
    if not row:return False
    stamp=datetime.now().isoformat(timespec='seconds')
    try:
        if action=='cancel':
            try:payload=json.loads(row[0])
            except (ValueError,TypeError):payload={'reference':reference}
            if not isinstance(payload,dict):payload={'reference':reference}
            payload['status']='ANNULÉ';payload['_local_reservation_action']='cancel'
            conn.execute("UPDATE module_records SET payload=?,created_at=? WHERE module='reservations' AND record_id=?",(json.dumps(payload,ensure_ascii=False),stamp,reference))
        else:conn.execute("DELETE FROM module_records WHERE module='reservations' AND record_id=?",(reference,))
        conn.execute("INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES('reservation_local_actions',?,?,?)",(reference,json.dumps({'action':action}),stamp))
        conn.commit()
    except Exception:
        conn.rollback();raise
    return True

def local_action(conn,reference):
    row=conn.execute("SELECT payload FROM module_records WHERE module='reservation_local_actions' AND record_id=?",(reference,)).fetchone()
    if row:
        try:return json.loads(row[0]).get('action','')
        except (ValueError,TypeError):pass
    return ''

def confirm(app,reference,action):
    """Always show explicit French Yes/No choices before changing the record."""
    deleting=action=='delete';color='#cf3855' if deleting else '#d88921'
    title='Supprimer la réservation' if deleting else 'Annuler la réservation'
    win=app._secondary_window(app.root);win.title(title);win.configure(bg='#f3f8fd');win.resizable(False,False);win.transient(app.root)
    result={'yes':False}
    tk.Label(win,text=title,bg=color,fg='white',font=('Segoe UI',14,'bold'),padx=15,pady=13).pack(fill='x')
    verb='supprimer' if deleting else 'annuler'
    tk.Label(win,text=f'Voulez-vous {verb} la réservation {reference},\nmême si des contraintes existent ?',bg='#f3f8fd',fg='#173b5a',font=('Segoe UI',11),wraplength=460,pady=18).pack(fill='both',expand=True,padx=15)
    foot=tk.Frame(win,bg='#f3f8fd');foot.pack(fill='x',padx=18,pady=(0,15))
    def yes():result['yes']=True;win.destroy()
    no=tk.Button(foot,text='Non',command=win.destroy,bg='#64758a',fg='white',relief='flat',font=('Segoe UI',10,'bold'),width=12,pady=7);no.pack(side='right',padx=5)
    tk.Button(foot,text='Oui',command=yes,bg=color,fg='white',relief='flat',font=('Segoe UI',10,'bold'),width=12,pady=7).pack(side='right',padx=5)
    win.protocol('WM_DELETE_WINDOW',win.destroy);win.bind('<Escape>',lambda e:win.destroy())
    win.update_idletasks();width,height=520,235
    win.geometry(f'{width}x{height}+{max(0,(win.winfo_screenwidth()-width)//2)}+{max(0,(win.winfo_screenheight()-height)//2)}')
    win.lift();win.grab_set();no.focus_set();win.wait_window()
    return result['yes']

def run(app,action):
    tree=getattr(app,'reservation_reference_table',None)
    selected=tree.selection() if tree else ()
    reference=str(selected[0]).split(':',1)[-1] if selected else app.module_vars['reservations']['reference'].get().strip()
    if not reference:
        messagebox.showinfo('Réservations','Sélectionnez une réservation.');return
    if not confirm(app,reference,action):return
    if not apply_action(app.conn,reference,action):
        messagebox.showinfo('Réservations','Réservation introuvable.');return
    app._audit('ANNULATION' if action=='cancel' else 'SUPPRESSION','RÉSERVATION',reference)
    app.conn.commit()
    if action=='cancel':app.module_vars['reservations']['status'].set('ANNULÉ')
    else:app.new_business_record('reservations')
    app.refresh_business_records('reservations');app.refresh_dashboard();app.schedule_web_sync()
