const portraitRoles = ['guardian','warrior','archer','shaman','healer','assassin'];
function portrait(fighter) {
  const roleId = typeof fighter === 'number' ? fighter : fighter.role_id;
  const role = portraitRoles[roleId] || 'warrior';
  const custom = typeof fighter === 'object' ? (fighter.portrait || '') : '';
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
const engine = new Worker(new URL('engine-worker.mjs?v=20261121-bc-season-terrain-1', document.baseURI), {type:'module'});
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
  const from = state?.battle?.frames.length ?? 0;
  try {
    state = await callEngine(path, data);
  } catch (e) {
    if (!state) screen.textContent = '';
    error.textContent = e.message;
    enabled.forEach(button => button.disabled = false);
    return;
  } finally {
    busy = false;
  }
  if (path === 'round') battle(from);
  else render();
}

function render() {
  document.querySelector('#meta').textContent = `${state.guild_name} · ${state.tier}부 ${state.rank}위 · ${state.season}시즌 ${state.week}주`;
  if (state.battle) battle();
  else if (state.elite_play) eliteScene();
  else management();
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
  const zones = state.zones.filter(z => z.selectable);
  screen.innerHTML = `<h2>출전 편성 <small id="count"></small></h2>
    <div class="bar"><label>목표 구역 <select id="zone">${zones.map(z => `<option value="${z.id}">구역 ${z.id} · ${escapeText(z.owner_name)} · ${escapeText(z.terrain.name)} · ${escapeText(z.tactic.name)} · 주 ${z.value}냥 기준</option>`).join('')}</select></label>
    </div><p id="zone-intel" class="muted-copy"></p>
    <div class="roster">${state.roster.map(f => `<article class="unit ${f.injured ? 'muted' : ''}" data-id="${f.id}">
      <div class="roster-face" aria-hidden="true">${portrait(f)}</div>
      <label><input class="member" type="checkbox" ${f.recommended ? 'checked' : ''} ${f.injured ? 'disabled' : ''}> ${escapeText(f.name)} · ${f.role}</label>
      <small>CA ${f.ca} · Lv ${f.lv} · 피로 ${f.fatigue}${f.injured ? ' · 부상 ' + f.injured + '주' : ''}</small>
      <select aria-label="전열 후열" class="line"><option value="front">전열</option><option value="back" ${[0,1].includes(f.role_id) ? '' : 'selected'}>후열</option></select>
      ${f.skills.map(k => `<label><input class="equip" type="checkbox" value="${k}" ${(f.equipped ?? f.skills).includes(k)?'checked':''}> ${state.skills[k].name}</label>`).join('')}
      </article>`).join('')}</div>
    <div class="controls"><button id="start" class="primary">모의전 출전</button><button id="back">문파 운영</button></div>`;
  const update = () => {
    const n = screen.querySelectorAll('.member:checked').length;
    screen.querySelector('#count').textContent = `${n}/5`;
    screen.querySelector('#start').disabled = n !== 5 || !zones.length;
    const selectedZone=zones.find(z=>z.id===Number(screen.querySelector('#zone').value));
    if(selectedZone) screen.querySelector('#zone-intel').textContent=`시즌: ${state.season_trend.name} (${state.season_trend.description}) · 지형: ${selectedZone.terrain.name} (${selectedZone.terrain.description}) · 적 전술: ${selectedZone.tactic.name} (${selectedZone.tactic.description}) · 적 편성: ${selectedZone.enemy_lineup.map(f=>f.name+' / '+f.role+' / '+f.row).join(', ')}`;
  };
  const selected = [...screen.querySelectorAll('.member:checked')].map(input=>input.closest('article').querySelector('.line'));
  if (selected.length && selected.every(select=>select.value==='back')) selected[0].value='front';
  screen.onchange = update;
  bindPortraits();
  update();
  screen.querySelector('#back').onclick = () => management();
  screen.querySelector('#start').onclick = () => {
    const team = [...screen.querySelectorAll('.roster article')].filter(card => card.querySelector('.member').checked);
    request('start',{zone:Number(screen.querySelector('#zone').value),practice:true,
      setup:team.map(card => ({id:Number(card.dataset.id),row:card.querySelector('.line').value,skills:[...card.querySelectorAll('.equip:checked')].map(e=>e.value)}))});
  };
}

function describe(skill) {
  const targets = {front:'적 전열 (암살형 우회)',enemy:'적 전·후열',self:'자신',ally:'아군 한 명'};
  return [skill.note, skill.power ? `배율 ${skill.power}` : '', targets[skill.target],
    `내공 ${skill.cost}`, `재사용 대기 ${skill.cooldown}라운드`].filter(Boolean).join(' · ');
}

