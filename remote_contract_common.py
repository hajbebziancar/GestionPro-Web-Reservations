"""Contrats autonomes pour lecture publique et signature distante."""
import base64,re,os,io
from pathlib import Path
from urllib.parse import urlparse,unquote
from PIL import Image,ImageOps

def normalize_png(payload):
    with Image.open(io.BytesIO(payload)) as im:
        if im.format!='PNG' or im.width*im.height>8_000_000:raise ValueError('Image invalide.')
        canvas=Image.new('RGBA',im.size,'white');canvas.alpha_composite(im.convert('RGBA'));im=canvas.convert('RGB')
    ink=ImageOps.grayscale(im).point(lambda p:255 if p<220 else 0);box=ink.getbbox()
    if not box or sum(ink.histogram()[1:])<12:raise ValueError('Signez dans le cadre avant de valider.')
    im=ImageOps.expand(im.crop(box),border=12,fill='white');out=io.BytesIO();im.save(out,'PNG');return out.getvalue()

def freeze_html(content):
    # The desktop builds trusted HTML, embedding its local document assets.
    def asset(m):
        if not m[2].startswith('file:'):return m[0]
        path=unquote(urlparse(m[2]).path)
        if os.name=='nt' and re.match(r'^/[A-Za-z]:',path):path=path[1:]
        p=Path(path);mime={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.svg':'image/svg+xml'}.get(p.suffix.lower())
        if not mime or not p.is_file():raise ValueError('Image du contrat introuvable : '+p.name)
        return 'src='+m[1]+'data:'+mime+';base64,'+base64.b64encode(p.read_bytes()).decode()+m[1]
    content=re.sub(r'src=([\'"])(.*?)\1',asset,content)
    content=re.sub(r'<script\b[^>]*>.*?</script>','',content,flags=re.I|re.S)
    return content

def insert_signature(content,payload):
    uri='data:image/png;base64,'+base64.b64encode(payload).decode()
    img=f'<img alt="Signature client" src="{uri}" style="display:block;max-width:100%;max-height:10mm;object-fit:contain;margin:.4mm auto">'
    def clean(body):return re.sub(r'<img\b[^>]*alt=[\'"]Signature client[\'"][^>]*>','',body,flags=re.I)
    patterns=[r'(<div class="signature-body signature-identity">)(.*?)(</div>)',r"(<div class='sighead'>8&nbsp;&nbsp;Signature client</div><div class='sigbody'[^>]*>)(.*?)(</div>)",r"(<div class='signature'><b>♟ SIGNATURE CLIENT</b>)(.*?)(</div>)(?=<div class='signature'>)"]
    for pattern in patterns:
        out,n=re.subn(pattern,lambda m:m[1]+img+clean(m[2])+m[3],content,count=1,flags=re.S)
        if n:return out
    if "<div class='signature'>Signature du locataire" in content:
        return content.replace("<div class='signature'>Signature du locataire","<div class='signature'>Signature du locataire"+img,1)
    raise ValueError('Cadre de signature du contrat non reconnu.')
