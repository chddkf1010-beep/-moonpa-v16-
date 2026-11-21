let currentTab = 'week';
let draft = {clock:'', assignments:{}, zone:null};
const number = value => Number(value).toLocaleString('ko-KR');
const money = value => `${number(value)}냥`;
const escapeText = value => String(value ?? '').replace(/[&<>"']/g, c =>
  ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[c]);
const decisions = {
  signed:'계약 완료', unavailable:'후보가 시장에 없습니다', roster_full:'임시 정원까지 가득 찼습니다',
  insufficient_cash:'계약금과 운영예비금이 부족합니다', outstanding_debt:'미지급 채무가 있습니다',
  declined_this_week:'이번 주 제안을 거절했습니다', market_closed:'전투 또는 주간 운영 중입니다',
  accepted:'수락 가능한 조건입니다', counter:'상대 문파가 조건을 변경해 제안했습니다',
  refused:'상대 문파가 거절했습니다', unfunded:'자금 또는 시장 가격 한도를 초과했습니다',
  roster:'거래 후 정원 조건을 충족하지 못합니다', locked:'이번 시즌에 이적한 문파원입니다',
  invalid:'제안 조건을 다시 확인하세요'
};
const applications = {auto:'자동 배치',training:'훈련',mission1:'수익 임무 1',mission2:'수익 임무 2',
  rest:'휴식',attack:'점령전'};
const labels = {estate_income:'장원 수입', facility_upgrade:'건축물 승급', territory_gross:'구역 수입', territory_direct_maintenance:'구역 유지비',
  territory_scale_overhead:'구역 관리비', weekly_wages:'문파원 주급', hall_upkeep:'문파 유지비',
  mission_gross_reward:'임무 보상', mission_preparation:'임무 준비비', paid_training:'훈련비',
  paid_investment:'육성 투자', fa_signing_fee:'계약금', transfer_fee:'이적료',
  mentor_fee:'사부 지도비', league_sponsor:'리그 후원금',
  garrison_cost:'주둔 비용', no_territory_livelihood:'생계 임무 수입'};

function panel() { return screen.querySelector('#management-panel'); }
function notice(message) { error.textContent = message; }
function stats() {
  return `<div class="summary-strip">
    <div><small>보유금</small><strong>${money(state.cash)}</strong></div>
    <div><small>문파원</small><strong>${state.roster.length}명</strong></div>
    <div><small>보유 구역</small><strong>${state.zones.filter(z=>z.owner===state.guild).length}곳</strong></div>
    <div><small>리그 순위</small><strong>${state.tier}부 ${state.rank}위</strong></div>
  </div>`;
}
async function management(message = '') {
  if (state.dead) {screen.textContent='문파가 해체되었습니다.';return;}
  notice(message);
  if (state.phase==='tutorial'||state.phase==='draft') {showOpening();return;}
  if (state.phase==='fa') currentTab='free';
  if (state.phase==='report') currentTab='ledger';
  document.querySelector('#phase').textContent='문파 운영';
  screen.onchange=null;
  const clock = `${state.season}:${state.week}`;
  if (draft.clock!==clock) draft={clock,assignments:{},zone:null};
  const tabs={week:'주간 운영',roster:'문파원 명부',ledger:'재정 장부',free:'낭인 시장',scout:'타 문파 스카우트',facility:'건축물'};
  screen.innerHTML = `${stats()}<nav class="management-tabs" aria-label="문파 운영">
    ${Object.entries(tabs).filter(([key])=>state.phase==='ready'||key===currentTab).map(([key,name])=>`<button data-tab="${key}" aria-pressed="${key===currentTab}">${name}</button>`).join('')}</nav>
    <div id="management-panel"></div>`;
  screen.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{
    if(busy) return;
    currentTab=button.dataset.tab;
    management();
  });
  if(currentTab==='week') showWeek();
  if(currentTab==='roster') showRoster();
  if(currentTab==='ledger') showLedger();
  if(currentTab==='facility') showFacilities();
  bindPortraits();
  panel().querySelectorAll('[data-member]').forEach(button=>button.onclick=()=>
    runMarket('member',{id:Number(button.dataset.member)},showMember));
  if(currentTab==='free') await runMarket('free_agents',{},showFree);
  if(currentTab==='scout') await runMarket('scout',{},showScout);
}

