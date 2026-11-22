/* v11: primary-eight growth dashboard; no training commit until weekly confirmation. */
const growthUI=(()=>{
  let mode='attack',view=null,chosenId=null,windowSize=5,preview=null,overwriteFocus=false;
  const esc=value=>escapeText(String(value??''));
  const fmt=value=>value==null?'—':Number(value).toLocaleString('ko-KR',{maximumFractionDigits:2});
  const plus=value=>value==null?'—':(value>0?'+':'')+fmt(value);
  const stats={strength:'근력',defense:'방어',stamina:'체력',agility:'민첩',
               inner_power:'내공',sorcery:'술법',insight:'통찰',willpower:'정신력'};
  const tactical={frontline:'전선 유지력',rear_protection:'후열 보호력',breakthrough:'돌파력',ranged_fire:'원거리 화력'};
  const weekLabel=r=>r.season+'시즌 '+r.week+'주';
  function open(nextMode='attack'){
    mode=nextMode;
    preview=null;
    runMarket('growth_view',{mode},result=>{
      view=result;
      if(!result.members.some(f=>f.id===chosenId))chosenId=result.members[0]?.id??null;
      draw();
    });
  }
  function recent(v){
    if(!v||v.delta==null)return '기록 없음';
    if(!v.observed_weeks)return '첫 기록';
    return plus(v.delta)+(v.complete?'':' · '+v.observed_weeks+'주 관측');
  }
  function plot(rows){
    if(!rows.length)return '<p class="muted-copy">주간 성장 기록이 없습니다. 다음 결산부터 관측됩니다.</p>';
    const data=rows.slice(-windowSize-1),values=data.map(x=>x.ca);
    const lo=Math.min(...values)-1, hi=Math.max(...values)+1;
    const xp=i=>data.length===1?320:50+i*530/(data.length-1);
    const yp=y=>145-(y-lo)/(hi-lo||1)*112;
    return `<svg class="growth-chart" viewBox="0 0 640 185" role="img" aria-label="실제 성장 기록 ${data.length}개에 대한 CA 변화">
      <line x1="38" y1="145" x2="590" y2="145" stroke="currentColor" opacity=".25"/>
      <line x1="38" y1="32" x2="38" y2="145" stroke="currentColor" opacity=".25"/>
      <text x="40" y="22">${fmt(hi)}</text><text x="40" y="161">${fmt(lo)}</text>
      ${data.length>1?`<polyline points="${data.map((p,i)=>xp(i).toFixed(1)+','+yp(p.ca).toFixed(1)).join(' ')}"
      stroke="#a7c79a" stroke-width="3" stroke-linejoin="round" stroke-linecap="round" fill="none"/>`:''}
      ${data.map((p,i)=>`<circle cx="${xp(i)}" cy="${yp(p.ca)}" r="4" fill="#ddb878">
        <title>${weekLabel(p)} · CA ${fmt(p.ca)} · ${esc(p.activity)}</title></circle>`).join('')}
      <text x="50" y="177">${weekLabel(data[0])}</text>
      <text x="590" y="177" text-anchor="end">${weekLabel(data[data.length-1])}</text>
    </svg>`;
  }

  function focusSelector(member){
    const selected=member.focus.focus;
    return `<label class="growth-focus-select">개인 수련 방향
      <select data-growth-focus="${member.id}" aria-label="${esc(member.name)} 수련 방향" ${view.ready?'':'disabled'}>
        ${view.focus_options.map(opt=>`<option value="${esc(opt.id)}" ${selected===opt.id?'selected':''}>${esc(opt.name)}</option>`).join('')}
      </select></label>`;
  }
  function selectedFocus(member){
    if(!member)return '';
    const current=member.focus;
    return `<section class="growth-focus-details">
      <div class="office-title"><h4>현재 수련 방향 · ${esc(current.focus_name)}</h4>
        <small>부문주 추천: ${esc(view.focus_options.find(x=>x.id===current.recommended)?.name||'균형 수련')}</small></div>
      <p class="muted-copy">${esc(current.recommend_reason)}. ${esc(current.note)}</p>
      <div class="growth-focus-bars">
        ${current.allocation.map(x=>`<label>
          <span>${esc(x.name)} <strong>${x.share}%</strong> <small>(균형 ${x.balanced_share}%)</small></span>
          <progress value="${x.share}" max="35"></progress>
        </label>`).join('')}
      </div>
    </section>`;
  }

  function focusPreviewPanel(){
    if(!preview||preview.mode!==mode||preview.overwrite!==overwriteFocus)return '';
    const label=key=>view.focus_options.find(x=>x.id===key)?.name||'균형 수련';
    return `<section class="growth-preview" aria-label="주력 8인 수련 추천안">
      <div class="office-title"><h4>적용 전 추천안 · ${mode==='attack'?'점령조':'방어조'} 8인</h4>
        <small>실제 변경 ${preview.effective_change_count}명 · 기존 수동 설정 유지 ${preview.preserved_count}명</small></div>
      <p class="muted-copy">${esc(preview.note)} 이번 추천의 적용 대상은 ${preview.assigned_count}명입니다.</p>
      <div class="growth-preview-rows">${preview.members.map(m=>`<div class="growth-preview-row">
        <span><strong>${esc(m.name)}</strong><small>${esc(m.role)} · ${m.row==='front'?'전열':'후열'}</small></span>
        <span>${esc(label(m.current))} <span aria-hidden="true">→</span> <strong>${esc(label(m.proposed))}</strong></span>
        <small>${m.preserved?'수동 설정 유지':m.changed?'변경 예정':'현재와 동일'}</small>
      </div>`).join('')}</div>
      <div class="growth-preview-actions">
        <button type="button" id="growth-focus-confirm" ${preview.assigned_count?'':'disabled'}>이 추천안 적용</button>
        <button type="button" id="growth-focus-cancel">미리보기 닫기</button>
      </div>
    </section>`;
  }
  function memberPanel(f){
    if(!f)return '<section class="wood"><h3>개인 성장 상세</h3><p>주력 인원이 부족합니다.</p></section>';
    const start=f.history[0];
    return `<section class="wood growth-person">
      <div class="office-title"><div><small>주력 개인 성장 분석 · ${f.row==='front'?'전열':'후열'}</small>
        <h3>${esc(f.name)}</h3><p>${esc(f.role)} · Lv.${f.level}
          ${f.captain?'· 대장':f.deputy?'· 부대장':''}</p></div>
        <button type="button" id="growth-member-detail">무공·문파원 상세</button></div>
      <div class="growth-person-stats">
        <div><small>최초 관측 CA</small><strong>${fmt(f.initial_ca)}</strong></div>
        <div><small>현재 CA</small><strong>${fmt(f.ca)}</strong></div>
        <div><small>현재 PA</small><strong>${fmt(f.pa)}</strong></div>
        <div><small>누적 성장</small><strong>${plus(f.total_delta)}</strong></div>
      </div>
      ${selectedFocus(f)}
      <div class="office-title"><h4>실제 CA 변화 기록</h4>
        <div class="inline-controls"><button type="button" data-growth-window="5" aria-pressed="${windowSize===5}">5주</button>
        <button type="button" data-growth-window="10" aria-pressed="${windowSize===10}">10주</button></div></div>
      ${plot(f.history)}
      <p>최근 5주 <b>${recent(f.growth_5)}</b> · 최근 10주 <b>${recent(f.growth_10)}</b></p>
      <p class="muted-copy">마지막 기록 활동: ${esc(f.recent_activity)} · 실측 기록이 부족하면 관측 기간만 표시됩니다.</p>
      <h4>8개 능력치 변화</h4>
      <div class="table-scroll"><table class="growth-attributes">
        <thead><tr><th>능력</th><th>최초 주간 기록</th><th>현재</th><th>변화</th></tr></thead>
        <tbody>${Object.keys(stats).map(key=>`<tr><th scope="row">${stats[key]}</th>
          <td>${start?fmt(start.attrs[key]):'—'}</td><td>${fmt(f.attrs[key])}</td>
          <td class="${(f.stat_deltas?.[key]||0)>0?'growth-positive':''}">${plus(f.stat_deltas?.[key])}</td></tr>`).join('')}</tbody></table></div>
    </section>`;
  }
  function draw(){
    if(currentTab!=='growth'||!view)return;
    const v=view,k=v.summary,f=v.members.find(x=>x.id===chosenId);
    panel().innerHTML=`<div class="growth-page">
      <section class="wood">
        <div class="office-title"><div><small>v11 · 실제 주간 성장 기록</small><h2>주력 8인 육성 관리실</h2></div>
          <button type="button" id="growth-warroom">전투 편성실</button></div>
        <nav class="growth-mode" aria-label="주력 8인 선택">
          <button type="button" data-growth-mode="attack" aria-pressed="${mode==='attack'}">점령조 8인</button>
          <button type="button" data-growth-mode="defense" aria-pressed="${mode==='defense'}">방어조 8인</button>
        </nav>
        <p class="muted-copy">편성 출처: <strong>${esc(v.source)}</strong> · ${v.season}시즌 ${v.week}주차</p>
        <section class="growth-focus-bulk">
          <div><strong>부문주 8인 수련 방향 추천</strong>
            <small>역할에 맞는 개인별 특화 방향을 설정합니다. 기존 수련비·성장 총량은 변경하지 않습니다.</small></div>
          <label><input type="checkbox" id="growth-focus-overwrite" ${overwriteFocus?'checked':''}>수동 설정도 추천으로 덮어쓰기</label>
          <button type="button" id="growth-focus-auto" ${v.ready?'':'disabled'}>추천안 미리보기</button>
        </section>
        ${focusPreviewPanel()}
        <div class="growth-kpis">
          <div><small>평균 CA</small><strong>${fmt(k.avg_ca)}</strong></div>
          <div><small>평균 PA</small><strong>${fmt(k.avg_pa)}</strong></div>
          <div><small>평균 잔여 성장 여지</small><strong>${fmt(k.avg_gap)}</strong></div>
          <div><small>최근 5주 성장 평균</small><strong>${plus(k.growth_5)}</strong>
            <small>${k.growth_5_sample}/8명 관측, 미완료 기간 포함</small></div>
        </div>
        <p>전열 ${k.front}명 / 후열 ${k.back}명 · 현재 편성 ${v.members.length}/8명</p>
        ${k.diagnosis?`<div class="growth-tactic">
          ${Object.entries(tactical).map(([key,label])=>`<label>
            <span>${label} · ${k.diagnosis[key]}/100</span>
            <progress value="${k.diagnosis[key]}" max="100"></progress></label>`).join('')}
        </div>`:''}
        <p class="muted-copy">${esc(v.note)}</p>
      </section>
      <div class="growth-layout">
        <section class="wood">
          <div class="office-title"><h3>출전 8인 성장 현황</h3><small>영구 성장기록 · 개인별 확인</small></div>
          <div class="growth-member-list">
            ${v.members.map(member=>`<article class="growth-unit ${member.id===chosenId?'active':''}">
              <button type="button" data-growth-member="${member.id}" aria-pressed="${member.id===chosenId}">
                <span><strong>${esc(member.name)}</strong><small>
                  ${member.captain?'대장 · ':member.deputy?'부대장 · ':''}${esc(member.role)} ·
                  ${member.row==='front'?'전열':'후열'}</small></span>
                <span><strong>CA ${fmt(member.ca)} / PA ${fmt(member.pa)}</strong>
                  <small>성장 여력 ${fmt(member.gap)} · 최근 5주 ${recent(member.growth_5)}</small></span>
              </button>
              <div class="growth-unit-actions"><small>${esc(member.training.reason)}</small>
                ${focusSelector(member)}
                <button type="button" data-growth-train="${member.id}" ${member.training.can_train?'':'disabled'}>집중 훈련 배치</button></div>
            </article>`).join('')||'<p>가용 문파원 8명을 확보해야 합니다.</p>'}
          </div>
        </section>
        ${memberPanel(f)}
      </div>
      <section class="wood">
        <div class="office-title"><div><small>부문주 참모 보고 · 실제 수치 기준</small><h3>육성 우선순위</h3></div>
          <button type="button" id="growth-week" ${v.ready?'':'disabled'}>주간 운영으로</button></div>
        <p class="muted-copy">잠재 여력, 전술 역할, 최근 실측 성장, 훈련 가능 상태로 평가합니다.
          수련 효과 예측이나 승률이 아니며 실제 배치·수련비 지출은 자동으로 수행하지 않습니다.</p>
        ${v.missing_roles.length?`<p class="growth-role-gaps">${v.missing_roles.map(esc).join(' · ')}</p>`:''}
        <div class="growth-priorities">${v.recommendations.map((r,i)=>`<article>
          <span class="growth-priority-no">${i+1}</span>
          <div><strong>${esc(r.name)}</strong><small>${esc(r.role)} · ${r.can_train?'훈련 가능':'현재 훈련 불가'}</small>
            <p>${r.reasons.map(esc).join(' · ')}</p></div>
          <button type="button" data-growth-train="${r.id}" ${r.can_train?'':'disabled'}>주간 훈련 배치</button>
        </article>`).join('')||'<p>주력 편성 인원이 없습니다.</p>'}</div>
        <p class="muted-copy">${esc(v.history_note)}</p>
      </section>
    </div>`;
    panel().querySelectorAll('[data-growth-mode]').forEach(b=>b.onclick=()=>open(b.dataset.growthMode));
    panel().querySelector('#growth-warroom').onclick=()=>{currentTab='warroom';management();};
    panel().querySelector('#growth-focus-overwrite').onchange=event=>{
      overwriteFocus=event.target.checked;
      preview=null;
      draw();
    };
    panel().querySelector('#growth-focus-auto')?.addEventListener('click',()=>{
      preview=null;
      runMarket('growth_focus_preview',{mode,overwrite:overwriteFocus},proposal=>{
        preview=proposal;
        draw();
      });
    });
    panel().querySelector('#growth-focus-cancel')?.addEventListener('click',()=>{
      preview=null;
      draw();
    });
    panel().querySelector('#growth-focus-confirm')?.addEventListener('click',()=>{
      if(!preview||preview.mode!==mode||preview.overwrite!==overwriteFocus)return;
      const expected=preview.token;
      runMarket('growth_focus_auto',{mode,overwrite:overwriteFocus,expected},payload=>{
        state=payload.state;
        preview=null;
        notice('수련 방향 지정 '+payload.result.changed_count+'명 · 실제 변경 '+payload.result.effective_change_count+
          '명 · 수동 설정 유지 '+payload.result.preserved_count+'명');
        queueMicrotask(()=>open(mode));
      });
    });
    panel().querySelectorAll('[data-growth-focus]').forEach(select=>{
      select.onchange=()=>{
        const id=Number(select.dataset.growthFocus);
        const focus=select.value;
        runMarket('growth_focus_set',{id,focus},payload=>{
          state=payload.state;
          notice('개인 수련 방향을 저장했습니다. 다음 실제 유료 훈련에서 적용됩니다.');
          queueMicrotask(()=>open(mode));
        });
      };
    });
    panel().querySelector('#growth-week').onclick=()=>{currentTab='week';management();};
    panel().querySelectorAll('[data-growth-member]').forEach(b=>b.onclick=()=>{
      chosenId=Number(b.dataset.growthMember);draw();
    });
    panel().querySelectorAll('[data-growth-window]').forEach(b=>b.onclick=()=>{
      windowSize=Number(b.dataset.growthWindow);draw();
    });
    panel().querySelectorAll('[data-growth-train]').forEach(b=>b.onclick=()=>{
      const id=Number(b.dataset.growthTrain);
      const current=v.members.find(x=>x.id===id);
      if(!current?.training.can_train)return;
      draft.assignments??={};
      const existing=draft.assignments[id];
      if(existing&&!['auto','training','rest'].includes(existing)&&
          !confirm(esc(current.name)+'의 기존 '+existing+' 배치를 집중 훈련으로 바꾸시겠습니까?'))return;
      draft.assignments[id]='training';
      currentTab='week';
      management(current.name+'의 집중 훈련을 주간 계획에 입력했습니다. 아직 확정 전입니다.');
    });
    panel().querySelector('#growth-member-detail')?.addEventListener('click',()=>{
      if(chosenId!=null)runMarket('member',{id:chosenId},showMember);
    });
  }
  return {open};
})();
