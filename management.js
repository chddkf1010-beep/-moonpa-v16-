let currentTab = 'office';
let leagueTier = null;
let draft = {clock:'', assignments:{}, zone:null};
const number = value => Number(value).toLocaleString('ko-KR');
const money = value => `${number(value)}냥`;
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const decisions = {
  replacement_required:'상대가 같은 역할의 즉시전력 또는 조건에 맞는 후계자를 요구합니다.',
  signed:'계약 완료', unavailable:'후보가 시장에 없습니다', roster_full:'임시 정원까지 가득 찼습니다',
  insufficient_cash:'계약금과 운영예비금이 부족합니다', outstanding_debt:'미지급 채무가 있습니다',
  declined_this_week:'이번 주 제안을 거절했습니다', market_closed:'전투 또는 주간 운영 중입니다',
  accepted:'수락 가능한 조건입니다', counter:'상대 문파가 조건을 변경해 제안했습니다',
  refused:'상대 문파가 거절했습니다', unfunded:'자금 또는 시장 가격 한도를 초과했습니다',
  roster:'거래 후 정원 조건을 충족하지 못합니다', locked:'이번 시즌에 이적한 문파원입니다',
  invalid:'제안 조건을 다시 확인하세요'
};
const applications = {auto:'자동 배치',training:'훈련',mission1:'수익 임무 1',mission2:'수익 임무 2',expedition1:'장기 임무 1',expedition2:'장기 임무 2',elite:'정예 임무',
  rest:'휴식',defend:'구역 방어',attack:'점령전'};
const labels = {estate_income:'장원 수입', facility_upgrade:'건축물 승급', territory_gross:'구역 수입', territory_direct_maintenance:'구역 유지비',
  territory_scale_overhead:'구역 관리비', weekly_wages:'문파원 주급', hall_upkeep:'문파 유지비',
  mission_gross_reward:'임무 보상', mission_preparation:'임무 준비비',
  expedition_preparation:'원정 준비비', expedition_upkeep:'원정 유지비',
  expedition_reward:'원정 최종 보상',elite_preparation:'정예 임무 준비비',elite_reward:'정예 임무 보상', paid_training:'훈련비',
  paid_investment:'육성 투자', fa_signing_fee:'계약금', transfer_fee:'이적료',
  mentor_fee:'사부 지도비', league_sponsor:'리그 후원금',
  garrison_cost:'주둔 비용', no_territory_livelihood:'생계 임무 수입'};


const TREASURY_POLICY_LABELS={save:'자금 비축',balanced:'균형 투자',growth:'집중 육성'};
function treasuryPolicyControl() {
  const t=state.treasury;
  return `<label class="treasury-policy-label">주간 자금 운용
    <select data-treasury-policy aria-label="주간 자금 운용 정책">
      ${Object.entries(TREASURY_POLICY_LABELS).map(([key,label])=>`<option value="${key}" ${key===t.policy?'selected':''}>${label}</option>`).join('')}
    </select></label>
    <small class="muted-copy">정책에 따른 추가 육성 투자율 최대 ${Math.round(t.rate*100)}% · 보호 기준 ${t.reserve_weeks}주치 ${money(t.reserve)}.
    급여·필수 훈련비·부채 상환은 정책과 관계없이 처리됩니다.</small>`;
}
function treasuryForecast() {
  const f=state.treasury.forecast;
  return `<div class="treasury-forecast">
    <p>보유 구역 유지 가정 · 주간 예상 수입 <strong>${money(f.income)}</strong>
      <small>구역 순수익 ${money(f.zone)} · 장원 ${money(f.estate)} · 후원금 ${money(f.sponsor)}</small></p>
    <p>고정 지출 <strong>${money(f.fixed+f.garrison)}</strong>
      <small>급여·유지비 ${money(f.fixed)} · 기본 주둔비 추정 ${money(f.garrison)}</small></p>
    <p>기본 주간 손익 <strong>${f.balance>=0?'+':''}${money(f.balance)}</strong></p>
    <small>점령·방어 결과, 임무 보상, 부채 상환, 훈련비 및 추가 투자는 제외한 참고치입니다.</small>
  </div>`;
}

function panel() { return screen.querySelector('#management-panel'); }
function notice(message) { error.textContent = message; }
function heroTag(f) {return f?.notable ? `<small class="hero-tag ${f.notable.rarity==='legend'?'hero-legend':'hero-named'}">${f.notable.rarity==='legend'?'전설':'네임드'} · ${escapeText(f.notable.title)}</small>` : '';}
function heroDescription(f) {return f?.notable?`${escapeText(f.notable.skill)} · ${escapeText(f.notable.description)}`:'';}
function stats() {
  return `<div class="summary-strip">
    <div><small>보유금</small><strong>${money(state.cash)}</strong></div>
    <div><small>문파원</small><strong>${state.roster.length}명</strong></div>
    <div><small>보유 구역</small><strong>${state.zones.filter(z=>z.owner===state.guild).length}곳</strong></div>
    <div><small>리그 순위</small><strong>${state.tier}부 ${state.rank}위</strong></div>
  </div>`;
}
async function management(message = '') {
  if (state.dead && !state.week_report) {screen.textContent='문파가 해체되었습니다.';return;}
  notice(message);
  if (state.phase==='tutorial'||state.phase==='draft') {showOpening();return;}
  if (state.phase==='fa') currentTab='free';
  if (state.phase==='report' && !['history','honors'].includes(currentTab)) currentTab='ledger';
  document.querySelector('#phase').textContent='문파 운영';
  screen.onchange=null;
  const clock = `${state.season}:${state.week}`;
  if (draft.clock!==clock) draft={clock,assignments:{},zone:null};
  const tabs={office:'운영실',league:'강호 리그',history:'문파 연대기',honors:'강호 명예록',warroom:'8대8 전술 편성',week:'주간 운영',roster:'문파원 명부',ledger:'주간 보고',free:'낭인 시장',scout:'타 문파 스카우트',facility:'건축물'};
  screen.innerHTML = `${stats()}<p class="muted-copy">이번 시즌 유행 병법: <strong>${escapeText(state.season_trend.name)}</strong> · ${escapeText(state.season_trend.description)} (다음 시즌에 변경)</p><nav class="management-tabs" aria-label="문파 운영">
    ${Object.entries(tabs).filter(([key])=>state.phase==='ready'||key===currentTab||(state.phase==='report'&&['ledger','history','honors'].includes(key))).map(([key,name])=>`<button data-tab="${key}" aria-pressed="${key===currentTab}">${name}</button>`).join('')}</nav>
    <div id="management-panel"></div>`;
  screen.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{
    if(busy) return;
    currentTab=button.dataset.tab;
    management();
  });
  if(currentTab==='office') showOffice();
  if(currentTab==='league') showLeague();
  if(currentTab==='history') honorsUI.showHistory();
  if(currentTab==='honors') honorsUI.showCodex();
  if(currentTab==='warroom') prebattleUI.load();
  if(currentTab==='week') showWeek();
  if(currentTab==='roster') showRoster();
  if(currentTab==='ledger') showLedger();
  const sort=panel().querySelector('[data-sort]');
  if(sort&&['week','roster'].includes(currentTab)){
    sort.onchange=()=>{rosterOrder=sort.value;management();};
    panel().querySelector('[data-sort-direction]').onclick=()=>{rosterAscending=!rosterAscending;management();};
  }
  if(currentTab==='facility') showFacilities();
  bindPortraits();
  panel().querySelectorAll('[data-member]').forEach(button=>button.onclick=()=>
    runMarket('member',{id:Number(button.dataset.member)},showMember));
  if(currentTab==='free') await runMarket('free_agents',{},showFree);
  if(currentTab==='scout') await runMarket('scout',{},showScout);
  screen.onchange=event=>{
    if(event.target.matches('[data-treasury-policy]'))
      request('treasury_policy',{policy:event.target.value});
  };
}

function advancePhase() {
  currentTab='office';
  request('advance_phase',{phase:state.phase});
}

function showOpening() {
  document.querySelector('#phase').textContent=state.phase==='tutorial'?'문파 창설':'신인 드래프트';

  if(state.phase==='tutorial') {
    screen.innerHTML=`${stats()}<section class="parchment founding-shell">
      <small>강호 입문 · 제4부 리그</small><h2>나의 문파 창설</h2>
      <p>이름과 운영 방침을 정하세요. 4부 리그는 총 8개 문파로 구성되며, 기존 문파의 자리를 승계해 시작합니다.</p>
      <form id="found-sect" class="founding-form">
        <label>문파 이름 (2~12자)<input id="sect-name" name="sect-name" type="text" minlength="2" maxlength="12"
          required value="${escapeText(state.guild_name)}" autocomplete="off"></label>
        <label>문파 운영 방침<select id="sect-strategy">
          <option value="balanced">균형 운영 · 훈련·임무·점령을 고루 수행</option>
          <option value="growth">육성 중심 · 수련과 유망주 확보 우선</option>
          <option value="transfer">영입 중심 · 이적시장과 전력 보강 적극 활용</option>
          <option value="conquest">정복 중심 · 구역 점령전 및 세력 확대 중시</option>
          <option value="baseline">안정 운영 · 재정과 기본 활동 중심</option>
        </select></label>
        <p class="muted-copy">선택한 방침은 기본 운영 및 투자 기준에 영향을 줍니다. 문파명은 같은 세계의 다른 문파와 중복될 수 없습니다.</p>
        <div class="controls"><button type="button" id="show-founders">초기 문파원 ${state.roster.length}명 보기</button>
          <button type="submit" class="primary">문파 창설 · 신인 드래프트 시작</button></div>
      </form><div id="founders" hidden></div></section>`;
    screen.querySelector('#sect-strategy').value=state.strategy||'balanced';
    screen.querySelector('#show-founders').onclick=()=>{
      const box=screen.querySelector('#founders');
      box.hidden=!box.hidden;
      if(!box.hidden){box.innerHTML=`<section class="wood">${rosterTable()}</section>`;
        box.querySelectorAll('.member-link').forEach(button=>button.disabled=true);
        bindPortraits();}
    };
    screen.querySelector('#found-sect').onsubmit=event=>{
      event.preventDefault();
      const name=screen.querySelector('#sect-name').value.trim();
      const strategy=screen.querySelector('#sect-strategy').value;
      request('found_sect',{name,strategy});
    };
    return;
  }
  const draft=state.draft;
  const sorted=[...draft.candidates].sort((a,b)=>b.pa-a.pa||b.ca-a.ca);
  screen.innerHTML=`${stats()}<section class="wood"><h2>신인 드래프트 · ${draft.round}/5라운드</h2>
    <p>라운드 ${draft.position}번째 순번 · 지명 ${draft.picks.length}/5명</p>
    <p class="muted-copy">이번 시즌 계약 · 계약금 없음. 다른 문파도 순서대로 지명해.</p>
    ${draft.picks.length?`<p>지명 완료 · ${draft.picks.map(escapeText).join(', ')}</p>`:''}
    <div class="controls"><button id="draft-pass">이번 순번 넘기기</button></div>
    <div class="table-scroll"><table><thead><tr><th>신인</th><th>역할</th><th>나이</th><th>전력 / 잠재력</th><th>주급</th><th>선택</th></tr></thead><tbody>
    ${sorted.map(f=>`<tr><th><span class="member-face">${portrait(f)}</span>${escapeText(f.name)}</th><td>${f.role}</td><td>${f.age}</td><td>${f.ca} / ${f.pa}</td><td>${money(f.wage)}</td>
    <td><button data-pick="${f.id}" ${draft.roster_full?'disabled':''}>지명</button></td></tr>`).join('')}</tbody></table></div></section>`;
  const pick=id=>request('draft_pick',{season:state.season,round:draft.round,id});
  screen.querySelector('#draft-pass').onclick=()=>pick(null);
  screen.querySelectorAll('[data-pick]').forEach(button=>button.onclick=()=>pick(Number(button.dataset.pick)));
}

