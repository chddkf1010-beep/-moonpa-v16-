const portraitRoles = ['guardian','warrior','archer','shaman','healer','assassin'];
function portrait(fighter) {
  const roleId = typeof fighter === 'number' ? fighter : fighter.role_id;
  const role = portraitRoles[roleId] || 'warrior';
  const custom = typeof fighter === 'object' ? (fighter.portrait || '') : '';
  const v2 = /^assets[/]portraits[/]diverse[/]v2_([0-5])_([0-7])[.]webp$/.exec(custom);
  if (v2) {
    const role = Number(v2[1]), slot = Number(v2[2]);
    const sheet = Math.floor(role / 2), tile = (role % 2)*8 + slot;
    return `<i class="portrait-atlas portrait-diverse-v2 portrait-v2-sheet-${sheet}" aria-hidden="true"
      style="background-position:${(tile%4)*100/3}% ${Math.floor(tile/4)*100/3}%"></i>`;
  }
  const diverse = /^assets\/portraits\/diverse\/v1_(\d{2})\.webp$/.exec(custom);
  if (diverse) {
    const tile = Number(diverse[1]);
    if (tile >= 0 && tile < 16)
      return `<i class="portrait-atlas portrait-diverse" aria-hidden="true"
        style="background-position:${(tile%4)*100/3}% ${Math.floor(tile/4)*100/3}%"></i>`;
  }
  const match = /^assets\/portraits\/founders\/seed16_(\d+)\.webp$/.exec(custom);
  const index = match ? Number(match[1]) - 640 : -1;
  const founder = index >= 0 && index < 20;
  const atlas = founder ?
    `<i class="portrait-atlas" aria-hidden="true" style="background-position:${(index%5)*25}% ${Math.floor(index/5)*100/3}%"></i>` : '';
  const src = founder ? custom : `assets/portraits/${role}_card.webp`;
  return `${atlas}<img loading="lazy" data-role-portrait src="${src}" alt="">`;
}
function bindPortraits() {
  for (const img of screen.querySelectorAll('img[data-role-portrait]')) {
    img.addEventListener('load',()=>img.classList.add('loaded'),{once:true});
    img.addEventListener('error',()=>img.remove(),{once:true});
    if(img.complete&&img.naturalWidth) img.classList.add('loaded');
  }
}

const screen = document.querySelector('#screen');
const error = document.querySelector('#error');
let state, busy = false, playback = 0, speed = 1;
let saveManager = null;
const engine = new Worker(new URL('engine-worker.mjs?v=full-roster-dual-presets2-contract-renewal1-negotiation1-market-wage1-engineboot2', document.baseURI), {type:'module'});
screen.textContent = '전투 엔진 불러오는 중…';

function callEngine(path, payload) {
  return new Promise((resolve, reject) => {
    engine.onmessage = ({data}) => {
      if(data.error){reject(new Error(data.error));return;}
      if(data.save && saveManager)saveManager.autosave(data.save);
      if(data.save_error && saveManager)saveManager.setStatus(data.save_error,true);
      resolve(data.state);
    };
    engine.onerror = () => reject(new Error('전투 엔진을 불러오지 못했습니다. 인터넷 연결을 확인하고 새로고침하세요.'));
    engine.postMessage({path, payload});
  });
}

async function request(path, data) {
  if (busy) return;
  busy = true;
  error.textContent = '';
  const enabled = [...screen.querySelectorAll('button')].filter(button=>!button.disabled);
  enabled.forEach(button => button.disabled = true);
  const monthlyButton=path==='month'?screen.querySelector('#top-week'):null;
  const monthlyLabel=monthlyButton?.textContent;
  if(monthlyButton)monthlyButton.textContent='월간 운영 처리 중…';
  const from = state?.battle?.frames.length ?? 0;
  try {
    state = await callEngine(path, data);
  } catch (e) {
    if (!state) screen.textContent = '';
    const target = screen.querySelector('#contract-error') || error;
    target.textContent = e.message;
    enabled.forEach(button => button.disabled = false);
    if(monthlyButton)monthlyButton.textContent=monthlyLabel;
    return;
  } finally {
    busy = false;
  }
  if (path === 'round') battle(from);
  else render();
}

