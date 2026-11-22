// Play the real browser game to an 8v8 conquest and verify reserve substitution.
// Uses only a fresh local browser profile. No user's existing save is touched.
const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const out='docs/bench-captures';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1550,height:900},deviceScaleFactor:1});
 const errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 try {
  await page.goto('http://127.0.0.1:8765/',{waitUntil:'domcontentloaded',timeout:120000});
  await page.locator('#found-sect').waitFor({timeout:240000});
  await page.locator('#sect-name').fill('청풍신검문');
  await page.locator('#found-sect button[type=submit]').click();
  await page.locator('#draft-pass').waitFor({timeout:240000});
  for(let round=1;round<=5;round++){
   await page.locator('#draft-pass').click();
   if(round<5) await page.waitForFunction(n=>document.querySelector('#screen h2')?.textContent?.includes((n+1)+'/5라운드'),round,{timeout:180000});
   else await page.locator('#market-start-season').waitFor({timeout:180000});
  }
  await page.locator('#market-start-season').click();
  await page.locator('[data-tab="week"]').waitFor({timeout:180000});
  await page.locator('[data-tab="week"]').click();
  const target=await page.locator('#target-zone option').evaluateAll(options=>options.map(o=>o.value).find(v=>v!==''));
  if(!target)throw Error('No capturable territory');
  await page.locator('#target-zone').selectOption(target);
  const candidates=page.locator('select.assignment:not(:disabled)');
  if(await candidates.count()<8)throw Error('Insufficient candidates');
  for(let index=0;index<8;index++)await candidates.nth(index).selectOption('attack');
  await page.locator('#top-week').click();
  await page.locator('#group-direct').waitFor({timeout:180000});
  await page.locator('#group-direct').click();
  await page.locator('iframe').waitFor({timeout:90000});
  const arena=page.frameLocator('iframe');
  await arena.locator('.arena-bench').waitFor({timeout:90000});
  const startId=await arena.locator('.slot[data-unit]').first().getAttribute('data-unit');
  const benchId=await arena.locator('.arena-bench [data-dual-to="attack"]').first().getAttribute('data-dual-move');
  if(!startId||!benchId)throw Error('Real live battle missing bench or starter');
  await arena.locator('[data-dual-move="'+startId+'"][data-dual-to="defense"]').click();
  await arena.locator('.arena-defense-member').first().waitFor({timeout:30000});
  if(await arena.locator('.slot[data-unit="'+startId+'"]').count())throw Error('Transferred fighter remains in attack slots');
  await arena.locator('[data-dual-move="'+benchId+'"][data-dual-to="attack"]').click();
  await arena.locator('.slot[data-unit="'+benchId+'"]').waitFor({timeout:30000});
  await arena.locator('[data-squad-save]').click();
  await arena.locator('#deployment-status').getByText('저장 데이터에 반영').waitFor({timeout:180000}).catch(async()=>{
    const note=await arena.locator('#deployment-status').innerText();
    if(!note.includes('저장 데이터에 반영'))throw Error('Monthly formation save failed: '+note);
  });
  const saved=await page.evaluate(()=>({
    attack:state.group_play.team.map(f=>f.id),defense:state.group_play.defenseTeam.map(f=>f.id)
  }));
  if(!saved.attack.includes(Number(benchId))||saved.attack.includes(Number(startId))||
      !saved.defense.includes(Number(startId)))throw Error('Server did not save defense transfer: '+JSON.stringify(saved));
  await arena.locator('.slot[data-unit="'+benchId+'"]').waitFor({timeout:30000});
  if(await arena.locator('.slot[data-unit="'+startId+'"]').count())throw Error('Outgoing fighter still deployed');
  await arena.locator('.slot[data-unit="'+benchId+'"]').click();
  await arena.locator('#fighter-stats-dialog[open]').waitFor({timeout:10000});
  const text=await arena.locator('#fighter-stats-content').innerText();
  for(const word of ['현재 전력','잠재력','근력','방어','내공']) {
    if(!text.includes(word))throw Error('Missing fighter detail: '+word);
  }
  await page.screenshot({path:out+'/live-8v8-bench-and-stats.png',fullPage:true,animations:'disabled'});
  await arena.locator('#fighter-stats-close').click();
  await page.screenshot({path:out+'/live-8v8-bench-formation.png',fullPage:true,animations:'disabled'});
  // Start an actual conquest with the saved attacker/defender split and skip
  // its battle playback without inventing any result.
  const originalMatch=await page.evaluate(()=>state.group_play.match);
  await arena.locator('#start').click();
  await arena.locator('#battle-skip:visible').waitFor({timeout:30000});
  await arena.locator('#battle-skip').click();
  await arena.locator('#battle-report-overlay:not([hidden])').waitFor({timeout:30000});
  const battleSummary=await arena.locator('#br-content').innerText();
  if(!battleSummary.includes('전투') && !battleSummary.includes('기여'))throw Error('Skip did not produce real report');
  await page.screenshot({path:out+'/live-8v8-skip-result.png',fullPage:true,animations:'disabled'});
  await arena.locator('#br-confirm').click();
  await page.waitForFunction(match=>state.phase==='report'||state.group_play?.match!==match,originalMatch,{timeout:180000});
  fs.writeFileSync(out+'/result.json',JSON.stringify({target,starter:startId,substitute:benchId,defenseAssigned:true,memberDetail:true,skipCompleted:true,errors},null,2));
  if(errors.length)throw Error('Page errors: '+errors.join('; '));
  console.log('LIVE 8v8 DUAL DEPLOYMENT PLAY PASS',JSON.stringify({target,startId,benchId}));
 }catch(e){
  console.error('LIVE 8v8 BENCH PLAY FAIL '+e.stack);
  await page.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});
  fs.writeFileSync(out+'/result.json',JSON.stringify({error:e.message,errors},null,2));
  process.exitCode=1;
 }finally {await browser.close();}
})();