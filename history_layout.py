"""Colonnes proportionnelles à la fenêtre et moyennes de CA par calendrier."""
from datetime import date

def column_widths(weights,available):
    available=max(len(weights),int(available))
    total=sum(weights) or 1
    result=[max(1,int(available*w/total)) for w in weights]
    while sum(result)>available:
        index=max(range(len(result)),key=result.__getitem__);result[index]-=1
    for i in range(available-sum(result)):result[i%len(result)]+=1
    return result

def fit_history_columns(tree):
    from tkinter import ttk
    name=tree.cget('style') or 'HistoryGeneral.Treeview'
    tree.configure(style=name)
    blue_history_headings(ttk.Style(tree),name)
    columns=list(tree['columns'])
    if 'tree' in str(tree['show']):columns=['#0']+columns
    weights=[max(20,int(tree.column(c,'width'))) for c in columns]
    def resize(event=None):
        width=tree.winfo_width()-4
        if width<len(columns):return
        if columns and columns[0]=='#0':
            photo_width=min(62,max(1,width-len(columns)+1))
            sizes=[photo_width]+column_widths(weights[1:],width-photo_width)
        else:sizes=column_widths(weights,width)
        for col,size in zip(columns,sizes):
            tree.column(col,width=size,minwidth=1,stretch=False)
        tree.xview_moveto(0)
    tree.bind('<Configure>',resize,add='+');tree.after_idle(resize)

def calendar_ca_averages(total,start,end):
    first=date.fromisoformat(start);last=date.fromisoformat(end)
    if last<first:raise ValueError('Période inversée.')
    months=(last.year-first.year)*12+last.month-first.month+1
    years=last.year-first.year+1
    return float(total)/years,float(total)/months,years,months

def filtered_ca_averages(total,rows,month,year):
    """The independent global page has month/year selectors instead of an interval."""
    dates=[]
    from datetime import datetime
    for row in rows:
        for i in (1,3):
            try:dates.append(datetime.strptime(str(row[i]),'%d/%m/%Y').date())
            except (ValueError,TypeError):pass
    if str(year).isdigit():years=1
    elif dates:years=max(d.year for d in dates)-min(d.year for d in dates)+1
    else:years=1
    months=12*years if month=='Tous les mois' else years
    return float(total)/years,float(total)/months


def blue_history_headings(style,name='ContractHistory.Treeview'):
    # Native Windows headings ignore background colors; use the clam cell only.
    element='HistoryBlue.Treeheading.cell'
    if element not in style.element_names():style.element_create(element,'from','clam','Treeheading.cell')
    style.layout(name+'.Heading',[(element,{'sticky':'nswe'}),('Treeheading.padding',{'sticky':'nswe','children':[('Treeheading.image',{'side':'right','sticky':''}),('Treeheading.text',{'sticky':'we'})]})])
    style.configure(name+'.Heading',background='#075493',foreground='white',font=('Segoe UI',10,'bold'),padding=(8,10),relief='flat')
    style.map(name+'.Heading',background=[('active','#0875bd')],foreground=[('active','white')])
