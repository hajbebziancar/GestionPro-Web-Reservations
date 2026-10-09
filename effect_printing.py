"""Impression des effets sur supports préimprimés, sans écriture financière."""
import json, html, tempfile, webbrowser
from pathlib import Path
from decimal import Decimal, InvalidOperation
from datetime import date
import tkinter as tk
from tkinter import ttk, messagebox

FIELDS={'beneficiary':'Bénéficiaire','amount':'Montant en chiffres','words':'Montant en lettres','place':'Lieu','date':'Date de création','due_date':'Date d’échéance','bank':'Banque / domiciliation','number':'Numéro de l’effet','issuer':'Tiré · nom / dénomination','account':'Compte bancaire'}

FIELDS.update({'drawer': 'Tireur · nom / dénomination', 'drawer_address': 'Tireur · adresse / siège', 'drawee_address': 'Tiré · adresse', 'bank_city': 'Domiciliation · ville', 'cause': 'Cause de la traite', 'acceptance': 'Date d’acceptation', 'aval': 'Bon pour aval · identité'})

def french_number(n):
    units=['zéro','un','deux','trois','quatre','cinq','six','sept','huit','neuf','dix','onze','douze','treize','quatorze','quinze','seize']
    if n<17:return units[n]
    if n<20:return 'dix-'+units[n-10]
    if n<70:
        a,b=divmod(n,10);head=['','','vingt','trente','quarante','cinquante','soixante'][a]
        return head+(' et un' if b==1 else '-'+french_number(b) if b else '')
    if n<80:return 'soixante'+(' et onze' if n==71 else '-'+french_number(n-60))
    if n<100:return 'quatre-vingts' if n==80 else 'quatre-vingt-'+french_number(n-80)
    if n<1000:
        a,b=divmod(n,100);return ('' if a==1 else french_number(a)+' ')+'cent'+('s' if a>1 and not b else '')+(' '+french_number(b) if b else '')
    for power,label in ((1000000000,'milliard'),(1000000,'million'),(1000,'mille')):
        if n>=power:
            a,b=divmod(n,power);head=label if power==1000 and a==1 else french_number(a)+' '+label+('s' if power!=1000 and a>1 else '')
            return head+(' '+french_number(b) if b else '')

def money_words(value):
    text=''.join(str(value or '').split()).replace(',','.')
    if not text:raise ValueError('Saisissez le montant du chèque ou de la traite avant de préparer l’impression.')
    try:
        amount=Decimal(text)
        if not amount.is_finite() or amount<=0 or amount>=Decimal('1000000000000'):raise ValueError('Saisissez un montant positif valide.')
        amount=amount.quantize(Decimal('.01'))
    except InvalidOperation:
        raise ValueError('Montant invalide. Exemple : 1 250,50 MAD, sans écrire MAD dans le champ.') from None
    whole=int(amount);cents=int((amount-whole)*100)
    return french_number(whole)+' dirham'+('s' if whole!=1 else '')+(' et '+french_number(cents)+' centime'+('s' if cents!=1 else '') if cents else '')

