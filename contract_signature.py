"""Signature photographique commune aux modèles 2/3 et au modèle historique."""
import re, html
from phone_signature import signature_data_uri

def strip_signature_images(content):
    return re.sub(r'<img\b[^>]*alt=[\'"]Signature client[\'"][^>]*>', '',content,flags=re.I)

def embed_client_signature(content,contract_no,cin=''):
    uri=signature_data_uri(contract_no)
    if not uri:return content
    image=f'<img class="hbz-client-signature" src="{uri}" alt="Signature client" style="display:block;width:auto;height:auto;max-width:100%;max-height:11mm;object-fit:contain;margin:1mm auto">'
    # Reference model: first sigbody following Signature client heading.
    content,n=re.subn(r"(<div class='sighead'>8&nbsp;&nbsp;Signature client</div><div class='sigbody'[^>]*>)(.*?)(</div>)",lambda m:m[1]+image+strip_signature_images(m[2])+m[3],content,count=1,flags=re.S)
    if n:return content
    content,n=re.subn(r"(<div class='signature'><b>♟ SIGNATURE CLIENT</b>)(.*?)(</div>)(<div class='signature'>)",lambda m:m[1]+image+strip_signature_images(m[2])+m[3]+m[4],content,count=1,flags=re.S)
    if n:return content
    return content.replace("<div class='signature'>Signature du locataire</div>","<div class='signature'>Signature du locataire"+image+"<strong>CIN : "+html.escape(str(cin))+"</strong></div>",1)