function render() {
  document.querySelector('#meta').textContent = `${state.guild_display_name||state.guild_name} · ${state.tier}부 ${state.rank}위 · ${state.season}시즌 ${state.month}개월차`;
  if (state.contract_review) management();
  else if (state.group_play) groupBattle();
  else if (state.battle) battle();
  else if (state.elite_play) eliteScene();
  else management();
}


// Open the real roster in the arena without creating a campaign battle.
// Only an explicit validated save edits world.prebattle_plans; trial battles
// are local simulations and can never produce group_finish settlements.
async function openTacticsArena(mode='attack',zone_id=null) {
  if(busy)return;
  if(state?.phase!=='ready'){
    error.textContent='연무장 전술 저장은 월간 운영을 시작하기 전에 이용할 수 있습니다.';
    return;
  }
  busy=true;
  error.textContent='';
  let config;
  try{
    config=await callEngine('prebattle_arena_view',{mode,zone_id});
  }catch(err){
    error.textContent=err.message;
    busy=false;
    return;
  }
  busy=false;
  screen.onchange=null;
  currentTab='warroom';
  let sessionMode=mode,sessionZone=config.zone;
  const frame=document.createElement('iframe');
  frame.title='연무장 · '+(mode==='defense'?'방어전':'점령전')+' 전술 편성';
  frame.style.cssText='display:block;width:100%;height:90vh;border:0';
  const send=message=>frame.contentWindow?.postMessage(message,location.origin);
  const leave=(message='')=>{
    window.removeEventListener('message',receive);
    management(message);
    window.scrollTo(0,0);
  };
  const receive=async event=>{
    if(!frame.isConnected){window.removeEventListener('message',receive);return;}
    if(event.origin!==location.origin||event.source!==frame.contentWindow)return;
    const msg=event.data||{};
    if(msg.type==='moonpa-group-ready'){
      send({type:'moonpa-group-config',config,progression:'manual',
        heading:'연무장 · '+(mode==='defense'?'방어전':'점령전')+' 전술 편성'});
    }else if(msg.type==='moonpa-arena-plan-back'){
      leave(msg.message||'');
    }else if(msg.type==='moonpa-arena-plan-switch'){
      if(busy){send({type:'moonpa-arena-plan-switch-result',error:'다른 처리가 진행 중입니다.'});return;}
      if(!['attack','defense'].includes(msg.mode)){
        send({type:'moonpa-arena-plan-switch-result',error:'점령전 또는 방어전만 선택할 수 있습니다.'});return;
      }
      busy=true;
      try{
        const next=await callEngine('prebattle_arena_view',{mode:msg.mode});
        sessionMode=msg.mode;
        sessionZone=next.zone;
        config=next;
        frame.title='연무장 · '+(sessionMode==='defense'?'방어전':'점령전')+' 전술 편성';
        document.querySelector('#phase').textContent=frame.title;
        send({type:'moonpa-arena-plan-switch-result',config:next,heading:frame.title});
      }catch(err){
        send({type:'moonpa-arena-plan-switch-result',error:err.message});
      }finally{busy=false;}
    }else if(msg.type==='moonpa-arena-plan-save'){
      if(busy){send({type:'moonpa-arena-plan-result',error:'다른 처리가 진행 중입니다.'});return;}
      if(msg.mode!==sessionMode||msg.zone_id!==sessionZone){
        send({type:'moonpa-arena-plan-result',error:'현재 연무장 구역과 전술 유형이 일치하지 않습니다.'});return;
      }
      busy=true;
      try {
        const saved=await callEngine('prebattle_arena_save',{
          mode:sessionMode,zone_id:sessionZone,team:msg.team,
          captain:msg.captain,deputy:msg.deputy,chosenArts:msg.chosenArts});
        config=saved.config;
        send({type:'moonpa-arena-plan-result',config,message:saved.message});
      }catch(err){
        send({type:'moonpa-arena-plan-result',error:err.message});
      }finally{busy=false;}
    }
  };
  window.addEventListener('message',receive);
  frame.src='moonpa-arena.html?v=enemy-tactics6';
  screen.replaceChildren(frame);
  document.querySelector('#phase').textContent=frame.title;
  window.scrollTo(0,0);
}

