import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {Arena} from '../group-engine.mjs';
import {eligibleBench,replaceDeployed,combatantStats} from '../arena-bench.mjs';

function fixture(){
  const terrain='field',mode=8;
  const team=Arena.place(Arena.playerTeam('hold',mode),Arena.battlefield(terrain,mode));
  const reserve={...team[1],id:400,name:'대기 검사문파원',ca:144,pa:185,level:9,attrs:{strength:127.5,defense:92.3}};
  return {config:{team,bench:[reserve],terrain,mode,captain:team[0].id,deputy:team[1].id,scenario:'attack'},
    reserve};
}
test('bench lists only authorized undeployed members and restores outgoing on swap',()=>{
  const {config,reserve}=fixture();
  assert.deepEqual(eligibleBench(config,config.team).map(f=>f.id),[400]);
  const outgoing=config.team[2];
  const swapped=replaceDeployed(config.team,config,reserve.id,outgoing.id);
  assert.equal(swapped.length,8);
  assert.equal(swapped[2].id,reserve.id);
  assert.equal(swapped[2].line,outgoing.line);
  assert.equal(swapped[2].slot,outgoing.slot);
  assert.ok(eligibleBench(config,swapped).some(f=>f.id===outgoing.id));
  assert.ok(!eligibleBench(config,swapped).some(f=>f.id===reserve.id));
  const back=replaceDeployed(swapped,config,outgoing.id,reserve.id);
  assert.deepEqual(back.map(f=>f.id),config.team.map(f=>f.id));
  assert.equal(config.team[2].id,outgoing.id); // original config never mutated
});
test('bench rejects unauthorized substitutions and duplicate deployments',()=>{
  const {config}=fixture();
  assert.throws(()=>replaceDeployed(config.team,config,999,config.team[0].id),/교체 가능한/);
  assert.throws(()=>replaceDeployed(config.team,config,config.team[0].id,config.team[1].id),/교체 가능한/);
  assert.throws(()=>replaceDeployed(config.team,config,400,999),/교체 가능한/);
});
test('battle settlement accepts exactly eight authorized fighters including bench and maintains original automatic mode',()=>{
  const {config,reserve}=fixture();
  const replacement=replaceDeployed(config.team,config,reserve.id,config.team[2].id);
  const original=Arena.settle(config);
  const changed=Arena.settle(config,{lineup:replacement,captain:config.captain,
    deputy:config.deputy,arts:Arena.baseArts});
  assert.equal(original.units.filter(u=>u.side===0).length,8);
  assert.equal(changed.units.filter(u=>u.side===0).length,8);
  assert.ok(changed.units.some(u=>u.id===reserve.id&&u.side===0));
  assert.ok(!changed.units.some(u=>u.id===config.team[2].id&&u.side===0));
  assert.throws(()=>Arena.settle(config,{lineup:[...replacement.slice(0,7),{...reserve,id:999,line:'back',slot:3}],captain:config.captain,
    deputy:config.deputy,arts:Arena.baseArts}),/진형/);
});
test('captain and deputy must actually remain deployed after substitution',()=>{
  const {config,reserve}=fixture();
  const replacement=replaceDeployed(config.team,config,reserve.id,config.captain);
  assert.throws(()=>Arena.settle(config,{lineup:replacement,captain:config.captain,
    deputy:config.deputy,arts:Arena.baseArts}),/진형/);
  const settled=Arena.settle(config,{lineup:replacement,captain:reserve.id,
    deputy:config.deputy,arts:Arena.baseArts});
  assert.equal(settled.units.filter(u=>u.side===0).length,8);
});
test('fighter detail helper returns real CA PA and eight-attribute data',()=>{
  const {reserve}=fixture();
  const details=combatantStats(reserve);
  assert.equal(details.ca,144);
  assert.equal(details.pa,185);
  assert.deepEqual(details.attrs,{strength:127.5,defense:92.3});
});
test('actual deployed interface includes portrait information modal and reserve swap controls',()=>{
  const html=readFileSync(join(import.meta.dirname,'..','moonpa-arena.html'),'utf8');
  const ui=readFileSync(join(import.meta.dirname,'..','arena-ui.mjs'),'utf8');
  assert.match(html,/id="fighter-stats-dialog"/);
  assert.match(html,/id="fighter-stats-content"/);
  assert.match(ui,/data-swap-out/);
  assert.match(ui,/data-bench-join/);
  assert.match(ui,/data-bench-info/);
  assert.match(ui,/fighterInfo\(unit\)/);
  assert.match(ui,/function swapBench/);
});