function showFacilities() {
  const status=(f,next=false)=>{
    const level=next?f.level+1:f.level;
    const value=next?f.next_value:f.current_value;
    return f.id==='training'?`훈련 성장 +${value}%`:f.id==='estate'?
      `주간 수입 +${value}냥 · 낭인 계약금 ${4*level}% 할인`:`부상 발생 확률 ${value}% 감소`;
  };
  panel().innerHTML=`<section class="wood"><h2>건축물 관리</h2><div class="facility-grid">
    ${state.facilities.map(f=>`<article class="unit"><h3>${f.name} · Lv ${f.level}/${f.max}</h3>
    <p>현재 · ${status(f)}</p>${f.next_cost==null?'<small>최고 레벨</small>':
    `<p>다음 · ${status(f,true)}</p>${f.id==='estate'?`<p class="muted-copy">추가 수입 +${money(f.next_value-f.current_value)}/주 · 투자금 회수 약 ${Math.ceil(f.next_cost/(f.next_value-f.current_value))}주 (계약금 할인 효과 제외)</p>`:''}
    <button data-upgrade="${f.id}" ${state.cash<f.next_cost?'disabled':''}>승급 · ${money(f.next_cost)}</button>`}</article>`).join('')}
    </div></section>`;
  panel().querySelectorAll('[data-upgrade]').forEach(button=>button.onclick=()=>{
    if(confirm(button.textContent+'을 진행할까요?')) request('upgrade',{id:button.dataset.upgrade});
  });
}
const rosterSorts={name:'이름',role:'역할',ca:'현재 전력',pa:'잠재력',age:'나이',lv:'레벨',contract_end:'계약 만료',wage:'주급'};
let rosterOrder='ca', rosterAscending=false, freeOrder='pa', freeAscending=false;
function sortControl(fields,key,ascending) {
  return `<div class="inline-controls"><label>정렬 <select data-sort>
    ${Object.entries(fields).map(([value,label])=>`<option value="${value}" ${key===value?'selected':''}>${label}</option>`).join('')}
    </select></label><button type="button" data-sort-direction>${ascending?'오름차순':'내림차순'}</button></div>`;
}

function sortedMembers(members,key,ascending) {
  return [...members].sort((a,b)=>{
    const diff=typeof a[key]==='number'?a[key]-b[key]:String(a[key]).localeCompare(String(b[key]),'ko');
    return (ascending?diff:-diff)||a.id-b.id;
  });
}

function zoneMap() {
  return `<section class="wood zone-map"><h3>${state.tier}부 구역 지도</h3>
    <div class="zone-legend"><span>● 보유</span><span>◆ 공격 가능</span><span>■ 보호 중</span></div>
    <div class="zone-land" aria-label="구역 지도">${state.zones.map(z=>{
      const owned=z.owner===state.guild;
      const selected=owned?draft.defenseZone===z.id:draft.zone===z.id;
      return `<button type="button" title="구역 ${z.id} · ${escapeText(z.owner_name)}" data-zone-tile="${z.id}" class="${owned?'owned':z.selectable?'open':'protected'}" aria-pressed="${selected}">
        <strong>${owned?'●':z.selectable?'◆':'■'} 구역 ${z.id}</strong><small>${escapeText(z.owner_name)}</small><small>${escapeText(z.terrain.name)} · ${escapeText(z.tactic.name)} 전술</small><b>${money(z.value)}</b></button>`;
    }).join('')}</div>
    <div id="zone-detail" class="zone-detail" aria-live="polite">구역에 커서를 올리거나 선택하면 소유 문파와 수입을 볼 수 있어.</div>
  </section>`;
}

function teamForOffer(roster,assignments,key,offer) {
  const roles=offer.suggested_roles||offer.recommended_roles||[];
  const available=roster.filter(f=>!f.injured&&!f.expedition&&
    [undefined,'auto',key].includes(assignments[f.id]));
  const current=available.filter(f=>assignments[f.id]===key);
  const limit=offer.max_members??5;
  if(current.length>limit) return null;
  if(offer.saga && !available.some(f=>f.id===offer.saga_leader)) return null;
  const team=[...current];
  if(offer.saga&&!team.some(f=>f.id===offer.saga_leader)){
    if(team.length>=limit) return null;
    team.push(available.find(f=>f.id===offer.saga_leader));
  }
  const target=Math.min(limit,Math.max(3,offer.min_members??3));
  while(team.length<target){
    const covered=new Set(team.flatMap(f=>[f.role,f.role_id]));
    const priority=f=>Number(roles.some(role=>!covered.has(role)&&(role===f.role||role===f.role_id)));
    const next=available.filter(f=>!team.includes(f)).sort((a,b)=>priority(b)-priority(a)||b.ca-a.ca||a.id-b.id)[0];
    if(!next) break;
    team.push(next);
  }
  return team.length>=(offer.min_members??3)?team:null;
}

function rosterTable(assignments=false) {
  return `<div class="table-scroll"><table><thead><tr><th>문파원</th><th>역할</th><th>CA / PA</th><th>나이</th><th>레벨</th><th>남은 계약</th><th>상태</th>${assignments?'<th>이번 주 배치</th>':''}</tr></thead><tbody>
  ${sortedMembers(state.roster,rosterOrder,rosterAscending).map(f=>`<tr><th scope="row"><span class="member-face">${portrait(f)}</span><button class="member-link" data-member="${f.id}">${escapeText(f.name)}</button> ${heroTag(f)}</th><td>${f.role}</td><td>${f.ca} / ${f.pa}</td><td>${f.age}</td><td>${f.lv}</td><td>${Math.max(0,f.contract_end-state.season+1)}시즌</td>
  <td>${f.expedition?'장기 임무 파견 중':(f.injured?`<span class="bad">부상 ${f.injured}주</span>`:'정상')}</td>${assignments?`<td><select class="assignment" data-id="${f.id}" aria-label="${escapeText(f.name)} 배치" ${f.expedition?'disabled':''}>
  ${(f.expedition?[['auto','원정 파견 중']]:Object.entries(applications).filter(([key])=>!f.injured || ['auto','rest'].includes(key))).map(([key,text])=>
    `<option value="${key}" ${draft.assignments[f.id]===key?'selected':''}>${text}</option>`).join('')}</select></td>`:''}</tr>`).join('')}
  </tbody></table></div>`;
}
function showRoster() {
  panel().innerHTML=`<section class="wood"><h2>문파원 명부</h2>${sortControl(rosterSorts,rosterOrder,rosterAscending)}${rosterTable()}</section>`;
}
const attributes = {strength:'근력', defense:'방어', stamina:'체력', agility:'민첩',
  inner_power:'내공', sorcery:'술법', insight:'통찰', willpower:'정신력'};

function showMember(f) {
  panel().innerHTML=`<div class="management-grid"><section class="wood">
  <div class="controls"><button id="member-back">명부로</button></div>
  <h2><span class="member-face">${portrait(f)}</span>${escapeText(f.name)} ${heroTag(f)}</h2>${f.notable?`<p class="muted-copy"><strong>고유 절기 ${escapeText(f.notable.skill)}</strong> — ${escapeText(f.notable.description)}</p><p class="muted-copy">전설 성장 기록: 승리 ${f.notable.progress?.wins||0}회 · 처치 ${f.notable.progress?.kills||0}명</p>`:''}<p>${f.role} · ${f.age}세 · Lv ${f.level} · 주급 ${money(f.wage)} · 계약 ${f.remaining}시즌 남음</p>
  ${!f.notable?`<p class="muted-copy">전설 성장 목표: Lv ${f.level}/10 · 점령전 ${f.legend_progress?.wins||0}/12승 · 적 처치 ${f.legend_progress?.kills||0}/20명</p>`:''}
  ${f.appearance?`<p class="muted-copy">외형: ${escapeText(f.appearance.build)} 체형 · ${escapeText(f.appearance.impression)} 인상 · ${f.appearance.details.map(escapeText).join(' · ')}</p>`:''}
  <div class="ledger-head"><span>현재 전력 <b>${f.ca}</b></span><span>잠재력 <b>${f.pa}</b></span></div>
  <table><thead><tr><th>능력</th><th>기본</th><th>특성 반영</th><th>역할 반영 비율</th></tr></thead><tbody>
  ${f.attributes.map(a=>`<tr><th scope="row">${attributes[a.key]}</th><td>${a.base}</td><td>${a.effective}</td><td>${a.weight}%</td></tr>`).join('')}</tbody></table>
  </section><aside class="wood"><h2>무공 수련</h2><p>남은 포인트 <strong>${f.points}</strong></p>
  <p class="muted-copy">장착 <span id="slot-count">${f.equipped.length}</span>/${f.slots} · 레벨마다 무공 포인트 1점, 투자 단계당 내공 소모 −2.</p>
  <p class="muted-copy">임무에서 지원·방어 무공은 성공률을 보조해.</p>
  ${f.skills.map(k=>`<article class="skill-node"><h3>${k.secret?'[비전 무공] ':''}${k.name} ${k.rank}/3</h3><p>${escapeText(k.note||'공격 배율 '+k.power)}</p>
  <small>해금 Lv ${k.level} · 내공 ${Math.max(0,k.cost-2*k.rank)} · 재사용 대기 ${k.cooldown}라운드</small>
  <label><input type="checkbox" data-equip="${k.id}" ${f.equipped.includes(k.id)?'checked':''} ${f.level<k.level?'disabled':''}> 장착</label>
  <button data-train="${k.id}" ${k.rank>=3||f.level<k.level||!f.points?'disabled':''}>1점 투자</button></article>`).join('')}
  <button id="save-skills" class="primary">장착 저장</button></aside></div>`;
  if(f.epithets?.length){
    const badge=document.createElement('section');badge.className='personal-story';
    const title=document.createElement('h3');title.textContent='무인 별호 · 영구 보유';badge.append(title);
    for(const achievement of f.epithets){
      const note=document.createElement('p');note.className='muted-copy';
      note.textContent=achievement.name+' ['+achievement.grade+'] ×'+achievement.count+
        ' · 획득 '+achievement.seasons.join(', ')+'시즌';badge.append(note);
    }
    panel().querySelector('section.wood').append(badge);
  }
  const heritage=document.createElement('p');
  heritage.className='muted-copy';
  heritage.textContent='기연 비급 '+(f.kiyun_manuals||0)+'개 · 보유 특성 '+(f.traits||[]).length+
    '개 · 동료 인연 '+(f.bonds||[]).map(x=>x.name+' '+x.value).join(', ');
  panel().querySelector('section.wood').append(heritage);
  if(f.personal){
    const p=f.personal;
    const personal=document.createElement('section');
    personal.className='personal-story';
    const heading=document.createElement('h3');heading.textContent='개인 서사 · '+p.title;
    const origin=document.createElement('p');
    origin.textContent=p.origin+' · '+p.history+' 목표: '+p.goal;
    const record=document.createElement('small');
    record.textContent='정예 임무 성공 '+p.elite_wins+'회'+
      (p.saga?' · '+p.saga.line+' ('+p.saga.status_label+
        ', '+p.saga.chapter+'/3장)':'');
    personal.append(heading,origin,record);
    for(const event of (p.events||[]).slice(-4).reverse()){
      const note=document.createElement('p');
      note.className='muted-copy';
      note.textContent=event.season+'시즌 '+event.week+'주 · '+event.title+
        ' · '+event.outcome+' — '+event.story;
      personal.append(note);
    }
    panel().querySelector('section.wood').append(personal);
  }
  const chosen=()=>[...panel().querySelectorAll('[data-equip]:checked')].map(e=>e.dataset.equip);
  panel().onchange=()=>{
    const count=chosen().length;
    panel().querySelector('#slot-count').textContent=count;
    panel().querySelector('#save-skills').disabled=count>f.slots;
  };
  panel().querySelector('#save-skills').onclick=()=>runMarket('equip',{id:f.id,skills:chosen()},r=>{
    state=r.state;showMember(r.detail);notice('무공 장착 저장 완료');
  });
  panel().querySelector('#member-back').onclick=()=>{currentTab='roster';management();};
  panel().querySelectorAll('[data-train]').forEach(button=>button.onclick=()=>
    runMarket('train_skill',{id:f.id,skill:button.dataset.train},showMember));
}
function exposedZones() {
  return state.zones.filter(z=>z.owner===state.guild && z.protected_until<=state.operations.clock);
}


