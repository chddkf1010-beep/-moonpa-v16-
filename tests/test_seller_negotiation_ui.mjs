import {test} from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';

test('negotiation UI loads, uses actual engine turn actions and protects signing',()=>{
 const ui=readFileSync(new URL('../market-negotiation-ui.js',import.meta.url),'utf8');
 const index=readFileSync(new URL('../index.html',import.meta.url),'utf8');
 const management=readFileSync(new URL('../management.js',import.meta.url),'utf8');
 assert.match(index,/market-negotiation-ui\.js/);
 assert.match(index,/market-negotiation\.css/);
 assert.match(management,/return transferTalkUI\.open\(info,fighter\)/);
 for(const name of ['transfer_talk_view','transfer_bargain','transfer_bargain_accept','transfer_bargain_decline']){
   assert.match(ui,new RegExp(name));
 }
 assert.match(ui,/조건 제안하기/);
 assert.match(ui,/역제안 수락 · 거래 확정/);
 assert.match(ui,/다시 제안하기/);
 assert.match(ui,/협상 종료/);
 assert.match(ui,/요구 조건 입력/);
 assert.match(ui,/memberText/);
 assert.match(ui,/data\.history/);
 assert.match(ui,/Number\.isSafeInteger/);
 assert.match(ui,/queueMicrotask\(\(\)=>management/);
 assert.doesNotMatch(ui,/transfer_accept/);
 const ctx={};vm.createContext(ctx);
 vm.runInContext(ui+'; globalThis.__found=typeof transferTalkUI.open;',ctx);
 assert.equal(ctx.__found,'function');
});
test('bridge and worker only autosave negotiating mutations',()=>{
 const bridge=readFileSync(new URL('../engine/pages_bridge.py',import.meta.url),'utf8');
 const worker=readFileSync(new URL('../engine-worker.mjs',import.meta.url),'utf8');
 assert.match(bridge,/path == 'transfer_talk_view'/);
 assert.match(bridge,/path == 'transfer_bargain'/);
 assert.match(bridge,/path == 'transfer_bargain_accept'/);
 assert.match(bridge,/path == 'transfer_bargain_decline'/);
 assert.match(worker,/'transfer_bargain','transfer_bargain_accept','transfer_bargain_decline'/);
});
