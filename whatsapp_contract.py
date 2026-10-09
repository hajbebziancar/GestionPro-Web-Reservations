"""Prépare un contrat PDF et ouvre la conversation WhatsApp du client."""
import re
import os
import webbrowser
import tkinter as tk
from pathlib import Path
from urllib.parse import quote
from tkinter import messagebox

def normalize_whatsapp_number(raw):
    text=str(raw or '').strip();digits=re.sub(r'\D','',text)
    if text.startswith('00'):digits=digits[2:]
    elif digits.startswith('0') and len(digits)==10:digits='212'+digits[1:]
    elif len(digits)==9 and digits[0] in '567':digits='212'+digits
    if not 8<=len(digits)<=15 or digits.startswith('0'):raise ValueError('Ajoutez un numéro de téléphone valide dans la fiche client, avec l’indicatif du pays.')
    return digits

def whatsapp_pdf_url(phone,number):
    return 'https://wa.me/'+normalize_whatsapp_number(phone)+'?text='+quote(f'Bonjour, voici votre contrat de location n° {number}.')

def open_whatsapp_pdf(parent,phone,path,number):
    path=Path(path)
    if not path.is_file():messagebox.showerror('WhatsApp','Le PDF du contrat n’a pas été créé.',parent=parent);return
    win=tk.Toplevel(parent);win.title('PDF pour WhatsApp — client');win.geometry('660x245');win.transient(parent.winfo_toplevel())
    tk.Label(win,text='PDF prêt pour le client : +'+phone,bg='#159447',fg='white',font=('Segoe UI',13,'bold'),pady=12).pack(fill='x')
    tk.Label(win,text='La conversation du client va s’ouvrir. Dans WhatsApp, choisissez\nJoindre → Document, sélectionnez ce PDF, puis confirmez l’envoi.',justify='left',font=('Segoe UI',10)).pack(anchor='w',padx=18,pady=12)
    value=tk.StringVar(value=str(path.resolve()));tk.Entry(win,textvariable=value,state='readonly',font=('Segoe UI',9)).pack(fill='x',padx=18)
    def copy():win.clipboard_clear();win.clipboard_append(str(path.resolve()));win.update()
    def folder():
        if os.name=='nt':
            import subprocess
            subprocess.Popen(['explorer.exe','/select,',str(path.resolve())])
        else:webbrowser.open(path.parent.resolve().as_uri())
    bar=tk.Frame(win);bar.pack(fill='x',padx=18,pady=14)
    for title,command in [('Copier le chemin du PDF',copy),('Afficher le PDF dans son dossier',folder),('Fermer',win.destroy)]:tk.Button(bar,text=title,command=command,padx=10,pady=6).pack(side='left',padx=4)
    webbrowser.open(whatsapp_pdf_url(phone,number));return win
