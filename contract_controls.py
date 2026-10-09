"""Contrôles du contrat : contours arrondis, pictogrammes explicites et alertes."""
import math
import tkinter as tk
from tkinter import ttk
from datetime import datetime, date
from reservation_reference import _reservation_round, _reservation_icon

ICON_NAMES={'person','car','save','print','edit','trash','clock','calendar','check','cancel','money','search','document','pdf','camera','fuel','gear','whatsapp','signature','plus','location','eraser','info','shield','chain','oil','phone','mail'}

def draw_icon(c,kind,x,y,s=1,color='white'):
    if kind not in ICON_NAMES:raise ValueError('Icône non définie : '+kind)
    if kind in ('person','car','save','print','edit','trash','clock','calendar','check','cancel','money'):
        _reservation_icon(c,kind,x,y,s,color);return
    def line(*p,width=2):c.create_line(*[x+a*s if i%2==0 else y+a*s for i,a in enumerate(p)],fill=color,width=width*s,capstyle='round',joinstyle='round')
    def box(a,b,d,e):c.create_rectangle(x+a*s,y+b*s,x+d*s,y+e*s,outline=color,width=2*s)
    def oval(a,b,d,e,fill=''):c.create_oval(x+a*s,y+b*s,x+d*s,y+e*s,outline=color,width=2*s,fill=fill)
    if kind=='search':oval(3,2,16,15);line(14,14,22,22,width=3)
    elif kind in ('document','pdf'):
        line(4,2,15,2,21,8,21,23,4,23,4,2);line(15,2,15,8,21,8)
        if kind=='pdf':c.create_text(x+12*s,y+16*s,text='PDF',fill=color,font=('Segoe UI',max(6,round(6*s)),'bold'))
        else:line(8,12,17,12);line(8,16,17,16);line(8,20,14,20)
    elif kind=='camera':box(2,7,22,21);line(6,7,8,3,16,3,18,7);oval(7,10,17,20)
    elif kind=='mail':box(2,4,22,21);line(2,4,12,13,22,4)
    elif kind=='phone':line(5,2,2,6,4,13,10,20,17,23,22,19,18,15,14,18,8,12,10,8,5,2,width=3)
    elif kind=='fuel':box(3,3,14,22);box(5,5,12,11);line(14,10,18,10,18,20,22,20,22,6,19,3);line(1,23,16,23)
    elif kind=='gear':
        oval(6,6,18,18);oval(10,10,14,14)
        for a in range(0,360,45):
            r=math.radians(a);line(12+6*math.cos(r),12+6*math.sin(r),12+10*math.cos(r),12+10*math.sin(r),width=3)
    elif kind=='whatsapp':oval(2,2,22,22);line(5,19,2,23,8,21);line(8,6,7,9,10,14,15,17,18,15,15,13,width=2.5)
    elif kind=='signature':line(2,20,5,12,8,18,11,7,13,16,17,10,20,13,23,11);line(2,23,23,23)
    elif kind=='plus':line(12,3,12,21,width=3);line(3,12,21,12,width=3)
    elif kind=='location':oval(5,1,19,15);oval(10,6,14,10);line(6,13,12,23,18,13)
    elif kind=='eraser':line(2,16,13,3,22,11,13,22,7,22,2,16);line(7,10,16,18)
    elif kind=='info':oval(2,2,22,22);line(12,11,12,19,width=3);oval(11,6,13,8,color)
    elif kind=='shield':line(12,2,22,6,21,15,17,20,12,23,7,20,3,15,2,6,12,2);line(7,12,11,16,17,9)
    elif kind=='chain':oval(2,3,15,16);oval(9,9,22,22);line(8,14,16,8)
    elif kind=='oil':line(12,2,4,12,3,17,6,22,12,24,18,22,21,17,20,12,12,2);line(7,17,9,20)

