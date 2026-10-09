"""État visuel du véhicule et copie conservée avec chaque contrat."""
import json
import tkinter as tk
from tkinter import ttk,messagebox
from pathlib import Path
from datetime import datetime
from uuid import uuid4
from PIL import Image,ImageTk,ImageDraw

BASE=Path(__file__).resolve().parent
REFERENCE=BASE/'assets'/'ETAT_VEHICULE_REFERENCE.png'
EQUIPMENT=('Cric','Roue de secours','Clé / Télécommande','Carte grise','Assurance','Visite technique','Feuille circulation','Vignette','Triangle de signalisation','Gilet de sécurité','Extincteur','Trousse de secours')

def read_state(conn,module,key):
    row=conn.execute('SELECT payload FROM module_records WHERE module=? AND record_id=?',(module,key)).fetchone()
    if not row:return {}
    try:return json.loads(row[0])
    except (TypeError,ValueError):return {}

def draw_state(strokes):
    image=Image.open(REFERENCE).convert('RGB');draw=ImageDraw.Draw(image)
    for stroke in strokes:
        points=[(max(0,min(1,float(x)))*image.width,max(0,min(1,float(y)))*image.height) for x,y in stroke['points']]
        if len(points)>1:draw.line(points,fill=stroke.get('color','#ed3345'),width=max(2,round(image.width/300)),joint='curve')
    return image