function showLeague() {
  const league=state.league;
  if(!league?.groups?.length){
    panel().innerHTML='<section class="wood"><p>리그 정보를 불러오지 못했습니다.</p></section>';
    return;
  }
  if(!league.groups.some(group=>group.tier===leagueTier))leagueTier=league.current_tier;
  const group=league.groups.find(group=>group.tier===leagueTier);
  const player=group.members.find(member=>member.player);
  panel().innerHTML=`<section class="wood league-page">
    <div class="league-head"><div><small>${league.season}시즌 · ${league.week}주차</small>
      <h2>강호 리그 · ${leagueTier}부</h2>
      <p class="muted-copy">같은 부 8개 문파가 시즌 점수로 경쟁합니다. 상대 문파를 선택해 전력과 보유 구역을 확인할 수 있습니다.</p></div>
      <button type="button" id="league-office">운영실로 돌아가기</button></div>
    <nav class="league-tiers" aria-label="리그 부 선택">${league.groups.map(x=>`<button type="button" data-tier="${x.tier}" aria-pressed="${x.tier===leagueTier}">${x.tier}부${x.tier===state.tier?' · 소속':''}</button>`).join('')}</nav>
    <div class="league-recap"><strong>${player?escapeText(player.name)+' · '+player.rank+'위':'다른 부 문파 분석'}</strong>
      <span>${player?'내 점수 '+player.score+'점 · 전력 '+player.strength:'다른 부의 문파도 상세 정보를 확인할 수 있습니다.'}</span></div>
    <div class="table-scroll"><table class="league-table"><thead><tr>
      <th>순위</th><th>문파</th><th>점수</th><th>평균 전력</th><th>구역</th><th>문파원</th><th>시즌 전망</th>
    </tr></thead><tbody>${group.members.map(row=>`<tr class="${row.player?'player-row':''}">
      <td><strong>${row.rank}</strong></td>
      <th scope="row"><button class="member-link" data-sect="${row.id}">${escapeText(row.display_name||row.name)}${row.player?' (내 문파)':''}</button></th>
      <td>${row.score}</td><td>${row.strength}</td><td>${row.zones}곳</td><td>${row.roster}명</td>
      <td><span class="league-outlook">${escapeText(row.outlook)}</span></td></tr>`).join('')}</tbody></table></div>
    <details class="league-rules"><summary>승격·강등 규칙</summary><p>${escapeText(league.rule)}</p>
      <p>승강 플레이오프는 상대 문파와의 전력 비교 및 확률 판정으로 결정됩니다. 현재 순위는 시즌 종료 때까지 변할 수 있습니다.</p></details>
  </section>`;
  panel().querySelector('#league-office').onclick=()=>{currentTab='office';management();};
  panel().querySelectorAll('[data-tier]').forEach(button=>button.onclick=()=>{
    leagueTier=Number(button.dataset.tier);showLeague();
  });
  panel().querySelectorAll('[data-sect]').forEach(button=>button.onclick=()=>{
    runMarket('sect_profile',{id:Number(button.dataset.sect)},showSectProfile);
  });
}

function showSectProfile(data) {
  const owned=data.zones||[];
  const attackable=owned.find(zone=>zone.selectable);
  panel().innerHTML=`<section class="wood sect-profile">
    <div class="league-head"><div><small>${data.tier}부 ${data.rank}위 · ${escapeText(data.outlook)}</small>
      <h2>${escapeText(data.display_name||data.name)}${data.player?' · 내 문파':''}</h2>
      <p>강호 명성 ${data.renown} · 상위 5인 평균 전력 ${data.strength} · 시즌 점수 ${data.score}</p></div>
      <button id="sect-back" type="button">리그 순위로</button></div>
    <div class="sect-profile-stats">
      <div><small>문파원</small><strong>${data.roster_count}명</strong></div>
      <div><small>보유 구역</small><strong>${data.zone_count}곳</strong></div>
      <div><small>재정 여력</small><strong>${escapeText(data.treasury)}</strong></div>
      <div><small>주간 급여</small><strong>${money(data.weekly_wages)}</strong></div></div>
    <p class="muted-copy">다른 문파의 재정은 주간 고정비 대비 보유금 기준의 구간으로 표시합니다. 잠재력과 숨겨진 영입 성향은 공개하지 않습니다.</p>
    <div class="sect-record"><span>점령전 ${data.record.attack_wins}/${data.record.attacks}승</span>
      <span>방어 성공 ${data.record.defense_wins}회</span>
      <span>임무 성공 ${data.record.mission_wins}/${data.record.missions}건</span>
      <span>승격 ${data.record.promoted}회 · 강등 ${data.record.relegated}회</span>
      <span>1부 우승 ${data.record.championships}회</span></div>
    <h3>보유 구역</h3><div class="sect-zones">${owned.map(z=>
      `<span>구역 ${z.id} · ${escapeText(z.terrain.name)} · 수비 ${escapeText(z.tactic.name)} · 주간 순수익 기준 ${money(z.value)}${z.selectable?' · 점령 가능':''}</span>`).join('')||'<p>현재 보유 구역이 없습니다.</p>'}</div>
    <div class="controls"><button id="sect-history" type="button">문파 연대기</button>${!data.player?`<button id="sect-scout" type="button" ${data.market_open?'':'disabled'}>이 문파에서 스카우트</button>`:''}
      ${attackable&&state.phase==='ready'?`<button id="sect-attack" type="button" class="primary">구역 ${attackable.id} 점령전 편성</button>`:''}</div>
    <h3>소속 문파원</h3>
    <div class="table-scroll"><table><thead><tr><th>이름</th><th>역할</th><th>나이</th><th>전력</th><th>레벨</th><th>주급</th><th>계약 만료</th></tr></thead>
      <tbody>${data.members.map(f=>`<tr><th scope="row"><span class="member-face">${portrait(f)}</span>${escapeText(f.name)} ${heroTag(f)}</th><td>${escapeText(f.role)}</td>
        <td>${f.age}</td><td>${f.ca}</td><td>${f.level}</td><td>${money(f.wage)}</td>
        <td>${f.contract_end}시즌${f.injured?' · 부상':''}</td></tr>`).join('')}</tbody></table></div>
  </section>`;
  panel().querySelector('#sect-back').onclick=showLeague;
  panel().querySelector('#sect-history').onclick=()=>honorsUI.visit('history',data.id);
  panel().querySelector('#sect-scout')?.addEventListener('click',()=>{
    currentTab='scout';
    runMarket('scout',{seller:data.id},info=>showScout(info,data.id));
  });
  panel().querySelector('#sect-attack')?.addEventListener('click',()=>{
    draft.zone=attackable.id;
    currentTab='week';management();
    panel().querySelector('#target-zone')?.focus();
  });
}

