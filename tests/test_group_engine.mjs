import assert from 'node:assert/strict';
import { test } from 'node:test';
import { Arena } from '../group-engine.mjs';

for (const mode of [8, 10]) {
  for (const terrain of Object.keys(Arena.terrains)) {
    test(`${mode}v${mode} uses the same slots and result in replay and settlement on ${terrain}`, () => {
      const layout = Arena.battlefield(terrain, mode);
      if (mode === 10) assert.deepEqual([layout.front, layout.back], [5, 5]);
      const team = Arena.place(Arena.playerTeam('balanced', mode), layout);
      const [a, b] = team;
      [a.slot, b.slot] = [b.slot, a.slot];
      const config = { team, terrain, mode, captain: a.id, deputy: b.id, loadout: [] };
      const selection = { lineup: team, captain: a.id, deputy: b.id, arts: Arena.baseArts };
      const game = Arena.create(config);
      assert.equal(game.units.length, 2 * mode);
      assert.equal(game.units.find(u => u.id === a.id).slot, 1);
      while (!game.finished) Arena.tick(game);
      const settled = Arena.settle(config, selection);
      assert.equal(settled.winner, game.winner);
      assert.deepEqual(settled.units.map(u => u.hp), game.units.map(u => u.hp));
      assert.throws(() => Arena.settle(config, { ...selection, lineup: [a, a, ...team.slice(2)] }));
    });
  }
}

test('a rear slot stays in place even if another rear slot is empty', () => {
  const terrain = Arena.battlefield('field', 10);
  const last = {id: 1, role: 'bow', line: 'back', slot: 4};
  const first = {id: 2, role: 'heal', line: 'back', slot: 0};
  assert.ok(Arena.deployPoint(last, terrain).y > Arena.deployPoint(first, terrain).y);
  const config = {terrain:'field', mode:10, captain:1, loadout:[]};
  const full = Arena.create({...config, team:[first,last]});
  const short = Arena.create({...config, team:[last]});
  assert.equal(full.units.find(u=>u.id===last.id).y, short.units[0].y);
});

test('the selected point sets spawn and home and is reproduced during settlement', () => {
  const mode=10, terrain='gate';
  const team=Arena.place(Arena.playerTeam('raid', mode), Arena.battlefield(terrain,mode));
  const config={team, mode, terrain, captain:team[0].id, deputy:team[1].id, loadout:[]};
  const deployed=team.map((u,i)=>i===0?{...u,position:{x:278,y:334}}:u);
  const game=Arena.create({...config,team:deployed});
  const unit=game.units.find(u=>u.id===team[0].id);
  assert.deepEqual([unit.x,unit.y,unit.homeX,unit.homeY], [278,334,278,334]);
  assert.ok(game.lanes[0].at(-1).units.includes(unit.id));
  while(!game.finished) Arena.tick(game);
  const selection={lineup:deployed,captain:config.captain,deputy:config.deputy,arts:Arena.baseArts};
  const settled=Arena.settle(config,selection);
  assert.equal(settled.winner,game.winner);
  assert.deepEqual(settled.units.map(u=>u.hp),game.units.map(u=>u.hp));

  for (const position of [{x:440,y:190},{x:451,y:210},{x:140,y:400}]) {
    const lineup=[{...deployed[0],position},...deployed.slice(1)];
    assert.throws(()=>Arena.settle(config,{...selection,lineup}));
  }
  assert.ok(Arena.canDeploy('gate',440,215));
  assert.ok(Arena.canDeploy('river',440,107.5));
  assert.ok(!Arena.canDeploy('river',440,215));
  assert.ok(Arena.canDeploy('field',440,215));
});

test('river blocks bow shots and units detour to a crossing without entering water', () => {
  const archer = (id) => ({id, role:'bow', name:String(id), line:'front', slot:0,
    position:{x:400,y:215}});
  const config = {team:[archer(1)], enemyRoster:[archer(2)], mode:8, captain:1,
    chosenArts:[], enemyArts:[]};
  const field = Arena.create({...config, terrain:'field'});
  const river = Arena.create({...config, terrain:'river'});
  assert.ok(Arena.clearPath(field.wall,...field.units));
  assert.ok(!Arena.clearPath(river.wall,...river.units));
  Arena.tick(field);
  Arena.tick(river);
  assert.ok(field.units.some(u=>u.actions===1));
  assert.ok(river.units.every(u=>u.actions===0&&u.hp===u.max));
  while(!river.finished){
    Arena.tick(river);
    for(const u of river.units)
      assert.ok(Arena.clearPath(river.wall,{x:u.prevX,y:u.prevY},u));
  }
  assert.ok(river.units.every(u=>Math.abs(u.y-215)>10));
  assert.ok(river.units.some(u=>u.hp<u.max));
});

test('each obstacle blocks direct shots until archers find a passable route',()=>{
  for(const key of ['forest','mountain','gate','gorge']){
    const wall=Arena.obstruction(key);
    const y=Array.from({length:205},(_,i)=>130+i).find(y=>
      !wall.openings.some(opening=>Math.abs(opening-y)<=wall.halfOpening));
    const unit=id=>({id,role:'bow',name:String(id),line:'front',slot:0,position:{x:380,y}});
    const game=Arena.create({terrain:key,mode:8,captain:1,team:[unit(1)],enemyRoster:[unit(2)],
      chosenArts:[],enemyArts:[]});
    assert.ok(!Arena.clearPath(game.wall,...game.units),key);
    assert.ok(!Arena.canDeploy(key,440,y),key);
    Arena.tick(game);
    assert.ok(game.units.every(f=>f.actions===0&&f.hp===f.max),key);
    while(!game.finished){
      Arena.tick(game);
      assert.ok(game.units.every(u=>Arena.clearPath(game.wall,{x:u.prevX,y:u.prevY},u)),key);
    }
    assert.ok(game.units.some(f=>f.hp<f.max),key);
  }
});

