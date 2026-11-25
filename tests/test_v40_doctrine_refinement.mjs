import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Arena} from '../group-engine.mjs';

const profiles={ironwall:['lotus','mercy'],archery:['wing','rain'],breakthrough:['tiger','wedge'],
  disrupt:['silence','fog'],flank:['net','wedge'],adaptive:['wall','swordlight']};
const ids=Object.keys(profiles);
function config(preset='balanced',terrain='field',rules=3,mode=8){
  const layout=Arena.battlefield(terrain,mode);
  const team=Arena.place(Arena.playerTeam(preset,mode),layout).map((u,i)=>({...u,id:100+i,strength:1}));
  const enemyRoster=team.map(u=>({...u,id:u.id+100}));
  return {team,enemyRoster,terrain,mode,captain:team[0].id,deputy:team[1].id,
    enemyCaptain:enemyRoster[0].id,enemyDeputy:enemyRoster[1].id,
    combatRules:rules,loadout:[],chosenArts:['lotus','cleanse'],enemyArts:['lotus','cleanse']};
}
function selection(c){return {lineup:c.team,captain:c.captain,deputy:c.deputy,arts:c.chosenArts};}
test('disrupt attacks reachable support instead of chasing an out-of-range healer',()=>{
  const c=config();c.teamTactic={id:'disrupt'};
  const g=Arena.create(c), u=g.units.find(v=>v.side===0&&v.role==='hex');
  const healer=g.units.find(v=>v.side===1&&v.role==='heal');
  const bow=g.units.find(v=>v.side===1&&v.role==='bow');
  for(const v of g.units.filter(v=>v.side===1)){v.x=800;v.y=215;}
  u.x=300;u.y=215;healer.x=515;bow.x=430;
  assert.equal(Arena.selectTarget(g,u)[0].id,bow.id);
  g.combatRules=2;
  assert.equal(Arena.selectTarget(g,u)[0].id,healer.id);
});
test('flank waits in normal combat and enters when a rear target becomes reachable',()=>{
  const c=config();c.teamTactic={id:'flank'};
  const g=Arena.create(c),u=g.units.find(v=>v.side===0&&v.role==='dash');
  for(const v of g.units){v.cd=100;v.tauntAt=100;}
  for(const v of g.units.filter(v=>v.side===1)){v.x=800;v.y=215;}
  u.x=300;u.y=215;
  Arena.tick(g);Arena.tick(g);
  assert.ok(!u.flank);
  const rear=g.units.find(v=>v.side===1&&v.line==='back'&&['bow','hex','heal'].includes(v.role));
  rear.x=u.x+50;rear.y=u.y;
  Arena.tick(g);
  assert.equal(u.flank,'strike');
});
test('v3 rules reproduce 8v8 and 10v10 replay and settlement',()=>{
  for(const mode of [8,10])for(const terrain of Object.keys(Arena.terrains)){
    const c=config('raid',terrain,3,mode);c.teamTactic={id:'flank'};c.enemyTactic={id:'disrupt'};
    c.chosenArts=profiles.flank;c.enemyArts=profiles.disrupt;
    const g=Arena.create(c);
    while(!g.finished)Arena.tick(g);
    const result=Arena.settle(c,selection(c));
    assert.equal(result.winner,g.winner);
    assert.deepEqual(result.units.map(u=>u.hp),g.units.map(u=>u.hp));
    assert.equal(result.performance.reduce((n,u)=>n+u.damage,0),result.performance.reduce((n,u)=>n+u.hit_taken,0));
  }
});
test('paired comparison: three roster presets, six terrains, all doctrine pairs and both sides',()=>{
  const aggregate={2:Object.fromEntries(ids.map(x=>[x,0])),3:Object.fromEntries(ids.map(x=>[x,0]))};
  const rows=[];
  for(const preset of ['balanced','hold','raid'])for(const rules of [2,3]){
    const wins=Object.fromEntries(ids.map(x=>[x,0])),games=Object.fromEntries(ids.map(x=>[x,0]));
    let matches=0,ties=0;
    for(const terrain of Object.keys(Arena.terrains))for(let i=0;i<ids.length;i++)for(let k=i+1;k<ids.length;k++)
      for(const [a,b] of [[ids[i],ids[k]],[ids[k],ids[i]]]){
        const c=config(preset,terrain,rules);
        Object.assign(c,{teamTactic:{id:a},enemyTactic:{id:b},chosenArts:profiles[a],enemyArts:profiles[b]});
        const r=Arena.settle(c,selection(c));
        assert.ok([-1,0,1].includes(r.winner));
        assert.ok(r.performance.every(u=>Number.isFinite(u.damage)&&u.damage>=0&&u.hp>=0&&u.hp<=u.max_hp&&u.shield_given>=0));
        assert.equal(r.performance.reduce((n,u)=>n+u.damage,0),r.performance.reduce((n,u)=>n+u.hit_taken,0));
        games[a]++;games[b]++;matches++;
        if(r.winner===-1){ties++;wins[a]+=.5;wins[b]+=.5;}else wins[r.winner===0?a:b]++;
      }
    assert.equal(matches,180);
    for(const id of ids)aggregate[rules][id]+=wins[id];
    const rates=Object.fromEntries(ids.map(id=>[id,+(100*wins[id]/games[id]).toFixed(1)]));
    rows.push({preset,rules,matches,ties,rates,spread:+(Math.max(...Object.values(rates))-Math.min(...Object.values(rates))).toFixed(1)});
  }
  const overall=[2,3].map(rules=>{
    const rates=Object.fromEntries(ids.map(id=>[id,+(100*aggregate[rules][id]/180).toFixed(1)]));
    return {rules,rates,spread:+(Math.max(...Object.values(rates))-Math.min(...Object.values(rates))).toFixed(1)};
  });
  console.log('V40_DOCTRINE_AUDIT '+JSON.stringify({rows,overall}));
  assert.ok(overall[1].spread<overall[0].spread);
  assert.ok(overall[1].rates.disrupt>overall[0].rates.disrupt);
  assert.ok(overall[1].rates.flank>overall[0].rates.flank);
});
