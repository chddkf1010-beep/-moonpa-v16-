import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const management=readFileSync(resolve(root,'management.js'),'utf8');
const style=readFileSync(resolve(root,'style.css'),'utf8');
const index=readFileSync(resolve(root,'index.html'),'utf8');

const found=management.match(/function attributeTraitDisplay\(a\) \{[\s\S]*?\n\}/);
assert.ok(found,'trait display function must remain available');
const display=vm.runInNewContext('('+found[0]+')');

test('shows exact pre/post stats and positive trait delta',()=>{
  assert.equal(display({base:105.9,effective:111.9}),
    '105.9 → <strong>111.9</strong> <small class="trait-bonus">(+6)</small>');
  assert.equal(display({base:72.9,effective:76.2}),
    '72.9 → <strong>76.2</strong> <small class="trait-bonus">(+3.3)</small>');
  assert.equal(display({base:199.9,effective:200}),
    '199.9 → <strong>200</strong> <small class="trait-bonus">(+0.1)</small>');
});

test('without a trait bonus, shows only the effective number',()=>{
  assert.equal(display({base:105.9,effective:105.9}),'105.9');
  assert.equal(display({base:91,effective:91}),'91');
  assert.equal(display({base:200,effective:200}),'200');
});

test('UI labels the applied stat and keeps base and role contribution fields',()=>{
  assert.match(management,/<th>능력<\/th><th>기본<\/th><th>특성 적용 후<\/th><th>역할 반영 비율<\/th>/);
  assert.match(management,/<td>\$\{a\.base\}<\/td><td>\$\{attributeTraitDisplay\(a\)\}<\/td><td>\$\{a\.weight\}%<\/td>/);
  assert.doesNotMatch(management,/<th>특성 반영<\/th>/);
  assert.match(style,/\.trait-bonus\{color:/);
  assert.match(index,/management\.js\?v=trait-delta1/);
  assert.match(index,/style\.css\?v=trait-delta1/);
});