class IconButton(tk.Canvas):
    def __init__(self,parent,text,command,color='#0789ee',ink='white',icon='document',**kwargs):
        if icon not in ICON_NAMES:raise ValueError(icon)
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,cursor='hand2',takefocus=True,**kwargs)
        self.caption=text;self.command=command;self.fill=color;self.ink=ink;self.icon=icon;self.hover=False
        self.bind('<Configure>',lambda e:self.paint())
        self.bind('<Enter>',lambda e:self.highlight(True));self.bind('<Leave>',lambda e:self.highlight(False))
        for event in ('<Button-1>','<Return>','<space>'):self.bind(event,lambda e:self.command())
    def highlight(self,v):self.hover=v;self.paint()
    def configure(self,cnf=None,**kw):
        if isinstance(cnf,dict):kw={**cnf,**kw};cnf=None
        for k,a in (('text','caption'),('bg','fill'),('fg','ink')):
            if k in kw:setattr(self,a,kw.pop(k))
        result=super().configure(cnf,**kw) if cnf is not None or kw else None
        self.paint();return result
    config=configure
    def paint(self):
        w=self.winfo_width();h=self.winfo_height()
        if w<2 or h<2:return
        self.delete('all');color=self.fill
        if self.hover:
            color='#'+''.join(f'{min(255,int(self.fill[i:i+2],16)+14):02x}' for i in (1,3,5))
        _reservation_round(self,1,1,w-1,h-1,min(9,h/4),color)
        s=min(1,h/32);small=not self.caption
        draw_icon(self,self.icon,(w-24*s)/2 if small else 11,h/2-12*s,s,self.ink)
        if not small:self.create_text(41*s,h/2,text=self.caption,anchor='w',fill=self.ink,width=max(1,w-47),font=('Segoe UI',max(8,round(10*min(1,w/190))),'bold'))

class ModernCheck(tk.Canvas):
    """Compact accessible selection tile backed by the existing Tk variable."""
    def __init__(self,parent,text,variable,command=None,onvalue=True,offvalue=False,color='#087fe5',width=200,height=26):
        super().__init__(parent,bg=parent.cget('bg'),width=width,height=height,highlightthickness=0,takefocus=True,cursor='hand2')
        self.caption=text;self.variable=variable;self.command=command
        self.onvalue=onvalue;self.offvalue=offvalue;self.accent=color;self.focused=False
        self._trace=variable.trace_add('write',lambda *a:self.paint())
        self.bind('<Configure>',lambda e:self.paint())
        for event in ('<Button-1>','<space>','<Return>'):self.bind(event,self.toggle)
        self.bind('<FocusIn>',lambda e:self.focus(True));self.bind('<FocusOut>',lambda e:self.focus(False))
        self.bind('<Destroy>',self.cleanup)
    def focus(self,value):self.focused=value;self.paint()
    def toggle(self,event=None):
        self.focus_set();self.variable.set(self.offvalue if str(self.variable.get())==str(self.onvalue) else self.onvalue)
        if self.command:self.command()
        return 'break'
    def cleanup(self,event):
        if event.widget is self:
            try:self.variable.trace_remove('write',self._trace)
            except tk.TclError:pass
    def paint(self):
        w=self.winfo_width();h=self.winfo_height()
        if w<2 or h<2:return
        selected=str(self.variable.get())==str(self.onvalue)
        self.delete('all')
        _reservation_round(self,1,1,w-1,h-1,7,self.accent if self.focused else '#d9e6f1')
        _reservation_round(self,2,2,w-2,h-2,6,'#e9f4ff' if selected else '#f7fafd')
        y=h/2
        _reservation_round(self,8,y-8,24,y+8,4,self.accent if selected else '#c4d5e3')
        if selected:self.create_line(11,y,15,y+4,21,y-4,fill='white',width=2,capstyle='round',joinstyle='round')
        else:_reservation_round(self,9,y-7,23,y+7,3,'white')
        self.create_text(32,y,text=self.caption,anchor='w',width=max(1,w-38),fill='#123e62',font=('Segoe UI',9,'bold' if selected else 'normal'))

