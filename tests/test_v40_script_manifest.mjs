import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync,existsSync} from 'node:fs';
import {resolve} from 'node:path';
const root=resolve(import.meta.dirname,'..');
test('all eleven main scripts are quoted, ordered and resolve to existing files',()=>{
 const html=readFileSync(resolve(root,'index.html'),'utf8');
 const tags=[...html.matchAll(/<script\b[^>]*>/g)].map(x=>x[0]);
 assert.equal(tags.length,11);
 const names=tags.map(tag=>{
  const m=tag.match(/^<script src="([a-zA-Z0-9_-]+\.js)\?v=[a-zA-Z0-9_-]+">$/);
  assert.ok(m,tag);assert.ok(existsSync(resolve(root,m[1])),m[1]);return m[1];
 });
 assert.deepEqual(names,['management.js','ledger-ui.js','roster-ui.js','prebattle-ui.js','honors-ui.js','market-ui.js','market-negotiation-ui.js','growth-ui.js','save-manager.js','world-map.js','game.js']);
});
