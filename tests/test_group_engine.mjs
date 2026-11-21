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