class RoundedField(tk.Canvas):
    def __init__(self,parent,variable,values=None,readonly=False,tint='white',bold=False,background=None):
        super().__init__(parent,bg=background or parent.cget('bg'),highlightthickness=0)
        self.tint=tint;self.border='#c9dbe9';self.focused=False
        options=dict(textvariable=variable,justify='center',font=('Segoe UI',11,'bold' if bold else 'normal'),state='readonly' if readonly else 'normal')
        if values is None:
            self.input=tk.Entry(self,**options,bg=tint,readonlybackground=tint,fg='#092d50',relief='flat',bd=0,highlightthickness=0)
        else:
            self.input=ttk.Combobox(self,**options,values=values,style='ContractRounded.TCombobox')
        tk.Canvas.bind(self,'<Configure>',lambda e:self.paint())
        self.input.bind('<FocusIn>',lambda e:self.focus_border(True),add='+');self.input.bind('<FocusOut>',lambda e:self.focus_border(False),add='+')
    def focus_border(self,v):self.focused=v;self.paint()
    def paint(self):
        w=self.winfo_width();h=self.winfo_height()
        if w<2 or h<2:return
        tk.Canvas.delete(self,'all');r=min(8,h/4)
        _reservation_round(self,0,0,w,h,r,'#0789ee' if self.focused else self.border)
        _reservation_round(self,1,1,w-1,h-1,max(0,r-1),self.tint)
        self.input.place(x=9,y=4,width=max(1,w-18),height=max(1,h-8))
    def configure(self,cnf=None,**kw):
        if isinstance(cnf,dict):kw={**cnf,**kw};cnf=None
        for k in ('font','state','values','postcommand','justify'):
            if k in kw:self.input.configure(**{k:kw.pop(k)})
        return super().configure(cnf,**kw) if cnf is not None or kw else None
    config=configure
    def keys(self):return list(set(super().keys())|{'font'})
    def cget(self,k):return self.input.cget(k) if k=='font' else super().cget(k)
    def bind(self,sequence=None,func=None,add=None):
        if sequence in ('<Configure>','<Destroy>'):return tk.Canvas.bind(self,sequence,func,add)
        return self.input.bind(sequence,func,add)
    def get(self):return self.input.get()
    def delete(self,*args):return self.input.delete(*args)
    def insert(self,*args):return self.input.insert(*args)
    def focus_set(self):return self.input.focus_set()
    def current(self,*args):return self.input.current(*args)


def vehicle_alerts(row, mileage=None, today=None):
    """Les seuils sont stricts. Une échéance non renseignée ne simule pas une alerte."""
    today=today or date.today()
    def get(key):
        try:return row[key]
        except (KeyError,IndexError):return None
    def number(raw):
        try:return int(float(str(raw).replace(' ', '').replace(',', '.')))
        except (ValueError,TypeError,OverflowError):return None
    current=number(mileage)
    if current is None:current=number(get('compteur')) or 0
    result=[]
    for title,target_key,remain_key,limit,icon in (('Vidange','prochaine_vidange','vidange_restant',1000,'oil'),('AdBlue','prochaine_adblue','adblue_restant',2000,'fuel'),('Chaîne','prochaine_chaine','chaine_restant',5000,'chain')):
        target=number(get(target_key));remaining=number(get(remain_key))
        if target and target>0:remaining=target-current
        elif remaining is None or remaining==0:remaining=None
        else:
            stored=number(get('compteur'))
            remaining-=current-(stored if stored is not None else current)
        active=remaining is not None and remaining<limit
        text='Non renseigné' if remaining is None else f'{remaining:,} km restants'.replace(',', ' ') if remaining>0 else 'À effectuer' if remaining==0 else f'Dépassée de {abs(remaining):,} km'.replace(',', ' ')
        result.append({'title':title,'text':text,'value':remaining,'active':active,'icon':icon})
    for title,key,icon in (('Visite technique','controle_technique','calendar'),('Assurance','assurance_fin','shield')):
        raw=str(get(key) or '').strip();due=None
        for fmt in ('%d/%m/%Y','%Y-%m-%d'):
            try:due=datetime.strptime(raw[:10],fmt).date();break
            except ValueError:pass
        days=(due-today).days if due else None
        text='Non renseignée' if days is None else f'Dans {days} jours' if days>0 else "Échéance aujourd’hui" if days==0 else f'Expirée depuis {abs(days)} jours'
        result.append({'title':title,'text':text,'value':days,'active':days is not None and days<10,'icon':icon})
    return result

class AlertCard(tk.Canvas):
    def __init__(self,parent,alert):
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0)
        self.alert=alert;self.phase=False;self.bind('<Configure>',lambda e:self.paint())
    def set_alert(self,alert):self.alert=alert;self.paint()
    def paint(self,phase=None):
        if phase is not None:self.phase=phase
        w=self.winfo_width();h=self.winfo_height()
        if w<2 or h<2:return
        self.delete('all');active=self.alert['active']
        soft,ink=('#ffe3e6','#c72435') if active and self.phase else ('#fff3f3','#a32235') if active else ('#eef3f8','#61758b') if self.alert['value'] is None else ('#eaf5f0','#187548')
        _reservation_round(self,0,0,w,h,8,soft)
        draw_icon(self,self.alert['icon'],9,max(3,h/2-10),.75,ink)
        size=max(7,min(10,round(w/20)))
        self.create_text(w/2+8,h*.30,text=self.alert['title'],fill=ink,font=('Segoe UI',size,'bold'))
        self.create_text(w/2+8,h*.71,text=self.alert['text'],fill=ink,font=('Segoe UI',max(7,size-1),'bold'),width=max(1,w-40))