function showOffice() {
  const report=state.week_report;
  const zones=exposedZones();
  const expiring=state.roster.filter(f=>f.contract_end===state.season);
  const ready=state.roster.filter(f=>!f.injured&&!f.expedition);
  const thin=[...new Map(state.roster.map(f=>[f.role_id,f.role]))]
    .map(([id,role])=>({role,count:ready.filter(f=>f.role_id===id).length}))
    .filter(x=>x.count<2).sort((a,b)=>a.count-b.count);
  const assignedDefense=ready.filter(f=>draft.assignments[f.id]==='defend').length;
  const alerts=zones.filter(z=>z.id!==draft.defenseZone||assignedDefense!==5);
  const tasks=state.long_missions||[];
  const pendingTasks=tasks.filter(task=>!draft.longActions?.[task.id]);
  panel().innerHTML=`<div class="office-grid"><div>
    <section class="wood"><div class="office-title"><h2>이번 주 운영</h2><button class="primary" data-office="week">주간 배치</button></div>
      <p>가용 ${ready.length}명 · 직접 배치 ${Object.values(draft.assignments).filter(x=>x!=='auto').length}명 · 원정 ${tasks.length}건</p>
      <h3>수익 임무</h3><ul>${state.mission_board.slice(0,3).map(job=>`<li>${escapeText(job.title)} · ${job.min_members}~${job.max_members}명 · 기준 보상 ${money(job.reward)}</li>`).join('')}</ul>
      <h3>점령 후보</h3><ul>${state.zones.filter(z=>z.selectable).slice(0,3).map(z=>`<li>구역 ${z.id} · ${escapeText(z.owner_name)} · 주간 기준 가치 ${money(z.value)}</li>`).join('')||'<li>현재 공격 가능 구역 없음</li>'}</ul>
    </section>
    <section class="wood"><div class="office-title"><h2>지난주 결산</h2>${report?'<button data-office="ledger">상세 보고</button>':''}</div>
      ${report?`<p>${report.season}시즌 ${report.week}주 · 순손익 <strong>${report.cash_change>0?'+':''}${money(report.cash_change)}</strong></p>
      <p>수입 ${money(report.income)} · 지출 ${money(report.expenses)} · 수익·정예 임무 ${(report.missions?.length||0)+(report.elite_missions?.length||0)}건</p>
      ${report.battle?`<p>구역 ${report.battle.zone} · ${report.battle.success?'점령 성공':'점령 실패'}</p>`:''}`:'<p>첫 주 결산 후 결과가 표시됩니다.</p>'}
    </section></div>
    <aside><section class="wood"><h2>결정 대기 ${alerts.length+pendingTasks.length}건</h2>
      ${pendingTasks.map(task=>`<p><button data-expedition="${escapeText(task.id)}">원정 결정</button> ${escapeText(task.title)} · 주간 배치 확정 시 안전 진행</p>`).join('')}
      ${alerts.map(z=>`<p><button data-defense="${z.id}">방어 배치</button> 구역 ${z.id} · 보호 종료 · 미배치 시 기본 수비</p>`).join('')}
      ${!alerts.length&&!pendingTasks.length?'<p>대기 중인 배치 결정이 없습니다.</p>':''}
      <h3>시즌 말 계약 검토 · ${expiring.length}명</h3>
      <details><summary>계약 만료 명단</summary><ul>${expiring.map(f=>`<li><button class="member-link" data-member="${f.id}">${escapeText(f.name)}</button> · ${f.role}</li>`).join('')||'<li>이번 시즌 만료 없음</li>'}</ul></details>
    </section><section class="wood"><div class="office-title"><h2>리그와 전력</h2><button type="button" data-office="league">순위표 보기</button></div>
      <p>${state.tier}부 ${state.rank}위 · ${state.operations.score}점 · 선두와 ${state.operations.leader_gap}점</p>
      <p>급여·유지비 ${money(state.operations.fixed)} · 미상환 부채 ${money(state.operations.debt)}</p>
      <p>${thin.map(x=>x.role+' 가용 '+x.count+'명').join(' · ')||'현재 명부의 모든 역할에 가용 인원 2명 이상'}</p>
    </section><section class="wood treasury-board"><h2>재정 운용</h2>${treasuryPolicyControl()}${treasuryForecast()}</section></aside></div>`;
  panel().querySelectorAll('[data-office]').forEach(btn=>btn.onclick=()=>{
    currentTab=btn.dataset.office; management();
  });
  panel().querySelectorAll('[data-defense],[data-expedition]').forEach(btn=>btn.onclick=()=>{
    if(btn.dataset.defense!==undefined) draft.defenseZone=Number(btn.dataset.defense);
    else draft.jobTab='long-board';
    currentTab='week';
    management();
    if(btn.hasAttribute('data-defense')) panel().querySelector('#defense-zone')?.focus();
    else [...panel().querySelectorAll('[data-expedition-decision]')]
      .find(select=>select.dataset.expeditionDecision===btn.dataset.expedition)?.focus();
  });
}

