/* Domain and IndexedDB. No network dependency for local writes. */
(function(global){
const CLIENT_FIELDS=['code','cin','nom','prenom','telephone','ville','adresse','permis','date_naissance','date_permis','categorie','validite_permis'];
function isoToday(){return new Intl.DateTimeFormat('en-CA',{timeZone:'Africa/Casablanca',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
function parseDate(value,time='00:00'){let s=String(value||'').slice(0,10);if(/^\d{2}\/\d{2}\/\d{4}$/.test(s))s=s.split('/').reverse().join('-');if(!/^\d{4}-\d{2}-\d{2}$/.test(s)||!/^\d{2}:\d{2}$/.test(time))throw Error('Date ou heure invalide.');const d=new Date(s+'T'+time+':00');if(!Number.isFinite(d.getTime())||d.getFullYear()!=+s.slice(0,4)||d.getMonth()+1!=+s.slice(5,7)||d.getDate()!=+s.slice(8,10))throw Error('Date invalide.');return d}
function iso(value){if(!value)return '';return String(value).includes('/')?String(value).split('/').reverse().join('-'):String(value).slice(0,10)}
function french(value){const s=iso(value);return s?s.split('-').reverse().join('/'):'—'}
function num(v){let n=Number(String(v??0).replace(/[\s\u00a0\u202f]/g,'').replace(',','.'));if(!Number.isFinite(n)||n<0)throw Error('Valeur numérique invalide.');return n}
function round(n){return Math.round((n+Number.EPSILON)*100)/100}
function quote(start,end,price,paid,st='09:00',et='09:00'){let a=parseDate(start,st),b=parseDate(end,et);if(b<=a)throw Error('La date de retour doit suivre le départ.');let days=Math.max(1,Math.round((Date.UTC(b.getFullYear(),b.getMonth(),b.getDate())-Date.UTC(a.getFullYear(),a.getMonth(),a.getDate()))/86400000));let total=round(days*num(price)),advance=num(paid);if(advance>total)throw Error('Le règlement dépasse le montant total.');return {days,total,paid:round(advance),balance:round(total-advance)}}
function closed(status){return /ANNUL|TERMIN|CONVERT|SUPPR|RETOUR CONFIRM|ANTICIP/.test(String(status||'').toUpperCase())}
function vehicleCode(r){return String(r.vehicle||r.vehicle_code||'').split('|')[0].trim()}
function availability(data,code,start,end,st='09:00',et='09:00',ignore=''){let a=parseDate(start,st),b=parseDate(end,et);if(b<=a)throw Error('Dates invalides.');a=parseDate(start);b=parseDate(end);if(b<=a){b=new Date(a);b.setDate(b.getDate()+1)}for(const r of data.contracts||[]){if(r.numero===ignore||r.vehicle_code!==code||closed(r.return_status))continue;const ra=parseDate(r.date_depart);const rb=/RETARD CONFIRM/.test(r.return_status||'')?new Date(8640000000000000):parseDate(r.actual_return_date||r.date_retour);if(a<rb&&b>ra)throw Error('Véhicule occupé : '+r.numero)}for(const r of data.reservations||[]){if(r.reference===ignore||vehicleCode(r)!==code||closed(r.status))continue;const ra=parseDate(r.start_date),rb=parseDate(r.end_date);if(a<rb&&b>ra)throw Error('Véhicule réservé : '+r.reference)}}
function vehicleStatus(data,vehicle,today=isoToday()){
 if(Number(vehicle.service)!==1)return {label:'Hors service',tone:'offline'};
 const rented=(data.contracts||[]).some(r=>r.vehicle_code===vehicle.code&&!closed(r.return_status)&&iso(r.date_depart)<=today&&(iso(r.actual_return_date||r.date_retour)>today||/RETARD CONFIRM/.test(r.return_status||'')));
 if(rented)return {label:'Loué',tone:'rented'};
 const reserved=(data.reservations||[]).some(r=>vehicleCode(r)===vehicle.code&&!closed(r.status)&&iso(r.start_date)<=today&&iso(r.end_date)>today);
 if(reserved)return {label:'Réservé',tone:'reserved'};
 return {label:'Disponible',tone:'available'};
}
function periodMatch(value,month){return !month||iso(value).startsWith(month)}
function finance(data,month=''){let contracts=(data.contracts||[]).filter(r=>!closed(r.return_status)&&periodMatch(r.date_depart,month)); // Returned contracts still count in finance.
contracts=(data.contracts||[]).filter(r=>!/ANNUL/.test(r.return_status||'')&&periodMatch(r.date_depart,month));
const reservations=(data.reservations||[]).filter(r=>!closed(r.status)&&periodMatch(r.start_date,month));let revenue=0,paid=0,remaining=0;for(const r of contracts){revenue+=num(r.montant);paid+=num(r.reglement);remaining+=num(r.reste)}let advances=reservations.reduce((n,r)=>n+num(r.deposit),0),bookings=reservations.reduce((n,r)=>n+num(r.total),0);let expenses=0,otherIncome=0,unpaidExpenses=0;let expenseRefs=new Set();
for(const r of data.expenses||[]){if(!periodMatch(r.date,month))continue;const amount=num(r.amount);if(String(r.type).toUpperCase()==='CHARGE'){if(/EN ATTENTE|NON PAY/.test(r.status||''))unpaidExpenses+=amount;else{expenses+=amount;expenseRefs.add(r.source_maintenance||r.maintenance_reference||r.reference)}}else if(String(r.type).toUpperCase()==='PRODUIT'&&!/EN ATTENTE/.test(r.status||''))otherIncome+=amount}
let maintenance=0;for(const r of data.maintenance||[]){if(periodMatch(r.date,month)&&!expenseRefs.has(r.reference))maintenance+=num(r.amount)}
const due=(data.checks||[]).filter(r=>!/PAY|ENCAISS|ANNUL/.test(String(r.status||'').toUpperCase())&&periodMatch(r.due_date,month));return {revenue:round(revenue),paid:round(paid),remaining:round(remaining),advances:round(advances),bookings:round(bookings),expenses:round(expenses),maintenance:round(maintenance),otherIncome:round(otherIncome),unpaidExpenses:round(unpaidExpenses),operatingEstimate:round(revenue+otherIncome-expenses-maintenance),due}}
function uid(prefix){return prefix+'-'+crypto.randomUUID()}
function cleanClient(r){return Object.fromEntries(CLIENT_FIELDS.map(k=>[k,r[k]??'']))}
function openDB(){return new Promise((res,rej)=>{let r=indexedDB.open('gestionpro-mobile-v1',1);r.onupgradeneeded=()=>r.result.createObjectStore('kv');r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error)})}
async function get(key){const db=await openDB();return new Promise((res,rej)=>{const tx=db.transaction('kv','readonly'),r=tx.objectStore('kv').get(key);r.onsuccess=()=>res(r.result);r.onerror=()=>rej(r.error);tx.oncomplete=()=>db.close()})}
async function set(key,value){const db=await openDB();return new Promise((res,rej)=>{const tx=db.transaction('kv','readwrite');tx.objectStore('kv').put(value,key);tx.oncomplete=()=>{db.close();res()};tx.onerror=()=>{db.close();rej(tx.error)}})}
const api={CLIENT_FIELDS,vehicleStatus,isoToday,parseDate,iso,french,num,round,quote,closed,vehicleCode,availability,finance,uid,cleanClient,get,set};global.GP=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
