import html, json

def _page(token, contract_no):
    c=html.escape(contract_no)
    return f'''<!doctype html><html lang="fr"><head><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no"><meta charset="utf-8"><title>Signature contrat {c}</title><style>
body{{font-family:Arial,sans-serif;margin:0;background:#eef4f8;color:#17324d}}.wrap{{max-width:850px;margin:auto;padding:18px}}h2{{margin:4px 0}}p{{color:#52687a}}canvas{{width:100%;height:52vh;min-height:330px;background:#fff;border:2px solid #1684d6;border-radius:14px;touch-action:none;box-sizing:border-box}}.bar{{display:flex;gap:12px;margin-top:14px}}button{{flex:1;border:0;border-radius:10px;padding:16px;font-size:18px;font-weight:700}}#clear{{background:#dfe8ef;color:#30495e}}#save{{background:#138c4b;color:#fff}}#msg{{font-weight:700;margin-top:12px}}</style></head><body><div class="wrap"><h2>HBZ Rent Car — Signature client</h2><p>Contrat <b>{c}</b> · Signez dans le cadre avec le S Pen ou le doigt.</p><canvas id="pad"></canvas><div class="bar"><button id="clear">Effacer</button><button id="save">Valider la signature</button></div><div id="msg"></div></div><script>
const token={json.dumps(token)};
const cv=document.getElementById('pad'),ctx=cv.getContext('2d');
const save=document.getElementById('save'),msg=document.getElementById('msg');
let drawing=false,dirty=false,revision='',saving=false,epoch=0,syncing=false;
function resize(){{
 const old=document.createElement('canvas');old.width=cv.width;old.height=cv.height;old.getContext('2d').drawImage(cv,0,0);
 const r=cv.getBoundingClientRect(),d=Math.min(window.devicePixelRatio||1,1.5);
 cv.width=Math.max(600,Math.floor(r.width*d));cv.height=Math.max(350,Math.floor(r.height*d));
 ctx.lineWidth=3*d;ctx.lineCap='round';ctx.lineJoin='round';ctx.strokeStyle='#111';
 ctx.drawImage(old,0,0,cv.width,cv.height);
}}
resize();window.addEventListener('resize',resize);
function pt(e){{let r=cv.getBoundingClientRect();return [(e.clientX-r.left)*cv.width/r.width,(e.clientY-r.top)*cv.height/r.height]}}
cv.addEventListener('pointerdown',e=>{{if(saving)return;e.preventDefault();drawing=true;epoch++;dirty=true;save.disabled=false;save.textContent='Valider la signature';cv.setPointerCapture(e.pointerId);ctx.beginPath();ctx.moveTo(...pt(e))}});
cv.addEventListener('pointermove',e=>{{if(!drawing)return;e.preventDefault();ctx.lineTo(...pt(e));ctx.stroke()}});
cv.addEventListener('pointerup',()=>drawing=false);cv.addEventListener('pointercancel',()=>drawing=false);
document.getElementById('clear').onclick=()=>{{if(saving)return;epoch++;ctx.clearRect(0,0,cv.width,cv.height);dirty=false;save.disabled=false;save.textContent='Valider la signature';msg.textContent='Signez dans le cadre. La signature enregistrée est conservée tant qu’un nouveau tracé n’est pas validé.'}};
async function synchronize(force=false){{
 if(syncing||drawing||dirty||saving)return;syncing=true;const ticket=epoch;
 try{{
  const r=await fetch('/status/'+token,{{cache:'no-store'}});if(!r.ok)return;
  const state=await r.json();if(!state.saved||(!force&&state.revision===revision))return;
  const imageResponse=await fetch('/image/'+token+'?revision='+state.revision,{{cache:'no-store'}});if(!imageResponse.ok)return;
  const blob=await imageResponse.blob(),url=URL.createObjectURL(blob);
  try{{
   const im=new Image();await new Promise((resolve,reject)=>{{im.onload=resolve;im.onerror=reject;im.src=url}});
   if(ticket!==epoch||drawing||dirty||saving)return;
   ctx.clearRect(0,0,cv.width,cv.height);
   const scale=Math.min(cv.width/im.width,cv.height/im.height)*.86,w=im.width*scale,h=im.height*scale;
   ctx.drawImage(im,(cv.width-w)/2,(cv.height-h)/2,w,h);revision=state.revision;
   save.disabled=true;save.textContent='✓ Signature validée';msg.textContent='✓ Signature enregistrée et affichée. Vous pouvez fermer cette page.';
  }}finally{{URL.revokeObjectURL(url)}}
 }}catch(_e){{}}finally{{syncing=false}}
}}
save.onclick=async()=>{{
 if(saving)return;
 if(!dirty){{msg.textContent='Signez dans le cadre avant de valider.';return}}
 saving=true;save.disabled=true;drawing=false;epoch++;msg.textContent='Enregistrement en cours…';
 try{{
  const r=await fetch('/save/'+token,{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{image:cv.toDataURL('image/png')}}),cache:'no-store'}});
  const j=await r.json();if(!r.ok||!j.ok)throw new Error(j.error||('HTTP '+r.status));
  dirty=false;revision='';msg.textContent='✓ Signature enregistrée. Vous pouvez fermer cette page.';save.textContent='✓ Signature validée';
 }}catch(e){{save.disabled=false;msg.textContent='Échec de validation : '+e.message}}
 finally{{saving=false}}
 await synchronize(true);
}};
synchronize();setInterval(synchronize,900);
</script></body></html>'''
