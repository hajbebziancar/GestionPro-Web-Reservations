'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
(async()=>{
const source=fs.readFileSync(require('node:path').join(__dirname,'../mobile/security.js'),'utf8');
let stored,writes=0,reads=0,decrypts=0;
const crypto={getRandomValues:webcrypto.getRandomValues.bind(webcrypto),subtle:new Proxy(webcrypto.subtle,{get(target,name){if(name==='decrypt')return async(...args)=>{decrypts++;return target.decrypt(...args)};return typeof target[name]==='function'?target[name].bind(target):target[name]}})};
const context=vm.createContext({crypto,TextEncoder,TextDecoder,Uint8Array,JSON,Promise,btoa,atob,setTimeout:()=>0,clearTimeout(){},document:{addEventListener(){},body:{classList:{add(){}}},getElementById:()=>({textContent:''})},location:{reload(){}},GP:{get:async()=>{reads++;return stored},set:async(_,value)=>{writes++;stored=value}}});
vm.runInContext(source,context);context.GP.loginScreen=async()=> 'password-valid-10';
await context.GP.unlock();await context.GP.get('state');
const state={data:{vehicles:[{photo_uri:'x'.repeat(8*1024*1024)}]},queue:[],archives:{},config:{token:'test'}};
await context.GP.set('state',state);const envelope=stored;assert.equal(envelope.encrypted,1);
// Reload with the previous encrypted database, which includes a large image.
vm.runInContext(source,vm.createContext({crypto,TextEncoder,TextDecoder,Uint8Array,JSON,Promise,btoa,atob,setTimeout:()=>0,clearTimeout(){},document:{addEventListener(){},body:{classList:{add(){}}},getElementById:()=>({textContent:''})},location:{reload(){}},GP:context.GP={get:async()=>{reads++;return stored},set:async(_,value)=>{writes++;stored=value}}}));
context.GP.loginScreen=async()=> 'password-valid-10';const previousWrites=writes,previousReads=reads,previousDecrypts=decrypts;
await context.GP.unlock();const opened=await context.GP.get('state');assert.equal(opened.data.vehicles[0].photo_uri.length,8*1024*1024);assert.equal(opened.config.token,'test');assert.equal(writes,previousWrites);assert.equal(reads-previousReads,1);assert.equal(decrypts-previousDecrypts,1);assert.equal(stored,envelope);
console.log('Connexion : base de 8 Mio compatible, un seul déchiffrement, aucune réécriture au déverrouillage.');
})().catch(e=>{console.error(e);process.exitCode=1});