function showWeek() {
  const owned=state.zones.filter(z=>z.owner===state.guild);
  const zones=state.zones.filter(z=>z.selectable);
  const offers=state.mission_board||[];
  const longOffers=state.long_mission_board||[];
  const longActive=state.long_missions||[];
  const eliteOffers=state.elite_board||[];
  draft.eliteChoice ??='';
  draft.eliteDecision ??='study';
  draft.eliteLead ??='';
  draft.missionChoices ??={1:offers[0]?.id||'',2:offers[1]?.id||''};
  draft.missionApproaches ??={1:'balanced',2:'balanced'};
  draft.longChoices ??={1:'',2:''};
  draft.longApproaches ??={1:'balanced',2:'balanced'};
  draft.longActions ??={};
  const longFor=slot=>longOffers.find(x=>x.id===draft.longChoices[slot]);
  const offerFor=slot=>offers.find(x=>x.id===draft.missionChoices[slot]);
  panel().innerHTML=`<div class="week-top">${zoneMap()}
    <section class="wood"><h3>임무 선택</h3><nav class="inline-controls" aria-label="임무 유형">
      <button type="button" data-job="mission-board">수익 임무</button><button type="button" data-job="long-board">장기 원정</button>
      <button type="button" data-job="elite-board">정예 임무</button></nav>
      <div id="mission-board"></div><div id="long-board" hidden></div><div id="elite-board" hidden></div>
    </section></div><div class="management-grid"><section class="wood"><h2>이번 주 배치</h2>
    <p class="muted-copy">자동 배치는 남은 자리를 훈련으로 채워. 임무별 권장 역할을 보고 자동 배치하거나 직접 고를 수 있어.</p>
    ${sortControl(rosterSorts,rosterOrder,rosterAscending)}${rosterTable(true)}</section>
    <aside class="wood side-board"><h2>주간 계획</h2><div id="staffing"></div>
    <section class="budget-preview" id="week-budget" aria-live="polite"></section>
    <label class="field">방어 구역<select id="defense-zone" ${owned.length?'':'disabled'}><option value="">구역 선택</option>
    ${owned.map(z=>`<option value="${z.id}" ${draft.defenseZone===z.id?'selected':''}>구역 ${z.id}</option>`).join('')}</select></label>
    <div id="defense-status"></div>
    <label class="field">점령 목표<select id="target-zone"><option value="">구역 선택</option>
    ${zones.map(z=>`<option value="${z.id}" ${draft.zone===z.id?'selected':''}>구역 ${z.id} · ${escapeText(z.owner_name)} · ${escapeText(z.terrain.name)} · ${escapeText(z.tactic.name)}</option>`).join('')}</select></label>
    <div id="lineup"></div><div class="controls"><button id="recommend" type="button">추천 5명 배치</button></div><div class="controls"><button class="primary" id="advance">주간 배치 확정</button><button id="practice">모의전</button>
    <hr><h3>보유 구역</h3>${state.zones.filter(z=>z.owner===state.guild).map(z=>`<p>구역 ${z.id} · 주 ${money(z.value)} 기준</p>`).join('')||'<p>보유 구역 없음</p>'}
    </aside></div>`;
  // The board offers six stable, uniquely named contracts per week.
  const missionBoard=panel().querySelector('#mission-board');
  const missionHeading=document.createElement('h3');
  missionHeading.textContent='임무 게시판 · 이번 주 의뢰 6건';
  missionBoard.append(missionHeading);
  const missionHint=document.createElement('p');
  missionHint.className='muted-copy';
  missionHint.textContent='각 임무에 문파원 2~5명을 배치해. 추천 역할은 성공 가능성에 영향을 주고 접근 방식에 따라 위험과 보상이 달라져.';
  missionBoard.append(missionHint);
  const choiceArea=document.createElement('div');
  choiceArea.className='mission-choice-area';
  const selections={};
  for(const slot of [1,2]) {
    const block=document.createElement('div');
    block.className='mission-choice';
    const label=document.createElement('label');
    label.textContent='수익 임무 '+slot+' 의뢰';
    const select=document.createElement('select');
    const empty=new Option('의뢰 선택','');
    select.add(empty);
    for(const offer of offers) {
      select.add(new Option(offer.title+' · '+offer.min_members+'~'+offer.max_members+'명',offer.id));
    }
    select.value=draft.missionChoices[slot]||'';
    selections[slot]=select;
    select.addEventListener('change',()=>{
      const other=slot===1?2:1;
      if(select.value && selections[other].value===select.value) {
        draft.missionChoices[other]='';
        selections[other].value='';
      }
      draft.missionChoices[slot]=select.value;
      update();
    });
    const tactics=document.createElement('select');
    for(const [key,label] of [
      ['cautious','신중하게 · 안전 우선'],
      ['balanced','정석대로 · 균형'],
      ['bold','과감하게 · 고위험 고보상']
    ]) tactics.add(new Option(label,key));
    tactics.value=draft.missionApproaches[slot];
    tactics.setAttribute('aria-label','임무 '+slot+' 접근 방식');
    tactics.addEventListener('change',()=>{draft.missionApproaches[slot]=tactics.value;});
    label.append(select);
    block.append(label,tactics,autoButton("mission"+slot,()=>offerFor(slot)));
    choiceArea.append(block);
  }
  missionBoard.append(choiceArea);
  const offerGrid=document.createElement('div');
  offerGrid.className='mission-board-grid';
  for(const offer of offers) {
    const card=document.createElement('article');
    card.className='mission-offer';
    const title=document.createElement('strong');
    title.textContent=offer.title;
    const about=document.createElement('small');
    about.textContent=offer.category+' · '+offer.difficulty_label+' · '+offer.min_members+'~'+offer.max_members+'명';
    const story=document.createElement('p');
    story.textContent=offer.story;
    const specialist=document.createElement('small');
    specialist.textContent='추천 역할: '+offer.suggested_roles.join(', ');
    const payout=document.createElement('small');
    payout.textContent='성공 기준 '+money(offer.reward)+' · 준비비 '+money(offer.cost);
    card.append(title,about,story,specialist,payout);
    offerGrid.append(card);
  }
  missionBoard.append(offerGrid);
  const longBoard=panel().querySelector('#long-board');
  const longHeading=document.createElement('h3');
  longHeading.textContent='장기 임무 · 2~4주 원정';
  longBoard.append(longHeading);
  const longInfo=document.createElement('p');
  longInfo.className='muted-copy';
  longInfo.textContent='원정 인원은 귀환할 때까지 훈련·점령전·다른 임무·이적이 불가능해. 문파원 급여는 계속 지급하고 최종 보상은 완수 주에 정산해.';
  longBoard.append(longInfo);
  const longChoiceArea=document.createElement('div');
  longChoiceArea.className='mission-choice-area';
  const longSelectors={};
  for(const slot of [1,2]) {
    const block=document.createElement('div');
    block.className='mission-choice';
    const label=document.createElement('label');
    label.textContent='새 원정 '+slot+' · 파견 인원 2~5명';
    const select=document.createElement('select');
    select.add(new Option('원정 선택 안 함',''));
    for(const offer of longOffers) select.add(new Option(offer.title+' / '+offer.duration+'주',offer.id));
    select.value=draft.longChoices[slot]||'';
    select.disabled=longActive.length>=2;
    longSelectors[slot]=select;
    select.addEventListener('change',()=>{
      const other=slot===1?2:1;
      if(select.value && longSelectors[other].value===select.value){
        longSelectors[other].value='';
        draft.longChoices[other]='';
      }
      draft.longChoices[slot]=select.value;
      update();
    });
    const tactic=document.createElement('select');
    for(const [value,text] of [['cautious','신중하게'],['balanced','정석대로'],['bold','과감하게']])
      tactic.add(new Option(text,value));
    tactic.value=draft.longApproaches[slot];
    tactic.disabled=longActive.length>=2;
    tactic.setAttribute('aria-label','새 원정 '+slot+' 접근 방식');
    tactic.addEventListener('change',()=>draft.longApproaches[slot]=tactic.value);
    label.append(select);
    block.append(label,tactic,autoButton("expedition"+slot,()=>longFor(slot)));
    longChoiceArea.append(block);
  }
  longBoard.append(longChoiceArea);
  if(longActive.length){
    const heading=document.createElement('h4');heading.textContent='진행 중인 원정';longBoard.append(heading);
    for(const task of longActive){
      const card=document.createElement('article');card.className='mission-offer active-expedition';
      const title=document.createElement('strong');title.textContent=task.title+' · '+task.progress+'/'+task.duration+'주 완료';
      const description=document.createElement('p');description.textContent=task.event.description;
      const crew=document.createElement('small');
      crew.textContent='파견: '+task.members.map(fid=>state.roster.find(f=>f.id===fid)?.name||'#'+fid).join(' · ');
      const expense=document.createElement('small');
      expense.textContent='누적 지출 '+money(task.spent)+' · 이번 주 유지비 '+money(task.weekly_cost);
      const decision=document.createElement('select');
      decision.setAttribute('aria-label',task.title+' 중간 선택');
      for(const [value,text] of Object.entries(task.event.choices))
        decision.add(new Option(text,value));
      decision.dataset.expeditionDecision=task.id;
      decision.value=draft.longActions[task.id]||'safe';
      decision.addEventListener('change',()=>{draft.longActions[task.id]=decision.value;});
      card.append(title,description,crew,expense,decision);
      longBoard.append(card);
    }
  }
  const longGrid=document.createElement('div');longGrid.className='mission-board-grid';
  const roleLabels=['수호형','무인형','사수형','주술형','치유형','암살형'];
  for(const offer of longOffers){
    const card=document.createElement('article');card.className='mission-offer';
    const name=document.createElement('strong');name.textContent=offer.title;
    const story=document.createElement('p');story.textContent=offer.story;
    const span=document.createElement('small');
    span.textContent=offer.category+' · '+offer.duration+'주 · 참가 '+offer.min_members+'~'+offer.max_members+'명';
    const specialist=document.createElement('small');
    specialist.textContent='유리한 역할: '+offer.recommended_roles.map(i=>roleLabels[i]).join(', ');
    const cost=document.createElement('small');
    cost.textContent='완료 기준 보상 '+money(offer.reward)+' · 예상 비용 '+money(offer.total_estimated_cost);
    card.append(name,story,span,specialist,cost);
    longGrid.append(card);
  }
  if(longOffers.length)longBoard.append(longGrid);
  else{
    const endNote=document.createElement('p');
    endNote.textContent='시즌 종료까지 원정을 끝낼 수 없어 이번 주 새 장기 임무는 모집하지 않아.';
    longBoard.append(endNote);
  }
  // An independent weekly elite slot with a story choice and permanent rewards.
  const eliteBoard=panel().querySelector('#elite-board');
  const eliteHeading=document.createElement('h3');
  eliteHeading.textContent='정예 임무 · 기연 탐색';
  eliteBoard.append(eliteHeading);
  const eliteInfo=document.createElement('p');
  eliteInfo.className='muted-copy';
  eliteInfo.textContent='3~5명과 핵심 인물을 선택해. 주간 배치를 확정한 뒤 현장 조사 → 대응 선택 → 전술 전투 → 기연 보상까지 직접 진행해.';
  eliteBoard.append(eliteInfo);
  const eliteChoice=document.createElement('label');
  eliteChoice.className='field';
  eliteChoice.textContent='정예 임무 의뢰';
  const eliteSelect=document.createElement('select');
  eliteSelect.add(new Option('정예 임무 선택 안 함',''));
  for(const offer of eliteOffers)eliteSelect.add(new Option(offer.title+' · '+offer.difficulty_label,offer.id));
  eliteSelect.value=draft.eliteChoice;
  eliteSelect.addEventListener('change',()=>{draft.eliteChoice=eliteSelect.value;update();});
  eliteChoice.append(eliteSelect);
  eliteBoard.append(eliteChoice);
  const leadLabel=document.createElement('label');
  leadLabel.className='field';
  leadLabel.textContent='이야기의 핵심 인물';
  const leadSelect=document.createElement('select');
  leadSelect.setAttribute('aria-label','정예 임무 핵심 인물');
  leadSelect.addEventListener('change',()=>{draft.eliteLead=leadSelect.value;});
  leadLabel.append(leadSelect);
  eliteBoard.append(leadLabel);
  eliteBoard.append(autoButton('elite',()=>eliteOffers.find(offer=>offer.id===draft.eliteChoice)));
  const eliteGrid=document.createElement('div');
  eliteGrid.className='mission-board-grid';
  for(const offer of eliteOffers){
    const card=document.createElement('article');
    card.className='mission-offer'+(offer.saga?' active-expedition':'');
    const title=document.createElement('strong');
    title.textContent=(offer.saga?'[연속 기연] ':'')+offer.title;
    const story=document.createElement('p');story.textContent=offer.story;
    if(offer.saga){
      const leader=document.createElement('small');
      const hero=state.roster.find(f=>f.id===offer.saga_leader);
      leader.textContent='핵심 인물 '+(hero?.name||'#'+offer.saga_leader)+
        ' · 제'+offer.saga_chapter+'장 / 3장 · 마감 '+offer.saga_deadline+'주차 시계';
      card.append(leader);
    }
    const detail=document.createElement('small');
    detail.textContent=offer.category+' · '+offer.difficulty_label+' · 3~5명 · 추천: '+offer.recommended_roles.join(', ');
    const budget=document.createElement('small');
    budget.textContent='기본 보상 '+money(offer.reward)+' · 준비비 '+money(offer.cost)+' · 기연 보상 가능';
    card.append(title,story,detail,budget);eliteGrid.append(card);
  }
  eliteBoard.append(eliteGrid);
  function autoButton(key,getOffer) {
    const button=document.createElement('button');
    button.type='button';button.textContent='자동 배치';
    button.onclick=()=>{
      const offer=getOffer();
      if(!offer){notice('의뢰를 먼저 선택하세요.');return;}
      const team=teamForOffer(state.roster,draft.assignments,key,offer);
      if(!team){notice('다른 임무에 배치되지 않은 가용 인원과 필수 인물을 확인하세요.');return;}
      for(const f of team) draft.assignments[f.id]=key;
      for(const select of panel().querySelectorAll('.assignment'))
        select.value=draft.assignments[select.dataset.id]||'auto';
      notice(team.map(f=>f.name).join(', ')+' 배치 완료');update();
    };
    return button;
  }

  const jobTabs=[...panel().querySelectorAll('[data-job]')];
  const jobTab=()=>jobTabs.forEach(button=>{
    const active=button.dataset.job===(draft.jobTab||'mission-board');
    button.setAttribute('aria-pressed',active);
    panel().querySelector('#'+button.dataset.job).hidden=!active;
  });
  jobTabs.forEach(button=>button.onclick=()=>{draft.jobTab=button.dataset.job;jobTab();});
  jobTab();
  const tiles=[...panel().querySelectorAll('[data-zone-tile]')];
  const reveal=z=>{
    const owned=z.owner===state.guild;
    const holdings=state.zones.filter(zone=>zone.owner===state.guild);
    const replace=holdings.length>=state.zone_cap;
    panel().querySelector('#zone-detail').innerHTML=`<strong>구역 ${z.id} · ${escapeText(z.owner_name)}</strong>
      <p>7일 기준 수입 ${money(z.gross)} − 직접 유지비 ${money(z.upkeep)} = ${money(z.gross-z.upkeep)}
      <small> · 추가 관리비 제외</small></p>
      <p>전장 환경: <strong>${escapeText(z.terrain.name)}</strong> · ${escapeText(z.terrain.description)}</p>
      <p>상대 전술: <strong>${escapeText(z.tactic.name)}</strong> · ${escapeText(z.tactic.description)}</p>
      <p>예상 수비 편성: ${z.enemy_lineup.map(f=>`${escapeText(f.name)}(${escapeText(f.role)}·${escapeText(f.row)}${f.ca===null?'':`·CA ${f.ca}`}${f.notable?`·${f.notable.rarity==='legend'?'전설':'네임드'} ${escapeText(f.notable.skill)}`:''})`).join(' / ')}</p>
      <p>${owned?'클릭하면 방어 목표로 선택':z.selectable?
        '클릭하면 공격 목표로 선택 · 점령 시 리그 +4점과 구역 수입'+(replace?' · 정원에 도달해 기존 최저 가치 구역 반환':''):
        '보호 중 · 현재 공격 불가'}</p>`;
  };
  for(const tile of tiles){
    const z=state.zones.find(zone=>zone.id===Number(tile.dataset.zoneTile));
    tile.onmouseenter=tile.onfocus=()=>reveal(z);
    tile.onclick=()=>{
      reveal(z);
      const owned=z.owner===state.guild;
      if(!owned&&!z.selectable)return;
      const select=panel().querySelector(owned?'#defense-zone':'#target-zone');
      select.value=z.id;
      if(owned) draft.defenseZone=z.id;
      else draft.zone=z.id;
      update();
    };
  }
  const selectedZone=state.zones.find(z=>z.id===(draft.defenseZone??draft.zone));
  if(selectedZone)reveal(selectedZone);
  const attackers=()=>state.roster.filter(f=>draft.assignments[f.id]==='attack');
  const lineup=()=>{
    panel().querySelector('#lineup').innerHTML=attackers().map((f,index)=>`<div class="lineup-row" data-fighter="${f.id}">
      <label>${escapeText(f.name)} <select class="row"><option value="front">전열</option><option value="back" ${(draft.rows?.[f.id]??([0,1].includes(f.role_id)||index===0?'front':'back'))==='back'?'selected':''}>후열</option></select></label>
      <div class="skills">${f.skills.map(key=>`<label><input type="checkbox" value="${key}" ${(draft.skills?.[f.id] ?? f.equipped ?? f.skills).includes(key)?'checked':''}>${state.skills[key].name}</label>`).join('')}</div>
      </div>`).join('');
  };
  const update=()=>{
    const counts=Object.values(draft.assignments);
    panel().querySelector('#staffing').textContent=[1,2].map(slot=>{
      const offer=offerFor(slot);
      return '임무 '+slot+' · '+counts.filter(x=>x==='mission'+slot).length+'/'+
        (offer ? offer.min_members+'~'+offer.max_members : '미선택');
    }).join(' / ')+' / 원정 진행 '+longActive.length+'/2 · 신규 '+counts.filter(x=>x==='expedition1'||x==='expedition2').length+'명 / 정예 '+counts.filter(x=>x==='elite').length+'/3~5 · 점령전 '+attackers().length+'/5';
    for(const tile of tiles){
      const id=Number(tile.dataset.zoneTile);
      tile.setAttribute('aria-pressed',id===draft.zone||id===draft.defenseZone);
    }
    // A saga is always led by its original discoverer. Ordinary elite jobs let
    // the player nominate any member of the selected team.
    const selected=state.roster.filter(f=>draft.assignments[f.id]==='elite');
    const chosenOffer=eliteOffers.find(x=>x.id===draft.eliteChoice);
    const required=chosenOffer?.saga?String(chosenOffer.saga_leader):'';
    const previous=required||draft.eliteLead;
    leadSelect.replaceChildren(new Option('첫 번째 참가자 자동 선택',''));
    for(const f of selected)leadSelect.add(new Option(f.name, String(f.id)));
    leadSelect.value=required||selected.some(f=>String(f.id)===previous)?previous:'';
    // Explicitly keep the default for an empty or mismatched selection.
    if(!selected.some(f=>String(f.id)===leadSelect.value))leadSelect.value='';
    leadSelect.disabled=!!chosenOffer?.saga;
    if(required)leadSelect.value=required;
    draft.eliteLead=leadSelect.value;
    lineup();
    const defense=state.roster.filter(f=>draft.assignments[f.id]==='defend');
    panel().querySelector('#defense-status').textContent=defense.length
      ? `방어 ${defense.length}/5명${defense.some(f=>f.role_id===4)?'':' · 치유형 미배치'}`
      : '방어조 미편성 시 기본 수비가 적용됩니다.';
    const missions=[1,2].map(slot=>({offer:offerFor(slot),count:counts.filter(x=>x==='mission'+slot).length}))
      .filter(({offer,count})=>offer&&count>=offer.min_members&&count<=offer.max_members);
    const expeditionCosts=[1,2].reduce((sum,slot)=>{
      const offer=longFor(slot), count=counts.filter(x=>x==='expedition'+slot).length;
      return sum+(offer&&count>=offer.min_members&&count<=offer.max_members?offer.initial_cost:0);
    },0)+longActive.filter(task=>draft.longActions[task.id]!=='withdraw').reduce((sum,task)=>sum+task.weekly_cost,0);
    const preparation=missions.reduce((sum,{offer,count})=>sum+Math.round(offer.cost*(1+.09*(count-3))),0)
      +expeditionCosts+(chosenOffer&&selected.length>=3&&selected.length<=5?chosenOffer.cost+(selected.length-3)*2:0);
    const baseReward=missions.reduce((sum,{offer})=>sum+offer.reward,0);
    const residual=state.cash-state.operations.fixed-preparation;
    const forecast=state.treasury.forecast;
    const baselineCash=state.cash+forecast.balance-preparation;
    panel().querySelector('#week-budget').innerHTML=`<h3>배치 예산</h3>
      ${treasuryPolicyControl()}
      <p>급여·유지비 ${money(state.operations.fixed)} · 임무·원정 준비비 ${money(preparation)}</p>
      <p>보상 제외 잔액 <strong>${money(residual)}</strong> · 수익 임무 기준 보상 반영 ${money(residual+baseReward)}</p>
      <p>구역 유지 가정 · 기본 현금 전망 <strong>${money(baselineCash)}</strong></p>
      <small>구역·장원·후원금 수입과 기본 주둔비 반영. 임무 보상, 점령·방어 결과, 부채 상환, 훈련비, 추가 육성 투자 및 정예·원정 보상은 제외한 참고치입니다.</small>`;
  };
  panel().onchange=e=>{
    if(e.target.matches('.assignment')) {draft.assignments[e.target.dataset.id]=e.target.value;update();}
    if(e.target.id==='defense-zone'){draft.defenseZone=e.target.value?Number(e.target.value):null;update();}
    if(!e.target.matches('.assignment')&&e.target.closest('#mission-board,#long-board,#elite-board')) update();
    if(e.target.id==='target-zone'){draft.zone=e.target.value?Number(e.target.value):null;update();}
    const fighter=e.target.closest('[data-fighter]');
    if(fighter&&e.target.matches('.row')) (draft.rows??={})[fighter.dataset.fighter]=e.target.value;
    if(fighter&&e.target.matches('input')) (draft.skills??={})[fighter.dataset.fighter]=[...fighter.querySelectorAll('input:checked')].map(x=>x.value);
  };
  panel().querySelector('#recommend').onclick=()=>{
    if(busy) return;
    const candidates=state.roster.filter(f=>!f.injured&&!f.expedition&&
      [undefined,'auto','attack'].includes(draft.assignments[f.id]));
    const team=candidates.sort((a,b)=>Number(b.recommended)-Number(a.recommended)||b.ca-a.ca).slice(0,5);
    if(team.length!==5) {notice('출전 가능한 문파원이 5명 미만입니다.');return;}
    for(const [id,value] of Object.entries(draft.assignments)) if(value==='attack') delete draft.assignments[id];
    for(const f of team) draft.assignments[f.id]='attack';
    for(const select of panel().querySelectorAll('.assignment')) select.value=draft.assignments[select.dataset.id]||'auto';
    update();
  };
  panel().querySelector('#practice').onclick=()=>{if(!busy){notice('');setup();}};
  panel().querySelector('#advance').onclick=()=>{
    const ids=key=>state.roster.filter(f=>draft.assignments[f.id]===key).map(f=>f.id);
    const attack=attackers();
    const defenders=ids('defend');
    if(defenders.length&&(defenders.length!==5||!owned.some(z=>z.id===draft.defenseZone))) {
      notice('보유 구역을 선택하고 방어 인원 5명을 배치하세요.');return;
    }
    const defense=defenders.length?{zone:draft.defenseZone,members:defenders}:null;
    const eliteMembers=ids('elite');
    const eliteOffer=eliteOffers.find(x=>x.id===draft.eliteChoice);
    if(eliteMembers.length&&(eliteMembers.length<3||eliteMembers.length>5||!eliteOffer)){
      notice('정예 임무 의뢰를 선택하고 문파원 3~5명을 배치하세요.');return;
    }
    if(eliteOffer?.saga&&!eliteMembers.includes(eliteOffer.saga_leader)){
      notice('연속 기연에는 단서를 발견한 핵심 문파원을 반드시 배치하세요.');return;
    }
    const lead=eliteOffer?.saga?eliteOffer.saga_leader:
      (eliteMembers.includes(Number(draft.eliteLead))?Number(draft.eliteLead):eliteMembers[0]);
    const elite_order=eliteMembers.length?{id:eliteOffer.id,members:eliteMembers,lead,choice:'study'}:null;
    const long_orders=[];
    for(const slot of [1,2]){
      const members=ids('expedition'+slot);
      if(!members.length)continue;
      const offer=longFor(slot);
      if(!offer){notice('장기 임무 '+slot+'의 의뢰를 선택하세요.');return;}
      if(members.length<offer.min_members||members.length>offer.max_members){
        notice('원정 「'+offer.title+'」은 '+offer.min_members+'~'+offer.max_members+'명이 필요해.');return;
      }
      long_orders.push({id:offer.id,members,approach:draft.longApproaches[slot]||'balanced'});
    }
    const long_actions=longActive.map(task=>({id:task.id,choice:draft.longActions[task.id]||'safe'}));
    const mission_orders=[];
    for (const slot of [1,2]) {
      const members=ids('mission'+slot);
      if (!members.length) continue;
      const offer=offerFor(slot);
      if (!offer) {notice('수행할 의뢰를 먼저 선택하세요.');return;}
      if (members.length<offer.min_members || members.length>offer.max_members) {
        notice('임무 '+slot+' 「'+offer.title+'」에는 '+offer.min_members+'~'+offer.max_members+'명이 필요해.');return;
      }
      mission_orders.push({id:offer.id,members,approach:draft.missionApproaches[slot]||'balanced'});
    }
    if(mission_orders.length+long_orders.length+longActive.length>2){
      notice('진행 중인 장기 임무를 포함해 주간 임무는 최대 두 건이야.');return;
    }
    if(attack.length&&(attack.length!==5||draft.zone===null)) {notice('점령전에 5명을 배치하고 목표 구역을 선택하세요.');return;}
    const setup=[...panel().querySelectorAll('[data-fighter]')].map(row=>({id:Number(row.dataset.fighter),
      row:row.querySelector('.row').value,skills:[...row.querySelectorAll('input:checked')].map(x=>x.value)}));
    if(setup.length&&!setup.some(f=>f.row==='front')) {notice('점령전에는 전열 문파원을 한 명 이상 배치하세요.');return;}
    currentTab='ledger';
    request('week',{season:state.season,week:state.week,assignment:{training:ids('training'),rest:ids('rest'),
      mission_orders,long_orders,long_actions,elite_order,defense,attack:attack.length?{zone:draft.zone,setup}:null}});
  };
  update();
}

