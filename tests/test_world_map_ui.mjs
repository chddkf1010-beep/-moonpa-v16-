import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {test} from 'node:test';
import vm from 'node:vm';

const source=readFileSync(join(import.meta.dirname,'..','world-map.js'),'utf8');
function harness() {
  const state={
    phase:'ready', tier:4, guild:7, operations:{clock:1},
    zones:[{id:47,selectable:true}],
    world_map:[
      {id:47,tier:4,name:'달빛여관터',site_grade:'소규모',owner:11,owner_name:'풍림문',defense_power:86.2,gross:410,upkeep:70,value:340,protected_until:0,selectable:true},
      {id:49,tier:4,name:'쇠목나루마을',site_grade:'소규모',owner:null,owner_name:'수비대',defense_power:79.2,gross:410,upkeep:70,value:340,protected_until:0,selectable:true},
      {id:58,tier:3,name:'양주 외곽',site_grade:'중간급',owner:7,owner_name:'내 문파',defense_power:101.7,gross:760,upkeep:100,value:660,protected_until:0,selectable:false}
    ],
    league:{groups:[
      {tier:4,members:[{id:11,name:'풍림문'}]},
      {tier:3,members:[{id:7,name:'내 문파'}]}
    ]}
  };
  const context={state,leagueTier:4,
    escapeText:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
    money:value=>value+'냥',
    powerLabel:value=>typeof value==='number'?value.toFixed(1):'—'
  };
  vm.createContext(context);
  vm.runInContext(source,context,{filename:'world-map.js'});
  return {state,context,render:()=>vm.runInContext('renderWorldMap()',context)};
}
test('real owner and defense power render without hardcoded demo data',()=>{
  const {render}=harness();
  const html=render();
  assert.match(html,/달빛여관터/);
  assert.match(html,/풍림문/);
  assert.match(html,/수비대/);
  assert.match(html,/86\.2/);
  assert.match(html,/data-world-zone="47"/);
  assert.doesNotMatch(html,/흑풍채 점령/);
});
test('changing league only changes the view; saving ownership stays in state',()=>{
  const {state,context,render}=harness();
  const owner=state.world_map[0].owner;
  assert.match(render(),/달빛여관터/);
  vm.runInContext('leagueTier=3',context);
  const t3=render();
  assert.match(t3,/양주 외곽/);
  assert.doesNotMatch(t3,/달빛여관터/);
  vm.runInContext('leagueTier=4',context);
  assert.match(render(),/달빛여관터/);
  assert.equal(state.world_map[0].owner,owner);
  state.world_map[0].owner=null;
  state.world_map[0].owner_name='수비대';
  assert.match(render(),/수비대/);
  assert.equal(state.world_map[0].owner,null);
});
test('map navigation provides no direct owner mutation actions',()=>{
  const {render}=harness();
  const html=render();
  assert.match(html,/점령전 준비/);
  assert.doesNotMatch(source,/\.owner\s*=\s*['"]ally['"]/);
  assert.doesNotMatch(source,/localStorage\.setItem/);
});