test('a narrow map puts opposing spawns within bow range sooner than a wide map', () => {
  const team=[{id:1,role:'bow',name:'A',line:'back',slot:0,position:{x:291,y:215}}];
  const config={team,enemyRoster:[{...team[0],id:2}],mode:8,captain:1,chosenArts:[],enemyArts:[]};
  const narrow=Arena.create({...config,terrain:'gate'});
  const wide=Arena.create({...config,terrain:'field'});
  Arena.tick(narrow);
  Arena.tick(wide);
  assert.ok(narrow.t.width<wide.t.width);
  assert.ok(narrow.units.some(u=>u.actions===1));
  assert.ok(wide.units.every(u=>u.actions===0));
});

test('squad separation keeps the rendered path inside the openings', () => {
  for(const terrain of Object.keys(Arena.terrains).filter(key=>Arena.obstruction(key))){
    for(const preset of ['balanced','hold']){
      const team=Arena.place(Arena.playerTeam(preset),Arena.battlefield(terrain,8));
      const g=Arena.create({team,terrain,opponent:'tang',mode:8,scenario:'defense',
        captain:team[0].id,deputy:team[1].id,loadout:[]});
      while(!g.finished){
        Arena.tick(g);
        assert.ok(g.units.every(u=>Arena.clearPath(g.wall,{x:u.prevX,y:u.prevY},u)));
      }
    }
  }
});

test('default automatic settlement matches a direct replay and credits real HP damage', () => {
  const terrain='field';
  const team=Arena.place(Arena.playerTeam('hold',8),Arena.battlefield(terrain,8));
  const config={team,terrain,mode:8,captain:team[0].id,deputy:team[1].id};
  const automatic=Arena.settle(config);
  const direct=Arena.settle(config,{lineup:team,captain:config.captain,deputy:config.deputy,arts:Arena.baseArts});
  assert.deepEqual(automatic,direct);
  assert.equal(automatic.performance.length,16);
  assert.ok(automatic.performance.some(row=>row.healing>0));
  for(const side of [0,1]){
    const caused=automatic.performance.filter(row=>row.side===side).reduce((sum,row)=>sum+row.damage,0);
    const received=automatic.performance.filter(row=>row.side!==side).reduce((sum,row)=>sum+row.hit_taken,0);
    assert.ok(caused>0);
    assert.equal(caused,received);
  }
});


test('enemy doctrine changes actual combat targets, not just its displayed arts',()=>{
  const terrain='field',layout=Arena.battlefield(terrain,8);
  const team=Arena.place(Arena.playerTeam('balanced',8),layout);
  const enemy=Arena.enemyTeam('tang',layout,8);
  const config={team,enemyRoster:enemy,terrain,mode:8,captain:team[0].id,
    deputy:team[1].id,loadout:[],enemyArts:['rain','poison']};
  function situation(kind){
    const g=Arena.create({...config,enemyTactic:{id:kind}});
    for(const fighter of g.units){fighter.x=450;fighter.y=215;}
    return g;
  }
  const disrupted=situation('disrupt');
  const bow=disrupted.units.find(f=>f.side===1&&f.role==='bow');
  assert.ok(bow);
  const [victim,art]=Arena.selectTarget(disrupted,bow);
  assert.equal(victim.role,'heal');
  assert.ok(['arrow','link'].includes(art));

  const ordinary=situation('balanced');
  const ordinaryBow=ordinary.units.find(f=>f.side===1&&f.role==='bow');
  const [ordinaryVictim]=Arena.selectTarget(ordinary,ordinaryBow);
  assert.equal(ordinaryVictim.line,'front');

  const hold=situation('ironwall');
  const guard=hold.units.find(f=>f.side===1&&f.role==='guard');
  const healer=hold.units.find(f=>f.side===1&&f.role==='heal');
  healer.hp=Math.round(healer.max*.80);
  const [protectedUnit,defenseSkill]=Arena.selectTarget(hold,guard);
  assert.equal(defenseSkill,'ward');
  assert.equal(protectedUnit.id,healer.id);

  const archers=situation('archery');
  const ranged=archers.units.find(f=>f.side===1&&f.role==='bow');
  const [fireTarget]=Arena.selectTarget(archers,ranged);
  assert.ok(['heal','hex'].includes(fireTarget.role));
  assert.equal(archers.tactics[1].id,'archery');
});

test('different doctrines keep settlement and replay deterministic',()=>{
  const layout=Arena.battlefield('mountain',8);
  const team=Arena.place(Arena.playerTeam('balanced',8),layout);
  const enemy=Arena.enemyTeam('tang',layout,8);
  for(const id of ['ironwall','archery','breakthrough','disrupt','flank','adaptive']){
    const config={team,enemyRoster:enemy,terrain:'mountain',mode:8,
      captain:team[0].id,deputy:team[1].id,loadout:[],enemyTactic:{id},
      enemyArts:['lotus','mercy']};
    const played=Arena.create(config);
    let steps=0;
    while(!played.finished&&steps++<500)Arena.tick(played);
    assert.equal(played.finished,true,id);
    const replay=Arena.settle(config,{lineup:team,captain:team[0].id,deputy:team[1].id,arts:Arena.baseArts});
    assert.equal(played.winner,replay.winner,id);
    assert.deepEqual(replay.units.map(u=>u.hp),played.units.filter(u=>u.id>=0).map(u=>u.hp),id);
  }
});
