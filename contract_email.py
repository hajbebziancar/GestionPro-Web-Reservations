"""Prepare a user-reviewed email draft with the exported contract attached."""
import base64,json,re,subprocess,sys,webbrowser
from urllib.parse import urlencode
from tkinter import simpledialog,messagebox

def prepare_contract_email(app,parent,number,recipient=''):
    recipient=simpledialog.askstring('Email du client','Adresse email du destinataire :',initialvalue=recipient,parent=parent)
    if recipient is None:return
    recipient=recipient.strip()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',recipient):messagebox.showwarning('Email','Indiquez une adresse email valide.',parent=parent);return
    subject='Contrat de location '+str(number)
    body='Bonjour,\nVeuillez trouver votre contrat de location en pièce jointe.\nCordialement.'
    def draft(path):
        if sys.platform=='win32':
            # Data is embedded as base64 JSON, never interpolated as executable syntax.
            data=base64.b64encode(json.dumps({'recipient':recipient,'subject':subject,'body':body,'path':str(path.resolve())},ensure_ascii=False).encode()).decode()
            script="$d=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"+data+"'))|ConvertFrom-Json;try{$o=New-Object -ComObject Outlook.Application;$m=$o.CreateItem(0);$m.To=$d.recipient;$m.Subject=$d.subject;$m.Body=$d.body;$m.Attachments.Add($d.path)|Out-Null;$m.Display();exit 0}catch{exit 1}"
            command=base64.b64encode(script.encode('utf-16le')).decode()
            try:
                result=subprocess.run(['powershell','-NoProfile','-EncodedCommand',command],timeout=20,creationflags=0x08000000)
                if result.returncode==0:return
            except (OSError,subprocess.TimeoutExpired):pass
        webbrowser.open('mailto:'+recipient+'?'+urlencode({'subject':subject,'body':body}))
        messagebox.showinfo('Email','Le brouillon est ouvert. Joignez le PDF enregistré :\n'+str(path),parent=app.root)
    app.export_contract_recto_pdf(on_saved=draft)
