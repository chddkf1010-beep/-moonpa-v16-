import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {join} from 'node:path';
import {test} from 'node:test';
import vm from 'node:vm';

const root=join(import.meta.dirname,'..');
const ledgerSource=readFileSync(join(root,'ledger-ui.js'),'utf8');
const rosterSource=readFileSync(join(root,'roster-ui.js'),'utf8');
const escapeText=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
function harness(){
  const context={
    money:value=>Number(value).toLocaleString('ko-KR')+'냥',
    escapeText,
    labels:{mission_gross_reward:'임무 보상',territory_gross:'구역 수입',
      weekly_wages:'문파원 주급',facility_upkeep:'시설 유지비'},
    portrait:()=>'<span class="portrait-icon"></span>',
    heroTag:()=>'<small class="hero-tag">네임드</small>',
    bindPortraits:()=>{},
    currentTab:'roster',
    management:()=>{},
    runMarket:()=>{},
    showMember:()=>{},
    showRoster:()=>{}
  };
  vm.createContext(context);
  vm.runInContext(ledgerSource,context,{filename:'ledger-ui.js'});
  vm.runInContext(rosterSource,context,{filename:'roster-ui.js'});
  return context;
}
const treasury={forecast:{fixed:85,garrison:15,zone:170,estate:12,sponsor:8,income:190,balance:90},debt:50};
const overview={cash:600,month:2,month_weeks:4,treasury};
const report={season:2,month:1,cash_before:270,cash:600,cash_change:330,
  income:850,expenses:520,entries:[
    {category:'mission_gross_reward',amount:700},{category:'territory_gross',amount:150},
    {category:'weekly_wages',amount:-380},{category:'facility_upkeep',amount:-140}
  ]};
const roster=[
  {id:1,name:'이청연',role:'검술',personal_title:'',ca:82.4,pa:140,lv:3,wage:22,contract_end:2,expedition:false,injured:0,notable:null},
  {id:2,name:'한비성',role:'수호',personal_title:'대호',ca:116.5,pa:135,lv:5,wage:45,contract_end:2,expedition:false,injured:2,notable:{rarity:'named',title:'불굴'}},
  {id:3,name:'남궁하린',role:'검술',personal_title:'',ca:93.5,pa:177,lv:4,wage:37,contract_end:5,expedition:true,injured:0,notable:{rarity:'legend',title:'청운검'}}
];

test('monthly finance hero uses actual sums, cash before/after, and no invented resources',()=>{
  const c=harness();
  c.report=report;c.overview=overview;
  const html=vm.runInContext('ledgerUI.render(report,overview)',c);
  assert.match(html,/2시즌 1개월차 실제 결산/);
  assert.match(html,/\+330냥/);
  assert.match(html,/\+850냥/);
  assert.match(html,/-520냥/);
  assert.match(html,/270냥/);
  assert.match(html,/600냥/);
  assert.match(html,/문파원 주급/);
  assert.match(html,/임무 보상/);
  assert.doesNotMatch(html,/세금|목재|충성도|피로도|재정 건강도 72/);
  assert.equal(report.cash-report.cash_before,report.cash_change);
});
test('before first month, finance shows labeled forecast not fictional settlement',()=>{
  const c=harness();
  c.overview=overview;
  const html=vm.runInContext('ledgerUI.render(null,overview)',c);
  assert.match(html,/기본 예상 수지/);
  assert.match(html,/\+360냥/);
  assert.match(html,/첫 월간 결산 전/);
  assert.doesNotMatch(html,/결산 전후 현금 변동/);
});
test('finance health derives from cash coverage, not arbitrary score',()=>{
  const c=harness();c.weeks=[3.9,4,7.9,8,13];
  const levels=Array.from(vm.runInContext('weeks.map(w=>ledgerUI.status(w).label)',c));
  assert.deepEqual(levels,['위험','주의','주의','안정','안정']);
});
test('CA PA and rarity/status filters compose and support sorting',()=>{
  const c=harness();c.roster=roster;
  c.criteria={query:'검술',role:'검술',rarity:'legend',status:'expedition',
    caMin:'90',paMin:'170',gapMin:'80',sort:'gap'};
  const selected=Array.from(vm.runInContext('rosterUI.filterRows(roster,criteria).map(m=>m.id)',c));
  assert.deepEqual(selected,[3]);
  c.criteria={query:'',role:'all',rarity:'all',status:'all',
    caMin:'',paMin:'',gapMin:'',sort:'ca'};
  assert.deepEqual(Array.from(vm.runInContext('rosterUI.filterRows(roster,criteria).map(m=>m.id)',c)),[2,3,1]);
});
test('roster renders real stats, Korean status badges, search, and detail hooks',()=>{
  const c=harness();c.roster=roster;
  const html=vm.runInContext('rosterUI.render(roster,2)',c);
  assert.match(html,/이청연/);
  assert.match(html,/116\.5/);
  assert.match(html,/177\.0/);
  assert.match(html,/부상 2주/);
  assert.match(html,/원정 중/);
  assert.match(html,/data-roster-query/);
  assert.match(html,/data-roster-filter="paMin"/);
  assert.match(html,/data-roster-detail="3"/);
  assert.match(html,/압축 보기/);
  assert.doesNotMatch(html,/충성도<\/th>|피로도<\/th>/);
  assert.equal(roster[0].ca,82.4); // render never mutates source
});
test('roster escapes hostile fighter names',()=>{
  const c=harness();
  c.roster=[{...roster[0],name:'<img src=x onerror=alert(1)>'}];
  const html=vm.runInContext('rosterUI.render(roster,2)',c);
  assert.match(html,/&lt;img src=x/);
  assert.doesNotMatch(html,/<img src=x onerror/);
});
