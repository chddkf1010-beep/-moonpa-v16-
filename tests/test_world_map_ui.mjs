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
      {id:47,tier:4,name:'달빛여관터',site_grade:'소규모',owner:11,owner_name:'풍림문',defense_power:86.2,weekly_net:295,terrain:{name:'협곡'},gross:410,upkeep:70,value:340,protected_until:0,selectable:true},
      {id:49,tier:4,name:'쇠목나루마을',site_grade:'소규모',owner:null,owner_name:'수비대',defense_power:79.2,weekly_net:340,terrain:{name:'평원'},gross:410,upkeep:70,value:340,protected_until:0,selectable:true},
      {id:58,tier:3,name:'양주 외곽',site_grade:'중간급',owner:7,owner_name:'내 문파',defense_power:101.7,weekly_net:580,terrain:{name:'요새'},gross:760,upkeep:100,value:660,protected_until:0,selectable:false}
    ],
    league:{groups:[
      {tier:4,members:[{id:11,name:'풍림문'}]},
      {tier:3,members:[{id:7,name:'내 문파'}]}
    ]}
  };
  const context={state,leagueTier:4,
    escapeText:value=>String(value).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('"','&quot;'),
    money:value=>value+'냥',
    number:value=>Number(value).toLocaleString('ko-KR'),
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
  assert.match(html,/주간 예상 순수입/);
  assert.match(html,/협곡/);
  assert.match(html,/295냥/);
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

test('clicking a selected map target transfers that exact zone into weekly assignment',()=>{
  const {state,context,render}=harness();
  render();
  const eventHandlers={};
  const zoneHandlers={};
  const zoneNode={
    tagName:'g',dataset:{worldZone:'47'},classList:{toggle(){}},
    setAttribute(){},addEventListener:(type,fn)=>zoneHandlers[type]=fn
  };
  const attack={
    dataset:{worldAttack:'47'},
    addEventListener:(type,fn)=>eventHandlers[type]=fn
  };
  const detail={innerHTML:''};
  let focused=false,opened=false;
  const root={
    querySelector(selector){
      if(selector==='#world-map-detail')return detail;
      if(selector==='[data-world-attack]')return attack;
      return null;
    },
    querySelectorAll:()=>[zoneNode]
  };
  context.panel=()=>({querySelector:selector=>
    selector==='#world-map'?root:selector==='#target-zone'?{focus(){focused=true;}}:null});
  context.draft={zone:null};
  context.currentTab='league';
  context.management=()=>{opened=true;};
  vm.runInContext('bindWorldMap()',context);
  assert.equal(typeof zoneHandlers.click,'function');
  zoneHandlers.click();
  assert.match(detail.innerHTML,/주간 예상 순수입/);
  assert.equal(typeof eventHandlers.click,'function');
  eventHandlers.click({currentTarget:attack});
  assert.equal(context.draft.zone,47);
  assert.equal(context.currentTab,'week');
  assert.equal(opened,true);
  assert.equal(focused,true);
  assert.equal(state.world_map[0].owner,11); // no premature capture
});


test('the atlas uses bounded, deterministic territory polygons and factual terrain decoration',()=>{
  const {context,render}=harness();
  const original=render();
  assert.match(original,/world-map-province/);
  assert.match(original,/world-map-emblem/);
  assert.match(original,/world-map-terrain-mark/);
  assert.match(original,/world-map-faction-item/);
  assert.match(original,/data-world-map-mode="owner"/);
  assert.match(original,/data-world-map-mode="income"/);
  assert.match(original,/data-world-map-mode="power"/);
  assert.doesNotMatch(original,/world-map-grid/);
  assert.equal(original,render());
  const positions=vm.runInContext('worldMapPositions(worldMapSites(4))',context);
  assert.equal(positions.length,2);
  const paths=vm.runInContext('worldMapPositions(worldMapSites(4)).map(p=>worldMapProvincePath(p,worldMapPositions(worldMapSites(4))))',context);
  assert.ok(paths.every(p=>p.startsWith('M')&&p.endsWith('Z')));
});

test('faction, income and defense modes change visual layers but not zone ownership or income',()=>{
  const {state,context,render}=harness();
  const before=JSON.stringify(state.world_map);
  const owner=render();
  vm.runInContext("worldMapMode='income'",context);
  const income=render();
  assert.match(income,/\+295냥\/주/);
  assert.match(income,/주간 순수입 기준/);
  vm.runInContext("worldMapMode='power'",context);
  const power=render();
  assert.match(power,/수비 86\.2/);
  assert.match(power,/승률 예측 아님/);
  assert.notEqual(owner,income);
  assert.notEqual(income,power);
  assert.equal(JSON.stringify(state.world_map),before);
});

test('own territory is selected first and the faction color stays stable across mode switches',()=>{
  const {context,render}=harness();
  vm.runInContext('leagueTier=3',context);
  const own=render();
  assert.match(own,/data-world-zone="58"/);
  assert.match(own,/내 문파/);
  assert.match(own,/내 거점 주간 순수익/);
  vm.runInContext('leagueTier=4',context);
  const rivals=render();
  assert.match(rivals,/풍림문/);
  assert.match(rivals,/world-map-status rival/);
});
