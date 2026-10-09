"""Copies figées des contrats signés et accès depuis les historiques."""
from pathlib import Path
from datetime import datetime
import base64,hashlib,json,os,re,secrets
from urllib.parse import unquote,urlparse
ROOT=Path(__file__).resolve().parent/'contrats_signes'

def key(number):
    value=str(number).strip()
    if not value:raise ValueError('Numéro de contrat absent.')
    return hashlib.sha256(value.encode()).hexdigest()[:24]
def find_signed(number,client_code=None):
    try:
        record=json.loads((ROOT/key(number)/'latest.json').read_text(encoding='utf-8'))
        if record['contract_no']!=str(number).strip():return None
        if client_code is not None and str(client_code).strip() not in record['client_codes']:return None
        if not (ROOT/key(number)/record['html']).is_file():return None
        return record
    except (OSError,ValueError,KeyError):return None

def signed_html(number,client_code=None):
    record=find_signed(number,client_code)
    return ROOT/key(number)/record['html'] if record else None

def archive_contract(number,client_codes,content,payload):
    if not content or not client_codes:raise ValueError('Le contrat doit être chargé avec son client avant signature.')
    uri='data:image/png;base64,'+base64.b64encode(payload).decode()
    img=f'<img src="{uri}" alt="Signature client" style="display:block;max-width:100%;max-height:10mm;object-fit:contain;margin:1mm auto">'
    from contract_signature import strip_signature_images
    # Model 1: only the first signature body belongs to the selected client.
    content,n=re.subn(r'(<div class="signature-body signature-identity">)(.*?)(</div>)',lambda m:m[1]+img+strip_signature_images(m[2])+m[3],content,count=1,flags=re.S)
    if not n:
        from contract_signature import embed_client_signature
        content=embed_client_signature(content,number)
    if uri not in content:raise ValueError('Le modèle du contrat ne comporte pas de cadre de signature reconnu.')
    # Freeze local assets so archived contracts survive later asset/vehicle changes.
    def asset(match):
        original=match[2]
        if not original.startswith('file:'):return match[0]
        try:
            path=Path(unquote(urlparse(original).path))
            if os.name=='nt' and re.match(r'^/[A-Za-z]:',str(path)):path=Path(str(path)[1:])
            mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.svg':'image/svg+xml'}.get(path.suffix.lower())
            if not mime or not path.is_file():return match[0]
            return 'src='+match[1]+'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode()+match[1]
        except OSError:return match[0]
    content=re.sub(r'src=([\'"])(.*?)\1',asset,content)
    folder=ROOT/key(number);folder.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S_%f')+'_'+secrets.token_hex(3)
    html_name=stamp+'.html';image_name=stamp+'.png'
    (folder/html_name).write_text(content,encoding='utf-8');(folder/image_name).write_bytes(payload)
    record={'contract_no':str(number).strip(),'client_codes':[str(c).strip() for c in client_codes if str(c).strip()],'signed_at':datetime.now().isoformat(timespec='seconds'),'html':html_name,'signature':image_name,'sha256':hashlib.sha256(payload).hexdigest()}
    temp=folder/(stamp+'.json.tmp');temp.write_text(json.dumps(record,ensure_ascii=False),encoding='utf-8');os.replace(temp,folder/'latest.json')
    return record

def has_signed(number):
    if find_signed(number):return True
    from phone_signature import saved_signature
    return bool(saved_signature(number))

def icon(number):return '✍ Ouvrir' if has_signed(number) else '—'

def install_signed_column(tree,opener):
    columns=list(tree['columns'])
    if 'signed_contract' not in columns:tree.configure(columns=columns+['signed_contract'])
    tree.heading('signed_contract',text='Contrat signé');tree.column('signed_contract',width=88,minwidth=75,anchor='center',stretch=True)
    def clicked(event):
        if tree.identify_region(event.x,event.y)!='cell':return
        col=tree.identify_column(event.x)
        if col!='#'+str(len(tree['columns'])):return
        item=tree.identify_row(event.y)
        if not item:return
        values=tree.item(item,'values')
        if values and has_signed(values[0]):opener(values[0]);return 'break'
    tree.bind('<ButtonRelease-1>',clicked,add='+')

def refresh_signed_column(tree):
    columns=list(tree['columns'])
    if 'signed_contract' not in columns:return
    for item in tree.get_children():
        values=list(tree.item(item,'values'))
        if not values:continue
        values=values[:len(columns)-1];values.extend(['']*(len(columns)-1-len(values)));values.append(icon(values[0]));tree.item(item,values=values)