def save_vehicle_state(conn,code,observations,strokes,equipment=None):
    if not conn.execute('SELECT 1 FROM vehicles WHERE code=?',(code,)).fetchone():raise ValueError('Sélectionnez un véhicule enregistré.')
    image=draw_state(strokes)
    folder=BASE/'assets'/'vehicle_states';folder.mkdir(exist_ok=True)
    path=folder/(uuid4().hex+'.png');image.save(path)
    data={'vehicle_code':code,'observations':observations.strip(),'strokes':strokes,'drawing':str(path.relative_to(BASE))}
    if equipment is not None:data['equipment']={name:bool(equipment.get(name,False)) for name in EQUIPMENT}
    try:
        with conn:conn.execute('INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,?)',
            ('vehicle_condition',code,json.dumps(data,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')))
    except Exception:path.unlink(missing_ok=True);raise
    return data

def snapshot_vehicle_state(conn,number,code):
    existing=read_state(conn,'contract_vehicle_condition',number)
    if existing and existing.get('vehicle_code')==code:return
    data=read_state(conn,'vehicle_condition',code) or {'vehicle_code':code,'observations':'','strokes':[],'drawing':''}
    conn.execute('INSERT OR REPLACE INTO module_records(module,record_id,payload,created_at) VALUES(?,?,?,?)',
        ('contract_vehicle_condition',number,json.dumps(data,ensure_ascii=False),datetime.now().isoformat(timespec='seconds')))

def contract_state(conn,number):
    data=read_state(conn,'contract_vehicle_condition',number)
    if data:return data
    row=conn.execute('SELECT vehicle_code FROM contracts WHERE numero=?',(number,)).fetchone()
    return read_state(conn,'vehicle_condition',row[0]) if row else {}

class VehicleStateEditor(tk.Frame):
    def __init__(self,parent,app,code_provider):
        super().__init__(parent,bg='#f4faff');self.app=app;self.provider=code_provider;self.code='';self.strokes=[];self.current=[];self.photo=None;self.transform=(0,0,1,1)
        self.pack(fill='both',expand=True)
        self.info=tk.StringVar(value='Choisissez un véhicule puis ouvrez cet onglet.')
        tk.Label(self,textvariable=self.info,bg='#eaf4ff',fg='#08315e',font=('Segoe UI',12,'bold'),anchor='w',pady=8).pack(fill='x',padx=12,pady=8)
        bar=tk.Frame(self,bg='#f4faff');bar.pack(fill='x',padx=12)
        self.tool=tk.StringVar(value='#ed3345')
        for caption,color in [('Rayure (rouge)','#ed3345'),('Retouche (bleu)','#0065ef')]:ttk.Radiobutton(bar,text=caption,variable=self.tool,value=color).pack(side='left',padx=8)
        for text,cmd,color in [('Annuler le dernier trait',self.undo,'#64748b'),('Effacer les traits',self.clear,'#ed3345'),('Enregistrer l’état',self.save,'#009642')]:tk.Button(bar,text=text,command=cmd,bg=color,fg='white',relief='flat',padx=12,pady=6).pack(side='left',padx=4)
        tk.Label(self,text='Dessinez les rayures ou retouches en maintenant le bouton gauche de la souris.',bg='#f4faff',fg='#557083',anchor='w').pack(fill='x',padx=16,pady=5)
        self.canvas=tk.Canvas(self,bg='white',height=340,highlightthickness=1,highlightbackground='#c6d7e5',cursor='crosshair');self.canvas.pack(fill='both',expand=True,padx=12,pady=5)
        self.canvas.bind('<Configure>',lambda _:self.repaint());self.canvas.bind('<Button-1>',self.start);self.canvas.bind('<B1-Motion>',self.drag);self.canvas.bind('<ButtonRelease-1>',self.finish)
        equipment_box=ttk.LabelFrame(self,text='Équipements remis');equipment_box.pack(fill='x',padx=12,pady=5)
        self.equipment={name:tk.BooleanVar(value=False) for name in EQUIPMENT}
        for index,name in enumerate(EQUIPMENT):
            row,col=divmod(index,4);equipment_box.grid_columnconfigure(col,weight=1)
            ttk.Checkbutton(equipment_box,text=name,variable=self.equipment[name]).grid(row=row,column=col,sticky='w',padx=8,pady=3)
        tk.Label(self,text='Observations : rayures, retouches, carrosserie et état du véhicule',bg='#f4faff',fg='#08315e',font=('Segoe UI',9,'bold'),anchor='w').pack(fill='x',padx=12)
        self.notes=tk.Text(self,height=4,wrap='word',font=('Segoe UI',10));self.notes.pack(fill='x',padx=12,pady=(4,12))
        self.load()
    def load(self):
        code=str(self.provider() or '').split('|')[0].strip()
        if code==self.code:return
        self.code=code;data=read_state(self.app.conn,'vehicle_condition',code);self.strokes=data.get('strokes',[]);self.current=[]
        self.notes.delete('1.0','end');self.notes.insert('1.0',data.get('observations',''))
        for name,var in self.equipment.items():var.set(bool(data.get('equipment',{}).get(name,False)))
        row=self.app.conn.execute('SELECT modele,immatriculation FROM vehicles WHERE code=?',(code,)).fetchone()
        self.info.set(f"État du véhicule — {row[0]} · {row[1]}" if row else 'Choisissez un véhicule enregistré.')
        self.repaint()
    def repaint(self):
        width=max(1,self.canvas.winfo_width());height=max(1,self.canvas.winfo_height())
        image=draw_state(self.strokes+([{'points':self.current,'color':self.tool.get()}] if self.current else []))
        image.thumbnail((width,height),Image.Resampling.LANCZOS);x=(width-image.width)/2;y=(height-image.height)/2
        self.transform=(x,y,image.width,image.height);self.photo=ImageTk.PhotoImage(image)
        self.canvas.delete('all');self.canvas.create_image(x,y,image=self.photo,anchor='nw')
    def point(self,event):
        x,y,w,h=self.transform
        if x<=event.x<=x+w and y<=event.y<=y+h:return ((event.x-x)/w,(event.y-y)/h)
    def start(self,event):
        point=self.point(event);self.current=[point] if point else []
    def drag(self,event):
        point=self.point(event)
        if self.current and point:self.current.append(point);self.repaint()
    def finish(self,event):
        if len(self.current)>1:self.strokes.append({'points':self.current.copy(),'color':self.tool.get()})
        self.current=[];self.repaint()
    def undo(self):
        if self.strokes:self.strokes.pop();self.repaint()
    def clear(self):
        if messagebox.askyesno('État du véhicule','Effacer les traits du dessin ?',parent=self):self.strokes=[];self.repaint()
    def save(self):
        try:save_vehicle_state(self.app.conn,self.code,self.notes.get('1.0','end'),self.strokes,{name:var.get() for name,var in self.equipment.items()})
        except Exception as exc:messagebox.showerror('État du véhicule',str(exc),parent=self);return
        messagebox.showinfo('État du véhicule','Dessin et observations enregistrés. Ils seront repris sur les nouveaux contrats.',parent=self)
