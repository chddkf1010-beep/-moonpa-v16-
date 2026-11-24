import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
import vm from 'node:vm';

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..');
const src=file=>readFileSync(resolve(root,file),'utf8');
const management=src('management.js'),growth=src('growth-ui.js');
const index=src('index.html');

function office(phase='ready'){
  const realm=vm.createContext({
    marketUI:{unreadCount:()=>0},
    state:{phase,season:2,month:4,month_weeks:4,cash:5794,guild:7,guild_name:'쌤문',tier:4,rank:3,
      roster:[{id:1,role:'수호형',name:'철무진',contract_end:2,injured:2}],
      zones:[{id:0,owner:7,name:'옥문소관',protected_until:112}],
      world_map:[{id:0,owner:7,name:'옥문소관',protected_until:112,weekly_net:295}],
      operations:{clock:112},
      treasury:{policy:'balanced',forecast:{income:890,fixed:720,garrison:15,zone:890}},
      league:{groups:[{tier:4,members:[{rank:3,name:'쌤문',player:true,score:39}]}]},
      week_report:{season:2,month:3,cash_change:620,tactical_defenses:[{zone:0,held:true}],
        members:[{id:1,ca_change:2.1,injured_before:1,injured:2}]}},
    fakePanel:{innerHTML:'',querySelectorAll:()=>[]},
    screen:{querySelector(selector){return selector==='#management-panel'?realm.fakePanel:null;}}
  });
  vm.runInContext(management,realm);
  return {realm,eval:source=>vm.runInContext(source,realm)};
}

test('five primary menus keep all eleven management pages reachable in their groups',()=>{
  const ui=office();
  const {groups}=ui.eval('campaignNavigation()');
  assert.deepEqual([...groups.matchAll(/data-tab="([^"]+)"/g)].map(row=>row[1]),
    ['office','roster','free','league','ledger']);
  assert.equal(ui.eval('CAMPAIGN_NAV.flatMap(group=>group[2]).length'),11);
  assert.match(ui.eval("currentTab='growth';campaignNavigation().sub"),/data-tab="growth" aria-pressed="true"/);
  assert.match(ui.eval("currentTab='honors';campaignNavigation().sub"),/data-tab="history" aria-pressed="true"/);
});

test('report locks write-action tabs and keeps monthly records available',()=>{
  const ui=office('report');
  const navigation=ui.eval('campaignNavigation()');
  assert.match(navigation.groups,/data-tab="free"[^>]*disabled/);
  assert.match(navigation.sub,/data-tab="warroom"[^>]*disabled/);
  assert.doesNotMatch(navigation.groups,/data-tab="ledger"[^>]*disabled/);
  assert.match(ui.eval('weeklyActions()'),/다음 달 진행/);
  ui.eval('showOffice()');
  assert.match(ui.realm.fakePanel.innerHTML,/월간 결산 확인/);
  assert.doesNotMatch(ui.realm.fakePanel.innerHTML,/data-defense/);
});

test('the office groups actual decisions and finance before the season dashboard',()=>{
  const ui=office();
  ui.eval('showOffice()');
  const html=ui.realm.fakePanel.innerHTML;
  assert.match(html,/방어 편성 필요[\s\S]*옥문소관 · 0\/8명/);
  assert.match(html,/계약 만료 예정 1명/);
  assert.match(html,/기본 예상 잔액[\s\S]*6,414냥/);
  assert.match(html,/이번 시즌 현황[\s\S]*쌤문[\s\S]*부상 2주 남음[\s\S]*295냥\/주/);
  assert.ok(html.indexOf('이번 달 결정할 일')<html.indexOf('이번 시즌 현황'));
  const hud=ui.eval('weeklyActions()');
  assert.match(hud,/이번 달 기본 예상 수지[\s\S]*\+620냥/);
  assert.match(hud,/다음 달 진행/);
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
  assert.match(index,/management\.js\?v=[a-zA-Z0-9_-]+/);
  assert.match(index,/growth-ui\.js\?v=20261122-reportnavfold-v2/);
  assert.match(index,/growth\.css\?v=20261122-reportnavfold-v2/);
});
