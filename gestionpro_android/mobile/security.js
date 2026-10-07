"use strict";
// The encryption key remains only in memory; IndexedDB stores an AES-GCM envelope.
(()=>{
const rawGet=GP.get,rawSet=GP.set,enc=new TextEncoder(),dec=new TextDecoder();let key,salt;
const b64=bytes=>btoa(Array.from(new Uint8Array(bytes),x=>String.fromCharCode(x)).join(''));
const un64=text=>Uint8Array.from(atob(text),x=>x.charCodeAt(0));
async function derive(password,salt){const material=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:310000,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt'])}
async function seal(value){const iv=crypto.getRandomValues(new Uint8Array(12));const ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv},key,enc.encode(JSON.stringify(value)));return {encrypted:1,salt:b64(salt),iv:b64(iv),ciphertext:b64(ciphertext)}}
async function readEnvelope(value){return JSON.parse(dec.decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:un64(value.iv)},key,un64(value.ciphertext))))}

GP.loginScreen=(title,creating=false,note='')=>new Promise(resolve=>{
 document.body.classList.add('connection-page','hbz-login');
 document.getElementById('main').innerHTML=`<section class="hbz-login-shell"><div class="hbz-login-scene" role="img" aria-label="HBZ Rent Car · Gestion Pro"></div><form class="hbz-login-form"><div class="login-lock">🔒</div><h1>${title}</h1><div class="gold-line"></div><label class="password-wrap"><span class="sr-only">Mot de passe</span><input id="hbz-password" type="password" placeholder="Saisir votre mot de passe" required autocomplete="${creating?'new-password':'current-password'}" ${creating?'minlength="10"':''}><button type="button" class="password-eye" aria-label="Afficher le mot de passe">◉</button></label>${creating?'<input id="hbz-confirm" type="password" placeholder="Confirmer le mot de passe" minlength="10" required autocomplete="new-password">':''}<p class="login-note">${note}</p><p id="login-error" role="alert"></p><button class="login-submit" type="submit">➜ &nbsp; ${creating?'CRÉER LE MOT DE PASSE':'SE CONNECTER'}</button></form><div class="hbz-login-footer"><span>🚘<small>Véhicules</small></span><span>♟<small>Clients</small></span><span>▤<small>Contrats</small></span><span>▥<small>Finances</small></span></div></section>`;
 const form=document.querySelector('.hbz-login-form'),input=document.getElementById('hbz-password');
 form.querySelector('.password-eye').onclick=e=>{input.type=input.type==='password'?'text':'password';e.currentTarget.setAttribute('aria-label',input.type==='password'?'Afficher le mot de passe':'Masquer le mot de passe')};
 form.onsubmit=e=>{e.preventDefault();if(creating&&input.value!==document.getElementById('hbz-confirm').value){document.getElementById('login-error').textContent='Les mots de passe sont différents.';return}document.body.classList.remove('hbz-login');resolve(input.value)};
});

GP.unlock=async()=>{
 if(!crypto.subtle)throw Error('HTTPS nécessaire pour protéger les données.');
 const old=await rawGet('state');
 if(old?.encrypted){salt=un64(old.salt);let opened=false;for(let n=0;n<5;n++){const password=await GP.loginScreen('Connexion',false,'Mot de passe local de ce téléphone.');if(password===null)throw Error('Application verrouillée. Rechargez pour déverrouiller.');try{key=await derive(password,salt);await readEnvelope(old);opened=true;break}catch(e){document.body.classList.add('hbz-login');document.getElementById('login-error').textContent='Mot de passe incorrect.'}}if(!opened)throw Error('Application verrouillée. Réessayez plus tard.');}
 else{let password=await GP.loginScreen('Première connexion',true,'Créez un mot de passe local de 10 caractères minimum. Conservez-le : il protège les données de ce téléphone et ne peut pas être récupéré.');if(!password||password.length<10)throw Error('Mot de passe de 10 caractères minimum requis. Rechargez pour continuer.');salt=crypto.getRandomValues(new Uint8Array(16));key=await derive(password,salt);await rawSet('state',await seal(old||{data:null,queue:[],archives:{},config:{token:''},lastSync:null}));}
};
GP.get=async name=>{const value=await rawGet(name);if(name==='state'&&value?.encrypted){if(!key)throw Error('Application verrouillée.');return readEnvelope(value)}return value};
GP.set=async(name,value)=>{if(name==='state'){if(!key)throw Error('Application verrouillée.');return rawSet(name,await seal(value))}return rawSet(name,value)};
let timer;const touch=()=>{clearTimeout(timer);timer=setTimeout(async()=>{if(typeof saving!=='undefined')await saving;location.reload()},10*60*1000)};['pointerdown','keydown'].forEach(type=>document.addEventListener(type,touch,{passive:true}));touch();
})();