def default_template(kind):
    positions={'beneficiary':[30,38,140,11,1],'amount':[160,15,40,12,1],'words':[20,25,175,10,1],'place':[130,52,30,10,1],'date':[164,52,40,10,1],'due_date':[150,65,45,10,kind=='TRAITE'],'bank':[20,65,110,10,kind=='TRAITE'],'number':[20,15,65,10,0],'issuer':[20,76,110,10,kind=='TRAITE'],'account':[20,84,110,8,0]}
    positions.update({k:[0,0,40,10,0] for k in ['drawer', 'drawer_address', 'drawee_address', 'bank_city', 'cause', 'acceptance', 'aval']})
    if kind=='TRAITE':
        positions.update(beneficiary=[59,27,94,9,1],amount=[177,20,37,11,1],words=[159,55,55,9,1],place=[69,43,31,9,1],date=[105,43,44,9,1],due_date=[174,9,40,10,1],bank=[68,86,80,8,1],number=[5,18,31,9,1],issuer=[67,59,82,9,1],account=[68,77,79,8,1],drawer=[5,40,56,9,1],drawer_address=[5,50,56,8,1],drawee_address=[67,66,82,8,1],bank_city=[68,91,79,8,1],cause=[83,50,66,9,1],acceptance=[5,68,30,9,0],aval=[5,87,55,9,0])
    if kind!='TRAITE':
        positions.update(beneficiary=[35,28,140,11,1],amount=[120,9,40,12,1],words=[15,23,120,10,1],place=[82,36,30,10,1],date=[164,52,40,10,0],due_date=[125,36,45,10,1])
    return {'width':220 if kind=='TRAITE' else 175,'height':104 if kind=='TRAITE' else 80,'offset_x':0,'offset_y':0,'positions':positions}

def render_document(values,template,path,guide=False):
    w=float(template['width']);h=float(template['height']);ox=float(template['offset_x']);oy=float(template['offset_y'])
    if not (40<=w<=420 and 30<=h<=297):raise ValueError('Dimensions du support invalides.')
    family=template.get('font_family','Arial')
    if family not in ('Arial','Calibri','Times New Roman','Courier New'):family='Arial'
    parts=[]
    for key,pos in template['positions'].items():
        x,y,width,font,enabled=pos
        if not enabled:continue
        x=float(x)+ox;y=float(y)+oy;width=float(width);font=float(font)
        if x<0 or y<0 or x+width>w or y>=h or width<=0 or not 6<=font<=30:raise ValueError('Position hors support : '+FIELDS[key])
        parts.append(f'<div class="field" style="left:{x}mm;top:{y}mm;width:{width}mm;text-align:{"center" if key in ("amount","place","date","due_date") else "left"};font-size:{font}pt">{html.escape(str(values.get(key,"")))}</div>')
    source=f'''<!doctype html><html lang="fr"><meta charset="utf-8"><title>Impression chèque / traite</title><style>
    @page{{size:{w}mm {h}mm;margin:0}}body{{margin:0;font-family:{family},sans-serif;background:#eef4fb}}.tools{{padding:16px;background:#133c64;color:white}}button{{padding:10px 18px;background:#0060df;color:white;border:0;border-radius:5px;cursor:pointer}}.sheet{{position:relative;width:{w}mm;height:{h}mm;background:white;margin:20px auto;outline:1px solid #b8cadb}}.field{{position:absolute;color:black;white-space:normal;line-height:1.15;{'outline:1px dashed #78a4cf;' if guide else ''}}}@media print{{.tools{{display:none}}body{{background:white}}.sheet{{margin:0;outline:none}}.field{{outline:none}}}}
    </style><div class="tools"><button onclick="window.print()">🖨 Imprimer</button> Impression à 100 % / taille réelle, marges aucune, en-têtes et pieds de page désactivés. Faites un essai sur papier avant le support original.</div><div class="sheet">{''.join(parts)}</div></html>'''
    Path(path).write_text(source,encoding='utf-8');return Path(path)

