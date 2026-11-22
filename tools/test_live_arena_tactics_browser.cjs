const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
 const out='docs/tactics-arena-captures';fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1550,height:950},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 try{
  await page.goto('http://127.0.0.1:8765/',{waitUntil:'domcontentloaded',timeout:120000});
  await page.locator('#found-sect').waitFor({timeout:240000});
  await page.locator('#sect-name').fill('전술검증문');
  await page.locator('#found-sect button[type=submit]').click();
  await page.locator('#draft-pass').waitFor({timeout:240000});
  for(let round=1;round<=5;round++){
    await page.locator('#draft-pass').click();
    if(round<5)await page.waitForFunction(n=>document.querySelector('#screen h2')?.textContent?.includes((n+1)+'/5라운드'),round,{timeout:180000});
    else await page.locator('#market-start-season').waitFor({timeout:180000});
  }
  await page.locator('#market-start-season').click();
  await page.locator('[data-tab="warroom"]').waitFor({timeout:180000});
  await page.waitForFunction(()=>state.phase==='ready'&&!busy,null,{timeout:180000});
  await page.locator('#open-arena-tactics').click();
  await page.waitForFunction(()=>Boolean(document.querySelector('iframe'))||
    Boolean(document.querySelector('#error')?.textContent?.trim()),null,{timeout:60000});
  if(!await page.locator('iframe').count()){
    throw Error('Connected arena failed to open: '+await page.locator('#error').innerText());
  }
  const arena=page.frameLocator('iframe');
  await arena.locator('#tactics-save-pane:visible').waitFor({timeout:60000});
  if(await arena.locator('.slot[data-unit]').count()!==8)throw Error('Actual 8 fighters missing');
  const firstId=await arena.locator('.slot[data-unit]').first().getAttribute('data-unit');
  const cashBefore=await page.evaluate(()=>state.cash);
  await arena.locator('[data-art="0"]').selectOption('tiger');
  await arena.locator('#tactics-save-btn').click();
  await page.waitForFunction(async()=>{
    const frame=document.querySelector('iframe')?.contentDocument;
    return frame?.querySelector('#tactics-save-status')?.textContent?.includes('저장했습니다.');
  },null,{timeout:180000});
  const saved=await page.evaluate(async()=>{
    const view=await callEngine('prebattle_arena_view',{mode:'attack'});
    return {arts:view.chosenArts,team:view.team.map(x=>x.id),phase:state.phase};
  });
  if(saved.arts[0]!=='tiger'||!saved.team.includes(Number(firstId))||saved.phase!=='ready')
    throw Error('Arena save not reflected in the actual Python engine: '+JSON.stringify(saved));
  await page.screenshot({path:out+'/live-attack-tactics-saved.png',fullPage:true,animations:'disabled'});
  await arena.locator('#start').click();
  await arena.locator('#battle-skip:visible').waitFor({timeout:60000});
  await arena.locator('#battle-skip').click();
  await arena.locator('#battle-report-overlay:not([hidden])').waitFor({timeout:30000});
  if(await page.evaluate(()=>state.phase)!=='ready')throw Error('Training battle caused campaign phase mutation');
  if(await page.evaluate(()=>state.cash)!==cashBefore)throw Error('Sparring battle charged game cash');
  await arena.locator('#br-close').click();
  await arena.locator('#edit').click();
  await arena.locator('#tactics-return').click();
  await page.locator('#pb-arena').waitFor({timeout:180000});
  await page.locator('#pb-arena').click();
  await arena.locator('#tactics-save-pane:visible').waitFor({timeout:90000});
  if(await arena.locator('[data-art="0"]').inputValue()!=='tiger')
    throw Error('Attack tactics did not restore when reopening arena');
  await arena.locator('#tactics-return').click();
  await page.locator('[data-pb-mode="defense"]').waitFor({timeout:60000});
  await page.locator('[data-pb-mode="defense"]').click();
  await page.locator('#pb-arena').waitFor({timeout:60000});
  if(await page.locator('#pb-arena').isDisabled())throw Error('Owned zone has no defense tactics');
  await page.locator('#pb-arena').click();
  await arena.locator('#tactics-save-pane:visible').waitFor({timeout:90000});
  await arena.locator('[data-art="0"]').selectOption('turtle');
  await arena.locator('#tactics-save-btn').click();
  await page.waitForFunction(()=>{
    const frame=document.querySelector('iframe')?.contentDocument;
    return frame?.querySelector('#tactics-save-status')?.textContent?.includes('저장했습니다.');
  },null,{timeout:90000});
  const after=await page.evaluate(async()=>({
    defense:(await callEngine('prebattle_arena_view',{mode:'defense'})).chosenArts,
    attack:(await callEngine('prebattle_arena_view',{mode:'attack'})).chosenArts,
    phase:state.phase,cash:state.cash
  }));
  if(after.attack[0]!=='tiger'||after.defense[0]!=='turtle'||after.phase!=='ready'||after.cash!==cashBefore)
    throw Error('Attack / defense profiles did not persist independently: '+JSON.stringify(after));
  await page.screenshot({path:out+'/live-defense-tactics-saved.png',fullPage:true,animations:'disabled'});
  if(errors.length)throw Error('Uncaught browser errors: '+errors.join('; '));
  fs.writeFileSync(out+'/result.json',JSON.stringify({firstId,cashBefore,saved,after,errors},null,2));
  console.log('LIVE ARENA TACTICS SAVE/RELOAD PASS',JSON.stringify({saved,after}));
 }catch(error){
   console.error('LIVE ARENA TACTICS FAIL '+error.stack);
   await page.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});
   fs.writeFileSync(out+'/result.json',JSON.stringify({error:error.message,errors},null,2));
   process.exitCode=1;
 }finally{await browser.close();}
})();