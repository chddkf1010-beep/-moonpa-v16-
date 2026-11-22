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
 const values={training:[0,8,16,24,32,40],estate:[0,20,46,78,116,160],medical:[0,12,24,36,48,60]};
 const current_value=values[id][level],next_value=values[id][Math.min(5,level+1)];
 return {id,name:names[id],level,max:5,current_value,next_value,
  next_cost:level===5?null:{training:240,estate:320,medical:200}[id]*(level+1)};
}
function makeContext(facilities,cash=2000){
 const panel={innerHTML:'',querySelectorAll:()=>[]};
 const context={state:{facilities,cash},panel:()=>panel,
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
 assert.match(output,/자금 340냥 부족/);
 assert.match(output,/추가 수입 \+26냥\/주/);
 assert.match(output,/background-position:100% 100%/);
});

test('image selection does not mutate levels, cash, or facility effects',()=>{
 const facilities=['training','estate','medical'].map((id,idx)=>sample(id,idx));
 const before=JSON.stringify(facilities);
 const {context}=makeContext(facilities,900);
 context.showFacilities();
 assert.equal(JSON.stringify(facilities),before);
 assert.equal(context.state.cash,900);
});