def register_effect(app,values,kind):
    if hasattr(app,'_user_has_permission') and not app._user_has_permission('Finance'):
        raise ValueError('Droit Finance requis.')
    payload={'reference':'EFF-PRINT-'+__import__('uuid').uuid4().hex[:12].upper(),'type':kind,'direction':'ÉMIS','client':values['beneficiary'].strip(),'bank':values['bank'].strip(),'number':values['number'].strip(),'due_date':values['due_date'].strip(),'amount':values['amount'].strip(),'status':'EN ATTENTE','notes':'Préparé pour impression numérique','print_date':values['date'],'print_place':values['place'],'print_words':values['words']}
    payload.update({k:values.get(k,'') for k in FIELDS})
    money_words(payload['amount'])
    error=app._validate_check(payload)
    if error:raise ValueError(error)
    for reference,raw in app.conn.execute("SELECT record_id,payload FROM module_records WHERE module='checks'"):
        old=json.loads(raw)
        if old.get('type')==kind and old.get('direction')=='ÉMIS' and str(old.get('number','')).strip()==payload['number'] and str(old.get('bank','')).strip().casefold()==payload['bank'].casefold():
            raise ValueError('Cet effet émis existe déjà : '+reference+'. Modifiez-le dans le centre Chèques / Traites.')
    app.conn.execute("INSERT INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,datetime('now'))",('checks',payload['reference'],json.dumps(payload,ensure_ascii=False)));app.conn.commit()
    if hasattr(app,'_audit'):app._audit('CRÉATION','CHÈQUE / TRAITE',payload['reference'])
    app.refresh_business_records('checks')
    if hasattr(app,'financial_center_cards'):app._refresh_financial_center()
    return payload['reference']

