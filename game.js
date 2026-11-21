const screen = document.querySelector('#screen');
const error = document.querySelector('#error');
let state, busy = false, playback = null;
const engine = new Worker(new URL('engine-worker.mjs?v=20261121-fix2', document.baseURI), {type:'module'});
screen.textContent = '전투 엔진 불러오는 중…';

function callEngine(path, payload) {
  return new Promise((resolve, reject) => {
    engine.onmessage = ({data}) => data.error ? reject(new Error(data.error)) : resolve(data.state);
    engine.onerror = () => reject(new Error('전투 엔진을 불러오지 못했습니다. 인터넷 연결을 확인하고 새로고침하세요.'));
    engine.postMessage({path, payload});
  });
}

async function request(path, data) {
  if (busy) return;
  busy = true;
  error.textContent = '';
  [...screen.querySelectorAll('button')].forEach(button => button.disabled = true);
  try {
    state = await callEngine(path, data);
    render();
  } catch (e) {
    if (!state) screen.textContent = '';
    error.textContent = e.message;
    [...screen.querySelectorAll('button')].forEach(button => button.disabled = false);
  } finally {
    busy = false;
  }
}

function render() {
  document.querySelector('#meta').textContent = `${state.season}시즌 ${state.week}주 · 문파 #${state.guild} · ${state.cash.toLocaleString()}냥`;
  if (state.battle) battle();
  else setup();
}

function setup() {
  if (state.dead) { screen.textContent = '문파가 해체되었습니다.'; return; }
  const zones = state.zones.filter(z => z.selectable);
  screen.innerHTML = `<h2>출전 편성 <small id="count"></small></h2>
    <div class="bar"><label>목표 구역 <select id="zone">${zones.map(z => `<option value="${z.id}">구역 ${z.id} · ${z.owner === null ? '수비대' : '문파 #' + z.owner} · 주 ${z.value}냥 기준</option>`).join('')}</select></label>
    <label><input id="practice" type="checkbox"> 모의전</label></div>
    <div class="roster">${state.roster.map(f => `<article class="unit ${f.injured ? 'muted' : ''}" data-id="${f.id}">
      <label><input class="member" type="checkbox" ${f.recommended ? 'checked' : ''} ${f.injured ? 'disabled' : ''}> ${f.role} #${f.id}</label>
      <small>CA ${f.ca} · Lv ${f.lv} · 피로 ${f.fatigue}${f.injured ? ' · 부상 ' + f.injured + '주' : ''}</small>
      <select aria-label="전열 후열" class="line"><option value="front">전열</option><option value="back" ${[0,1].includes(f.role_id) ? '' : 'selected'}>후열</option></select>
      ${f.skills.map(k => `<label><input class="equip" type="checkbox" value="${k}" checked> ${state.skills[k].name}</label>`).join('')}
      </article>`).join('')}</div>
    <button id="start" class="primary">출전</button>`;
  const update = () => {
    const n = screen.querySelectorAll('.member:checked').length;
    screen.querySelector('#count').textContent = `${n}/5`;
    screen.querySelector('#start').disabled = n !== 5 || !zones.length;
  };
  const selected = [...screen.querySelectorAll('.member:checked')].map(input=>input.closest('article').querySelector('.line'));
  if (selected.length && selected.every(select=>select.value==='back')) selected[0].value='front';
  screen.onchange = update;
  update();
  screen.querySelector('#start').onclick = () => {
    const team = [...screen.querySelectorAll('.roster article')].filter(card => card.querySelector('.member').checked);
    request('start',{zone:Number(screen.querySelector('#zone').value),practice:screen.querySelector('#practice').checked,
      setup:team.map(card => ({id:Number(card.dataset.id),row:card.querySelector('.line').value,skills:[...card.querySelectorAll('.equip:checked')].map(e=>e.value)}))});
  };
}

function describe(skill) {
  const targets = {front:'적 전열 (암살형 우회)',enemy:'적 전·후열',self:'자신',ally:'아군 한 명'};
  return [skill.note, skill.power ? `배율 ${skill.power}` : '', targets[skill.target],
    `내공 ${skill.cost}`, `재사용 대기 ${skill.cooldown}라운드`].filter(Boolean).join(' · ');
}

