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
  for(const terrain of ['gate','river']){
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
