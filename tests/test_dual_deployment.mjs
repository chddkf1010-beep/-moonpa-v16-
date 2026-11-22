import assert from 'node:assert/strict';
import {test} from 'node:test';
import {Arena} from '../group-engine.mjs';
import {moveAssignment,waitingMembers,assignmentPool} from '../arena-assign.mjs';

function fixture(defenseCount=8) {
 const terrain=Arena.battlefield('field',8);
 const attack=Arena.place(Arena.playerTeam('hold',8),terrain);
 const defense=Arena.place(Arena.playerTeam('balanced',8),terrain)
   .map((member,i)=>({...member,id:500+i,name:'방어 '+(i+1)})).slice(0,defenseCount);
 const bench=[{...attack[0],id:600,name:'대기 첫째'},
              {...attack[2],id:601,name:'대기 둘째'}];
 const config={kind:'territory',team:attack,defenseTeam:defense,bench,mode:8,defenseEnabled:true};
 return {config,attack,defense,bench,terrain};
}
test('moving an attacker to a partially filled defense really removes them from attack',()=>{
 const {config,attack,defense,bench,terrain}=fixture(4);
 const moved=moveAssignment(config,attack,defense,attack[0].id,'defense',terrain);
 assert.equal(moved.attack.length,7);
 assert.equal(moved.defense.length,5);
 assert.ok(moved.defense.some(f=>f.id===attack[0].id));
 assert.ok(!moved.attack.some(f=>f.id===attack[0].id));
 const refilled=moveAssignment(config,moved.attack,moved.defense,bench[0].id,'attack',terrain);
 assert.equal(refilled.attack.length,8);
 assert.equal(refilled.defense.length,5);
 assert.ok(refilled.attack.some(f=>f.id===bench[0].id));
 assert.equal(new Set([...refilled.attack,...refilled.defense].map(f=>f.id)).size,13);
});
test('full defense requires an explicit target and swaps two real squads',()=>{
 const {config,attack,defense,terrain}=fixture();
 assert.throws(()=>moveAssignment(config,attack,defense,attack[1].id,'defense',terrain),/가득 찼습니다/);
 const swapped=moveAssignment(config,attack,defense,attack[1].id,'defense',terrain,defense[3].id);
 assert.equal(swapped.attack.length,8);
 assert.equal(swapped.defense.length,8);
 assert.ok(swapped.defense.some(u=>u.id===attack[1].id));
 assert.ok(swapped.attack.some(u=>u.id===defense[3].id));
 assert.equal(swapped.defense.find(u=>u.id===attack[1].id).slot,defense[3].slot);
 assert.equal(swapped.attack.find(u=>u.id===defense[3].id).slot,attack[1].slot);
});
test('moving a defender back to attack and moving to waiting are reversible',()=>{
 const {config,attack,defense,terrain}=fixture(7);
 const changed=moveAssignment(config,attack,defense,defense[0].id,'wait',terrain);
 assert.equal(changed.defense.length,6);
 assert.ok(waitingMembers(config,changed.attack,changed.defense).some(x=>x.id===defense[0].id));
 const again=moveAssignment(config,changed.attack,changed.defense,defense[0].id,'defense',terrain);
 assert.equal(again.defense.length,7);
 const swap=moveAssignment(config,again.attack,again.defense,defense[0].id,'attack',terrain,attack[0].id);
 assert.ok(swap.attack.some(u=>u.id===defense[0].id));
 assert.ok(swap.defense.some(u=>u.id===attack[0].id));
});
test('authorization, unique assignments, and unavailable defense are enforced',()=>{
 const {config,attack,defense,terrain}=fixture(2);
 assert.equal(assignmentPool(config).size,12);
 assert.throws(()=>moveAssignment(config,attack,defense,999999,'defense',terrain),/허용되지/);
 assert.throws(()=>moveAssignment({...config,defenseEnabled:false},attack,defense,attack[0].id,'defense',terrain),/보유 거점/);
 assert.throws(()=>moveAssignment(config,attack,defense,attack[0].id,'error',terrain),/알 수 없는/);
});
