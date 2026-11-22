import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Arena} from '../group-engine.mjs';
import {finishGroupBattleNow} from '../arena-skip.mjs';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';

const makeConfig=(mode=8,kind='territory')=>{
  const terrain='field',field=Arena.battlefield(terrain,mode);
  const team=Arena.place(Arena.playerTeam('hold',mode),field);
  return {kind,match:'2:4:'+kind,mode,terrain,team,
    enemyRoster:Arena.place(Arena.enemyTeam('tang',field,mode),field),
    captain:team[0].id,deputy:team[1].id,
    chosenArts:Arena.baseArts,sectNames:['청운문','검풍문'],
    scenario:kind==='defense'?'defense':'attack'};
};

for(const kind of ['territory','conquest_duel','defense']){
  test(kind+' in-progress skip uses same simulation and full result',()=>{
    const config=makeConfig(8,kind);
    const full=Arena.settle(config);
    const game=Arena.create(config);
    for(let i=0;i<12;i++)Arena.tick(game);
    assert.equal(game.finished,false);
    assert.equal(finishGroupBattleNow(game,Arena),true);
    assert.equal(game.finished,true);
    assert.equal(game.winner,full.winner);
    assert.deepEqual(game.events,full.events);
    assert.deepEqual(game.units.filter(u=>u.side===0).map(u=>u.hp),
      full.units.filter(u=>u.side===0).map(u=>u.hp));
    assert.equal(finishGroupBattleNow(game,Arena),false);
  });
}
test('10v10 promotions can also be skipped safely',()=>{
  const config=makeConfig(10,'playoff');
  const game=Arena.create(config);
  assert.equal(finishGroupBattleNow(game,Arena),true);
  assert.equal(game.winner,Arena.settle(config).winner);
});
test('no battle or individual duel cannot invoke group skip',()=>{
  assert.equal(finishGroupBattleNow(null,Arena),false);
  assert.equal(finishGroupBattleNow({mode:3,finished:false},Arena),false);
});
test('every group choice exposes instant settlement and sends actual group_auto request',async()=>{
  const source=readFileSync(new URL('../game.js',import.meta.url),'utf8');
  const snippet=source.slice(source.indexOf('function groupBattle('),source.indexOf('function eliteScene('));
  for(const kind of ['conquest_duel','defense','territory','conquest_final','playoff']){
    const match=makeConfig(kind==='playoff'?10:8,kind);
    const nodes=new Map();
    const node=id=>{
      if(!nodes.has(id))nodes.set(id,{showModal(){},addEventListener(){}});
      return nodes.get(id);
    };
    const requests=[];
    const screen={querySelector:node};
    const context={state:{tier:4,group_play:match},screen,playback:0,busy:false,
      document:{querySelector:node},powerLabel:v=>String(v),
      siteName:(_,name)=>name||'거점',escapeText:v=>String(v),
      request:(path,payload)=>requests.push({path,payload})};
    runInNewContext(snippet,context);
    context.groupBattle();
    assert.match(screen.innerHTML,/id="group-skip"/);
    node('#group-skip').onclick();
    assert.equal(requests.length,1);
    assert.equal(requests[0].path,'group_auto');
    assert.equal(requests[0].payload.match,match.match);
  }
});
test('live arena toolbar includes skip button and routes to original result dialog',()=>{
 const html=readFileSync(new URL('../moonpa-arena.html',import.meta.url),'utf8');
 const source=readFileSync(new URL('../arena-ui.mjs',import.meta.url),'utf8');
 assert.match(html,/id="battle-skip"/);
 assert.match(source,/finishGroupBattleNow\(game,Arena\)/);
 assert.match(source,/refresh\(\)/);
 assert.match(source,/openBattleReport\(\)/);
 assert.match(source,/confirmCampaignResult\(\)/);
});
