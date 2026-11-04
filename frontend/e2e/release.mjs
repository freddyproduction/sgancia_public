import {chromium} from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import assert from 'node:assert/strict';
import fs from 'node:fs';
const base='http://localhost:18088';
const output=new URL('../../.local/release-qa/',import.meta.url);fs.mkdirSync(output,{recursive:true});
const browser=await chromium.launch({...(process.env.CI?{}:{channel:'chrome'}),headless:true});
const context=await browser.newContext({viewport:{width:390,height:844}});const page=await context.newPage();
page.setDefaultTimeout(20000);
const errors=[];page.on('pageerror',e=>errors.push(e.message));
async function audit(name){const result=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();assert.deepEqual(result.violations.map(x=>({id:x.id,targets:x.nodes.map(n=>n.target)})),[],name);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),name+' overflow');}
async function login(){await page.goto(base);await page.getByLabel('Proponi il salvataggio nel gestore password del browser').uncheck();await page.getByLabel('Chiave di accesso',{exact:true}).fill('qa-installation-gate');await page.getByRole('button',{name:'Continua',exact:true}).click();await page.getByLabel('Email',{exact:true}).fill('qa@example.org');await page.getByLabel('Password',{exact:true}).fill('qa-password-long');await page.getByRole('button',{name:'Accedi',exact:true}).click();await page.getByRole('heading',{name:/Ciao,/}).waitFor();}
try{
 if(!process.env.QA_RESTART_ONLY){
 await page.goto(base+'/help');await page.getByRole('heading',{name:'Guida e informazioni',exact:true}).waitFor();await page.getByLabel('Cerca nella guida').fill('valute');await page.getByText('Valute e conversione',{exact:true}).click();await audit('guida-mobile');assert.equal(await page.getByRole('link',{name:/Offri un caffè/}).count(),0);await page.getByLabel('La tua idea').fill('Un esempio sintetico per la guida.');await page.getByText('Anteprima da copiare',{exact:true}).click();await page.getByText('Comportamento desiderato:',{exact:false}).last().waitFor();await page.screenshot({path:new URL('guida-mobile.png',output).pathname,fullPage:true});
 }
 await login();
 if(!process.env.QA_RESTART_ONLY){
  await page.setViewportSize({width:1280,height:900});
  await page.getByRole('button',{name:'Impostazioni',exact:true}).first().click();
  let protectedRequests=0;
  await page.route('**/api/v1/auth/totp/setup',async route=>{protectedRequests++;await route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({detail:'Conferma nuovamente la tua identità'})})});
  await page.getByRole('button',{name:'Configura MFA',exact:true}).click();
  const identity=page.getByRole('dialog',{name:'Conferma la tua identità',exact:true});await identity.waitFor();
  await page.setViewportSize({width:390,height:844});await audit('identity-mobile');
  await identity.getByLabel('Password account',{exact:true}).fill('invalid-password-long');await identity.getByRole('button',{name:'Conferma identità',exact:true}).click();await identity.getByText('Verifica identità fallita',{exact:true}).waitFor();
  await identity.getByLabel('Password account',{exact:true}).fill('qa-password-long');await identity.getByRole('button',{name:'Conferma identità',exact:true}).click();
  await page.getByRole('dialog',{name:'Identità confermata',exact:true}).waitFor();assert.equal(protectedRequests,1);
  await page.getByRole('button',{name:'Torna all’operazione',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});await page.unroute('**/api/v1/auth/totp/setup');
  const global=page.locator('.registration-admin');await global.getByLabel('Email destinatario invito',{exact:true}).fill('invited-qa@example.org');await global.getByLabel('Durata nuovo invito (giorni)',{exact:true}).fill('2');await global.getByRole('button',{name:'Crea invito globale',exact:true}).click();
  const link=global.locator('a.secret-code');await link.waitFor();const oldUrl=await link.getAttribute('href');
  await global.getByRole('button',{name:'Rinnova durata',exact:true}).click();let modal=page.getByRole('dialog',{name:'Rinnova invito',exact:true});await modal.getByLabel('Durata da adesso (giorni)',{exact:true}).fill('3');await modal.getByRole('button',{name:'Conferma rinnovo',exact:true}).click();await modal.waitFor({state:'hidden'});
  await global.getByRole('button',{name:'Rigenera codice',exact:true}).click();modal=page.getByRole('dialog',{name:'Rigenera invito',exact:true});await modal.getByRole('button',{name:'Conferma rigenerazione',exact:true}).click();await modal.waitFor({state:'hidden'});await link.waitFor();const freshUrl=await link.getAttribute('href');assert.notEqual(oldUrl,freshUrl);
  await global.getByLabel('Modalità registrazioni').selectOption('approval');await global.getByRole('button',{name:'Salva modalità registrazioni',exact:true}).click();await global.getByText('Modalità aggiornata. Le richieste già in attesa vanno comunque gestite singolarmente.',{exact:true}).waitFor();
  assert.equal((await(await page.request.get(base+'/api/v1/admin/registration')).json()).registration,'approval');
  let response=await page.request.post(base+'/api/v1/auth/register',{data:{email:'invited-qa@example.org',name:'Invitato QA globale',password:'qa-password-long',invite:new URL(freshUrl).hash.slice(1)}});assert.equal(response.status(),201);assert.equal((await response.json()).status,'pending');
  let applicant=global.locator('.invitation-row').filter({hasText:'Invitato QA globale'});await applicant.getByRole('button',{name:'Approva',exact:true}).click();await page.getByRole('dialog',{name:'Approva registrazione',exact:true}).getByRole('button',{name:'Conferma approvazione',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
  response=await page.request.post(base+'/api/v1/auth/register',{data:{email:'rejected-qa@example.org',name:'Richiesta QA rifiutata',password:'qa-password-long'}});assert.equal(response.status(),201);
  applicant=global.locator('.invitation-row').filter({hasText:'Richiesta QA rifiutata'});await applicant.getByRole('button',{name:'Rifiuta richiesta',exact:true}).click();await page.getByRole('dialog',{name:'Rifiuta registrazione',exact:true}).getByRole('button',{name:'Rifiuta e sospendi',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});
  const moderated=await(await page.request.get(base+'/api/v1/admin/users')).json();assert.equal(moderated.find(u=>u.email==='invited-qa@example.org').status,'active');assert.equal(moderated.find(u=>u.email==='rejected-qa@example.org').status,'suspended');
  await global.getByLabel('Email destinatario invito',{exact:true}).fill('revoke-qa@example.org');await global.getByRole('button',{name:'Crea invito globale',exact:true}).click();await global.getByRole('button',{name:'Rimuovi / revoca',exact:true}).click();await page.getByRole('dialog',{name:'Revoca invito',exact:true}).getByRole('button',{name:'Conferma revoca',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});await global.getByLabel('Stato inviti').selectOption('revoked');await global.getByText('Revocato · Scadenza',{exact:false}).first().waitFor();await audit('global-invitations-mobile');
  console.log('PASS: global invite create/renew/regenerate/revoke, approval/rejection, mobile accessibility');
  await page.setViewportSize({width:1280,height:900});await page.getByRole('button',{name:'Panoramica',exact:true}).first().click();await page.setViewportSize({width:390,height:844});
  console.log('PASS: recent-identity popup, wrong/correct password, mobile accessibility, no automatic operation replay');
 }
 if(process.env.QA_RESTART_ONLY){const list=await(await page.request.get(base+'/api/v1/groups/qa-group/expenses')).json();assert.equal(list.length,1);assert.equal(list[0].title,'Cena QA rilascio');console.log('PASS restart: authenticated expenses persisted');}
 else{
 await page.getByRole('button',{name:'Attiva tema scuro'}).click();await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');await page.getByRole('button',{name:'Apri menu',exact:true}).click();await page.getByRole('button',{name:'Guida e informazioni',exact:true}).last().click();await page.getByRole('heading',{name:'Guida e informazioni',exact:true}).waitFor();await page.getByLabel('Cerca nella guida').fill('Smart');await audit('guida-dark-mobile');
 await page.setViewportSize({width:1280,height:900});await page.getByRole('button',{name:/Prova rilascio/}).first().click();await page.getByRole('heading',{name:'Prova rilascio',exact:true}).waitFor();await page.getByRole('button',{name:'Aggiungi spesa',exact:true}).click();await page.getByLabel('Per cosa avete speso?').fill('Cena QA rilascio');await page.getByLabel('Descrizione voce 1').fill('Cena');await page.getByLabel('Importo voce 1').fill('60');await page.getByRole('button',{name:'Controlla la divisione',exact:true}).click();await page.getByRole('button',{name:'Conferma e salva',exact:true}).click();await page.getByRole('dialog').waitFor({state:'hidden'});await page.getByText('Cena QA rilascio',{exact:true}).waitFor();
 const finance=await(await page.request.get(base+'/api/v1/groups/qa-group/finance')).json();assert.equal(finance.summary.expenses_total,6000);assert.equal(finance.summary.receivable,3000);
 // Concurrent authenticated reads and simulated offline recovery; no writes are replayed by the client.
 const begin=Date.now();const reads=await Promise.all(Array.from({length:30},()=>page.request.get(base+'/api/v1/groups/qa-group/finance')));assert(reads.every(r=>r.status()===200));console.log('30 finance reads ms:',Date.now()-begin);
 await context.setOffline(true);await context.setOffline(false);await page.reload();await page.getByRole('heading',{name:/Ciao,/}).waitFor();
 await page.getByRole('button',{name:'Impostazioni',exact:true}).first().click();await page.getByRole('heading',{name:'Amministrazione e operatività'}).waitFor();await page.getByText('Bot Telegram · configurazione e servizio',{exact:true}).click();assert.equal(await page.getByText('docker compose --profile telegram up -d telegram',{exact:true}).count(),0);await page.getByRole('button',{name:'Salva e applica Telegram',exact:true}).waitFor();
 const p=await(await page.request.get(base+'/api/v1/project')).json();assert.equal(p.developer,'PjChaosEOW');assert.equal(p.version,'0.2.0-dev');assert(p.email===null||/^[^\s@]+@[^\s@]+$/.test(p.email));assert(p.repository_url===null||p.repository_url.startsWith('https://github.com/'));assert(p.donation_url===null||p.donation_url.startsWith('https://buymeacoffee.com/'));console.log('PASS: help light/dark/mobile, login, expense/preview, exact finance, 30 reads, network recovery, global Telegram controls');
 }
 assert.deepEqual(errors,[]);
}catch(error){await page.screenshot({path:new URL('failure.png',output).pathname,fullPage:true}).catch(()=>{});throw error}finally{await browser.close()}
