// Screenshot the actual deployed game through an isolated clean Chromium profile.
// No mocks, fabricated HTML, or user savegame access.
const { chromium } = require('playwright');
const fs = require('fs');
(async()=>{
  const output = 'docs/screenshots';
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({channel:'chrome',headless:true,args:['--no-sandbox']});
  const page = await browser.newPage({viewport:{width:1536,height:1000},deviceScaleFactor:1});
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('console',m=>{if(m.type()==='error')errors.push('console: '+m.text());});
  try {
    console.log('OPEN '+new Date().toISOString());
    await page.goto('https://chddkf1010-beep.github.io/-moonpa-v16-/',{waitUntil:'domcontentloaded',timeout:90000});
    await page.locator('#found-sect').waitFor({timeout:240000});
    console.log('FOUNDING SCREEN');
    await page.locator('#sect-name').fill('청명검문');
    await page.locator('#found-sect button[type=submit]').click();
    await page.locator('#draft-pass').waitFor({timeout:180000});
    for(let round=1;round<=5;round++){
      console.log('DRAFT '+round);
      await page.locator('#draft-pass').click();
      if(round<5) {
        await page.waitForFunction(r=>document.querySelector('#screen h2')?.textContent?.includes((r+1)+'/5라운드'),round,{timeout:180000});
      }else await page.locator('#market-start-season').waitFor({timeout:180000});
    }
    console.log('OPEN SEASON');
    await page.locator('#market-start-season').click();
    await page.locator('[data-tab="league"]').waitFor({timeout:180000});
    await page.locator('[data-tab="league"]').click();
    await page.locator('#world-map .world-map-canvas svg').waitFor({timeout:60000});
    console.log('LEAGUE MAP READY');
    // Capture exact in-game live content, not a reconstruction.
    await page.locator('#world-map').screenshot({path:output+'/live-league-map.png',animations:'disabled'});
    await page.screenshot({path:output+'/live-league-full.png',fullPage:true,animations:'disabled'});
    // Pick an actual attackable 4th-tier site from live atlas.
    const ids=await page.locator('.world-map-node[data-world-zone]').evaluateAll(nodes=>nodes.map(n=>Number(n.getAttribute('data-world-zone'))));
    let selected=null;
    for(const id of ids) {
      await page.locator('.world-map-node[data-world-zone="'+id+'"]').click();
      if(await page.locator('[data-world-attack]').count()) {selected=id;break;}
    }
    if(selected===null)throw Error('No attackable target in live game');
    console.log('ATTACKABLE '+selected);
    await page.locator('#world-map').screenshot({path:output+'/live-selected-target.png',animations:'disabled'});
    await page.locator('[data-world-attack]').click();
    await page.locator('#target-zone').waitFor({timeout:60000});
    const picked=await page.locator('#target-zone').inputValue();
    if(Number(picked)!==selected)throw Error('Selected target differs: '+picked+' vs '+selected);
    await page.screenshot({path:output+'/live-weekly-assignment.png',fullPage:true,animations:'disabled'});
    console.log('WEEKLY TARGET CONNECTED '+picked);
    // Visit the league again after switching; state is never modified.
    await page.locator('[data-tab="league"]').click();
    await page.locator('#world-map').waitFor();
    await page.reload({waitUntil:'domcontentloaded',timeout:90000});
    await page.locator('[data-tab="league"]').waitFor({timeout:240000});
    await page.locator('[data-tab="league"]').click();
    await page.locator('#world-map').waitFor();
    await page.locator('#world-map').screenshot({path:output+'/live-map-after-reload.png',animations:'disabled'});
    console.log('RELOAD MAP READY');
    fs.writeFileSync(output+'/capture-report.json',JSON.stringify({url:page.url(),site:selected,picked,errors},null,2));
    console.log('PAGE ERRORS '+JSON.stringify(errors));
  }catch(e){
    console.error('CAPTURE ERROR '+e.stack);
    await page.screenshot({path:output+'/failure.png',fullPage:true}).catch(()=>{});
    fs.writeFileSync(output+'/capture-report.json',JSON.stringify({error:String(e),errors},null,2));
    process.exitCode=1;
  }finally{await browser.close();}
})();