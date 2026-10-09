"""Compact one-page layouts for the two receivables views."""
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

PASTELS = (("#eaf3ff", "#245c96"), ("#eaf7ef", "#28734c"),
           ("#fff5e6", "#946322"), ("#fdeef0", "#a44554"))

def fit_columns(tree):
    weights = [max(35, int(tree.column(key, 'width'))) for key in tree['columns']]
    def resize(event=None):
        width = tree.winfo_width() - 4
        if width < 100: return
        total = sum(weights)
        for key, weight in zip(tree['columns'], weights):
            tree.column(key, width=max(1, int(width * weight / total)), minwidth=1, stretch=True)
    tree.bind('<Configure>', resize, add='+')
    tree.after_idle(resize)

def one_page(container, flexible):
    """Reserve space for every section and shrink tables rather than hide actions."""
    children = list(container.pack_slaves())
    for row, child in enumerate(children):
        info = child.pack_info()
        child.pack_forget()
        child.grid(row=row, column=0, sticky='nsew' if child in flexible else 'ew',
                   padx=info.get('padx', 0), pady=info.get('pady', 0))
        container.grid_rowconfigure(row, weight=1 if child in flexible else 0,
                                    minsize=65 if child in flexible else 0)
    container.grid_columnconfigure(0, weight=1)
    originals = {}
    def remember(widget):
        data = {}
        for key in ('padx', 'pady', 'font'):
            try: data[key] = widget.cget(key)
            except tk.TclError: pass
        if isinstance(widget, ttk.Treeview):
            fit_columns(widget)
            data['tree'] = True
            widget.configure(height=3)
        manager = widget.winfo_manager()
        if manager in ('pack', 'grid'):
            values = widget.pack_info() if manager == 'pack' else widget.grid_info()
            data['manager'] = (manager, {key: values[key] for key in ('padx', 'pady') if key in values})
        originals[widget] = data
        for child in widget.winfo_children(): remember(child)
    remember(container)
    pending = {'job': None, 'scale': None}
    def apply():
        pending['job'] = None
        height, width = container.winfo_height(), container.winfo_width()
        if height < 100: return
        scale = .65 if height < 610 else .78 if height < 750 else 1.0
        if width < 1050: scale = min(scale, .78)
        if pending['scale'] == scale: return
        pending['scale'] = scale
        def spacing(value):
            if isinstance(value, (list, tuple)): return tuple(spacing(v) for v in value)
            try: return max(0, round(float(value)*scale))
            except (TypeError, ValueError):
                parts = str(value).split()
                return tuple(spacing(v) for v in parts) if len(parts)>1 else value
        for widget, data in originals.items():
            options = {k:spacing(data[k]) for k in ('padx','pady') if k in data}
            if 'font' in data:
                try:
                    f = tkfont.Font(root=container, font=data['font']).actual()
                    options['font']=(f['family'],max(7,round(abs(f['size'])*scale)),f['weight'])
                except tk.TclError: pass
            if options: widget.configure(**options)
            if 'manager' in data:
                manager, values = data['manager']
                (widget.pack_configure if manager=='pack' else widget.grid_configure)(**{k:spacing(v) for k,v in values.items()})
        st=ttk.Style(container)
        st.configure('Receivables3D.Treeview',rowheight=20 if scale<1 else 25,font=('Segoe UI',8 if scale<1 else 9))
        st.configure('Receivables3D.Treeview.Heading',font=('Segoe UI',8 if scale<1 else 9,'bold'),padding=3)
    def schedule(event=None):
        if pending['job'] is not None: container.after_cancel(pending['job'])
        pending['job']=container.after_idle(apply)
    container.bind('<Configure>',schedule,add='+');schedule()