function weeklyBriefing(report) {
  const brief=report.briefing;
  if(!brief) return '';
  const next=brief.next;
  const mission=next.mission;
  const signed=value=>(value>0?'+':'')+money(value);
  const leveled=report.members.filter(member=>member.levels>0).length;
  const newInjuries=report.members.filter(member=>!member.injured_before&&member.injured).length;
  const completed=(report.missions?.length||0)+(report.elite_missions?.length||0);
  const fortunes=report.elite_missions?.filter(item=>item.kiyun).length||0;
  return `<section class="wood weekly-brief">
    <h2>${report.season}시즌 ${report.week}주 주간 보고</h2>
    <div class="weekly-brief-grid">
      <div><h3>이번 주 주요 변화</h3><ul>
        <li>순위 <strong>${brief.tier_before}부 ${brief.rank_before}위 → ${brief.tier}부 ${brief.rank}위</strong></li>
        <li>보유 구역 ${brief.territories_before}개 → <strong>${brief.territories}개</strong> · 재정 ${signed(report.cash_change)}</li>
        <li>임무 결과 ${completed}건 · 기연 ${fortunes}건 · 레벨 상승 ${leveled}명 · 신규 부상 ${newInjuries}명</li>
        ${brief.defense_plan?`<li>구역 ${brief.defense_plan.zone} 방어 배치 · ${brief.defense_plan.members.map(escapeText).join(', ')}</li>`:''}
        ${brief.defenses.map(item=>`<li>${escapeText(item.attacker)}의 구역 ${item.zone} 공격 · <strong>${item.held?'방어 성공':'구역 상실'}</strong></li>`).join('')}
      </ul></div>
      <div><h3>${next.stage==='week'?`${next.week}주 배치 참고`:'다음 단계'}</h3>
        ${next.stage==='bankrupt'?'<p>문파가 파산해 운영이 종료됐어.</p>':
          next.stage==='draft'?`<p>${next.season}시즌 ${next.tier}부 신인 드래프트가 열려.</p>`:
          `<ul>
            <li>배치 가능 <strong>${next.ready}명</strong> · 부상 ${next.injured}명 · 원정 중 ${next.away}명</li>
            <li>급여·문파 유지비 <strong>${money(next.fixed)}</strong> · 미상환 부채 ${money(next.debt)}</li>
            ${next.exposed.length?`<li>보호 기간이 끝난 보유 구역 ${next.exposed.join(', ')} · 방어 배치 검토</li>`:''}
            ${next.target!==null?`<li>점령 후보 · 수비대 구역 ${next.target}</li>`:''}
            ${mission?`<li>임무 후보 · <strong>${escapeText(mission.title)}</strong> (${mission.min_members}~${mission.max_members}명) · 준비비 ${money(mission.cost)} · 기준 보상 ${money(mission.reward)}</li>`:''}
          </ul>`}
      </div>
    </div>
  </section>`;
}