def open_printing(app):
    payload=app._business_payload('checks')
    win=tk.Toplevel(app.root);win.title('Impression numérique · Chèque / Traite');win.geometry('1080x720');win.minsize(850,600);win.configure(bg='#eef5fc')
    tk.Label(win,text='🖨 Impression numérique des chèques et traites',bg='#143d66',fg='white',font=('Segoe UI',18,'bold'),padx=18,pady=16).pack(fill='x')
    footer=tk.Frame(win,bg='#eef5fc');footer.pack(side='bottom',fill='x',padx=15,pady=12)
    book=ttk.Notebook(win);book.pack(fill='both',expand=True,padx=15,pady=10)
    data=tk.Frame(book,bg='white');settings=tk.Frame(book,bg='white');book.add(data,text='Données à imprimer');book.add(settings,text='Positionnement · millimètres')
    kind=tk.StringVar(value='TRAITE' if payload.get('type')=='TRAITE' else 'CHÈQUE')
    ttk.Label(data,text='Support').grid(row=0,column=0,padx=12,pady=12,sticky='w');combo=ttk.Combobox(data,textvariable=kind,values=['CHÈQUE','TRAITE'],state='readonly');combo.grid(row=0,column=1,sticky='ew',padx=12)
    vals={key:tk.StringVar(value=str(payload.get({'beneficiary':'client','date':'print_date'}.get(key,key),''))) for key in FIELDS};vals['date'].set(payload.get('print_date') or date.today().strftime('%d/%m/%Y'));vals['beneficiary'].set(payload.get('beneficiary') or payload.get('client',''));vals['place'].set(payload.get('print_place') or payload.get('agency',''))
    for i,(key,label) in enumerate(FIELDS.items()):
        row=1+i//3;col=(i%3)*2
        ttk.Label(data,text=label).grid(row=row,column=col,sticky='w',padx=8,pady=5);ttk.Entry(data,textvariable=vals[key]).grid(row=row,column=col+1,sticky='ew',padx=8)
    for col in (1,3,5):data.columnconfigure(col,weight=1)
    data.columnconfigure(1,weight=1)
    def words():
        try:vals['words'].set(money_words(vals['amount'].get()))
        except (ValueError,InvalidOperation):messagebox.showerror('Montant','Saisissez un montant positif valide.',parent=win)
    ttk.Button(data,text='Calculer le montant en lettres',command=words).grid(row=8,column=1,sticky='w',padx=12,pady=8)
    dims={key:tk.StringVar() for key in ('width','height','offset_x','offset_y')};coordinates={}
    top=tk.Frame(settings,bg='white');top.pack(fill='x',padx=10,pady=10)
    for i,(key,label) in enumerate((('width','Largeur mm'),('height','Hauteur mm'),('offset_x','Décalage X'),('offset_y','Décalage Y'))):
        ttk.Label(top,text=label).grid(row=0,column=i*2,padx=4);ttk.Entry(top,textvariable=dims[key],width=8).grid(row=0,column=i*2+1,padx=4)
    grid=tk.Frame(settings,bg='white');grid.pack(fill='x',padx=12)
    for c,label in enumerate(('Champ','X mm','Y mm','Largeur mm','Police pt','Imprimer')):ttk.Label(grid,text=label).grid(row=0,column=c,padx=8,pady=8)
    for r,(key,label) in enumerate(FIELDS.items(),1):
        ttk.Label(grid,text=label).grid(row=r,column=0,sticky='w',pady=7)
        coordinates[key]=[tk.StringVar() for _ in range(4)]+[tk.BooleanVar()]
        for c,var in enumerate(coordinates[key]):
            widget=ttk.Checkbutton(grid,variable=var) if c==4 else ttk.Entry(grid,textvariable=var,width=9)
            widget.grid(row=r,column=c+1,padx=8)
    ttk.Label(settings,text='Les positions sont à adapter au format réel de votre banque. Aucun logo, cadre ou fond n’est imprimé.').pack(padx=12,pady=14)
    def load(*_):
        row=app.conn.execute("SELECT payload FROM module_records WHERE module='effect_print_templates' AND record_id=?",(kind.get(),)).fetchone()
        template=json.loads(row[0]) if row else default_template(kind.get())
        for key,var in dims.items():var.set(template[key])
        for key,variables in coordinates.items():
            for var,value in zip(variables,template['positions'].get(key,default_template(kind.get())['positions'][key])):var.set(value)
    def gather():
        import math
        def number(var,label):
            try:
                value=float(''.join(var.get().split()).replace(',','.'))
                if not math.isfinite(value):raise ValueError()
                return value
            except (ValueError,TypeError):raise ValueError('Réglage invalide : '+label+'. Saisissez un nombre en millimètres ou en points.') from None
        names={'width':'largeur du support','height':'hauteur du support','offset_x':'décalage X','offset_y':'décalage Y'}
        template={key:number(var,names[key]) for key,var in dims.items()}
        template['positions']={key:[number(v,FIELDS[key]+' · '+label) for v,label in zip(variables[:4],('X','Y','largeur','police'))]+[variables[4].get()] for key,variables in coordinates.items()}
        return template
    def preview(save=False):
        try:
            template=gather()
            with tempfile.TemporaryDirectory(prefix='gestionpro_modele_') as folder:
                # Validate positioning independently of any amount or client data.
                render_document({},template,Path(folder)/'validation.html',True)
            if save:
                app.conn.execute("INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,datetime('now'))",('effect_print_templates',kind.get(),json.dumps(template)));app.conn.commit();messagebox.showinfo('Réglages','Modèle enregistré pour ce type de support.',parent=win)
                return
            words=money_words(vals['amount'].get())
            vals['words'].set(words)
            output=Path(tempfile.mkdtemp(prefix='gestionpro_effet_'))/'impression.html'
            render_document({k:v.get() for k,v in vals.items()},template,output,True)
            webbrowser.open(output.as_uri())
        except Exception as exc:messagebox.showerror('Impression',str(exc),parent=win)
    def register():
        try:
            reference=register_effect(app,{k:v.get() for k,v in vals.items()},kind.get())
            messagebox.showinfo('Effet émis',reference+' enregistré en attente à son échéance.',parent=win)
        except Exception as exc:messagebox.showerror('Effet émis',str(exc),parent=win)
    for label,command,color in [('＋ Enregistrer effet émis',register,'#7037ce'),('🖨 Aperçu / Imprimer',preview,'#005cdb'),('💾 Enregistrer le modèle',lambda:preview(True),'#008646'),('✕ Fermer',win.destroy,'#607c98')]:
        tk.Button(footer,text=label,command=command,bg=color,fg='white',relief='flat',font=('Segoe UI',10,'bold'),padx=16,pady=10).pack(side='left',padx=5)
    combo.bind('<<ComboboxSelected>>',load);load()
