(function(global){
function signature(canvas){const ratio=window.devicePixelRatio||1;canvas.width=900*ratio;canvas.height=300*ratio;const ctx=canvas.getContext('2d');ctx.scale(ratio,ratio);ctx.lineWidth=3;ctx.strokeStyle='#133b67';ctx.lineCap='round';let down=false,ink=false;const point=e=>{const r=canvas.getBoundingClientRect();return [(e.clientX-r.left)*900/r.width,(e.clientY-r.top)*300/r.height]};canvas.onpointerdown=e=>{canvas.setPointerCapture(e.pointerId);down=true;ctx.beginPath();ctx.moveTo(...point(e));e.preventDefault()};canvas.onpointermove=e=>{if(down){ctx.lineTo(...point(e));ctx.stroke();ink=true;e.preventDefault()}};canvas.onpointerup=canvas.onpointercancel=()=>down=false;return {clear(){ctx.clearRect(0,0,900,300);ink=false},value(){return ink?canvas.toDataURL('image/png'):''}}}
async function image(src){return new Promise((res,rej)=>{const i=new Image();i.onload=()=>res(i);i.onerror=()=>rej(Error('Image invalide'));i.src=src})}
async function pdf(frozen,signatureURI){
const remote=location.pathname.startsWith('/mobile/signature/');const endpoint=remote?location.pathname.replace(/\/$/,'')+'/pdf':'/mobile/api/contract-pdf';
let token='';if(!remote){const st=await GP.get('state');token=st?.config?.token||''}
let r;try{r=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json',...(!remote?{'Authorization':'Bearer '+token}:{})},body:JSON.stringify({frozen,signature:signatureURI})})}catch(x){throw Error('Une connexion est nécessaire pour produire le contrat HBZ recto verso. La saisie et les données restent sur ce téléphone.')}
const data=await r.json();if(!r.ok)throw Error(data.error||'Conversion PDF indisponible.');return bytes(data.pdf)
}
function toBase64(bytes){let out='';for(let i=0;i<bytes.length;i+=8192)out+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(out)}
function bytes(b64){return Uint8Array.from(atob(b64),c=>c.charCodeAt(0))}
function download(data,name,type='application/pdf'){let url=URL.createObjectURL(new Blob([data],{type}));let a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000)}
function phone(value){let p=String(value||'').replace(/\D/g,'');if(p.startsWith('00'))p=p.slice(2);if(p.length===10&&p[0]==='0')p='212'+p.slice(1);if(!/^[1-9]\d{7,14}$/.test(p))throw Error('Téléphone client absent ou invalide.');return p}
async function sharePDF(b64,name,number){const file=new File([bytes(b64)],name,{type:'application/pdf'});if(navigator.canShare&&navigator.canShare({files:[file]})){await navigator.share({files:[file],title:'Contrat de location',text:'Votre contrat de location'});return}phone(number);download(bytes(b64),name);window.open('https://wa.me/'+phone(number)+'?text='+encodeURIComponent('Bonjour, voici votre contrat de location. Je joins le PDF signé.'),'_blank','noopener');return 'Joignez le PDF téléchargé dans WhatsApp.'}
global.GPDoc={signature,pdf,toBase64,bytes,download,phone,sharePDF};
})(window);
