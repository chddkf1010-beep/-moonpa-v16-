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
const labels = {territory_gross:'구역 수입', territory_direct_maintenance:'구역 유지비',
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
  document.querySelector('#phase').textContent='문파 운영';
  screen.onchange=null;
  const clock = `${state.season}:${state.week}`;
  if (draft.clock!==clock) draft={clock,assignments:{},zone:null};
  const tabs={week:'주간 운영',roster:'문파원 명부',ledger:'재정 장부',free:'낭인 시장',scout:'타 문파 스카우트'};
  screen.innerHTML = `${stats()}<nav class="management-tabs" aria-label="문파 운영">
    ${Object.entries(tabs).map(([key,name])=>`<button data-tab="${key}" aria-pressed="${key===currentTab}">${name}</button>`).join('')}</nav>
    <div id="management-panel"></div>`;
  screen.querySelectorAll('[data-tab]').forEach(button=>button.onclick=()=>{
    if(busy) return;
    currentTab=button.dataset.tab;
    management();
  });
  if(currentTab==='week') showWeek();
  if(currentTab==='roster') showRoster();
  if(currentTab==='ledger') showLedger();
  bindPortraits();
  if(currentTab==='free') await runMarket('free_agents',{},showFree);
  if(currentTab==='scout') await runMarket('scout',{},showScout);
}

function rosterTable(assignments=false) {
  return `<div class="table-scroll"><table><thead><tr><th>문파원</th><th>역할</th><th>CA</th><th>레벨</th><th>피로</th><th>상태</th>${assignments?'<th>이번 주 배치</th>':''}</tr></thead><tbody>
  ${state.roster.map(f=>`<tr><th scope="row"><span class="member-face">${portrait(f)}</span>${escapeText(f.name)}</th><td>${f.role}</td><td>${f.ca}</td><td>${f.lv}</td><td>${Math.round(f.fatigue)}</td>
  <td>${f.injured?`<span class="bad">부상 ${f.injured}주</span>`:'정상'}</td>${assignments?`<td><select class="assignment" data-id="${f.id}" aria-label="${escapeText(f.name)} 배치">
  ${Object.entries(applications).filter(([key])=>!f.injured || ['auto','rest'].includes(key)).map(([key,text])=>
    `<option value="${key}" ${draft.assignments[f.id]===key?'selected':''}>${text}</option>`).join('')}</select></td>`:''}</tr>`).join('')}
  </tbody></table></div>`;
}
function showRoster() {
  panel().innerHTML=`<section class="wood"><h2>문파원 명부</h2>${rosterTable()}</section>`;
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
      <div class="skills">${f.skills.map(key=>`<label><input type="checkbox" value="${key}" ${draft.skills?.[f.id]?.includes(key)!==false?'checked':''}>${state.skills[key].name}</label>`).join('')}</div>
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
  <button class="primary" id="next-week">다음 주 배치</button></section></div>`;

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
  panel().querySelector('#next-week').onclick=()=>{currentTab='week';management();};
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
  ${market.candidates.length?'':'<p>현재 영입할 수 있는 낭인이 없어.</p>'}</section>`;
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

function showScout(info,seller='') {
  panel().innerHTML=`<div class="management-grid"><section class="wood"><h2>타 문파 스카우트</h2>
  <label class="field">문파 선택<select id="seller"><option value="">문파 선택</option>${info.sects.map(s=>`<option value="${s.id}" ${seller===s.id?'selected':''}>${s.tier}부 · ${escapeText(s.name)}</option>`).join('')}</select></label>
  ${seller===''?'':`<div class="table-scroll"><table><thead><tr><th>후보</th><th>역할</th><th>전력 / 잠재력</th><th>예상 이적료</th><th>주급</th><th>협상</th></tr></thead><tbody>
  ${info.candidates.map(f=>`<tr><th scope="row">${escapeText(f.name)}</th><td>${f.role}</td><td>${f.ca_grade} / ${f.pa_grade}</td><td>${money(f.estimate)}</td><td>${money(f.wage)}</td><td><button data-negotiate="${f.id}" ${f.locked||info.market_closed?'disabled':''}>${f.locked?'이적 제한':'제안'}</button></td></tr>`).join('')}</tbody></table></div>`}</section>
  <aside class="wood side-board" id="offer"><h2>이적 제안</h2><p>후보를 골라 제안 조건을 확인해.</p></aside></div>`;
  panel().querySelector('#seller').onchange=e=>{
    const value=e.target.value;
    if(value==='') showScout({...info,candidates:[]});
    else runMarket('scout',{seller:Number(value)},reply=>showScout(reply,Number(value)));
  };
  panel().querySelectorAll('[data-negotiate]').forEach(btn=>btn.onclick=()=>showOffer(info,
    info.candidates.find(f=>f.id===Number(btn.dataset.negotiate))));
}
function showOffer(info,fighter) {
  const box=panel().querySelector('#offer');
  box.innerHTML=`<h2>${escapeText(fighter.name)}</h2><p>${fighter.role} · 현재 주급 ${money(fighter.wage)} · ${fighter.contract_end}시즌 만료</p>
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
      reply.textContent=decisions[t.status]||t.status;
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
