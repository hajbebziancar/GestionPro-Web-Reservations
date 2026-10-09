"""Shared reference palette, real icon images, and white editable controls."""
from pathlib import Path
import tkinter as tk
from tkinter import ttk
BG='#eff7ff'; BLUE='#005be5'; NAVY='#102e52'; BAR='#176aab'; GREEN='#008747'; ORANGE='#ed8200'; RED='#cd0035'; PURPLE='#753de9'; INK='#122d50'; LINE='#d5e5f0'
def image(owner,name,size=22):
    from PIL import Image,ImageTk
    root=owner.winfo_toplevel();cache=getattr(root,'_reference_icon_cache',None)
    if cache is None:cache={};root._reference_icon_cache=cache
    key=(name,size)
    if key not in cache:
        path=Path(__file__).parent/'assets/reference_ui'/f'{name}.png'
        pic=Image.open(path).convert('RGBA');pic.thumbnail((size,size),Image.Resampling.LANCZOS)
        cache[key]=ImageTk.PhotoImage(pic,master=root)
    return cache[key]
def button(parent,text,command,color=BLUE,icon=None,small=False):
    return tk.Button(parent,text=text,command=command,bg=color,fg=INK if color in ('#e5f2fc','#d8ebf9') else 'white',activebackground=color,activeforeground='white',image=image(parent,icon,16 if small else 20) if icon else '',compound='left',relief='flat',bd=0,padx=0 if not text else 7 if small else 10,pady=4 if small else 8,font=('Segoe UI',8 if small else 9,'bold'),cursor='hand2')
def section(parent,title,icon=None,color=BAR,soft=None):
    box=tk.Frame(parent,bg='white',highlightbackground=LINE,highlightthickness=1)
    heading=tk.Label(box,text='  '+title,image=image(box,icon,18) if icon else '',compound='left',bg=soft or color,fg=INK if soft else 'white',font=('Segoe UI',10,'bold'),anchor='w',padx=10,pady=6)
    heading.pack(fill='x');body=tk.Frame(box,bg='white');body.pack(fill='both',expand=True,padx=7,pady=5)
    return box,body

def styles(owner):
    st=ttk.Style(owner)
    if st.theme_use()!='clam':st.theme_use('clam')
    st.configure('Reference.TCombobox',fieldbackground='white',background='white',foreground=INK,arrowcolor=INK,bordercolor=LINE,padding=4)
    st.map('Reference.TCombobox',fieldbackground=[('readonly','white')],foreground=[('readonly',INK)],selectbackground=[('readonly','white')],selectforeground=[('readonly',INK)])
    st.configure('Reference.Treeview',font=('Segoe UI',9),rowheight=25,background='white',fieldbackground='white',foreground=INK,borderwidth=0)
    st.configure('Reference.Treeview.Heading',font=('Segoe UI',9,'bold'),foreground='white',background='#154c7b',padding=5,relief='flat')
    st.map('Reference.Treeview',background=[('selected','#bde4fb')],foreground=[('selected',INK)])
    st.map('Reference.Treeview.Heading',background=[('active','#176aab')])

def entry(parent,var,readonly=False,tint='white',width=10):
    return tk.Entry(parent,textvariable=var,font=('Segoe UI',9),bg=tint,readonlybackground=tint,fg=INK,state='readonly' if readonly else 'normal',relief='solid',bd=1,highlightbackground=LINE,highlightcolor=BLUE,highlightthickness=1,width=width)

def fit_page(container):
    """Reduce fixed spacing on short displays; leave scrolling inside tables."""
    import tkinter.font as tkfont
    pending={'job':None,'compact':None}
    def resize():
        pending['job']=None
        height=container.winfo_height()
        if height<100:return
        compact=height<800
        if compact==pending['compact']:return
        pending['compact']=compact
        def walk(widget):
            if not hasattr(widget,'_reference_metrics'):
                metrics={}
                for option in ('font','padx','pady'):
                    try:metrics[option]=widget.cget(option)
                    except tk.TclError:pass
                for manager in ('pack','grid'):
                    if widget.winfo_manager()==manager:
                        info=widget.pack_info() if manager=='pack' else widget.grid_info()
                        metrics['manager']=(manager,{key:info[key] for key in ('padx','pady','ipadx','ipady') if key in info})
                widget._reference_metrics=metrics
            metrics=widget._reference_metrics
            def spacing(value):
                if not compact:return value
                if isinstance(value,(tuple,list)):return tuple(spacing(x) for x in value)
                try:return max(0,round(float(value)*.5))
                except (ValueError,TypeError):return value
            options={key:spacing(metrics[key]) for key in ('padx','pady') if key in metrics}
            if 'font' in metrics:
                try:
                    f=tkfont.Font(font=metrics['font'],root=widget.winfo_toplevel()).actual()
                    size=max(7,round(abs(f['size'])*.82)) if compact else abs(f['size'])
                    options['font']=(f['family'],size,f['weight'],f['slant'])
                except tk.TclError:pass
            if options:widget.configure(**options)
            if 'manager' in metrics:
                manager,values=metrics['manager'];values={key:spacing(value) for key,value in values.items()}
                (widget.pack_configure if manager=='pack' else widget.grid_configure)(**values)
            for child in widget.winfo_children():walk(child)
        walk(container)
        st=ttk.Style(container);st.configure('Reference.Treeview',rowheight=20 if compact else 25,font=('Segoe UI',8 if compact else 9));st.configure('Reference.Treeview.Heading',font=('Segoe UI',8 if compact else 9,'bold'),padding=3 if compact else 5)
        container.update_idletasks()
    def schedule(event=None):
        if pending['job'] is not None:container.after_cancel(pending['job'])
        pending['job']=container.after_idle(resize)
    container.bind('<Configure>',schedule,add='+');schedule()