const effects = {wall:'방패진', guard:'방어', ward:'호신', taunt:'도발', stun:'기절',
  curse:'공격력 −50%', veil:'은신', riposte:'반격', valor:'무투가'};

function battle(from = null) {
  const playing = from !== null;
  playback++; screen.onchange = null;
  const b = state.battle, done = b.winner !== null;
  document.querySelector('#phase').textContent = b.kind==='elite' ? '정예 임무 전투' : b.practice ? '모의전' : '점령전';
  const teams = [1,0].map(side => `<div class="side"><h3>${side ? (b.kind==='elite'?'시련의 적':'수비측') : '아군'}</h3><div class="team">
    ${b.units.filter(u=>u.side===side).map(u=>`<article class="unit ${u.hp ? '' : 'muted'}" data-unit="${u.id}">
    <div class="portrait" aria-hidden="true"><span>${u.role.slice(0,1)}</span>${portrait(u)}<b class="float"></b></div>
    <strong>${u.name}</strong><small>${u.row==='front' ? '전열' : '후열'} · <span class="hp">${u.hp}/${u.max_hp}</span> 체력</small>
    <progress class="health" value="${u.hp}" max="${u.max_hp}"></progress><small><span class="energy">${u.qi}/${u.max_qi}</span> 내공</small>
    <progress class="qi" value="${u.qi}" max="${u.max_qi}"></progress>
    <small class="effects">${u.effects.map(k=>effects[k]).join(" · ")}</small>
    ${!side && u.hp && !done && !playing ? `<select class="skill" aria-label="무공"><option value="">행동 선택</option>${Object.entries(u.options).map(([k,ids])=>`<option value="${k}" ${ids.length?'':'disabled'}>${state.skills[k].name}</option>`).join('')}</select>
    <select class="target" aria-label="대상" disabled></select><button class="info" type="button">무공 정보</button><small class="tip" hidden></small>` : ''}
    ${done && !playing ? `<small>피해 ${u.damage} · 회복 ${u.healing} · 보호 ${u.prevented}</small>` : ''}
    </article>`).join('')}</div></div>`).join('');
  const result = state.result;
  const eliteSummary=result?.elite ? escapeText(result.title)+' · '+escapeText(result.outcome)+' · 보상 '+money(result.gross)+' · 준비비 '+money(result.cost)+' — '+escapeText(result.summary) : '';
  screen.innerHTML = `<h2 id="round">${b.kind==='elite'?escapeText(b.title)+' · ':''}${b.round} / 20 라운드</h2>${b.environment?`<p class="muted-copy">유행 병법: ${escapeText(b.environment.trend.name)} · ${escapeText(b.environment.trend.description)} / 전장: ${escapeText(b.environment.terrain.name)} · ${escapeText(b.environment.terrain.description)} / 적 전술: ${escapeText(b.environment.tactic.name)}</p>`:''}<div id="initiative" aria-label="행동 순서"></div><p id="action" aria-live="polite"></p>${teams}
    <div class="controls"><label>연출 속도 <select id="speed"><option value="1">1배속</option><option value="2">2배속</option><option value="4">4배속</option><option value="0">즉시</option></select></label>
    ${playing ? '<button id="skip">즉시 결과 보기</button>' : ''}</div>
    ${playing ? "" : done ? `<div class="panel result"><h3>${b.winner===0?'공격측 승리':'방어측 승리'}</h3>
      <p>${result.elite?eliteSummary:result.practice?'모의전 종료 · 문파 상태 유지':`구역 ${result.zone} · ${result.success?'점령 성공':'점령 실패'} · 주간 현금 변동 ${result.cash_change}냥${result.released===null?'':' · 기존 구역 '+result.released+' 반납'}`}</p>
      ${result.participants ? `<small>${result.participants.filter(x=>x.side===0).map(x=>`#${x.id} 경험치 +${x.xp}, 피로 +${x.fatigue}${x.injured ? ', 부상 '+x.injured+'주' : ''}`).join(' / ')}</small>` : ''}</div>
      <div class="controls"><button id="replay">재생</button><button id="again" class="primary">${result.elite?(state.elite_play?.next_attack?"전리품 확정 · 점령전 계속":"전리품 확정 · 주간 결산"):"문파 운영"}</button></div>`
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
  draft={clock:'',assignments:{},zone:null};
  render();
}

saveManager = new SaveManager({
  callEngine,applyGame:applyLoadedGame,
  isBusy:()=>busy,
  setBusy:value=>{busy=value;}
});
saveManager.boot();