function advancePhase() {
  currentTab='week';
  request('advance_phase',{phase:state.phase});
}

function showOpening() {
  document.querySelector('#phase').textContent=state.phase==='tutorial'?'문파 창설':'신인 드래프트';
  if(state.phase==='tutorial') {
    screen.innerHTML=`${stats()}<section class="parchment"><h2>${escapeText(state.guild_name)} 창설</h2>
      <p>4부에서 시작해 문파원을 키우고 구역을 확보해 1부 우승에 도전해.</p>
      <p>지금은 창설 문파원 ${state.roster.length}명이 있어. 먼저 드래프트 5라운드에서 신인을 한 명씩 골라. 그다음 낭인 시장에서 필요한 역할을 보강할 수 있어.</p>
      <p>매주 훈련·수익 임무·점령전을 배치하고, 결산에서 수입과 지출을 확인하면 돼.</p>
      <button class="primary" id="opening-next">초기 문파원 확인</button><div id="founders"></div></section>`;
    const button=screen.querySelector('#opening-next');
    button.onclick=()=>{
      screen.querySelector('#founders').innerHTML=`<section class="wood">${rosterTable()}</section>`;
      screen.querySelectorAll('#founders .member-link').forEach(link=>link.disabled=true);
      bindPortraits();
      button.textContent='신인 드래프트 시작';button.onclick=advancePhase;
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
    ${sorted.map(f=>`<tr><th>${escapeText(f.name)}</th><td>${f.role}</td><td>${f.age}</td><td>${f.ca} / ${f.pa}</td><td>${money(f.wage)}</td>
    <td><button data-pick="${f.id}" ${draft.roster_full?'disabled':''}>지명</button></td></tr>`).join('')}</tbody></table></div></section>`;
  const pick=id=>request('draft_pick',{season:state.season,round:draft.round,id});
  screen.querySelector('#draft-pass').onclick=()=>pick(null);
  screen.querySelectorAll('[data-pick]').forEach(button=>button.onclick=()=>pick(Number(button.dataset.pick)));
}

function showFacilities() {
  const status=(id,level)=>id==='training'?`훈련 성장 +${8*level}%`:id==='estate'?
    `주간 수입 +${20*level}냥 · FA 계약금 ${4*level}% 할인`:`부상 발생 확률 ${12*level}% 감소`;
  panel().innerHTML=`<section class="wood"><h2>건축물 관리</h2><div class="facility-grid">
    ${state.facilities.map(f=>`<article class="unit"><h3>${f.name} · Lv ${f.level}/${f.max}</h3>
    <p>현재 · ${status(f.id,f.level)}</p>${f.next_cost==null?'<small>최고 레벨</small>':
    `<p>다음 · ${status(f.id,f.level+1)}</p><button data-upgrade="${f.id}" ${state.cash<f.next_cost?'disabled':''}>승급 · ${money(f.next_cost)}</button>`}</article>`).join('')}
    </div></section>`;
  panel().querySelectorAll('[data-upgrade]').forEach(button=>button.onclick=()=>{
    if(confirm(button.textContent+'을 진행할까요?')) request('upgrade',{id:button.dataset.upgrade});
  });
}
function rosterTable(assignments=false) {
  return `<div class="table-scroll"><table><thead><tr><th>문파원</th><th>역할</th><th>CA</th><th>레벨</th><th>남은 계약</th><th>상태</th>${assignments?'<th>이번 주 배치</th>':''}</tr></thead><tbody>
  ${state.roster.map(f=>`<tr><th scope="row"><span class="member-face">${portrait(f)}</span><button class="member-link" data-member="${f.id}">${escapeText(f.name)}</button></th><td>${f.role}</td><td>${f.ca}</td><td>${f.lv}</td><td>${Math.max(0,f.contract_end-state.season+1)}시즌</td>
  <td>${f.injured?`<span class="bad">부상 ${f.injured}주</span>`:'정상'}</td>${assignments?`<td><select class="assignment" data-id="${f.id}" aria-label="${escapeText(f.name)} 배치">
  ${Object.entries(applications).filter(([key])=>!f.injured || ['auto','rest'].includes(key)).map(([key,text])=>
    `<option value="${key}" ${draft.assignments[f.id]===key?'selected':''}>${text}</option>`).join('')}</select></td>`:''}</tr>`).join('')}
  </tbody></table></div>`;
}
function showRoster() {
  panel().innerHTML=`<section class="wood"><h2>문파원 명부</h2>${rosterTable()}</section>`;
}
const attributes = {strength:'근력', defense:'방어', stamina:'체력', agility:'민첩',
  inner_power:'내공', sorcery:'술법', insight:'통찰', willpower:'정신력'};

function showMember(f) {
  panel().innerHTML=`<div class="management-grid"><section class="wood">
  <div class="controls"><button id="member-back">명부로</button></div>
  <h2>${escapeText(f.name)}</h2><p>${f.role} · ${f.age}세 · Lv ${f.level} · 주급 ${money(f.wage)} · 계약 ${f.remaining}시즌 남음</p>
  <div class="ledger-head"><span>현재 전력 <b>${f.ca}</b></span><span>잠재력 <b>${f.pa}</b></span></div>
  <table><thead><tr><th>능력</th><th>기본</th><th>특성 반영</th><th>역할 반영 비율</th></tr></thead><tbody>
  ${f.attributes.map(a=>`<tr><th scope="row">${attributes[a.key]}</th><td>${a.base}</td><td>${a.effective}</td><td>${a.weight}%</td></tr>`).join('')}</tbody></table>
  </section><aside class="wood"><h2>무공 수련</h2><p>남은 포인트 <strong>${f.points}</strong></p>
  <p class="muted-copy">장착 <span id="slot-count">${f.equipped.length}</span>/${f.slots} · 레벨마다 무공 포인트 1점, 투자 단계당 내공 소모 −2.</p>
  <p class="muted-copy">임무에서 지원·방어 무공은 성공률을 보조해.</p>
  ${f.skills.map(k=>`<article class="skill-node"><h3>${k.name} ${k.rank}/3</h3><p>${escapeText(k.note||'공격 배율 '+k.power)}</p>
  <small>해금 Lv ${k.level} · 내공 ${Math.max(0,k.cost-2*k.rank)} · 재사용 대기 ${k.cooldown}라운드</small>
  <label><input type="checkbox" data-equip="${k.id}" ${f.equipped.includes(k.id)?'checked':''} ${f.level<k.level?'disabled':''}> 장착</label>
  <button data-train="${k.id}" ${k.rank>=3||f.level<k.level||!f.points?'disabled':''}>1점 투자</button></article>`).join('')}
  <button id="save-skills" class="primary">장착 저장</button></aside></div>`;
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
function showWeek() {
  const zones=state.zones.filter(z=>z.selectable);
  const offers=state.mission_board||[];
  draft.missionChoices ??={1:offers[0]?.id||'',2:offers[1]?.id||''};
  draft.missionApproaches ??={1:'balanced',2:'balanced'};
  const offerFor=slot=>offers.find(x=>x.id===draft.missionChoices[slot]);
  panel().innerHTML=`<div class="management-grid"><section class="wood"><h2>이번 주 배치</h2>
    <p class="muted-copy">자동 배치는 남은 자리를 훈련으로 채워. 수익 임무는 팀마다 3명, 점령전은 5명이 필요해.</p>
    ${rosterTable(true)}</section>
    <aside class="wood side-board"><h2>주간 계획</h2><div id="staffing"></div>
    <label class="field">점령 목표<select id="target-zone"><option value="">구역 선택</option>
    ${zones.map(z=>`<option value="${z.id}" ${draft.zone===z.id?'selected':''}>구역 ${z.id} · ${escapeText(z.owner_name)}</option>`).join('')}</select></label>
    <div id="lineup"></div><div class="controls"><button id="recommend" type="button">추천 5명 배치</button></div><hr><div id="mission-board"></div><div class="controls"><button class="primary" id="advance">주간 배치 확정</button><button id="practice">모의전</button>
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
    block.append(label,tactics);
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
    }).join(' / ')+' / 점령전 · '+attackers().length+'/5';
    panel().querySelector('#target-zone').disabled=!attackers().length;
    lineup();
  };
  panel().onchange=e=>{
    if(e.target.matches('.assignment')) {draft.assignments[e.target.dataset.id]=e.target.value;update();}
    if(e.target.id==='target-zone') draft.zone=e.target.value?Number(e.target.value):null;
    const fighter=e.target.closest('[data-fighter]');
    if(fighter&&e.target.matches('.row')) (draft.rows??={})[fighter.dataset.fighter]=e.target.value;
    if(fighter&&e.target.matches('input')) (draft.skills??={})[fighter.dataset.fighter]=[...fighter.querySelectorAll('input:checked')].map(x=>x.value);
  };
  panel().querySelector('#recommend').onclick=()=>{
    if(busy) return;
    const team=state.roster.filter(f=>f.recommended&&!f.injured);
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
    if(attack.length&&(attack.length!==5||draft.zone===null)) {notice('점령전에 5명을 배치하고 목표 구역을 선택하세요.');return;}
    const setup=[...panel().querySelectorAll('[data-fighter]')].map(row=>({id:Number(row.dataset.fighter),
      row:row.querySelector('.row').value,skills:[...row.querySelectorAll('input:checked')].map(x=>x.value)}));
    if(setup.length&&!setup.some(f=>f.row==='front')) {notice('점령전에는 전열 문파원을 한 명 이상 배치하세요.');return;}
    currentTab='ledger';
    request('week',{season:state.season,week:state.week,assignment:{training:ids('training'),rest:ids('rest'),
      mission_orders,attack:attack.length?{zone:draft.zone,setup}:null}});
  };
  update();
}

