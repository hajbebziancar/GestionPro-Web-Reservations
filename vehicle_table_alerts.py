"""Blinking maintenance/administrative alerts for rental rows and selected photo."""
import tkinter as tk
from contract_controls import vehicle_alerts,AlertCard

def install(app,parent,tree,number_getter):
    holder=tk.Frame(parent,bg='#f4faff');holder.pack(fill='x',padx=12,pady=5)
    photo=tk.Label(holder,text='Sélectionnez une location',bg='white',width=15);photo.pack(side='left',padx=6)
    cards=[AlertCard(holder,a) for a in vehicle_alerts({})]
    for c in cards:c.configure(width=155,height=50);c.pack(side='left',fill='x',expand=True,padx=3)
    state={'rows':{},'phase':False,'image':None}
    tree.tag_configure('maintenance_alarm',background='#ffdade',foreground='#c00020')
    tree.tag_configure('maintenance_idle',background='#fff4f4',foreground='#981e2e')
    def refresh():
        vehicles={str(r['code']):dict(r) for r in app.conn.execute('SELECT * FROM vehicles')}
        contracts={str(r[0]):str(r[1]) for r in app.conn.execute('SELECT numero,vehicle_code FROM contracts')}
        state['rows']={}
        for iid in tree.get_children():
            no=number_getter(iid);v=vehicles.get(contracts.get(str(no),''),{});alarms=[a for a in vehicle_alerts(v) if a['active']]
            tags=tuple(t for t in tree.item(iid,'tags') if t not in ('maintenance_alarm','maintenance_idle'))
            tree.item(iid,tags=tags+('maintenance_idle',) if alarms else tags)
            if alarms:state['rows'][iid]=tags
        chosen=tree.selection();v=vehicles.get(contracts.get(str(number_getter(chosen[0])),'') if chosen else '',{})
        for c,a in zip(cards,vehicle_alerts(v)):c.set_alert(a)
        photo.configure(image='',text='Photo du véhicule');state['image']=None
        if v:
            try:
                from PIL import Image,ImageTk,ImageOps
                path=app._resolve_vehicle_photo_path(v.get('photo',''),v['code'])
                with Image.open(path) as im:pic=ImageOps.exif_transpose(im).copy()
                pic.thumbnail((105,60));state['image']=ImageTk.PhotoImage(pic);photo.configure(image=state['image'],text='')
            except (OSError,ValueError,TypeError):pass
    job=[None]
    def blink():
        if not holder.winfo_exists():return
        state['phase']=not state['phase']
        if holder.winfo_viewable():
            for iid,tags in state['rows'].items():
                if tree.exists(iid):tree.item(iid,tags=tags+('maintenance_alarm' if state['phase'] else 'maintenance_idle',))
            for c in cards:c.paint(state['phase'])
        job[0]=holder.after(650,blink)
    def cleanup(e):
        if e.widget is holder and job[0]:holder.after_cancel(job[0])
    holder.bind('<Destroy>',cleanup,add='+');tree.bind('<<TreeviewSelect>>',lambda e:refresh(),add='+');job[0]=holder.after(650,blink)
    refresh();return refresh