function battle() {
  clearInterval(playback); screen.onchange = null;
  const b = state.battle, done = b.winner !== null;
  document.querySelector('#phase').textContent = b.practice ? '모의전' : '점령전';
  const labels = {wall:'방패진', guard:'방어', ward:'호신', taunt:'도발', stun:'기절', curse:'약화', veil:'은신', riposte:'반격', valor:'무투가'};
  const teams = [1,0].map(side => `<div class="side"><h3>${side ? '수비측' : '아군'}</h3><div class="team">
    ${b.units.filter(u=>u.side===side).map(u=>`<article class="unit ${u.hp ? '' : 'muted'}" data-unit="${u.id}">
    <strong>${u.name}</strong><small>${u.row==='front' ? '전열' : '후열'} · <span class="hp">${u.hp}/${u.max_hp}</span> 체력</small>
    <progress class="health" value="${u.hp}" max="${u.max_hp}"></progress><small><span class="energy">${u.qi}/${u.max_qi}</span> 내공</small>
    <progress class="qi" value="${u.qi}" max="${u.max_qi}"></progress>
    ${u.effects.length ? `<small>${u.effects.map(k=>labels[k]).join(" · ")}</small>` : ""}
    ${!side && u.hp && !done ? `<select class="skill" aria-label="무공"><option value="">행동 선택</option>${Object.entries(u.options).map(([k,ids])=>`<option value="${k}" ${ids.length?'':'disabled'}>${state.skills[k].name}</option>`).join('')}</select>
    <select class="target" aria-label="대상" disabled></select><button class="info" type="button">무공 정보</button><small class="tip" hidden></small>` : ''}
    ${done ? `<small>피해 ${u.damage} · 회복 ${u.healing} · 보호 ${u.prevented}</small>` : ''}
    </article>`).join('')}</div></div>`).join('');
  const result = state.result;
  screen.innerHTML = `<h2 id="round">${b.round} / 20 라운드</h2>${teams}
    ${done ? `<div class="panel result"><h3>${b.winner===0?'공격측 승리':'방어측 승리'}</h3>
      <p>${result.practice?'모의전 종료 · 문파 상태 유지':`구역 ${result.zone} · ${result.success?'점령 성공':'점령 실패'} · 주간 현금 변동 ${result.cash_change}냥${result.released===null?'':' · 기존 구역 '+result.released+' 반납'}`}</p>
      ${result.participants ? `<small>${result.participants.filter(x=>x.side===0).map(x=>`#${x.id} 경험치 +${x.xp}, 피로 +${x.fatigue}${x.injured ? ', 부상 '+x.injured+'주' : ''}`).join(' / ')}</small>` : ''}</div>
      <div class="controls"><button id="replay">재생</button><label>배속 <select id="speed"><option>1</option><option>2</option><option>4</option></select></label><button id="skip">건너뛰기</button><button id="again" class="primary">다음 편성</button></div>`
      : `<div class="controls"><button class="primary" id="manual" disabled>명령 확정</button>
      <label>자동 전술 <select id="style"><option value="balanced">균형</option><option value="protect">치유형 보호</option><option value="pressure">후열 압박</option></select></label>
      <button id="auto">자동 1라운드</button><button id="finish">자동으로 끝까지</button></div>`}
      <div class="panel"><h3>전투 기록</h3><div class="log" id="log"></div></div>`;
  showLog(b.events);
  if (done) { replayControls(b); return; }
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
    const show = () => {tip.textContent = select.value ? describe(state.skills[select.value]) : '무공을 선택하세요.';tip.hidden = false;};
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

function replayControls(b) {
  const frame = i => {
    const snapshot = b.frames[i];
    screen.querySelector('#round').textContent = `${snapshot.round} / 20 라운드`;
    for (const unit of snapshot.units) {
      const card = screen.querySelector(`[data-unit="${unit.id}"]`);
      card.querySelector('.health').value = unit.hp;
      card.querySelector('.qi').value = unit.qi;
      card.querySelector('.hp').textContent = `${unit.hp}/${card.querySelector('.health').max}`;
      card.querySelector('.energy').textContent = `${unit.qi}/${card.querySelector('.qi').max}`;
      card.classList.toggle('muted',!unit.hp);
    }
    showLog(b.events.filter(e=>e.round<=snapshot.round));
  };
  screen.querySelector('#replay').onclick = () => {
    clearInterval(playback);
    let index = 0;
    frame(index++);
    playback = setInterval(()=>{if(index>=b.frames.length) clearInterval(playback); else frame(index++);},
      800/Number(screen.querySelector('#speed').value));
  };
  screen.querySelector('#skip').onclick = () => {clearInterval(playback);frame(b.frames.length-1);};
  screen.querySelector('#again').onclick = () => {clearInterval(playback);state.battle=null;setup();};
}
request('state');
