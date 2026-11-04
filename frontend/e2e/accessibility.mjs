import {chromium} from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import assert from 'node:assert/strict';
const target=process.env.SGANCIA_A11Y_URL;
if(!target||new URL(target).port!=='18088'||!['localhost','127.0.0.1'].includes(new URL(target).hostname))throw Error('Use the disposable QA instance on loopback port 18088, never real installation data');
const output=new URL('../../.local/accessibility-qa/',import.meta.url);fs.mkdirSync(output,{recursive:true});

const browser=await chromium.launch({channel:'chrome',headless:true});
const context=await browser.newContext({viewport:{width:1280,height:900}});const page=await context.newPage();const results=[];
async function audit(name){await page.waitForTimeout(150);const r=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','best-practice']).analyze();const overflow=await page.evaluate(()=>({width:innerWidth,scroll:document.documentElement.scrollWidth}));results.push({name,overflow,violations:r.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary})).slice(0,12)}))});fs.writeFileSync(new URL('audit.json',output),JSON.stringify(results,null,2));console.log(name,JSON.stringify({overflow,issues:results.at(-1).violations.map(v=>[v.id,v.nodes.length])}));}
try{
 await page.goto(target);await audit('gate');await page.getByLabel('Chiave di accesso',{exact:true}).fill('qa-installation-gate');await page.getByRole('button',{name:'Continua',exact:true}).click();await page.getByLabel('Email',{exact:true}).fill('qa@example.org');await page.getByLabel('Password',{exact:true}).fill('qa-password-long');await page.getByRole('button',{name:'Accedi',exact:true}).click();await page.getByRole('heading',{name:/Ciao,/}).waitFor();if(await page.getByRole('button',{name:'Tema chiaro',exact:true}).isVisible()){await page.getByRole('button',{name:'Tema chiaro',exact:true}).click();await page.waitForFunction(()=>document.documentElement.dataset.theme==='light')}await audit('home-light');
 await page.getByRole('button',{name:'✳ Prova blocco 07',exact:true}).first().click();await page.getByRole('button',{name:'Aggiungi spesa',exact:true}).waitFor();await audit('group-light');
 await page.getByRole('button',{name:'Aggiungi spesa',exact:true}).click();await audit('expense-light');
 const d=page.getByRole('dialog');await d.getByRole('button',{name:'Chiudi',exact:true}).click();
 await page.getByRole('button',{name:'Impostazioni gruppo',exact:true}).click();await audit('group-settings-light');await page.getByRole('button',{name:'Torna alle spese',exact:true}).click();
 for(const width of [320,390,768]){await page.setViewportSize({width,height:844});await audit('group-'+width);await page.getByRole('button',{name:'Aggiungi spesa',exact:true}).click();await audit('expense-'+width);await page.getByRole('dialog').getByRole('button',{name:'Chiudi',exact:true}).click();}
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Attiva tema scuro'}).click();await page.waitForFunction(()=>document.documentElement.dataset.theme==='dark');await audit('group-dark');await page.getByRole('button',{name:'Aggiungi spesa',exact:true}).click();await audit('expense-dark');await page.getByRole('dialog').getByRole('button',{name:'Chiudi',exact:true}).click();

 await page.setViewportSize({width:1280,height:900});await page.getByRole('button',{name:'Ricerca, statistiche e conti',exact:true}).click();await audit('insights-dark');await page.getByRole('button',{name:'Budget',exact:true}).click();await audit('budgets-dark');await page.getByRole('dialog').getByRole('button',{name:'Chiudi',exact:true}).click();
 await page.getByRole('button',{name:'Importa / esporta',exact:true}).click();await audit('exchange-dark');await page.getByRole('dialog').getByRole('button',{name:'Chiudi',exact:true}).click();
 await page.getByRole('button',{name:'Modelli, ricorrenze e anticipi',exact:true}).click();await audit('tools-dark');
 await page.getByRole('button',{name:'Crea modello o ricorrenza',exact:true}).click();await audit('nested-editor-dark');
 if(await page.locator('dialog[open]').count()!==2)throw Error('Expected nested native dialogs');
 for(let i=0;i<35;i++){await page.keyboard.press('Tab');if(await page.evaluate(()=>document.querySelector('main')?.contains(document.activeElement)))throw Error('Focus escaped to background')}
 await page.keyboard.press('Escape');if(await page.locator('dialog[open]').count()!==1)throw Error('Escape closed parent dialog');
 if(!await page.getByRole('button',{name:'Crea modello o ricorrenza',exact:true}).evaluate(e=>e===document.activeElement))throw Error('Focus not restored to opener');

 await page.getByRole('dialog').getByRole('button',{name:'Chiudi',exact:true}).click();
 await page.getByRole('button',{name:'Impostazioni',exact:true}).click();await audit('account-dark');await page.getByRole('tab',{name:'Notifiche',exact:true}).click();await audit('notifications-dark');await page.getByRole('tab',{name:'Sicurezza',exact:true}).click();for(const el of await page.locator('[role=tabpanel]:not([hidden]) details>summary').all()){await el.click()}await audit('account-expanded-dark');
 await page.evaluate(()=>{document.documentElement.style.fontSize='32px'});await page.setViewportSize({width:1280,height:900});await audit('account-text-200');
 await page.evaluate(()=>{document.documentElement.style.fontSize='16px'});
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'Apri menu',exact:true}).click();await page.getByRole('button',{name:'Panoramica e gruppi',exact:true}).click();await page.getByRole('heading',{name:'I tuoi gruppi 1'}).waitFor();await page.getByRole('button',{name:/In corso Prova blocco 07/}).click();await page.getByRole('button',{name:'Aggiungi spesa',exact:true}).waitFor();
 await page.getByRole('button',{name:'Aggiungi spesa',exact:true}).focus();await page.keyboard.press('Enter');await page.getByRole('dialog').waitFor();await page.evaluate(()=>{document.documentElement.style.fontSize='32px'});await audit('expense-mobile-text-200');await page.evaluate(()=>{document.documentElement.style.fontSize='16px'});await page.screenshot({path:fileURLToPath(new URL('sgancia-accessibilita-mobile.png',output))});
 await page.keyboard.press('Escape');assert.equal(await page.getByRole('button',{name:'Aggiungi spesa',exact:true}).evaluate(e=>e===document.activeElement),true);
 assert.equal(results.reduce((sum,r)=>sum+r.violations.length,0),0,'Accessibility violations');assert.equal(results.some(r=>r.overflow.scroll>r.overflow.width+1),false,'Horizontal page overflow');console.log('PASS',results.length,'audited views and keyboard regressions');


}finally{fs.writeFileSync(new URL('audit.json',output),JSON.stringify(results,null,2));await browser.close();}
