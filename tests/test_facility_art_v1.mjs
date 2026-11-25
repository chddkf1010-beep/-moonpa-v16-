/** Facility illustration regression; visual assets are display-only. */
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
import {join,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=join(dirname(fileURLToPath(import.meta.url)),'..');
const script=readFileSync(join(root,'management.js'),'utf8');
const begin=script.indexOf('/* Visual stages are intentionally');
const end=script.indexOf('const rosterSorts=',begin);
assert.ok(begin>=0&&end>begin,'facility visual implementation is present');
const code=script.slice(begin,end);
const stylesheet=readFileSync(join(root,'style.css'),'utf8');
const art=readFileSync(join(root,'assets/facilities/facility_growth_v1.webp'));

function sample(id,level){
 const names={training:'훈련소',estate:'장원',medical:'의료시설'};
 const values={training:[0,12,26,42,60,80],estate:[0,35,80,140,215,305],medical:[0,1,2,3,4,5]};
 const next=Math.min(5,level+1),upkeep=[0,0,0,8,20,40];
 const current_value=values[id][level],next_value=values[id][next];
 const costs={training:[240,480,720,1440,1800],estate:[320,640,960,1920,2400],medical:[200,400,600,1200,1500]};
 return {id,name:names[id],level,max:5,current_value,next_value,
  current_discount:level*5,next_discount:Math.min(5,level+1)*5,
  current_upkeep:upkeep[level],next_upkeep:upkeep[next],next_cost:costs[id][level]??null};
}
function makeContext(facilities,cash=2000){
 const panel={innerHTML:'',querySelectorAll:()=>[]};
 const rows=facilities.map(f=>{
   const reserve=4*(100+f.next_upkeep-f.current_upkeep);
   const shortfall=f.next_cost==null?0:Math.max(0,reserve-(cash-f.next_cost));
   return {...f,operational:true,reserve_after:reserve,cash_after:cash-(f.next_cost??0),shortfall,
     can_upgrade:f.next_cost!=null&&!shortfall};
 });
 const context={state:{facilities:rows,cash,phase:'ready'},panel:()=>panel,
   escapeText:text=>String(text).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
   money:n=>`${n}냥`,confirm:()=>true,request:()=>{}};
 runInNewContext(code,context);
 return {context,panel};
}

test('15 real images are committed in a 5 x 3 atlas',()=>{
 assert.ok(art.length>25000,'binary artwork should not be a placeholder');
 assert.equal(art.toString('ascii',0,4),'RIFF');
 assert.equal(art.toString('ascii',8,12),'WEBP');
 assert.equal(art.readUInt32LE(4)+8,art.length);
 assert.match(stylesheet,/background-size:\s*500%\s+300%/);
 assert.match(stylesheet,/facility_growth_v1[.]webp/);
});

test('level 0 is an unbuilt plot, 1 through 5 are distinct images for all three buildings',()=>{
 for(const [row,id] of ['training','estate','medical'].entries()){
  for(let level=0;level<=5;level++){
   const f=sample(id,level);const {context}=makeContext([f]);
   const artHtml=context.facilityStageArt(f,level);
   if(level===0){
    assert.match(artHtml,/facility-art-empty/);assert.doesNotMatch(artHtml,/facility-art-sprite/);
   }else{
    assert.match(artHtml,/facility-art-sprite/);
    assert.match(artHtml,new RegExp(`background-position:${(level-1)*25}% ${row*50}%`));
   }
  }
 }
});

test('current vs next preview, upgrade cost, and maximum level remain consistent',()=>{
 const training=sample('training',0),estate=sample('estate',1),medical=sample('medical',5);
 const {context,panel}=makeContext([training,estate,medical],300);
 context.showFacilities();
 const output=panel.innerHTML;
 assert.match(output,/data-facility="training"/);
 assert.match(output,/data-facility="estate"/);
 assert.match(output,/data-facility="medical"/);
 assert.match(output,/현재 효과/);assert.match(output,/승급 후 효과/);
 assert.match(output,/data-upgrade="training"/);
 assert.match(output,/data-upgrade="estate" disabled/);
 assert.doesNotMatch(output,/data-upgrade="medical"/);
 assert.match(output,/최고 레벨 달성/);
 assert.match(output,/낭인 계약금 10% 할인/);
 assert.match(output,/4주 예비자금 740냥 부족/);
 assert.match(output,/data-upgrade="training" disabled/);
 assert.match(output,/추가 순수입 \+45냥\/주/);
 assert.match(output,/background-position:100% 100%/);
});

test('the fifth estate upgrade shows net payback and higher weekly upkeep',()=>{
 const {context,panel}=makeContext([sample('estate',4)],3000);
 context.showFacilities();
 assert.match(panel.innerHTML,/주간 유지비 20냥/);
 assert.match(panel.innerHTML,/주간 유지비 40냥/);
 assert.match(panel.innerHTML,/추가 순수입 \+70냥\/주 · 회수 약 35주/);
 assert.match(panel.innerHTML,/Lv\.5 승급 · 2400냥|Lv\.5 승급 · 2,400냥/);
});

test('image selection does not mutate levels, cash, or facility effects',()=>{
 const facilities=['training','estate','medical'].map((id,idx)=>sample(id,idx));
 const before=JSON.stringify(facilities);
 const {context}=makeContext(facilities,900);
 context.showFacilities();
 assert.equal(JSON.stringify(facilities),before);
 assert.equal(context.state.cash,900);
});