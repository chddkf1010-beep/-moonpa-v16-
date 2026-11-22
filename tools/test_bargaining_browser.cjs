const {chromium}=require('playwright');
const fs=require('fs');
(async()=>{
  const out='docs/negotiation-captures';
  fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1450,height:950},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',err=>errors.push(err.message));
  try{
    await page.goto('http://127.0.0.1:8765/',{waitUntil:'domcontentloaded',timeout:120000});
    await page.locator('#found-sect').waitFor({timeout:240000});
    await page.locator('#sect-name').fill('협상검문');
    await page.locator('#found-sect button[type=submit]').click();
    await page.locator('#draft-pass').waitFor({timeout:240000});
    for(let round=1;round<=5;round++){
      await page.locator('#draft-pass').click();
      if(round<5)await page.waitForFunction(n=>document.querySelector('#screen h2')?.textContent?.includes((n+1)+'/5라운드'),round,{timeout:180000});
      else await page.locator('#market-start-season').waitFor({timeout:180000});
    }
    await page.locator('#market-start-season').click();
    await page.locator('[data-tab="scout"]').waitFor({timeout:180000});
    await page.locator('[data-tab="scout"]').click();
    await page.locator('[data-negotiate]').first().waitFor({timeout:45000});
    const seller=await page.locator('#seller option').evaluateAll(options=>
      options.find(o=>o.textContent.includes('4부')&&o.value)?.value);
    if(seller)await page.locator('#seller').selectOption(seller);
    let counter=null;
    const maximum=Math.min(25,await page.locator('[data-negotiate]').count());
    const startingCash=await page.evaluate(()=>state.cash);
    for(let i=0;i<maximum;i++){
      const candidate=page.locator('[data-negotiate]').nth(i);
      const fid=Number(await candidate.getAttribute('data-negotiate'));
      await candidate.click();
      const box=page.locator('#offer[open]');
      await box.locator('#talk-propose').waitFor({timeout:45000});
      await box.locator('#talk-fee').fill('0');
      await box.locator('#talk-propose').click();
      await page.waitForFunction(()=>document.querySelector('#offer #talk-round')?.textContent?.includes('1/4회 제안'),null,{timeout:90000});
      const reply=await box.locator('.trade-response-status').innerText();
      if(reply.includes('역제안')) {counter={fid,index:i};break;}
      await box.locator('.trade-heading button').click();
    }
    if(!counter)throw Error('Could not find affordable seller counteroffer in first '+maximum+' local candidates');
    const box=page.locator('#offer[open]');
    if(!await box.locator('.trade-request').count())throw Error('Counteroffer missing actual terms');
    if(!await box.locator('.trade-chat-rival').count())throw Error('Missing conversation transcript');
    const demand=await box.locator('.trade-request').innerText();
    const before=await page.evaluate(()=>state.cash);
    if(before!==startingCash)throw Error('Cash moved before accepting trade');
    await page.screenshot({path:out+'/real-seller-counteroffer.png',fullPage:true,animations:'disabled'});
    const req=box.locator('button').filter({hasText:'역제안 수락 · 거래 확정'});
    await req.click();
    await page.waitForFunction(fid=>state.roster.some(row=>row.id===fid),counter.fid,{timeout:90000});
    const after=await page.evaluate(()=>({cash:state.cash,roster:state.roster.length}));
    if(after.cash>before)throw Error('Buyer cash increased after signing');
    if(errors.length)throw Error('Browser JS errors: '+errors.join('; '));
    fs.writeFileSync(out+'/report.json',JSON.stringify({counter,startingCash,before,after,demand,errors},null,2));
    console.log('BARGAINING LIVE PLAY PASS '+JSON.stringify({counter,after,demand}));
  }catch(error){
    console.error('BARGAINING LIVE PLAY FAIL '+error.stack);
    await page.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});
    fs.writeFileSync(out+'/report.json',JSON.stringify({error:error.message,errors},null,2));
    process.exitCode=1;
  }finally{await browser.close();}
})();