function groupBattle(progression) {
  playback++;
  screen.onchange=null;
  const match=state.group_play;
  const defense=match.kind==='defense';
  const duel=match.kind==='conquest_duel';
  const title=match.kind==='playoff'?'10대10 승강전':defense?'방어전':duel?'점령지 쟁탈전':match.contestFinal?'최종 점령전':'점령전';
  const heading=title+(match.defenseTotal>1?` ${match.defenseNumber}/${match.defenseTotal}`: '');
  document.querySelector('#phase').textContent=heading;
  if(!progression){
    const enemyPower=match.enemyPower??(match.sectNames[1]==='구역 수비대'
      ? state.zones.find(zone=>zone.id===match.zone)?.defense_power : null);
    const opponentLabel=match.kind==='playoff'?'상대 문파':defense?'공격 문파':duel?'경쟁 문파':
      match.sectNames[1]==='구역 수비대'?'':'점령 문파';
    screen.innerHTML=`<dialog class="wood battle-choice" aria-labelledby="battle-choice-title">
      <h2 id="battle-choice-title">${heading}</h2>
      ${match.zone==null?'':`<p class="battle-site">${match.tier??state.tier}부 · ${siteName(match.zone,match.zoneName)}</p>`}
      <p>${opponentLabel} <strong>${escapeText(match.sectNames[1])}</strong></p>
      <p>${defense||duel?'공격대':match.kind==='playoff'?'상대':'수비대'} 평균 전력 <strong>${powerLabel(enemyPower)}</strong></p>
      <p class="muted-copy">${defense?`수비대 ${match.team.length}명 · 최대 체력`:
        `${escapeText(match.sectNames[0])} ${match.team.length}명 · 평균 전력 ${powerLabel(match.teamPower)}`}</p>
      ${duel?'<p>승리한 공격대가 수비대와 맞붙습니다. 무승부는 평균 전력이 높은 쪽이 진출합니다.</p>':''}
      <div class="controls">
        <button type="button" class="primary" id="group-auto" aria-describedby="auto-watch">${match.observer?'전투 관전':'자동 진행'}</button>
        ${match.observer?'':'<button type="button" id="group-direct">수동 진행</button>'}
        <button type="button" id="group-skip" title="전투 연출을 생략하고 결과를 정산합니다.">전투 스킵 · 즉시 정산</button>
      </div>
      <small id="auto-watch">${match.observer?'경쟁 문파가 다음 전투를 치릅니다.':'자동은 저장된 편성으로 바로 관전하고, 수동은 진형과 무공을 조정한 뒤 시작합니다.'} 스킵은 현재 전투 1건의 연출을 생략하고 실제 승패·부상·점령 결과를 반영합니다.</small>
    </dialog>`;
    const choice=screen.querySelector('dialog');
    choice.addEventListener('cancel',event=>event.preventDefault());
    screen.querySelector('#group-auto').onclick=()=>{if(!busy)groupBattle('auto');};
    const manual=screen.querySelector('#group-direct');
    if(manual)manual.onclick=()=>{if(!busy)groupBattle('manual');};
    screen.querySelector('#group-skip').onclick=()=>{if(!busy)request('group_auto',{match:match.match});};
    choice.showModal();
    return;
  }
  const frame=document.createElement('iframe');
  frame.title=heading;
  frame.style.cssText='display:block;width:100%;height:90vh;border:0';
  const send=message=>frame.contentWindow?.postMessage(message,location.origin);
  const receive=async event=>{
    if(!frame.isConnected){window.removeEventListener('message',receive);return;}
    if(event.origin!==location.origin||event.source!==frame.contentWindow)return;
    if(event.data?.type==='moonpa-group-ready')send({type:'moonpa-group-config',config:match,progression,heading});
    if(event.data?.type==='moonpa-group-assign'){
      if(busy){send({type:'moonpa-group-assignment-result',error:'이미 다른 처리가 진행 중입니다.'});return;}
      busy=true;
      try {
        state=await callEngine('group_assign',event.data);
        send({type:'moonpa-group-assignment-result',config:state.group_play});
      } catch(error) {
        send({type:'moonpa-group-assignment-result',error:error.message});
      } finally {busy=false;}
      return;
    }
    if(event.data?.type==='moonpa-group-finish'&&!busy){
      await request('group_finish',event.data);
      if(frame.isConnected)send({type:'moonpa-group-error'});
      else window.removeEventListener('message',receive);
    }
  };
  window.addEventListener('message',receive);
  frame.src='moonpa-arena.html?v=enemy-tactics6';
  screen.replaceChildren(frame);
  window.scrollTo(0,0);
}