function showLedger() {
  const report=state.week_report;
  if(!report) {panel().innerHTML='<section class="wood"><h2>재정 장부</h2><p>첫 주간 결산 후 수입·지출을 볼 수 있어.</p></section>';return;}
  const sums=new Map();
  for(const entry of report.entries) sums.set(entry.category,(sums.get(entry.category)||0)+entry.amount);
  const changed=report.members.filter(f=>f.ca_change||f.levels||f.xp_before!==f.xp||f.fatigue_change||f.injured_before!==f.injured);
  panel().innerHTML=`<div class="management-grid"><section class="parchment"><h2>${report.season}시즌 ${report.week}주 결산</h2>
  <div class="ledger-head"><span>수입 <b>${money(report.income)}</b></span><span>지출 <b>${money(report.expenses)}</b></span><span>기말 잔액 <b>${money(report.cash)}</b></span></div>
  ${report.battle?`<p>구역 ${report.battle.zone} · ${report.battle.success?'점령 성공':'점령 실패'}</p>`:''}
  <h3>장부 내역</h3><dl>${[...sums].map(([k,v])=>`<dt>${escapeText(labels[k]||k)}</dt><dd>${v>0?'+':''}${money(v)}</dd>`).join('')}</dl>
  <h3>구역별 총수입</h3><dl>${report.territories.map(t=>`<dt>구역 ${t.zone} · ${t.days}일</dt><dd>${money(t.gross)}</dd>`).join('')}</dl></section>
  <section class="wood"><h2>문파원 변동</h2><dl>${changed.map(f=>`<dt>${escapeText(state.roster.find(x=>x.id===f.id)?.name??'#'+f.id)}</dt><dd>CA ${f.ca_change>0?'+':''}${f.ca_change} · 피로 ${f.fatigue_change>0?'+':''}${f.fatigue_change}${f.injured?` · 부상 ${f.injured}주`:''}</dd>`).join('')}</dl>
  <button class="primary" id="next-week">${report.season===state.season?'다음 주로':'신인 드래프트로'}</button></section></div>`;
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
  panel().querySelector('#next-week').onclick=state.phase==='report'?advancePhase:()=>{currentTab='week';management();};
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
  panel().innerHTML=`<section class="wood"><h2>낭인 시장</h2><p class="muted-copy">문파원 ${market.roster_count}/${market.normal_roster_limit}명 · 임시 정원 ${market.roster_limit}명</p>
  <div class="table-scroll"><table><thead><tr><th>후보</th><th>역할</th><th>나이</th><th>CA / PA</th><th>계약금</th><th>주급</th><th>예상 잔액</th><th>계약</th></tr></thead><tbody>
  ${market.candidates.map(f=>`<tr data-candidate="${f.id}"><th scope="row">${escapeText(f.name)}</th><td>${f.role}</td><td>${f.age}</td><td>${f.ca} / ${f.pa}</td><td>${money(f.fee)}</td><td>${money(f.wage)}</td><td>${money(f.cash_after)}</td>
    <td>${f.eligible?`<div class="inline-controls"><select class="years" aria-label="계약 기간">${market.terms_years.map(y=>`<option value="${y}">${y}시즌</option>`).join('')}</select><button class="hire" type="button">영입</button></div>`:`<small>${decisions[f.reason]||'영입 불가'}</small>`}</td></tr>`).join('')}</tbody></table></div>
  ${market.candidates.length?'':'<p>현재 영입할 수 있는 낭인이 없어.</p>'}
  ${state.phase==='fa'?'<div class="controls"><button class="primary" id="start-season">시즌 시작</button></div>':''}</section>`;
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

function showScout(info) {
  const sects=new Map(info.sects.map(s=>[s.id,s]));
  const roles=[...new Set(info.candidates.map(f=>f.role))];
  panel().innerHTML=`<div class="management-grid"><section class="wood"><h2>타 문파 스카우트</h2>
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
    <aside class="wood side-board" id="offer"><h2>이적 제안</h2><p>후보 이름을 눌러 제안해.</p></aside></div>`;
  const get=id=>panel().querySelector('#'+id);
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
    get('scout-list').innerHTML=rows.slice(page*30,page*30+30).map(f=>`<tr><th scope="row"><button class="member-link" data-negotiate="${f.id}">${escapeText(f.name)}</button></th>
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
  box.innerHTML=`<h2>${escapeText(fighter.name)}</h2><p>${fighter.role} · ${fighter.age}세 · 현재 ${fighter.ca} / 잠재력 ${fighter.pa} · 현재 주급 ${money(fighter.wage)} · ${fighter.contract_end}시즌 만료</p>
  <label class="field">현금 제안<input id="fee" type="number" min="0" step="1" max="${info.cash}" value="${Math.min(fighter.estimate,info.cash)}"></label>
  <details><summary>교환 문파원 선택 (최대 3명)</summary><div class="exchange-list">
  ${info.exchange_pool.map(f=>`<label><input type="checkbox" value="${f.id}" ${f.locked?'disabled':''}> ${escapeText(f.name)} · ${f.role}</label>`).join('')}</div></details>
  <div class="controls"><button class="primary" id="propose">조건 제안</button></div><div id="offer-reply" aria-live="polite"></div>`;
  const reply=box.querySelector('#offer-reply');
  box.oninput=()=>{reply.textContent='';};
  box.querySelector('#propose').onclick=()=>{
    const fee=box.querySelector('#fee'),exchange=[...box.querySelectorAll('input[type=checkbox]:checked')].map(el=>Number(el.value));
    if(fee.value===''||!fee.checkValidity()||exchange.length>3) {reply.textContent='현금 금액과 교환 인원을 확인하세요.';return;}
    const terms={season:info.season,week:info.week,seller:fighter.seller,id:fighter.id,fee:Number(fee.value),exchange};
    runMarket('transfer_offer',terms,({transfer:t})=>{
      reply.textContent=(decisions[t.status]||t.status) +
        (t.status==='insufficient_cash'&&t.counter_fee!=null ? ` · 상대 요구 현금 ${money(t.counter_fee)}` : '');
      if(t.status==='counter'||t.status==='accepted') {
        const action=document.createElement('button');
        action.textContent=t.status==='counter'?`역제안 ${money(t.counter_fee)} 적용`:`확정 · 잔액 ${money(t.cash_after)}`;
        action.onclick=()=>{
          if(t.status==='counter'){fee.value=t.counter_fee;box.querySelector('#propose').click();return;}
          runMarket('transfer_accept',terms,result=>{
            state=result.state;
            const outcome=result.transfer.status;
            if(outcome==='signed') queueMicrotask(()=>management(`${fighter.name} 이적 완료`));
            else reply.textContent=decisions[outcome]||outcome;
          });
        };
        reply.append(' ',action);
      }
    });
  };
}
