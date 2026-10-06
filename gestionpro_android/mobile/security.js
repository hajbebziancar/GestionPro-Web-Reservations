"use strict";
// The encryption key remains only in memory; IndexedDB stores an AES-GCM envelope.
(()=>{
const rawGet=GP.get,rawSet=GP.set,enc=new TextEncoder(),dec=new TextDecoder();let key,salt;
const b64=bytes=>btoa(Array.from(new Uint8Array(bytes),x=>String.fromCharCode(x)).join(''));
const un64=text=>Uint8Array.from(atob(text),x=>x.charCodeAt(0));
async function derive(password,salt){const material=await crypto.subtle.importKey('raw',enc.encode(password),'PBKDF2',false,['deriveKey']);return crypto.subtle.deriveKey({name:'PBKDF2',salt,iterations:310000,hash:'SHA-256'},material,{name:'AES-GCM',length:256},false,['encrypt','decrypt'])}
async function seal(value){const iv=crypto.getRandomValues(new Uint8Array(12));const ciphertext=await crypto.subtle.encrypt({name:'AES-GCM',iv},key,enc.encode(JSON.stringify(value)));return {encrypted:1,salt:b64(salt),iv:b64(iv),ciphertext:b64(ciphertext)}}
async function readEnvelope(value){return JSON.parse(dec.decode(await crypto.subtle.decrypt({name:'AES-GCM',iv:un64(value.iv)},key,un64(value.ciphertext))))}
GP.unlock=async()=>{
 if(!crypto.subtle)throw Error('HTTPS nécessaire pour protéger les données.');
 const old=await rawGet('state');
 if(old?.encrypted){salt=un64(old.salt);let opened=false;for(let n=0;n<5;n++){const password=prompt('Mot de passe local Gestion Pro (données chiffrées)');if(password===null)throw Error('Application verrouillée. Rechargez pour déverrouiller.');try{key=await derive(password,salt);await readEnvelope(old);opened=true;break}catch(e){alert('Mot de passe incorrect.')}}if(!opened)throw Error('Application verrouillée. Réessayez plus tard.');}
 else{let password=prompt('Créez un mot de passe local de 10 caractères minimum. Gardez-le : il ne peut pas être récupéré. Les données existantes seront conservées et chiffrées.');if(!password||password.length<10)throw Error('Mot de passe de 10 caractères minimum requis. Rechargez pour continuer.');if(prompt('Confirmez votre mot de passe local')!==password)throw Error('Confirmation différente. Les données restent intactes.');salt=crypto.getRandomValues(new Uint8Array(16));key=await derive(password,salt);await rawSet('state',await seal(old||{data:null,queue:[],archives:{},config:{token:''},lastSync:null}));}
};
GP.get=async name=>{const value=await rawGet(name);if(name==='state'&&value?.encrypted){if(!key)throw Error('Application verrouillée.');return readEnvelope(value)}return value};
GP.set=async(name,value)=>{if(name==='state'){if(!key)throw Error('Application verrouillée.');return rawSet(name,await seal(value))}return rawSet(name,value)};
let timer;const touch=()=>{clearTimeout(timer);timer=setTimeout(async()=>{if(typeof saving!=='undefined')await saving;location.reload()},10*60*1000)};['pointerdown','keydown'].forEach(type=>document.addEventListener(type,touch,{passive:true}));touch();
})();