function showLedger() {
  const report=state.week_report;
  if(!report) {panel().innerHTML='<section class="wood"><h2>주간 보고</h2><p>첫 주간 결산 후 주요 변화와 수입·지출을 볼 수 있어.</p></section>';return;}
  const sums=new Map();
  for(const entry of report.entries) sums.set(entry.category,(sums.get(entry.category)||0)+entry.amount);
  const changed=report.members.filter(f=>f.ca_change||f.levels||f.xp_before!==f.xp||f.fatigue_change||f.injured_before!==f.injured);
  const honor=state.last_season_review;
  const annual=report.season!==state.season&&honor?`<section class="annual-judgment"><h2>천하 결산 · ${report.season}시즌</h2>
    <p>시즌 최종 성적 · <strong>${honor.tier}부 ${honor.rank}위</strong> · 점수 ${honor.score}점</p>
    <div class="annual-judgment-summary"><strong>${escapeText(honor.result)} → ${honor.next_tier}부</strong>
       <span>순위 존호: ${escapeText(honor.rank_title||'수여 없음')} · 다음 시즌에만 유효</span></div>
    <p>특별 존호 신규 획득: ${honor.special_awards.length?honor.special_awards.map(escapeText).join(' · '):'없음'}</p>
    <p>점령전 ${honor.season_wins}/${honor.season_attacks}승 · 방어전 ${honor.season_defenses}승</p>
    <div class="controls"><button id="annual-history" type="button">해당 시즌 연대기</button>
      <button id="annual-codex" type="button">강호 명예록</button></div>
    </section>`:'';
  panel().innerHTML=`${annual}${weeklyBriefing(report)}<div class="management-grid"><section class="parchment"><h2>재정 장부</h2>
  <div class="ledger-head"><span>수입 <b>${money(report.income)}</b></span><span>지출 <b>${money(report.expenses)}</b></span><span>기말 잔액 <b>${money(report.cash)}</b></span></div>
  ${report.battle?`<p>구역 ${report.battle.zone} · ${report.battle.success?'점령 성공':'점령 실패'}</p>`:''}
  ${report.treasury_policy?`<p class="muted-copy">자금 정책: ${escapeText(TREASURY_POLICY_LABELS[report.treasury_policy]||report.treasury_policy)} · 선택적 육성 투자 ${money(report.investment_paid||0)}</p>`:''}
  ${report.budget?`<h3>배치 예산과 실제 지출</h3>
  <p>급여·유지비 ${money(report.budget.fixed)} → ${money(-((sums.get('weekly_wages')||0)+(sums.get('hall_upkeep')||0)))} 실제 지출</p>
  <p>임무·원정 비용 ${money(report.budget.preparation)} → ${money(-['mission_preparation','expedition_preparation','expedition_upkeep','elite_preparation'].reduce((sum,key)=>sum+(sums.get(key)||0),0))} 실제 지출</p>
  ${report.season!==state.season?'<small>실제 지출에는 시즌 마감 정산이 포함됩니다.</small>':''}`:''}
  <h3>장부 내역</h3><dl>${[...sums].map(([k,v])=>`<dt>${escapeText(labels[k]||k)}</dt><dd>${v>0?'+':''}${money(v)}</dd>`).join('')}</dl>
  <h3>구역별 총수입</h3><dl>${report.territories.map(t=>`<dt>구역 ${t.zone} · ${t.days}일</dt><dd>${money(t.gross)}</dd>`).join('')}</dl></section>
  <section class="wood"><h2>문파원 변동</h2><dl>${changed.map(f=>`<dt>${escapeText(state.roster.find(x=>x.id===f.id)?.name??'#'+f.id)}</dt><dd>CA ${f.ca_change>0?'+':''}${f.ca_change} · 피로 ${f.fatigue_change>0?'+':''}${f.fatigue_change}${f.injured?` · 부상 ${f.injured}주`:''}</dd>`).join('')}</dl>
  ${state.dead?'':`<button class="primary" id="next-week">${state.phase!=='report'?'주간 운영으로':report.season===state.season?'다음 주로':'신인 드래프트로'}</button>`}</section></div>`;
  panel().querySelector('#annual-history')?.addEventListener('click',()=>honorsUI.visit('history',state.guild,report.season));
  panel().querySelector('#annual-codex')?.addEventListener('click',()=>honorsUI.visit('honors',state.guild));
  // Mission consequences are visible in the same week-end ledger as money.
  if(report.missions?.length) {
    const receipts=document.createElement('section');
    receipts.className='mission-receipts';
    const heading=document.createElement('h3');
    heading.textContent='이번 주 임무 결과';
    receipts.append(heading);
    for(const mission of report.missions) {
      const item=document.createElement('article');
      item.className='mission-receipt';
      const name=document.createElement('strong');
      name.textContent=mission.title+' · '+mission.outcome_label;
      const narrative=document.createElement('p');
      narrative.textContent=mission.narrative;
      const team=document.createElement('small');
      team.textContent='참가: '+mission.members.map(fid=>state.roster.find(f=>f.id===fid)?.name||'#'+fid).join(' · ');
      const financials=document.createElement('small');
      financials.textContent='보상 '+money(mission.gross)+' / 준비비 '+money(mission.cost)+' / 순수익 '+money(mission.net);
      item.append(name,narrative,team,financials);
      receipts.append(item);
    }
    const parchment=panel().querySelector('.parchment');
    parchment.insertBefore(receipts,parchment.querySelector('h3'));
  }
  if(report.long_missions?.length){
    const receipts=document.createElement('section');
    receipts.className='mission-receipts';
    const heading=document.createElement('h3');
    heading.textContent='장기 원정 보고';
    receipts.append(heading);
    for(const mission of report.long_missions){
      const card=document.createElement('article');card.className='mission-receipt';
      const title=document.createElement('strong');
      title.textContent=mission.title+' · '+mission.status_label+' · '+mission.stage+'/'+mission.duration+'주';
      const story=document.createElement('p');story.textContent=mission.narrative;
      const members=document.createElement('small');
      members.textContent='참가: '+mission.members.map(fid=>state.roster.find(f=>f.id===fid)?.name||'#'+fid).join(' · ');
      const cash=document.createElement('small');
      cash.textContent='이번 주 준비·유지비 '+money(mission.cost)+
        ' · 수령 보상 '+money(mission.gross)+' · 누적 지출 '+money(mission.total_spent);
      card.append(title,story,members,cash);
      if(mission.event){
        const update=document.createElement('small');
        update.textContent=mission.event.outcome;
        card.append(update);
      }
      receipts.append(card);
    }
    const parchment=panel().querySelector('.parchment');
    parchment.insertBefore(receipts,parchment.querySelector('h3'));
  }
  if(report.elite_missions?.length){
    const receipts=document.createElement('section');receipts.className='mission-receipts';
    const heading=document.createElement('h3');heading.textContent='정예 임무와 기연';receipts.append(heading);
    for(const mission of report.elite_missions){
      const card=document.createElement('article');card.className='mission-receipt';
      const title=document.createElement('strong');title.textContent=mission.title+' · '+mission.outcome_label;
      const story=document.createElement('p');story.textContent=mission.narrative;
      const crew=document.createElement('small');
      crew.textContent='참가: '+mission.members.map(fid=>state.roster.find(f=>f.id===fid)?.name||'#'+fid).join(' · ')+' · '+mission.choice_label;
      const net=document.createElement('small');net.textContent='보상 '+money(mission.gross)+' / 준비비 '+money(mission.cost);
      card.append(title,story,crew,net);
      if(mission.combat){
        const fight=document.createElement('small');
        fight.textContent='직접 전투 '+(mission.combat.won?'승리':'패배')+
          ' · '+mission.combat.rounds+'라운드 · 잔존 체력 '+
          Math.round(mission.combat.health*100)+'%'+
          (mission.combat.fallen.length?' · 전투불능 '+mission.combat.fallen.length+'명':'');
        card.append(fight);
      }
      if(mission.story_events?.length){
        for(const event of mission.story_events){
          const episode=document.createElement('p');
          episode.className='muted-copy';
          episode.textContent=event.title+' — '+event.text;
          card.append(episode);
        }
      }
      if(mission.kiyun){
        const reward=document.createElement('p');
        reward.textContent='기연 발견: '+mission.kiyun.label+' — '+mission.kiyun.description;
        card.append(reward);
      }
      receipts.append(card);
    }
    const parchment=panel().querySelector('.parchment');
    parchment.insertBefore(receipts,parchment.querySelector('h3'));
  }
  const nextButton=panel().querySelector('#next-week');
  if(nextButton) nextButton.onclick=state.phase==='report'?advancePhase:()=>{currentTab='week';management();};
}

