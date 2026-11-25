import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Arena} from '../group-engine.mjs';
const profiles={
 ironwall:['lotus','mercy'],archery:['wing','rain'],breakthrough:['tiger','wedge'],
 disrupt:['silence','fog'],flank:['net','wedge'],adaptive:['wall','swordlight']
};
function config(terrain='field',rules=2){
 const t=Arena.battlefield(terrain,8);
 const team=Arena.place(Arena.playerTeam('balanced',8),t).map((u,i)=>({...u,id:i+100,strength:1}));
 const enemyRoster=team.map(u=>({...u,id:u.id+100}));
 return {team,enemyRoster,terrain,mode:8,captain:team[0].id,deputy:team[1].id,
 enemyCaptain:enemyRoster[0].id,enemyDeputy:enemyRoster[1].id,combatRules:rules,loadout:[],
 chosenArts:['lotus','cleanse'],enemyArts:['lotus','cleanse']};
}
test('rear cover is single 10% modifier and bypasses broken, stunned, and breached defenses',()=>{
 const g=Arena.create(config()),attacker=g.units.find(u=>u.side===0&&u.role==='bow'),
 target=g.units.find(u=>u.side===1&&u.line==='back'),guards=g.units.filter(u=>u.side===1&&u.role==='guard'&&u.line==='front');
 assert.ok(guards.length);
 assert.equal(Arena.rearCover(g,attacker,target),.9);
 guards.forEach(u=>u.stun=5);
 assert.equal(Arena.rearCover(g,attacker,target),1);
 guards.forEach(u=>u.stun=0);
 g.fronts[1].broken=true;assert.equal(Arena.rearCover(g,attacker,target),1);
 g.fronts[1].broken=false;attacker.flank='strike';assert.equal(Arena.rearCover(g,attacker,target),1);
 attacker.flank=null;g.combatRules=1;assert.equal(Arena.rearCover(g,attacker,target),1);
});
test('completed casting cannot hit an out-of-range target under new rules',()=>{
 const g=Arena.create(config()),hex=g.units.find(u=>u.side===0&&u.role==='hex'),target=g.units.find(u=>u.side===1&&u.line==='back');
 for(const u of g.units){u.cd=100;u.tauntAt=100;}
 hex.x=100;target.x=800;hex.cast={id:target.id,key:'curse',until:.15};
 Arena.tick(g);assert.equal(hex.actions,0);assert.equal(hex.cast,null);
 assert.equal(target.weak,0);
});
test('legacy config omission exactly equals explicit old rules',()=>{
 const old=config('forest',1),{combatRules,...implicit}=old;
 const selection={lineup:old.team,captain:old.captain,deputy:old.deputy,arts:old.chosenArts};
 assert.deepEqual(Arena.settle(old,selection),Arena.settle(implicit,selection));
});
test('versioned replay and settlement match with new mechanics',()=>{
 const cfg=config('river',2),g=Arena.create(cfg);
 while(!g.finished)Arena.tick(g);
 const r=Arena.settle(cfg,{lineup:cfg.team,captain:cfg.captain,deputy:cfg.deputy,arts:cfg.chosenArts});
 assert.equal(r.winner,g.winner);assert.deepEqual(r.units.map(u=>u.hp),g.units.map(u=>u.hp));
});
test('paired doctrine audit on six terrains, same roster/strength and both sides',()=>{
 const ids=Object.keys(profiles), results=[];
 for(const rules of [1,2]){
  const wins=Object.fromEntries(ids.map(id=>[id,0])),games=Object.fromEntries(ids.map(id=>[id,0]));
  let ties=0,side0=0,total=0;
  for(const terrain of Object.keys(Arena.terrains))for(let i=0;i<ids.length;i++)for(let k=i+1;k<ids.length;k++)for(const [a,b] of [[ids[i],ids[k]],[ids[k],ids[i]]]){
   const cfg=config(terrain,rules);
   Object.assign(cfg,{teamTactic:{id:a},enemyTactic:{id:b},chosenArts:profiles[a],enemyArts:profiles[b]});
   const r=Arena.settle(cfg,{lineup:cfg.team,captain:cfg.captain,deputy:cfg.deputy,arts:profiles[a]});
   assert.ok([-1,0,1].includes(r.winner));
   assert.ok(r.performance.every(u=>Number.isFinite(u.damage)&&u.damage>=0&&u.hp>=0&&u.hp<=u.max_hp&&u.shield_given>=0));
   const damage=r.performance.reduce((s,u)=>s+u.damage,0), received=r.performance.reduce((s,u)=>s+u.hit_taken,0);
   assert.equal(damage,received);
   games[a]++;games[b]++;total++;
   if(r.winner===-1){ties++;wins[a]+=.5;wins[b]+=.5;}
   else{wins[r.winner===0?a:b]++;if(r.winner===0)side0++;}
  }
  const rates=Object.fromEntries(ids.map(id=>[id,+(100*wins[id]/games[id]).toFixed(1)]));
  results.push({rules,total,ties,side0,rates,spread:+(Math.max(...Object.values(rates))-Math.min(...Object.values(rates))).toFixed(1)});
 }
 console.log('V40_BALANCE_AUDIT '+JSON.stringify(results));
 assert.equal(results[0].total,180);assert.equal(results[1].total,180);
});
