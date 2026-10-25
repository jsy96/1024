// Optional Mac UI check. Requires Playwright + Chrome and a disposable fixture on port 8001.
const { chromium } = require('playwright');
const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const root = path.resolve(__dirname, '..');
const assets = path.join(root, 'data/competition-build/assets');
const base = 'http://127.0.0.1:8001';

(async () => {
  const browser = await chromium.launch({executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless:true});
  const context = await browser.newContext({viewport:{width:1365,height:960},geolocation:{latitude:30.5938,longitude:114.3065,accuracy:10},permissions:['geolocation']});
  const page = await context.newPage();
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const check = (v,m)=>{if(!v)throw Error(m);};
  const shot = n=>page.screenshot({path:path.join(assets,n+'.png')});
  async function login(phone,password='123456') {
    await page.goto(base);
    if(await page.locator('#app-view').isVisible())await page.locator('#btn-logout').click();
    await page.locator('#login-phone').fill(phone);await page.locator('#login-pwd').fill(password);
    await page.locator('#login-form button').click();await page.locator('#order-list').waitFor();
  }
  async function tab(name,selector) {await page.locator(`[data-tab="${name}"]`).click();await page.locator(selector).waitFor();}
  await login('13900000000','community123');
  await shot('community-orders');
  await tab('contracts','#new-contract');await shot('community-contracts');
  await page.locator('#new-contract').click();await page.locator('#contract-form').waitFor();await page.locator('#modal-close').click();
  await tab('people','#new-person');await page.locator('[data-person]').first().click();await page.locator('#person-form').waitFor();await page.locator('#modal-close').click();
  await tab('ledger','#credit-form');await shot('community-ledger');
  await tab('settle','#settle-form');await page.locator('[data-batch]').first().click();await page.locator('.modal').waitFor();await page.locator('#modal-close').click();
  const downloadPromise=page.waitForEvent('download');await page.locator('[data-export]').first().click();const download=await downloadPromise;
  check(download.suggestedFilename().endsWith('.csv'),'CSV UI download');
  await login('13800002001');await tab('book','#booking-form');
  check(await page.locator('#company-select option').count()===2,'two contracted companies');
  await page.locator('#company-select').selectOption({label:'康乐养老'});
  check(await page.locator('#worker-select').innerText()==='赵春梅','company worker filter');
  await page.locator('#company-select').selectOption({label:'安心养老'});await shot('customer-book');
  await tab('orders','#order-list');await page.locator('[data-order="1"][data-act="details"]').click();
  await page.locator('#proof-photo').waitFor();await page.waitForFunction(()=>document.querySelector('#proof-photo')?.naturalWidth>0);await shot('order-proof');await page.locator('#modal-close').click();
  await tab('ledger','.tbl');check((await page.locator('main').innerText()).includes('720.00'),'customer running balance');
  await tab('book','#booking-form');
  const tomorrow=new Date();tomorrow.setDate(tomorrow.getDate()+1);
  const date=tomorrow.toLocaleDateString('sv-SE');
  await page.locator('#f-sched_start').fill(date+'T10:00');
  await page.locator('#f-duration_minutes').fill('60');await page.locator('#booking-form button[type=submit]').click();await page.locator('#order-list').waitFor();
  const newId=await page.evaluate(async()=>Math.max(...(await API.call('/orders')).orders.map(x=>x.id)));
  check(newId>3,'UI booking persisted');
  await login('13800001001');await page.locator(`[data-order="${newId}"][data-act="confirm"]`).click();await page.locator(`[data-order="${newId}"][data-act="checkin"]`).waitFor();
  execFileSync(path.join(root,'.venv-mac/bin/python'),['-c',
    "import sqlite3,sys;from datetime import datetime,timedelta;c=sqlite3.connect(sys.argv[1]);n=datetime.now();c.execute('UPDATE orders SET sched_start=?,sched_end=? WHERE id=?',(n.strftime('%Y-%m-%d %H:%M'),(n+timedelta(hours=1)).strftime('%Y-%m-%d %H:%M'),int(sys.argv[2])));c.commit()",
    path.join(root,'data/competition-build/browser-demo.db'),String(newId)]);
  await page.reload();await page.locator(`[data-order="${newId}"][data-act="checkin"]`).click();
  await page.locator('#f-address').fill('江岸区中山大道100号（浏览器测试）');await page.locator('#locate').click();
  await page.locator('#submit-checkin:not([disabled])').waitFor();await shot('worker-checkin');await page.locator('#submit-checkin').click();
  await page.locator(`[data-order="${newId}"][data-act="complete"]`).click();
  await page.locator('#photo-input').setInputFiles(path.join(assets,'演示合影占位.png'));await page.locator('[name=consent]').check();await page.locator('#f-note').fill('浏览器自动核验：模拟位置与占位图，无真实履约');
  await shot('worker-photo');await page.locator('#complete-form button[type=submit]').click();
  await page.waitForFunction(id=>[...document.querySelectorAll('[data-order]')].filter(e=>e.dataset.order===String(id)).length===1,newId);
  await tab('batches','main h1');
  await login('13900000001','admin123');await tab('manage','#new-worker');await page.locator('#new-item').click();await page.locator('#item-form').waitFor();await page.locator('#modal-close').click();
  await tab('settle','#settle-form');await page.locator('#settle-form button').click();await page.locator('#create-batch-form').waitFor();await shot('company-settle');
  await page.locator('#f-reference').fill('BROWSER-TEST-ONLY');await page.locator('#create-batch-form button').click();
  await page.waitForFunction(()=>document.querySelector('main').textContent.includes('BROWSER-TEST-ONLY'));
  await page.setViewportSize({width:390,height:844});await tab('orders','#order-list');
  check(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'mobile page overflow');await shot('mobile-orders');
  check(errors.length===0,errors.join('\n'));
  fs.writeFileSync(path.join(root,'data/competition-build/browser-check.json'),JSON.stringify({ok:true,roles:4,booking:newId,checkin:true,photo:true,settlement:true,csv:true,mobile:true,errors},null,2));
  console.log('四端页面、跨公司筛选、预约、模拟定位打卡、照片上传、结算、CSV和手机布局均通过。');
  await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
