import assert from 'node:assert/strict';
import {test} from 'node:test';
import {readFileSync} from 'node:fs';
import {runInNewContext} from 'node:vm';
const source=readFileSync(new URL('../management.js',import.meta.url),'utf8');
const start=source.indexOf('function battlePerformance(');
const end=source.indexOf('function showLedger()',start);
assert.ok(start>0&&end>start);
const context={
  memberSortControl:(id,fields)=>Object.keys(fields).map(key=>'<button data-key="'+key+'">'+fields[key]+'</button>').join(''),
  sortMembers:(_,rows,key)=>[...rows].sort((a,b)=>(b[key]??0)-(a[key]??0)),
  portrait:f=>'<i data-portrait="'+f.portrait+'"></i>',
  escapeText:x=>String(x).replaceAll('<','&lt;'),
  number:n=>String(n)
};
runInNewContext(source.slice(start,end),context);
test('auto-resolved weekly 8v8 and 10v10 reports retain portraits, kills and shields',()=>{
  const fighters=[{id:1,side:0,name:'남궁검',portrait:'assets/portraits/diverse/v2_1_2.webp',
    damage:410,hit_taken:185,healing:0,kills:2,absorbed:44,shield_given:12},
    {id:21,side:1,name:'당문검',portrait:'',damage:175,hit_taken:325,healing:50,kills:1,absorbed:0,shield_given:0}];
  const html=context.battlePerformance('attack','점령전',fighters);
  assert.match(html,/남궁검/);
  assert.match(html,/당문검/);
  assert.match(html,/v2_1_2.webp/);
  assert.match(html,/보호막 흡수/);
  assert.match(html,/보호막 부여/);
  assert.match(html,/킬/);
  assert.match(html,/data-performance-rows="attack-0"/);
  assert.match(html,/data-performance-rows="attack-1"/);
  assert.match(html,/>410</);
  assert.match(html,/>44</);
  assert.match(html,/>2</);
});
test('legacy weekly battle reports without kill/shield keys still render zeros',()=>{
  const rows=[{id:1,side:0,name:'지산',portrait:'',damage:4,hit_taken:2,healing:0}];
  const html=context.battlePerformance('defense','방어전',rows);
  assert.match(html,/지산/);
  assert.match(html,/>0</);
  assert.equal(context.battlePerformance('none','none',[]),'');
});
