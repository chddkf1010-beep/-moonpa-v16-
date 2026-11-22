import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const src=file=>readFileSync(resolve(root,file),'utf8');
const management=src('management.js'),growth=src('growth-ui.js');
const index=src('index.html');

test('ready and report phases keep all eleven top-level menu entries visible',()=>{
  const match=management.match(/const tabs=(\{[^;]+\});/);
  assert.ok(match);
  const tabs=Function('return ('+match[1]+')')();
  assert.equal(Object.keys(tabs).length,11);
  assert.equal(tabs.history,'문파 연대기');
  assert.ok(!('honors' in tabs),'honor codex remains nested');
  assert.match(management,/\['ready','report'\]\.includes\(state\.phase\)\|\|key===currentTab/);
  assert.doesNotMatch(management,/state\.phase==='ready'\|\|key===currentTab\|\|\(state\.phase==='report'/);
});

test('report locks write-action tabs but allows other pages to remain browsable',()=>{
  assert.match(management,/state\.phase==='report'&&\['warroom','week','free','scout'\]\.includes\(key\)/);
  assert.match(management,/locked\?'disabled title=/);
  assert.match(management,/\['office','league','history','honors','growth','roster','ledger','facility'\]\.includes\(currentTab\)/);
  assert.match(management,/shortfall\|\|state\.phase!=='ready'/);
  assert.match(management,/data-treasury-policy[^>]+state\.phase==='ready'/);
  assert.match(management,/if\(state\.phase!=='ready'\) panel\(\)\.querySelectorAll\('\[data-office="week"\]/);
  assert.match(management,/key==='history'&&currentTab==='honors'/);
});

test('optional bulk training helper opens only when asked and never commits immediately',()=>{
  assert.match(growth,/plannerExpanded=false/);
  assert.match(growth,/plannerExpanded\?\x60<div id="growth-training-panel">/);
  assert.match(growth,/id="growth-training-toggle" aria-expanded="/);
  assert.match(growth,/plannerExpanded=!plannerExpanded;/);
  assert.match(growth,/draft\.assignments\[fid\]='training'/);
  assert.doesNotMatch(growth,/v11-3 · 주간 운영 배치안 연동/);
  assert.match(growth,/주간 결산 전에는 비용이 발생하지 않습니다/);
});

test('both updated UIs invalidate old cached scripts',()=>{
  assert.match(index,/management\.js\?v=20261122-reportnavfold-v2/);
  assert.match(index,/growth-ui\.js\?v=20261122-reportnavfold-v2/);
  assert.match(index,/growth\.css\?v=20261122-reportnavfold-v2/);
});
