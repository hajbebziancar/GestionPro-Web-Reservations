"""Observations du contrat imprimées à côté du schéma du véhicule."""
import html
import json
import re

FUEL_COLORS=('#ed3345','#f4c542','#a8cf73','#009642','#009642','#009642','#009642','#009642')

def contract_details(conn,number):
    row=conn.execute("SELECT payload FROM module_records WHERE module='client_rapide_contract' AND record_id=?",(number,)).fetchone()
    if not row:return {}
    try:return json.loads(row[0])
    except (TypeError,ValueError):return {}

def apply_equipment_selection(content,selection):
    aliases={'Cric et outils':'Cric','Clé véhicule':'Clé / Télécommande','Clé(s) du véhicule':'Clé / Télécommande','Clé de roue':'Clé / Télécommande',
        'Assurance (échéance)':'Assurance','Carte visite technique (échéance)':'Visite technique','Feuille de circulation':'Feuille circulation','Feuille de circulation (f/m)':'Feuille circulation','Triangle':'Triangle de signalisation'}
    def checked(label):return bool(selection.get(aliases.get(html.unescape(label.strip()),html.unescape(label.strip())),False))
    def span(match):return '<span>'+('☑ ' if checked(match[1]) else '☐ ')+match[1]+'</span>'
    content=re.sub(r'<span>[☑☐] ([^<]+)</span>',span,content)
    def item(match):return "<div class='eq'><span class='check'>"+('✓' if checked(match[1]) else '')+'</span>'+match[1]+'</div>'
    return re.sub(r"<div class='eq'><span class='check'>[^<]*</span>([^<]+)</div>",item,content)

def add_print_observations(content,conn,number):
    from vehicle_condition import contract_state,BASE
    state=contract_state(conn,number)
    if 'equipment' in state:content=apply_equipment_selection(content,state['equipment'])
    drawing=BASE/str(state.get('drawing',''))
    pattern=r'<img\b[^>]*(?:ETAT_VEHICULE|[Éé]tat du v[ée]hicule|vehicle-state-image)[^>]*>'
    if state.get('drawing') and drawing.is_file():
        match=re.search(pattern,content,re.IGNORECASE)
        if match:
            picture=re.sub(r'src=[\"\'][^\"\']*[\"\']',lambda _: 'src="'+html.escape(drawing.resolve().as_uri())+'"',match.group(0))
            if 'alt=' not in picture:picture=picture.replace('<img','<img alt="État du véhicule annoté"',1)
            content=content[:match.start()]+picture+content[match.end():]
    parts=[str(state.get('observations','') or '').strip(),str(contract_details(conn,number).get('ref_notes','') or '').strip()]
    notes='\n'.join(dict.fromkeys(part for part in parts if part))
    if not notes:return content
    escaped=html.escape(notes).replace('\n','<br>')
    # Match only the vehicle condition drawing, not the rented vehicle photograph.
    pattern=r'<img\b[^>]*(?:ETAT_VEHICULE|[Éé]tat du v[ée]hicule|vehicle-state-image)[^>]*>'
    match=re.search(pattern,content,re.IGNORECASE)
    if not match:return content
    block=("<div class='contract-state-with-notes'>"+match.group(0)+
        "<div class='contract-state-notes'><b>Observations — état du véhicule</b><br>"+escaped+"</div></div>")
    content=content[:match.start()]+block+content[match.end():]
    css="""<style>
.contract-state-with-notes{display:flex;align-items:center;gap:2mm;width:100%;height:auto;line-height:1.3}
.contract-state-with-notes>img{width:53%!important;max-width:53%!important;object-fit:contain}
.contract-state-notes{flex:1;min-width:0;text-align:left;white-space:normal;overflow-wrap:anywhere;font-size:7px;color:#18364c;line-height:1.3}
.state-image:has(.contract-state-notes),.state-photo:has(.contract-state-notes){height:auto!important;max-height:none!important;overflow:visible!important}
</style>"""
    return content.replace('</head>',css+'</head>',1)

def ensure_single_recto_pdf(path):
    """Contrôle et composition A4 avec pypdf, sans DLL native PyMuPDF."""
    from pypdf import PdfReader,PdfWriter,Transformation
    from pathlib import Path
    path=Path(path)
    with path.open('rb') as stream:
        source=PdfReader(stream)
        if not source.pages:raise ValueError('Le contrat PDF est vide.')
        if len(source.pages)==1:return
        writer=PdfWriter();page=writer.add_blank_page(width=595.276,height=841.89)
        height=841.89/len(source.pages)
        for index,original in enumerate(source.pages):
            original.transfer_rotation_to_content()
            box=original.mediabox;scale=min(595.276/float(box.width),height/float(box.height))
            x=(595.276-float(box.width)*scale)/2
            y=841.89-(index+1)*height+(height-float(box.height)*scale)/2
            transform=Transformation().translate(-float(box.left),-float(box.bottom)).scale(scale).translate(x,y)
            page.merge_transformed_page(original,transform,expand=False)
        temporary=path.with_name(path.stem+'_one_page.tmp.pdf')
        try:
            with temporary.open('wb') as destination:writer.write(destination)
        except Exception:temporary.unlink(missing_ok=True);raise
    temporary.replace(path)