async function runMarket(path,payload,onSuccess) {
  if(busy) return;
  busy=true;
  const buttons=[...screen.querySelectorAll('button')].filter(b=>!b.disabled);
  buttons.forEach(b=>b.disabled=true);
  try {onSuccess(await callEngine(path,payload));}
  catch(e){notice(e.message);}
  finally {busy=false;buttons.forEach(b=>b.disabled=false);}
}
function showFree(market) {
  panel().innerHTML=`<section class="wood"><h2>낭인 시장</h2>${sortControl({name:'이름',role:'역할',age:'나이',ca:'현재 전력',pa:'잠재력',fee:'계약금',wage:'주급'},freeOrder,freeAscending)}<p class="muted-copy">문파원 ${market.roster_count}/${market.normal_roster_limit}명 · 임시 정원 ${market.roster_limit}명</p>
  <div class="table-scroll"><table><thead><tr><th>후보</th><th>역할</th><th>나이</th><th>CA / PA</th><th>계약금</th><th>주급</th><th>예상 잔액</th><th>계약</th></tr></thead><tbody>
  ${sortedMembers(market.candidates,freeOrder,freeAscending).map(f=>`<tr data-candidate="${f.id}"><th scope="row"><span class="member-face">${portrait(f)}</span>${escapeText(f.name)} ${heroTag(f)}${f.notable?`<small title="${heroDescription(f)}">${heroDescription(f)}</small>`:''}</th><td>${f.role}</td><td>${f.age}</td><td>${f.ca} / ${f.pa}</td><td>${money(f.fee)}</td><td>${money(f.wage)}</td><td>${money(f.cash_after)}</td>
    <td>${f.eligible?`<div class="inline-controls"><select class="years" aria-label="계약 기간">${market.terms_years.map(y=>`<option value="${y}">${y}시즌</option>`).join('')}</select><button class="hire" type="button">영입</button></div>`:`<small>${decisions[f.reason]||'영입 불가'}</small>`}</td></tr>`).join('')}</tbody></table></div>
  ${market.candidates.length?'':'<p>현재 영입할 수 있는 낭인이 없어.</p>'}
  ${state.phase==='fa'?'<div class="controls"><button class="primary" id="start-season">시즌 시작</button></div>':''}</section>`;
  panel().querySelector('[data-sort]').onchange=e=>{freeOrder=e.target.value;showFree(market);};
  panel().querySelector('[data-sort-direction]').onclick=()=>{freeAscending=!freeAscending;showFree(market);};
  if(state.phase==='fa') panel().querySelector('#start-season').onclick=advancePhase;
  panel().querySelectorAll('.hire').forEach(button=>button.onclick=()=>{
    const row=button.closest('[data-candidate]');
    const candidate=market.candidates.find(f=>f.id===Number(row.dataset.candidate));
    const years=Number(row.querySelector('.years').value);
    if(!confirm(`${candidate.name} · ${years}시즌 계약\n계약금 ${money(candidate.fee)} · 주급 ${money(candidate.wage)}`)) return;
    runMarket('recruit',{season:market.season,week:market.week,id:candidate.id,years},result=>{
      state=result.state;
      queueMicrotask(()=>management(result.recruitment.status==='signed'?`${candidate.name} 영입 완료`:decisions[result.recruitment.status]));
    });
  });
}

function showScout(info, selectedSeller=null) {
  const sects=new Map(info.sects.map(s=>[s.id,s]));
  const roles=[...new Set(info.candidates.map(f=>f.role))];
  panel().innerHTML=`<section class="wood"><h2>타 문파 스카우트</h2>
    <div class="scout-filters">
      <label>문파<select id="seller"><option value="">전체 문파</option>${info.sects.map(s=>`<option value="${s.id}">${s.tier}부 · ${escapeText(s.name)}</option>`).join('')}</select></label>
      <label>포지션<select id="scout-role"><option value="">전체 역할</option>${roles.map(r=>`<option>${r}</option>`).join('')}</select></label>
      <label>현재 전력 이상<input id="min-ca" type="number" min="0" max="200" placeholder="제한 없음"></label>
      <label>잠재력 이상<input id="min-pa" type="number" min="0" max="200" placeholder="제한 없음"></label>
      <label>예상 이적료 이하<input id="max-fee" type="number" min="0" placeholder="제한 없음"></label>
      <label>주급 이하<input id="max-wage" type="number" min="0" placeholder="제한 없음"></label>
      <label>나이 이하<input id="max-age" type="number" min="0" placeholder="제한 없음"></label>
      <label>정렬<select id="scout-sort"><option value="pa">잠재력 높은 순</option><option value="ca">현재 전력 높은 순</option><option value="estimate">이적료 낮은 순</option></select></label>
      <label><input id="scout-available" type="checkbox" checked> 이적 제한 제외</label>
    </div><p id="scout-count"></p>
    <div class="table-scroll"><table><thead><tr><th>후보</th><th>소속 · 역할</th><th>현재 / 잠재력</th><th>예상 이적료</th><th>주급</th></tr></thead><tbody id="scout-list"></tbody></table></div>
    <div class="controls"><button id="scout-prev">이전</button><span id="scout-page"></span><button id="scout-next">다음</button></div></section>
    <dialog class="wood trade-dialog" id="offer" aria-labelledby="trade-title"></dialog>`;
  const get=id=>panel().querySelector('#'+id);
  if(selectedSeller!==null)get('seller').value=String(selectedSeller);
  let page=0;
  function update() {
    const seller=get('seller').value, role=get('scout-role').value;
    const max=id=>get(id).value===''?Infinity:Number(get(id).value);
    const sort=get('scout-sort').value;
    const rows=info.candidates.filter(f=>(seller===''||f.seller===Number(seller))&&(!role||f.role===role)
      && f.ca>=Number(get('min-ca').value)&&f.pa>=Number(get('min-pa').value)
      && f.estimate<=max('max-fee')&&f.wage<=max('max-wage')&&f.age<=max('max-age')
      && (!get('scout-available').checked||!f.locked))
      .sort((a,b)=>sort==='estimate'?a.estimate-b.estimate:(sort==='ca'?b.ca-a.ca:b.pa-a.pa));
    const pages=Math.max(1,Math.ceil(rows.length/30));
    get('scout-count').textContent=`검색 결과 ${rows.length}명`;
    get('scout-page').textContent=`${page+1} / ${pages}`;
    get('scout-prev').disabled=page===0;get('scout-next').disabled=page+1>=pages;
    get('scout-list').innerHTML=rows.slice(page*30,page*30+30).map(f=>`<tr><th scope="row"><span class="member-face">${portrait(f)}</span><button class="member-link" data-negotiate="${f.id}">${escapeText(f.name)}</button>${heroTag(f)}${f.notable?`<small>${heroDescription(f)}</small>`:''}</th>
      <td>${escapeText(sects.get(f.seller)?.name)} · ${f.role}</td><td>${f.ca} / ${f.pa}</td><td>${money(f.estimate)}</td><td>${money(f.wage)}</td></tr>`).join('');
    get('scout-list').querySelectorAll('[data-negotiate]').forEach(button=>button.onclick=()=>
      showOffer(info,rows.find(f=>f.id===Number(button.dataset.negotiate))));
  }
  panel().querySelector('.scout-filters').oninput=()=>{page=0;update();};
  panel().querySelector('.scout-filters').onchange=panel().querySelector('.scout-filters').oninput;
  get('scout-prev').onclick=()=>{page--;update();};
  get('scout-next').onclick=()=>{page++;update();};
  update();
}
function showOffer(info,fighter) {
  const box=panel().querySelector('#offer');
  if (busy) return;
  const seller = info.sects.find(s=>s.id===fighter.seller);
  box.innerHTML=`<div class="trade-heading"><h2 id="trade-title">${escapeText(seller.name)} 협상</h2><form method="dialog"><button>닫기</button></form></div>
  <h3><span class="member-face">${portrait(fighter)}</span>${escapeText(fighter.name)} ${heroTag(fighter)}</h3>${fighter.notable?`<p>${heroDescription(fighter)}</p>`:''}<p>${fighter.role} · ${fighter.age}세 · 현재 ${fighter.ca} / 잠재력 ${fighter.pa} · 현재 주급 ${money(fighter.wage)} · ${fighter.contract_end}시즌 만료</p>
  <p id="seller-terms" aria-live="polite">상대 문파의 조건을 확인하는 중…</p>
  <label class="field">현금 제안<input id="fee" type="number" min="0" step="1" max="${info.cash}" value="${Math.min(fighter.estimate,info.cash)}"></label>
  <details><summary>교환 문파원 선택 (최대 3명)</summary><div class="exchange-list">
  ${info.exchange_pool.map(f=>`<label><input type="checkbox" value="${f.id}" ${f.locked?'disabled':''}> ${escapeText(f.name)} · ${f.role}</label>`).join('')}</div></details>
  <div class="controls"><button class="primary" id="propose">조건 제안</button></div><div id="offer-reply" aria-live="polite"></div>`;
  const reply=box.querySelector('#offer-reply');
  box.showModal();
  const context={season:info.season,week:info.week,seller:fighter.seller,id:fighter.id};
  const assess=box.querySelector('#seller-terms');
  assess.textContent='';
  runMarket('transfer_suggestion',context,t=>{
    assess.textContent=t.message||decisions[t.status]||'상대 조건을 확인하지 못했습니다.';
    if(t.fee!=null) {
      box.querySelector('#fee').value=t.fee;
      const matches=[...box.querySelectorAll('input[type=checkbox]')].filter(input=>t.exchange.includes(Number(input.value)));
      matches.forEach(input=>input.checked=true);
      box.querySelector('details').open=matches.length>0;
      assess.textContent += ` 상대 제안: 현금 ${money(t.fee)}${matches.length?' 및 '+matches.map(input=>input.closest('label').textContent.trim()).join(', '):''}.`;
      if(t.status==='insufficient_cash') assess.textContent+=' 운영예비금을 남기면 현재 현금으로는 부족합니다.';
    }
  });
  box.oninput=()=>{reply.textContent='';};
  box.querySelector('#propose').onclick=()=>{
    const fee=box.querySelector('#fee'),exchange=[...box.querySelectorAll('input[type=checkbox]:checked')].map(el=>Number(el.value));
    if(fee.value===''||!fee.checkValidity()||exchange.length>3) {reply.textContent='현금 금액과 교환 인원을 확인하세요.';return;}
    const terms={season:info.season,week:info.week,seller:fighter.seller,id:fighter.id,fee:Number(fee.value),exchange};
    runMarket('transfer_offer',terms,({transfer:t})=>{
      reply.textContent=(t.status==='insufficient_cash'&&t.counter_fee!=null ? `이적에 쓸 수 있는 현금 ${money(t.cash_limit)} · 상대 최소 요구액 ${money(t.counter_fee)} · 부족분 ${money(t.cash_shortfall)}` : (decisions[t.status]||t.status));
      if(t.status==='counter'||t.status==='accepted') {
        const action=document.createElement('button');
        action.textContent=t.status==='counter'?`역제안 ${money(t.counter_fee)} 적용`:`확정 · 잔액 ${money(t.cash_after)}`;
        action.onclick=()=>{
          if(t.status==='counter'){fee.value=t.counter_fee;box.querySelector('#propose').click();return;}
          runMarket('transfer_accept',terms,result=>{
            state=result.state;
            const outcome=result.transfer.status;
            if(outcome==='signed') {box.close();queueMicrotask(()=>management(`${fighter.name} 이적 완료`));}
            else reply.textContent=decisions[outcome]||outcome;
          });
        };
        reply.append(' ',action);
      }
    });
  };
}
