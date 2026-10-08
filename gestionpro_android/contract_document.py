"""Adaptateur des données mobiles vers le modèle HBZ du PC fourni."""
import html,json,sqlite3,base64,re
from pathlib import Path
from datetime import datetime
from .contract_model1 import render_contract_model1
from .contract_support import image_data
from .contract_print_details import add_print_observations
ROOT=Path(__file__).resolve().parent
CONTRACT_ACKNOWLEDGEMENT = (
    "Je soussigné, locataire du présent véhicule, déclare avoir pris connaissance "
    "des termes et obligations cités au recto et au verso du présent contrat "
    "et je m'engage à les respecter. Je suis responsable des violations de toutes "
    "les lois et réglementations en vigueur, notamment celles relatives à la "
    "circulation et à la réglementation douanière."
)
CONTRACT_ACKNOWLEDGEMENT_AR = (
    "يقر المستأجر بأنه اطلع على شروط الكراء ويلتزم بإرجاع السيارة في حالتها الأصلية. "
    "أنا الموقع أسفله، مستأجر هذه السيارة، أصرح بأنني اطلعت على البنود والالتزامات "
    "المذكورة في وجه هذا العقد وظهره، وأتعهد باحترامها. وأتحمل مسؤولية مخالفة "
    "جميع القوانين والأنظمة الجاري بها العمل، ولا سيما المتعلقة بالسير والتنظيم الجمركي."
)
class Value:
    def __init__(self,v):self.v=v
    def get(self):return self.v
class Document:
    def __init__(self,frozen,signature=''):
        self.signature=signature;self.settings=frozen['settings'];r=frozen['record'];c=frozen['client'];v=frozen['vehicle']
        self.photo_uri=v.get('photo_uri','')
        fields={'contract_no':r['numero'],'client_code':c['code'],'last_name':c.get('nom'),'first_name':c.get('prenom'),'cin':c.get('cin'),'birth_date':c.get('date_naissance'),'address':c.get('adresse'),'city':c.get('ville'),'phone':c.get('telephone'),'license_no':c.get('permis'),'license_date':c.get('date_permis'),'vehicle_code':v['code'],'vehicle_model':v.get('modele'),'plate':v.get('immatriculation'),'chassis':v.get('chassis'),'km_start':r.get('km_depart'),'date_start':r['date_depart'],'time_start':r.get('heure_depart'),'date_end':r['date_retour'],'time_end':r.get('heure_retour'),'duration':r.get('duree'),'daily_price':r.get('prix'),'total':r.get('montant'),'paid':r.get('reglement'),'balance':r.get('reste')}
        for target,key in [('age','date_naissance'),('license_age','date_permis')]:
            try:
                d=datetime.strptime(c.get(key,''),'%d/%m/%Y');today=datetime.now();fields[target]=str(today.year-d.year-((today.month,today.day)<(d.month,d.day)))
            except ValueError:fields[target]=''
        second=frozen.get('second_client') or {}
        for target,key in [('second_code','code'),('second_last','nom'),('second_first','prenom'),('second_cin','cin'),('second_birth_date','date_naissance'),('second_phone','telephone'),('second_license','permis'),('second_license_date','date_permis')]:fields[target]=second.get(key,'')
        fields['fuel_level']=r.get('fuel_level','½')
        self.vars={k:Value(str(x if x is not None else '')) for k,x in fields.items()}
        self.conn=sqlite3.connect(':memory:');self.conn.row_factory=sqlite3.Row
        keys=[k for k in v if re.fullmatch('[A-Za-z_][A-Za-z0-9_]*',k) and not isinstance(v[k],(dict,list))]
        self.conn.execute('CREATE TABLE vehicles('+','.join('"'+k+'"' for k in keys)+')')
        self.conn.execute('INSERT INTO vehicles VALUES('+','.join('?' for k in keys)+')',[v[k] for k in keys])
        self.conn.execute('CREATE TABLE contracts(numero,return_status)');self.conn.execute('INSERT INTO contracts VALUES(?,?)',(r['numero'],'En cours'))
        self.conn.execute('CREATE TABLE contract_vehicle_states(contract_no,payload)')
        self.conn.execute('CREATE TABLE module_records(module,record_id,payload)')
        self.conn.execute('INSERT INTO module_records VALUES(?,?,?)',('client_rapide_contract',r['numero'],json.dumps({'ref_notes':'\n'.join(filter(None,[r.get('notes',''),'Départ : '+r['departure_location'] if r.get('departure_location') else '', 'Retour : '+r['return_location'] if r.get('return_location') else '', 'Paiement : '+r['payment_mode'] if r.get('payment_mode') else '']))})))
        self.conn.execute('INSERT INTO module_records VALUES(?,?,?)',('contract_vehicle_condition',r['numero'],json.dumps(r.get('condition',v.get('condition',{})))))
    def _get_setting(self,key,fallback=''):return self.settings.get(key,fallback)
    def _resolve_vehicle_photo_path(self,stored,code):
        return self.photo_uri
    def _document_logo_uri(self):return image_data(ROOT/'assets/HBZ_REN_CAR_LOGO.png')

    def _printed_contract_conditions(self):
        """Préserve les clauses françaises existantes et ajoute la déclaration fournie."""
        default="Le locataire reconnaît avoir pris connaissance des conditions de location et s’engage à restituer le véhicule dans l’état initial."
        current=str(self._get_setting("general_conditions",default) or "").strip()
        if "je soussigné" in current.lower() and "réglementation douani" in current.lower():
            return current
        return (current+"\n" if current else "")+CONTRACT_ACKNOWLEDGEMENT

    def _contract_conditions_html(self):
        french=html.escape(self._printed_contract_conditions()).replace("\n","<br>")
        arabic=html.escape(str(self._get_setting("general_conditions_ar",CONTRACT_ACKNOWLEDGEMENT_AR) or "")).replace("\n","<br>")
        return (f'<div lang="fr" style="margin:0 0 1mm">{french}</div>'
                f'<div lang="ar" dir="rtl" style="text-align:right;font-family:Arial,Tahoma,sans-serif;'
                f'font-size:1.08em;line-height:1.25">{arabic}</div>')

    @staticmethod
    def _style_bilingual_conditions(content):
        css = '<style id="hbz-bilingual-conditions">\n.conditions-content,.condbody{column-count:auto!important;display:grid!important;\ngrid-template-columns:1fr 1fr!important;align-items:start!important;gap:3mm!important;\nfont-size:7px!important;line-height:1.2!important}\n.conditions-content>div,.condbody>div{min-width:0;overflow-wrap:anywhere}\n</style>'
        return content.replace('</head>', css + '</head>', 1)