function eliteScene() {
  playback++;
  screen.onchange=null;
  const quest=state.elite_play;
  document.querySelector('#phase').textContent='정예 임무 · 현장 사건';
  const team=quest.team.map(f=>'<article class="elite-hero"><strong>'+
    escapeText(f.name)+'</strong><small>'+escapeText(f.role)+
    (f.id===quest.lead?' · 핵심 인물':'')+'</small></article>').join('');
  const chapter=quest.saga?' · 연속 기연':'';
  const scene=quest.stage==='scene';
  screen.innerHTML='<section class="wood elite-quest">'+
    '<small>정예 임무 직접 진행'+chapter+' · '+escapeText(quest.difficulty)+'</small>'+
    '<h2>'+escapeText(quest.title)+'</h2>'+
    '<p>'+escapeText(quest.story)+'</p>'+
    '<div class="elite-story"><h3>'+(scene?'1단계 · 현장 도착':'2단계 · 현장 결정')+'</h3>'+
    '<p>'+escapeText(quest.scene)+'</p>'+
    (scene?'<p class="muted-copy">임무의 단서를 조사한 뒤 대응 방식을 결정하세요.</p>':
    '<p>'+escapeText(quest.warning)+'</p>')+'</div>'+
    '<h3>임무 참가 문파원</h3><div class="elite-party">'+team+'</div>'+
    (scene?'<div class="controls"><button class="primary" id="elite-inspect">현장 단서 조사</button></div>':
     '<h3>어떻게 대응하시겠습니까?</h3><div class="elite-decisions">'+
        Object.entries(quest.choices).map(([key,c])=>
        '<button type="button" class="elite-decision" data-elite-choice="'+key+'">'+
        '<strong>'+escapeText(c.title)+'</strong><small>'+escapeText(c.description)+'</small></button>').join('')+
     '</div><p class="muted-copy">선택을 확정하면 바로 전투가 시작되며, 승패·생존 상태에 따라 전리품과 기연 결과가 결정됩니다.</p>')+
    '</section>';
  if(scene)screen.querySelector('#elite-inspect').onclick=()=>request('elite_inspect',{});
  else screen.querySelectorAll('[data-elite-choice]').forEach(b=>
    b.onclick=()=>request('elite_decide',{choice:b.dataset.eliteChoice}));
}

