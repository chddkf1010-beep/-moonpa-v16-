import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {fileURLToPath} from 'node:url';
import {dirname,resolve} from 'node:path';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const management=readFileSync(resolve(root,'management.js'),'utf8');
const honors=readFileSync(resolve(root,'honors-ui.js'),'utf8');
const index=readFileSync(resolve(root,'index.html'),'utf8');

test('main tabs show sect chronicle but not the honor codex',()=>{
  const match=management.match(/const tabs=(\{[^;]+\});/);
  assert.ok(match,'management tabs must be defined');
  const tabs=Function('return ('+match[1]+')')();
  assert.equal(tabs.history,'문파 연대기');
  assert.ok(!Object.hasOwn(tabs,'honors'),'codex must not occupy a top-level tab');
  assert.equal(Object.keys(tabs).length,11,'one tab slot freed without hiding other pages');
  assert.ok(!Object.values(tabs).includes('강호 명예록'));
});

test('honor subpage remains accessible and keeps its parent tab selected',()=>{
  assert.match(management,/if\(currentTab==='history'\) honorsUI\.showHistory\(\)/);
  assert.match(management,/if\(currentTab==='honors'\) honorsUI\.showCodex\(\)/);
  assert.match(management,/key==='history'&&currentTab==='honors'/,
    'the parent chronicle should be selected while the inner codex is open');
  assert.match(honors,/id="honors-to-codex">강호 명예록<\/button>/);
  assert.match(honors,/#honors-to-codex'\)\.onclick=\(\)=>visit\('honors',target\)/);
  assert.match(honors,/#codex-to-history'\)\.onclick=\(\)=>visit\('history',target\)/);
  assert.match(honors,/\[data-honor-title\]/);
  assert.match(honors,/\[data-codex-season\]/);
});

test('navigation script loads with a fresh cache key',()=>{
  assert.match(index,/<script src="management\.js\?v=[a-zA-Z0-9_-]+"><\/script>/);
});