def document_html(frozen,signature=''):
    from remote_contract_common import freeze_html,ensure_verso,insert_signature,normalize_png
    d=Document(frozen)
    try:content=d._style_bilingual_conditions(add_print_observations(render_contract_model1(d),d.conn,frozen['record']['numero']))
    finally:d.conn.close()
    content=ensure_verso(freeze_html(content))
    if signature:
        if not signature.startswith('data:image/png;base64,'):raise ValueError('Signature PNG requise.')
        content=insert_signature(content,normalize_png(base64.b64decode(signature.split(',',1)[1],validate=True)))
    return content

def document_pdf(frozen,signature=''):
    from remote_signatures import render_pdf
    from pypdf import PdfReader,PdfWriter,Transformation
    import io
    content=document_html(frozen,signature)
    render_content=re.sub(r'<img class="hbz-conditions"[^>]*>', '<div class="hbz-conditions"></div>',content)
    payload=render_pdf(render_content)
    reader=PdfReader(io.BytesIO(payload))
    if len(reader.pages)!=2:raise ValueError('Le contrat doit contenir exactement un recto et un verso. Vérifiez les données.')
    # Same original vector conditions PDF as the PC, preserving every clause.
    writer=PdfWriter();writer.add_page(reader.pages[0]);back=writer.add_blank_page(width=595.276,height=841.89)
    original=PdfReader(ROOT/'assets/contract_verso_conditions.pdf').pages[0]
    back.merge_transformed_page(original,Transformation().scale(.93).translate(21,45))
    signature_page=reader.pages[1];signature_page.cropbox.lower_left=(0,0);signature_page.cropbox.upper_right=(595.276,110)
    back.merge_page(signature_page)
    writer.add_metadata({'/Title':'Contrat '+str(frozen['record']['numero']),'/Author':str(frozen['settings'].get('company_name','Gestion Pro'))})
    out=io.BytesIO();writer.write(out)
    return out.getvalue(),content