function setup() {
  if (state.dead) { screen.textContent = '문파가 해체되었습니다.'; return; }
  document.querySelector('#phase').textContent='모의전 편성';
  const zones = state.zones.filter(z => z.selectable);
  screen.innerHTML = `<div class="weekly-actions"><strong>5대5 모의전 편성 <small id="count"></small></strong>
    <button type="button" id="back">문파 운영</button><button type="button" id="start" class="primary">모의전 출전</button></div>
    <div class="bar"><label>목표 구역 <select id="zone">${zones.map(z => `<option value="${z.id}">${siteTargetLabel(z)}</option>`).join('')}</select></label>
    </div><p id="zone-intel" class="muted-copy">${zones.length?'':'공격 가능한 구역이 없습니다. 전투 연무장에서는 구역 없이 연습할 수 있습니다.'}</p>
    ${memberSortControl('practice',rosterSorts)}
    <div class="roster">${sortMembers('practice',state.roster).map(f => `<article class="unit  ${f.injured || f.expedition ? 'muted' : ''}" data-sort-id="${f.id}">
      <div class="roster-face" aria-hidden="true">${portrait(f)}</div>
      <label><input class="member" type="checkbox" ${f.recommended && !f.injured && !f.expedition ? 'checked' : ''} ${f.injured || f.expedition ? 'disabled' : ''}> ${escapeText(f.name)} · ${f.role}${f.notable?` · ${f.notable.rarity==='legend'?'전설':'네임드'} ${escapeText(f.notable.title)}`:''}</label>
      <small>CA ${f.ca} · Lv ${f.lv}${f.injured ? ' · 부상 ' + f.injured + '주' : f.expedition?' · 원정 중':''}</small>
      <select aria-label="전열 후열" class="line"><option value="front">전열</option><option value="back" ${[0,1].includes(f.role_id) ? '' : 'selected'}>후열</option></select>
      ${f.skills.map(k => `<label><input class="equip" type="checkbox" value="${k}" ${(f.equipped ?? f.skills).includes(k)?'checked':''}> ${state.skills[k].name}</label>`).join('')}
      </article>`).join('')}</div>
    `;
  const update = () => {
    const n = screen.querySelectorAll('.member:checked').length;
    screen.querySelector('#count').textContent = `${n}/5`;
    screen.querySelector('#start').disabled = n !== 5 || !zones.length;
    const selectedZone=zones.find(z=>z.id===Number(screen.querySelector('#zone').value));
    if(selectedZone) screen.querySelector('#zone-intel').textContent=`시즌: ${state.season_trend.name} (${state.season_trend.description}) · 지형: ${selectedZone.terrain.name} (${selectedZone.terrain.description}) · 적 전술: ${selectedZone.tactic.name} (${selectedZone.tactic.description}) · 적 편성: ${selectedZone.enemy_lineup.map(f=>f.name+' / '+f.role+' / '+f.row+(f.notable?' / '+f.notable.skill+' ('+f.notable.description+')':'')).join(', ')}`;
  };
  const selected = state.roster.map(f=>screen.querySelector(`[data-sort-id="${f.id}"]`))
    .filter(card=>card.querySelector('.member').checked).map(card=>card.querySelector('.line'));
  if (selected.length && selected.every(select=>select.value==='back')) selected[0].value='front';
  screen.onchange = update;
  bindSort(screen,'practice',()=>reorderMembers(screen.querySelector('.roster'),'practice',state.roster));
  bindPortraits();
  update();
  screen.querySelector('#back').onclick = () => management();
  screen.querySelector('#start').onclick = () => {
    const team = state.roster.map(f=>screen.querySelector(`[data-sort-id="${f.id}"]`))
      .filter(card=>card.querySelector('.member').checked);
    request('start',{zone:Number(screen.querySelector('#zone').value),practice:true,
      setup:team.map(card => ({id:Number(card.dataset.sortId),row:card.querySelector('.line').value,skills:[...card.querySelectorAll('.equip:checked')].map(e=>e.value)}))});
  };
}

function describe(skill) {
  const targets = {front:'적 전열 (암살형 우회)',enemy:'적 전·후열',self:'자신',ally:'아군 한 명'};
  return [skill.note, skill.power ? `배율 ${skill.power}` : '', targets[skill.target],
    `내공 ${skill.cost}`, `재사용 대기 ${skill.cooldown}라운드`].filter(Boolean).join(' · ');
}

const effects = {wall:'방패진', guard:'방어', ward:'호신', taunt:'도발', stun:'기절',
  notable_seal:'무공 봉인', zhuge_power:'호법진', legend_speed:'천기삼변', legend_barrier:'생사윤회', legend_redirect:'부동명왕',
  curse:'공격력 −50%', veil:'은신', riposte:'반격', valor:'무투가'};

