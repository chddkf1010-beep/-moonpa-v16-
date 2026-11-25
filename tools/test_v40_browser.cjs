const {chromium} = require('playwright');
const fs = require('fs');
(async()=>{
  const out='docs/v40-browser-captures';
  fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1512,height:950},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  try{
    await page.goto('http://127.0.0.1:8765/',{waitUntil:'domcontentloaded',timeout:120000});
    await page.locator('#found-sect').waitFor({timeout:240000});
    await page.locator('#sect-name').fill('청명금문');
    await page.locator('#found-sect button[type=submit]').click();
    await page.locator('#draft-pass').waitFor({timeout:240000});
    for(let i=1;i<=5;i++){
      await page.locator('#draft-pass').click();
      if(i<5)await page.waitForFunction(round=>document.querySelector('#screen h2')?.textContent?.includes((round+1)+'/5라운드'),i,{timeout:180000});
      else await page.locator('#market-start-season').waitFor({timeout:180000});
    }
    await page.locator('#market-start-season').click();
    await page.locator('.campaign-main-nav [data-tab="roster"]').waitFor({timeout:180000});
    await page.locator('.campaign-main-nav [data-tab="roster"]').click();
    const board=page.locator('#roster-board');
    await board.waitFor({timeout:30000});
    const firstName=(await page.locator('.roster-rich-table tbody [data-roster-detail]').first().textContent()).trim();
    const count=await page.locator('.roster-rich-row').count();
    if(count<8)throw Error('Expected >=8 real founder fighters, found '+count);
    await page.screenshot({path:out+'/actual-roster.png',fullPage:true,animations:'disabled'});
    await page.locator('[data-roster-query]').fill(firstName);
    const matched=await page.locator('.roster-rich-row').count();
    if(matched!==1)throw Error('Name filter found '+matched+' rows for '+firstName);
    await page.locator('[data-roster-density="compact"]').click();
    if(!await page.locator('.roster-rich-table.compact').count())throw Error('Compact mode failed');
    await page.screenshot({path:out+'/actual-roster-filtered.png',fullPage:true,animations:'disabled'});
    await page.locator('.campaign-main-nav [data-tab="ledger"]').click();
    await page.locator('.finance-dashboard').waitFor({timeout:45000});
    if(!await page.getByText('이번 달 기본 예상 수지').count())throw Error('Initial monthly forecast not rendered');
    await page.screenshot({path:out+'/actual-monthly-finance-preview.png',fullPage:true,animations:'disabled'});
    await page.locator('[data-tab="journal"]').click();
    await page.getByRole('heading',{name:'누적 재정 장부',exact:true}).waitFor();
    if(!await page.getByText('장부 차이 0냥').count()&&!await page.getByText('장부 차이 +0냥').count())throw Error('Initial journal mismatch');
    await page.locator('.campaign-main-nav [data-tab="roster"]').click();
    await page.locator('[data-tab="growth"]').click();
    await page.getByRole('heading',{name:'전체 문파원 육성 현황'}).waitFor();
    if(await page.locator('[data-cultivate]').count()!==count)throw Error('Cultivation roster mismatch');
    await page.locator('[data-cultivate]').first().click();
    await page.getByRole('heading',{name:'개인 성장 기록'}).waitFor();
    await page.locator('.campaign-main-nav [data-tab="free"]').click();
    await page.locator('[data-tab="incoming"]').click();
    await page.locator('#incoming-member').waitFor();
    await page.locator('#incoming-member').selectOption({index:1});
    await page.locator('#incoming-price').fill('300');
    await page.locator('#incoming-list').click();
    await page.locator('[data-withdraw]').waitFor({timeout:60000});
    await page.reload({waitUntil:'domcontentloaded'});
    await page.locator('.campaign-main-nav [data-tab="free"]').waitFor({timeout:240000});
    await page.locator('.campaign-main-nav [data-tab="free"]').click();
    await page.locator('[data-tab="incoming"]').click();
    await page.locator('[data-withdraw]').waitFor({timeout:60000});
    await page.screenshot({path:out+'/incoming-restored.png',fullPage:true});
    await page.locator('[data-withdraw]').first().click();
    await page.locator('[data-withdraw]').waitFor({state:'detached',timeout:60000});
    await page.locator('.campaign-main-nav [data-tab="office"]').click();
    await page.locator('[data-tab="facility"]').click();
    await page.getByText('4주 고정비',{exact:false}).first().waitFor();
    await page.locator('.campaign-main-nav [data-tab="league"]').click();
    await page.getByRole('heading',{name:'시즌 무투대회'}).waitFor();
    await page.locator('.campaign-main-nav [data-tab="office"]').click();
    // Run a real four-week month with default roster allocation. Continue only
    // if the engine settles; do not fake a report or chart.
    await page.locator('[data-tab="week"]').click();
    await page.locator('#top-week').click();
    const report=await page.waitForFunction(()=>document.querySelector('#phase')?.textContent==='문파 운영' &&
      document.querySelector('.weekly-brief')?.textContent.includes('월간 보고'),null,{timeout:150000}).then(()=>true).catch(()=>false);
    if(!report)throw Error('Real monthly settlement did not complete');
    if(report){
      await page.locator('.campaign-main-nav [data-tab="ledger"]').click();
      await page.locator('.finance-dashboard').waitFor();
      if(!await page.getByText('실제 결산').count())throw Error('Expected actual monthly report');
      await page.screenshot({path:out+'/actual-monthly-finance-settlement.png',fullPage:true,animations:'disabled'});
    }
    await page.locator('[data-tab="journal"]').click();
    await page.getByRole('heading',{name:'누적 재정 장부',exact:true}).waitFor();
    if(await page.locator('#journal-rows tr').count()<2)throw Error('Journal transactions missing');
    if(await page.locator('#save-status').getAttribute('data-problem')==='true')throw Error('Autosave failed');
    await page.screenshot({path:out+'/journal-settled.png',fullPage:true});
    if(errors.length)throw Error('Browser page errors: '+errors.join('; '));
    fs.writeFileSync(out+'/report.json',JSON.stringify({firstName,founderCount:count,nameFilterMatches:matched,compactMode:true,monthlySettled:report,errors},null,2));
    console.log('Browser UI smoke: PASS; founderCount='+count+'; monthlySettled='+report);
  }catch(error){
    console.error('Browser UI smoke: '+error.stack);
    await page.screenshot({path:out+'/failure.png',fullPage:true}).catch(()=>{});
    fs.writeFileSync(out+'/report.json',JSON.stringify({error:error.message,errors},null,2));
    process.exitCode=1;
  }finally{await browser.close();}
})();