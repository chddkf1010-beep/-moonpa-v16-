import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Arena} from '../group-engine.mjs';
import {buildBattleReport,escapeBattleText,fighterPortrait,renderBattleReport,SORTS} from '../battle-report.mjs';

for(const mode of [8,10]){
  test(mode+' vs '+mode+' real battle produces exact damage and knockout counts',()=>{
    const t=Arena.battlefield('field',mode);
    const team=Arena.place(Arena.playerTeam('balanced',mode),t);
    const config={team,terrain:'field',mode,captain:team[0].id,deputy:team[1].id,
      scenario:'attack',loadout:[],chosenArts:Arena.baseArts};
    const match=Arena.create(config);
    let guard=0;
    while(!match.finished&&guard<20000){Arena.tick(match);guard++;}
    assert.ok(match.finished,'simulation must terminate');
    const report=buildBattleReport(match);
    assert.equal(report.sides[0].rows.length,mode);
    assert.equal(report.sides[1].rows.length,mode);
    assert.deepEqual(report.sides.map(s=>s.alive),
      [0,1].map(side=>match.units.filter(u=>u.side===side&&u.hp>0).length));
    const events=match.events.filter(e=>e.kind==='knockout'&&e.actor!==undefined);
    assert.ok(report.sides.reduce((a,s)=>a+s.totals.kills,0)>=
      events.filter(e=>match.units.some(u=>u.id===e.actor)).length,
      'individually attributed martial-art kills need not emit legacy actor events');
    for(const row of report.sides.flatMap(s=>s.rows)){
      const unit=match.units.find(u=>u.side===row.side&&u.id===row.id);
      assert.equal(row.damage,unit.damage);
      assert.equal(row.taken,unit.hitTaken);
      assert.equal(row.healing,unit.healing);
      assert.equal(row.kills,unit.kills);
      assert.equal(row.protection,unit.absorbed+unit.shieldGiven);
      assert.ok(row.score>=0&&row.score<=100);
      assert.ok(row.damage>=0&&row.kills>=0);
    }
    const totalDamage=report.sides.reduce((acc,s)=>acc+s.totals.damage,0);
    const totalTaken=report.sides.reduce((acc,s)=>acc+s.totals.taken,0);
    assert.ok(totalDamage<=totalTaken,'personal credited HP damage cannot exceed actual HP losses');
    assert.ok(report.note.includes('보호막'));
    const markup=renderBattleReport(report,0,'damage');
    assert.match(markup,/우리 문파 MVP/);
    assert.match(markup,/data-br-side="1"/);
    assert.match(markup,/data-br-sort="healing"/);
    assert.equal((markup.match(/<tr class="/g)||[]).length,mode);
    const replay=Arena.settle(config,{lineup:team,captain:config.captain,deputy:config.deputy,arts:Arena.baseArts});
    assert.equal(replay.winner,match.winner);
    for(const u of replay.units){
      const actual=match.units.find(x=>x.id===u.id&&x.side===u.side);
      assert.equal(u.hit_taken,actual.hitTaken);
      assert.equal(u.healing,actual.healing);
      assert.equal(u.kills,actual.kills);
      const performance=replay.performance.find(p=>p.side===u.side&&p.id===u.id);
      assert.equal(performance.damage,actual.damage);
      assert.equal(performance.kills,actual.kills);
      assert.equal(performance.shield_given,actual.shieldGiven);
    }
  });
}

test('role-aware MVP, team selection and sortable comparison are deterministic',()=>{
  const units=Array.from({length:16},(_,id)=>({
    id,side:id<8?0:1,name:'낭인 '+id,role:id%8===0?'guard':id%8===1?'heal':'blade',
    portrait:'',line:id%2?'back':'front',hp:id===2?0:100,max:100,
    damageDealt:id===2?700:id===0?20:15,hitTaken:id===0?400:10,
    healing:id===1?600:0,kills:id===2?3:0,absorbed:id===0?400:0,
    shieldGiven:id===0?300:0,actions:id===2?30:10
  }));
  const report=buildBattleReport({mode:8,finished:true,units,time:15,
    winner:0,reason:'전투 승리',sectNames:['청운문','당문'],artEvents:[
      {side:0,damage:45,restored:30},{side:1,damage:12,restored:0}
    ]});
  assert.equal(report.sides[0].leaders.damage.id,2);
  assert.equal(report.sides[0].leaders.kills.id,2);
  assert.equal(report.sides[0].leaders.healing.id,1);
  assert.equal(report.sides[0].leaders.protection.id,0);
  assert.equal(report.sides[0].totals.artDamage,45);
  assert.equal(report.sides[0].totals.artHealing,30);
  assert.equal(report.sides[0].rows.find(x=>x.id===2).alive,false);
  const own=renderBattleReport(report,0,'kills');
  const enemy=renderBattleReport(report,1,'taken');
  assert.ok(own.includes('최다 처치')&&own.includes('전투불능'));
  assert.ok(enemy.includes('당문 (8/8)'));
  assert.equal((own.match(/<tr class="/g)||[]).length,8);
  assert.equal((enemy.match(/<tr class="/g)||[]).length,8);
  assert.equal(SORTS.length,6);
});

test('portrait atlas keeps identity and rejects untrusted path injection',()=>{
  const fighter={name:'<script>x</script>',role:'heal',alive:true,
    portrait:'assets/portraits/diverse/v2_5_7.webp'};
  const v2=fighterPortrait(fighter,true);
  assert.match(v2,/atlas_v2_2.webp/);
  assert.match(v2,/background-position:100% 100%/);
  assert.ok(!v2.includes('<script>'));
  assert.ok(v2.includes('&lt;script&gt;'));
  assert.match(fighterPortrait({...fighter,portrait:'assets/portraits/founders/seed16_640.webp'}),/founder_atlas.webp/);
  assert.match(fighterPortrait({...fighter,portrait:'assets/portraits/diverse/v1_05.webp'}),/atlas_v1.webp/);
  const injected=fighterPortrait({...fighter,portrait:'x" onerror="alert(1)'});
  assert.ok(!injected.includes('onerror'));
  assert.match(injected,/healer_card.webp/);
  assert.equal(escapeBattleText('<"&'), '&lt;&quot;&amp;');
});

test('battle report is read-only and rejects ongoing/non-group fights',()=>{
  const game={mode:8,finished:true,units:[{id:0,side:0,name:'무인',role:'blade',hp:10,max:100,
    damageDealt:20,hitTaken:80,healing:0,kills:1,actions:3}],sectNames:['청운문','당문'],artEvents:[]};
  const before=JSON.stringify(game);
  const report=buildBattleReport(game);
  renderBattleReport(report);
  assert.equal(JSON.stringify(game),before);
  assert.throws(()=>buildBattleReport({...game,finished:false}));
  assert.throws(()=>buildBattleReport({...game,mode:5}));
  assert.throws(()=>renderBattleReport(report,3));
  assert.throws(()=>renderBattleReport(report,0,'fake'));
});