function battle(from = null) {
  const playing = from !== null;
  playback++; screen.onchange = null;
  const b = state.battle, done = b.winner !== null;
  document.querySelector('#phase').textContent = b.kind==='elite' ? '정예 임무 전투' : b.practice ? '모의전' : '점령전';
  const teams = [1,0].map(side => `<div class="side"><h3>${side ? (b.kind==='elite'?'시련의 적':'수비측') : '아군'}</h3><div class="team">
    ${b.units.filter(u=>u.side===side).map(u=>`<article class="unit ${u.hp ? '' : 'muted'}" data-unit="${u.id}">
    <div class="portrait" aria-hidden="true"><span>${u.role.slice(0,1)}</span>${portrait(u)}<b class="float"></b></div>
    <strong>${u.name}</strong>${u.notable?`<small class="hero-tag ${u.notable.rarity==='legend'?'hero-legend':'hero-named'}">${u.notable.rarity==='legend'?'전설':'네임드'} · ${escapeText(u.notable.skill)}</small>`:''}<small>${u.row==='front' ? '전열' : '후열'} · <span class="hp">${u.hp}/${u.max_hp}</span> 체력</small>
    <progress class="health" value="${u.hp}" max="${u.max_hp}"></progress><small><span class="energy">${u.qi}/${u.max_qi}</span> 내공</small>
    <progress class="qi" value="${u.qi}" max="${u.max_qi}"></progress>
    <small class="effects">${u.effects.map(k=>effects[k]).join(" · ")}</small>
    ${!side && u.hp && !done && !playing ? `<select class="skill" aria-label="무공"><option value="">행동 선택</option>${Object.entries(u.options).map(([k,ids])=>`<option value="${k}" ${ids.length?'':'disabled'}>${state.skills[k].name}</option>`).join('')}</select>
    <select class="target" aria-label="대상" disabled></select><button class="info" type="button">무공 정보</button><small class="tip" hidden></small>` : ''}
    ${done && !playing ? `<small>가한 피해 ${u.damage} · 받은 피해 ${u.hit_taken} · 치유량 ${u.healing}</small>` : ''}
    </article>`).join('')}</div></div>`).join('');
  const result = state.result;
  const eliteSummary=result?.elite ? escapeText(result.title)+' · '+escapeText(result.outcome)+' · 보상 '+money(result.gross)+' · 준비비 '+money(result.cost)+' — '+escapeText(result.summary) : '';
  screen.innerHTML = `<h2 id="round">${b.kind==='elite'?escapeText(b.title)+' · ':''}${b.round} / 20 라운드</h2>${b.environment?`<p class="muted-copy">유행 병법: ${escapeText(b.environment.trend.name)} · ${escapeText(b.environment.trend.description)} / 전장: ${escapeText(b.environment.terrain.name)} · ${escapeText(b.environment.terrain.description)} / 적 전술: ${escapeText(b.environment.tactic.name)}</p>`:''}<div id="initiative" aria-label="행동 순서"></div><p id="action" aria-live="polite"></p>${teams}
    <div class="controls"><label>연출 속도 <select id="speed"><option value="1">1배속</option><option value="2">2배속</option><option value="4">4배속</option><option value="0">즉시</option></select></label>
    ${playing ? '<button id="skip">즉시 결과 보기</button>' : ''}</div>
    ${playing ? "" : done ? `<div class="panel result"><h3>${b.winner===0?'공격측 승리':'방어측 승리'}</h3>
      <p>${result.elite?eliteSummary:result.practice?'모의전 종료 · 문파 상태 유지':`${siteName(result.zone,result.zone_name)} · ${result.success?'점령 성공':'점령 실패'} · 주간 현금 변동 ${result.cash_change}냥${result.released===null?'':' · 기존 구역 '+result.released+' 반납'}`}</p>
      ${result.participants ? `<small>${result.participants.filter(x=>x.side===0).map(x=>`#${x.id} 경험치 +${x.xp}${x.injured ? ', 부상 '+x.injured+'주' : ''}${x.legendary_awakened?' · 전설 각성!':''}`).join(' / ')}</small>` : ''}</div>
      <div class="controls"><button id="replay">재생</button><button id="again" class="primary">${result.elite?(state.elite_play?.next_attack?"전리품 확정 · 점령전 계속":"전리품 확정 · 월간 진행"):"문파 운영"}</button></div>`
      : `<div class="controls"><button class="primary" id="manual" disabled>명령 확정</button>
      <label>자동 전술 <select id="style"><option value="balanced">균형</option><option value="protect">치유형 보호</option><option value="pressure">후열 압박</option></select></label>
      <button id="auto">자동 1라운드</button><button id="finish">자동으로 끝까지</button></div>`}
      <div class="panel"><h3>전투 기록</h3><div class="log" id="log"></div></div>`;
  bindPortraits();
  const control = screen.querySelector('#speed');
  control.value = String(speed);
  control.onchange = () => {
    speed = Number(control.value);
    if (playing && !speed) render();
  };
  if (playing) {
    screen.querySelector('#skip').onclick = render;
    playActions(b, from, playback);
    return;
  }
  const frame = done ? b.frames.at(-1) : null;
  showOrder(b, frame?.order || b.initiative, b.units, null, new Set(done ? frame.order : []));
  showLog(b.events);
  if (done) {
    screen.querySelector('#replay').onclick = () => { if (!speed) speed=1; battle(0); };
    screen.querySelector('#again').onclick = () => {
      currentTab = b.practice ? 'week' : 'ledger';
      request(result.elite?'elite_finish':'dismiss_battle',{});
    };
    return;
  }
  const inputs = [...screen.querySelectorAll('article')].filter(card => card.querySelector('.skill'));
  const update = () => screen.querySelector('#manual').disabled = !inputs.every(card => card.querySelector('.target').value);
  for (const card of inputs) {
    const u = b.units.find(x=>x.id===Number(card.dataset.unit));
    const select = card.querySelector('.skill'), target = card.querySelector('.target'), tip = card.querySelector('.tip');
    const info = card.querySelector('.info');
    let timer;
    select.onchange = () => {
      const ids = u.options[select.value] || [];
      target.innerHTML = ids.map(id=>`<option value="${id}">${b.units.find(x=>x.id===id).name}</option>`).join('');
      target.disabled = !ids.length;
      tip.hidden = true;
      update();
    };
    target.onchange = update;
    const show = () => {tip.textContent = select.value ? describe({...state.skills[select.value],cost:Math.max(0,state.skills[select.value].cost-2*(u.skill_ranks?.[select.value]||0))}) : '무공을 선택하세요.';tip.hidden = false;};
    info.onclick = () => tip.hidden ? show() : tip.hidden = true;
    for (const trigger of [info,select]) {
      trigger.onmouseenter = () => timer = setTimeout(show,1000);
      trigger.onmouseleave = () => clearTimeout(timer);
    }
  }
  const step = (commands,finish=false) => request('round',{round:b.round,seed:b.seed,commands,finish,style:screen.querySelector('#style').value});
  screen.querySelector('#auto').onclick = () => step(null);
  screen.querySelector('#finish').onclick = () => step(null,true);
  screen.querySelector('#manual').onclick = () => step(Object.fromEntries(inputs.map(card=>[card.dataset.unit,
    [card.querySelector('.skill').value,Number(card.querySelector('.target').value)]])));
}

function showLog(events) {
  const log = screen.querySelector('#log');
  log.replaceChildren(...events.map(event=>{const p=document.createElement('p');p.textContent=`R${event.round} · ${event.text}`;return p;}));
  log.scrollTop=log.scrollHeight;
}

function showOrder(b, order, snapshot, current, completed) {
  const byId = new Map(snapshot.map(u=>[u.id,u]));
  screen.querySelector('#initiative').innerHTML = order.map((id,index)=>{
    const fighter = b.units.find(u=>u.id===id), status = byId.get(id);
    const disabled = !status.hp || status.effects.includes('stun');
    const label = !status.hp ? '전투불능' : disabled ? '기절' : fighter.side ? '수비측' : '아군';
    return `<div class="order-entry ${id===current?'acting':''} ${completed.has(id)||disabled?'muted':''}">
      <b>${index+1}</b><span>${fighter.name}<small>${label}</small></span></div>`;
  }).join('');
}

function updateCards(snapshot) {
  for (const unit of snapshot) {
    const card = screen.querySelector(`[data-unit="${unit.id}"]`);
    const health = card.querySelector('.health'), energy = card.querySelector('.qi');
    health.value = unit.hp;
    energy.value = unit.qi;
    card.querySelector('.hp').textContent = `${unit.hp}/${health.max}`;
    card.querySelector('.energy').textContent = `${unit.qi}/${energy.max}`;
    card.querySelector('.effects').textContent = unit.effects.map(k=>effects[k]).join(' · ');
    card.classList.toggle('muted',!unit.hp);
  }
}

const melee = new Set(['hit','strike','fang','riposte']);
const motes = {arrow:'➶',pin:'⟐',curse:'✦',ward:'◈',heal:'✚',cleanse:'✧',taunt:'❗'};
const impactKinds = new Set(['damage','critical','miss','resist','reflection','heal','buff','debuff']);

async function animateImpact(event, source, target) {
  if (!source || !target || !speed || !impactKinds.has(event.kind) ||
      matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const origin = source.querySelector('.portrait').getBoundingClientRect();
  const end = target.querySelector('.portrait').getBoundingClientRect();
  const y = end.top + end.height/2 - origin.top - origin.height/2;
  const x = end.left + end.width/2 - origin.left - origin.width/2;
  const charge = melee.has(event.skill) && event.kind !== 'reflection'
    && ['damage','critical','miss'].includes(event.kind);
  const mote = event.kind==='reflection' ? '↯' : motes[event.skill];
  if (!charge && !mote && source !== target) return;
  const sprite = document.createElement('div');
  sprite.className = charge ? 'battle-sprite portrait' : 'battle-sprite battle-mote';
  sprite.dataset.skill = event.skill;
  sprite.dataset.kind = event.kind;
  if (charge) {
    const face = source.querySelector('.portrait');
    const visible = face.querySelector('img.loaded, .portrait-atlas');
    sprite.append((visible || face.querySelector('span')).cloneNode(true));
  }
  else sprite.textContent = mote || '◈';
  const w = charge ? origin.width : 38, h = charge ? origin.height : 38;
  Object.assign(sprite.style, {left:`${origin.left+(origin.width-w)/2}px`,
    top:`${origin.top+(origin.height-h)/2}px`, width:`${w}px`,height:`${h}px`});
  sprite.setAttribute('aria-hidden','true');
  screen.append(sprite);
  const anim = sprite.animate([
    {transform:'translate(0,0) scale(.9)',opacity:0},
    {transform:`translate(${x*.12}px,${y*.12-12}px) scale(1.08)`,opacity:1,offset:.24},
    {transform:`translate(${x}px,${y}px) scale(1.18)`,opacity:1,offset:.86},
    {transform:`translate(${x}px,${y}px) scale(.8)`,opacity:0}
  ], {duration:(charge ? 510 : 410)/speed, easing:'ease-in-out'});
  try { await anim.finished; } finally { sprite.remove(); }
}

async function playActions(b, from, token) {
  const valid = () => token === playback;
  const pause = ms => new Promise(resolve=>setTimeout(resolve,ms/Math.max(1,speed)));
  const card = id => screen.querySelector(`[data-unit="${id}"]`);
  let seen = from ? b.frames[from-1].event_end : 0;
  if (!speed) { render(); return; }
  for (const frame of b.frames.slice(from)) {
    const completed = new Set();
    screen.querySelector('#round').textContent = `${frame.round} / 20 라운드`;
    updateCards(frame.initial);
    showOrder(b,frame.order,frame.initial,null,completed);
    showLog(b.events.slice(0,seen));
    await pause(440);
    if (!valid()) return;
    let snapshot = frame.initial;
    for (const action of frame.actions) {
      const actor = card(action.actor);
      actor.classList.add('acting');
      showOrder(b,frame.order,snapshot,action.actor,completed);
      screen.querySelector('#action').textContent = `${b.units.find(u=>u.id===action.actor).name} · ${state.skills[action.skill].name}`;
      for (const event of b.events.slice(action.start,action.end)) {
        const target = card(event.target);
        await animateImpact(event, card(event.actor), target);
        if (!valid()) return;
        snapshot = event.units;
        updateCards(snapshot);
        showOrder(b,frame.order,snapshot,action.actor,completed);
        if (target) {
          const fx = target.querySelector('.float');
          const text = {miss:'회피!', resist:'저항', debuff:event.skill==='curse'?'공격력 −50%':event.skill==='taunt'?'도발':'기절',
            buff:state.skills[event.skill]?.name, knockout:'전투불능'};
          fx.textContent = event.amount === null ? text[event.kind] || '' : `${event.kind==='heal'?'+':'−'}${event.amount}`;
          target.dataset.fx = event.kind;
          target.dataset.skill = event.skill || '';
        }
        showLog(b.events.slice(0,++seen));
        await pause(['knockout','skip'].includes(event.kind) ? 360 : 660);
        if (!valid()) return;
        if (target) { delete target.dataset.fx; delete target.dataset.skill; target.querySelector('.float').textContent=''; }
      }
      actor.classList.remove('acting');
      completed.add(action.actor);
    }
    seen = frame.event_end;
    updateCards(frame.units);
    showOrder(b,frame.order,frame.units,null,completed);
    showLog(b.events.slice(0,seen));
  }
  if (valid()) render();
}
function applyLoadedGame(loaded) {
  playback++; // Cancel pending combat animations from a different save.
  state=loaded;
  currentTab='office';
  leagueTier=null;
  worldMapSelectedId=null;
  draft={clock:'',assignments:{},zone:null};
  render();
}

saveManager = new SaveManager({
  callEngine,applyGame:applyLoadedGame,
  isBusy:()=>busy,
  setBusy:value=>{busy=value;}
});
document.querySelector('#open-arena-tactics')?.addEventListener('click',()=>{
  if(!busy)openTacticsArena('attack');
});
saveManager.boot();
