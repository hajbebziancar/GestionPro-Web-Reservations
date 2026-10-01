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
        if n:return insert_verso_signature(out,img)
    pattern=r"(<div class='signature'>Signature du locataire)(.*?)(</div>)"
    out,n=re.subn(pattern,lambda m:m[1]+img+clean(m[2])+m[3],content,count=1,flags=re.S)
    if n:return insert_verso_signature(out,img)
    raise ValueError('Cadre de signature du contrat non reconnu.')


def ensure_verso(content):
    """Use the same bilingual conditions sheet as the desktop application."""
    if 'id="hbz-remote-verso"' in content:return content
    picture=Path(__file__).resolve().parent/'assets'/'contract_verso_conditions.jpg'
    if not picture.is_file():raise ValueError('Le verso des conditions générales est introuvable.')
    uri='data:image/jpeg;base64,'+base64.b64encode(picture.read_bytes()).decode()
    existing=re.search(r'<div class=[\"\']hbz-contract-verso[\"\']>\s*<img[^>]*src=([\"\'])(.*?)\1[^>]*>\s*</div>',content,re.S)
    if existing:
        uri=existing[2]
        content=content[:existing.start()]+content[existing.end():]
    css='<style id="hbz-remote-duplex">@page{size:A4;margin:4mm}html,body{height:auto!important;max-height:none!important;overflow:visible!important}#hbz-remote-verso{page-break-before:always;break-before:page;box-sizing:border-box;width:100%;height:280mm;display:block;position:relative;background:white;color:#17324d}#hbz-remote-verso>.hbz-conditions{display:block;width:100%;height:257mm;max-height:257mm;object-fit:contain}#hbz-remote-verso>.hbz-back-signature{height:20mm;box-sizing:border-box;border:1px solid #789;padding:2mm;font:11px Arial;break-inside:avoid}#hbz-remote-verso>.hbz-back-signature img{max-height:11mm!important}</style>'
    verso='<section id="hbz-remote-verso"><img class="hbz-conditions" alt="Conditions générales du contrat, verso" src="'+uri+'"><div class="hbz-back-signature"><b>Signature du client — acceptation des conditions au recto et au verso</b><div id="hbz-verso-signature"></div></div></section>'
    if not re.search(r'</body>',content,re.I):raise ValueError('Document de contrat incomplet.')
    content=re.sub(r'</head>',lambda m:css+m[0],content,count=1,flags=re.I)
    return re.sub(r'</body>',lambda m:verso+m[0],content,count=1,flags=re.I)


def insert_verso_signature(content,img):
    pattern=r'(<div id="hbz-verso-signature">)(.*?)(</div>)'
    out,n=re.subn(pattern,lambda m:m[1]+img+m[3],content,count=1,flags=re.S)
    if not n:raise ValueError('Le cadre de signature au verso est absent.')
    return out
