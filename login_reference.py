"""JUSTE PRO login layout; uses the existing account and password verification."""
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox
from PIL import Image,ImageTk
from contract_controls import IconButton

def password_account(app, password):
    """Resolve one active account without changing its role or credentials."""
    if not password:
        return None
    matches = []
    for role in ('ADMINISTRATEUR', 'UTILISATEUR'):
        row = app._login_account_for_role(role, password)
        if row is not None:
            matches.append(row)
    if len(matches) > 1:
        raise ValueError('Plusieurs comptes utilisent ce mot de passe. Contactez l’administrateur pour attribuer des mots de passe distincts.')
    return matches[0] if matches else None

def show_login(app):
    if app._authenticated:return
    win=app._secondary_window(app.root);win.title('Connexion — JUSTE PRO');win.configure(bg='#eaf4ff');win.transient(app.root);win.grab_set()
    width=min(1280,win.winfo_screenwidth()-50);height=min(850,win.winfo_screenheight()-100)
    win.geometry(f'{width}x{height}+{max(0,(win.winfo_screenwidth()-width)//2)}+{max(0,(win.winfo_screenheight()-height)//2)}');win.minsize(850,600)
    left=tk.Label(win,bg='#194d7c');left.place(relx=0,rely=0,relwidth=.55,relheight=1)
    source=Path(__file__).resolve().parent/'assets'/'login_juste_pro_reference.png'
    picture=None
    try:
        with Image.open(source) as im:picture=im.crop((0,0,round(im.width*.562),im.height)).copy()
    except OSError:left.configure(text='JUSTE PRO\nLocation de voitures',fg='white',font=('Segoe UI',28,'bold'))
    def resized(e):
        if picture and e.width>0 and e.height>0:
            left._image=ImageTk.PhotoImage(picture.resize((e.width,e.height),Image.Resampling.LANCZOS));left.configure(image=left._image)
    left.bind('<Configure>',resized)
    form=tk.Frame(win,bg='white');form.place(relx=.565,rely=.025,relwidth=.42,relheight=.95)
    tk.Label(form,text='JUSTE PRO',bg='white',fg='#063b70',font=('Segoe UI',30,'bold')).pack(pady=(35,5))
    tk.Label(form,text='G E S T I O N   D E   L O C A T I O N',bg='white',fg='#7b91a7',font=('Segoe UI',10)).pack(pady=(0,25))
    password=tk.StringVar();error=tk.StringVar()
    tk.Label(form,text='Mot de passe',bg='white',fg='#063b70',anchor='w',font=('Segoe UI',12,'bold')).pack(fill='x',padx=30)
    field=tk.Frame(form,bg='#c8d9eb',height=50)
    field.pack(fill='x',padx=30,pady=(8,12))
    field.pack_propagate(False)
    secret=tk.Entry(field,textvariable=password,show='•',font=('Segoe UI',16),bg='white',fg='#063b70',insertbackground='#063b70',relief='flat',bd=0)
    secret.place(x=2,y=2,relwidth=1,width=-52,height=46)
    reveal=tk.Button(field,text='Voir',command=lambda:toggle_password(),bg='#eaf4ff',fg='#063b70',relief='flat',takefocus=True)
    reveal.place(relx=1,x=-49,y=2,width=47,height=46)
    def toggle_password():
        hidden=bool(secret.cget('show'))
        secret.configure(show='' if hidden else '•')
        reveal.configure(text='Cacher' if hidden else 'Voir')
        secret.focus_set()
    tk.Label(form,textvariable=error,bg='white',fg='#c72435',wraplength=350).pack(fill='x',padx=30,pady=8)
    attempts={'count':0,'until':0}
    def authenticate():
        if time.monotonic()<attempts['until']:error.set('Patientez quelques secondes avant de réessayer.');return
        try:row=password_account(app,password.get())
        except ValueError as exc:error.set(str(exc));password.set('');return
        if not row:
            attempts['count']+=1
            if attempts['count']>=5:attempts['until']=time.monotonic()+30;attempts['count']=0
            error.set('Mot de passe incorrect.');password.set('');return
        app._authenticated=True;app.current_username=row[0];app.current_user=row[1] or row[0];app.current_role=row[3]
        app._apply_user_permissions_to_navigation();win.destroy();app.root.title(f"GestionPro — {app._get_setting('company_name','HBZ Rent Car')} — {app.current_user}");app.root.after(100,app._show_startup_alerts)
    IconButton(form,'Se connecter',authenticate,icon='person',width=350,height=54).pack(fill='x',padx=30,pady=10)
    IconButton(form,'Mot de passe oublié ?',lambda:messagebox.showinfo('Accès','Contactez l’administrateur pour réinitialiser votre mot de passe dans Paramètres utilisateurs.',parent=win),icon='info',width=350,height=38).pack(fill='x',padx=30,pady=4)
    tk.Label(form,text='Connexion par QR code : non disponible pour cette session PC.',bg='#edf6ff',fg='#61758b',wraplength=340,pady=10).pack(fill='x',padx=30,pady=15)
    tk.Label(form,text='Windows · Android · Web',bg='white',fg='#063b70').pack(pady=10)
    IconButton(form,'Quitter',app.close,icon='cancel',width=350,height=38).pack(fill='x',padx=30,pady=5)
    win.after_idle(secret.focus_set);win.bind('<Return>',lambda e:authenticate());win.bind('<Escape>',lambda e:app.close());win.protocol('WM_DELETE_WINDOW',app.close);win.wait_window()
