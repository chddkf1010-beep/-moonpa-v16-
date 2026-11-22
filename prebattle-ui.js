/* 8v8 prebattle editor. No combat simulation, no settlement, no arena mutation.
   It consumes a versioned input contract from engine/moonpa_prebattle.py. */
const prebattleUI=(()=>{
  let view=null,plan=null,diagnosis=null,briefing='',dirty=false;
  const clone=value=>JSON.parse(JSON.stringify(value));
  const empty=()=>({id:null,row:'back',skills:[]});
  const selected=()=>plan.formation.filter(x=>Number.isInteger(x.id)&&x.id>0);
  const roster=()=>view?.roster||[];
  const data=()=>({formation:selected().map(x=>({id:x.id,row:x.row,skills:[...x.skills]})),
                   captain:plan.captain,deputy:plan.deputy});
  const payload=()=>({mode:view.mode,zone_id:view.zone_id,data:data()});
  function load(mode='attack',zone_id=null){
    runMarket('prebattle_view',{mode,zone_id},result=>{
      view=result;
      plan=clone(view.plan||{formation:[],captain:null,deputy:null});
      diagnosis=view.diagnosis;
      briefing=view.briefing||'수동 편성 또는 부문주 자동편성을 진행하세요.';
      dirty=false;
      render();
    });
  }
  function updated(message='편성이 변경되었습니다. 편성 진단을 눌러 평가를 갱신하세요.'){
    diagnosis=null;dirty=true;
    notice(message);
    render();
  }
  function skillLabel(key){
    const s=roster().flatMap(f=>f.skills).find(s=>s.id===key);
    return s?.name||key;
  }
  function abilityLabel(id,appointment){
    const f=roster().find(x=>x.id===id);
    return f?.[appointment+'_ability']?.label||'지정 필요';
  }
  function render(){
    if(currentTab!=='warroom'||!view)return;
    const box=panel();
    const candidates=sortMembers('warroom-own',roster().filter(x=>x.available));
    const slots=Array.from({length:8},(_,i)=>plan.formation[i]||empty());
    const members=selected().map(x=>roster().find(f=>f.id===x.id)).filter(Boolean);
    const statsNames={strength:'근력',defense:'방어',stamina:'체력',agility:'민첩',
                      inner_power:'내공',sorcery:'주술',insight:'통찰',willpower:'의지'};
    const attrLine=f=>Object.entries(f.attrs).map(([k,v])=>`<span>${statsNames[k]||escapeText(k)} <b>${v}</b></span>`).join('');
    box.innerHTML=`<div class="prebattle-page">
      <section class="wood prebattle-heading">
        <div class="office-title"><div><small>8대8 통합 사전 편성 · v1</small><h2>전술 편성실</h2></div>
          <div class="inline-controls">
            <button type="button" data-pb-mode="attack" aria-pressed="${view.mode==='attack'}">점령전</button>
            <button type="button" data-pb-mode="defense" aria-pressed="${view.mode==='defense'}">방어전</button>
          </div></div>
        <p class="muted-copy">이 화면은 별도 8대8 전투 엔진에 전달할 입력을 준비합니다. 기존 5대5 전투·전투 결과 정산은 변경하지 않습니다.</p>
        <label class="field">분석 대상 구역
          <select id="pb-zone" ${view.zones.length?'':'disabled'}>${view.zones.map(z=>
            `<option value="${z.id}" ${z.id===view.zone_id?'selected':''}>${siteTargetLabel(state.zones.find(site=>site.id===z.id)??{...z,owner_name:z.opponent})}</option>`).join('')}</select>
        </label>
        ${view.zones.length?'':`<p>이 모드에 선택할 수 있는 구역이 없습니다. 점령할 상대 구역 또는 현재 보유 구역이 필요합니다.</p>`}
      </section>
      ${view.enemy?`<div class="prebattle-layout">
        <div class="prebattle-own">
          <section class="wood"><div class="office-title"><h3>출전 8명 · 아군 편성</h3><span>${members.length}/8명</span></div>
            <p class="muted-copy">각 슬롯의 문파원을 교체하고 전열·후열과 장착 무공을 직접 지정할 수 있습니다. 전열은 2~5명입니다.</p>
            ${memberSortControl('warroom-own',{name:'이름',role:'역할',ca:'현재 전력',level:'레벨'})}
            <div class="prebattle-slots">${slots.map((entry,i)=>{
              const f=roster().find(u=>u.id===entry.id);
              return `<article class="prebattle-slot" data-pb-slot="${i}">
                <div class="prebattle-slot-head"><strong>${i+1}번 · ${f?escapeText(f.name):'미배치'}</strong>
                  <select data-pb-member aria-label="${i+1}번 출전 문파원">
                    <option value="">선택</option>
                    ${candidates.map(u=>`<option value="${u.id}" ${entry.id===u.id?'selected':''}>${escapeText(u.name)} · ${escapeText(u.role)} · 전력 ${u.ca}</option>`).join('')}
                  </select>
                  <select data-pb-row aria-label="${i+1}번 전열 후열" ${f?'':'disabled'}>
                    <option value="front" ${entry.row==='front'?'selected':''}>전열</option>
                    <option value="back" ${entry.row==='back'?'selected':''}>후열</option>
                  </select>
                </div>
                ${f?`<div class="prebattle-unit-details"><small>Lv ${f.level} · 전력 ${f.ca} · 무공 ${entry.skills.length}/${f.slots}</small>
                  <details><summary>무공 변경 · ${entry.skills.map(skillLabel).map(escapeText).join(', ')||'없음'}</summary>
                    <div class="prebattle-skills">${f.skills.map(skill=>`<label title="${escapeText(skill.note||'')}">
                       <input type="checkbox" data-pb-skill="${skill.id}" ${entry.skills.includes(skill.id)?'checked':''}>
                       ${escapeText(skill.name)} <small>내공 ${skill.cost} · 대기 ${skill.cooldown}</small></label>`).join('')}</div>
                  </details></div>`:''}</article>`;
            }).join('')}</div>
          </section>
          <section class="wood prebattle-lead"><h3>대장·부대장</h3>
            <div class="prebattle-leader-grid"><label>대장<select id="pb-captain"><option value="">대장 선택</option>
              ${members.map(f=>`<option value="${f.id}" ${plan.captain===f.id?'selected':''}>${escapeText(f.name)}</option>`).join('')}</select></label>
              <label>부대장<select id="pb-deputy"><option value="">부대장 선택</option>
              ${members.map(f=>`<option value="${f.id}" ${plan.deputy===f.id?'selected':''}>${escapeText(f.name)}</option>`).join('')}</select></label></div>
            <p><strong>대장 효과</strong> · ${escapeText(abilityLabel(plan.captain,'captain'))}</p>
            <p><strong>부대장 효과</strong> · ${escapeText(abilityLabel(plan.deputy,'deputy'))}</p>
            <small>효과는 향후 8대8 전투 엔진에서 한 번만 계산하도록 패킷에 명시합니다. 이 화면에서는 적용되지 않습니다.</small>
          </section>
          <section class="wood"><h3>전술 진단</h3>
            ${diagnosis?`<div class="prebattle-diagnostics">${[
              ['전선 유지력',diagnosis.frontline],['후열 보호력',diagnosis.rear_protection],
              ['돌파력',diagnosis.breakthrough],['원거리 화력',diagnosis.ranged_fire]
            ].map(([label,n])=>`<label>${label} · <strong>${n}/100</strong><progress max="100" value="${n}"></progress></label>`).join('')}
              <p>${diagnosis.notes.map(escapeText).join(' ')}</p><small>${escapeText(diagnosis.meaning)}</small></div>`:
              '<p class="muted-copy">편성을 저장하거나 진단 버튼을 누르면 실제 문파원 능력치를 기준으로 평가합니다.</p>'}
            <div class="controls">
              <button id="pb-auto" type="button">부문주 자동편성</button>
              <button id="pb-preview" type="button">편성 진단</button>
              <button id="pb-save" class="primary" type="button" ${view.locked?'disabled':''}>편성 저장</button>
              <button id="pb-export" type="button">8대8 입력 JSON 내보내기</button>
            </div>
            <p class="prebattle-brief"><strong>부문주 보고</strong> · ${escapeText(briefing)}</p>
            ${dirty?'<small>저장되지 않은 변경 사항이 있습니다.</small>':'<small>조회 화면 또는 저장된 편성입니다.</small>'}
          </section>
        </div>
        <aside class="prebattle-enemy">
          <section class="wood"><h3>상대 정보 · 완전 공개</h3>
            <p><strong>${escapeText(view.enemy.name)}</strong> · ${view.enemy.members.length}명</p>
            <p class="muted-copy">${escapeText(view.enemy.note)}</p>
            <p class="muted-copy">상대 대장 ${escapeText(view.enemy.members.find(x=>x.id===view.enemy.captain)?.name||'')} /
                부대장 ${escapeText(view.enemy.members.find(x=>x.id===view.enemy.deputy)?.name||'')}</p>
            <p><strong>대장 효과</strong> · ${escapeText(view.enemy.members.find(x=>x.id===view.enemy.captain)?.captain_ability.label||'')}</p>
            <p><strong>부대장 효과</strong> · ${escapeText(view.enemy.members.find(x=>x.id===view.enemy.deputy)?.deputy_ability.label||'')}</p>
            ${memberSortControl('warroom-enemy',{name:'이름',role:'역할',ca:'현재 전력',level:'레벨',row:'전열·후열'})}
            <div class="prebattle-rivals">${sortMembers('warroom-enemy',view.enemy.members).map(f=>`<details>
              <summary><strong>${escapeText(f.name)}</strong> · ${escapeText(f.role)} · ${f.row==='front'?'전열':'후열'} · Lv ${f.level} · 전력 ${f.ca}</summary>
              <div class="prebattle-attrs">${attrLine(f)}</div>
              <p>장착 무공: ${f.equipped.map(key=>escapeText(f.skills.find(x=>x.id===key)?.name||key)).join(', ')}</p>
              <p class="muted-copy">무공 세부 효과: ${f.skills.filter(sk=>f.equipped.includes(sk.id)).map(sk=>
                escapeText(sk.name)+' (내공 '+sk.cost+', 대기 '+sk.cooldown+', 위력 '+sk.power+')').join(' / ')}</p>
            </details>`).join('')}</div>
          </section>
        </aside>
      </div>`:''}
      <section class="wood prebattle-foot">
        <h3>엔진 연결 상태</h3><p>${escapeText(view.note)}</p>
        <p class="muted-copy">아래 연무장은 현재 독립 더미 데이터로 작동합니다. 이 편성을 자동 반영하거나 점령전 결과를 정산하지 않습니다.</p>
        <a href="moonpa-arena.html" target="_blank" rel="noopener">독립 연무장 데모 열기</a>
      </section>
    </div>`;
    bind();
  }
  function bind(){
    const root=panel();
    root.querySelectorAll('[data-pb-mode]').forEach(button=>button.onclick=()=>{
      if(dirty&&!confirm('저장하지 않은 편성 변경이 있습니다. 전투 모드를 바꾸시겠습니까?'))return;
      load(button.dataset.pbMode);
    });
    const zone=root.querySelector('#pb-zone');
    if(zone)zone.onchange=()=>{
      if(dirty&&!confirm('저장하지 않은 편성 변경이 있습니다. 구역을 바꾸시겠습니까?')){
        zone.value=String(view.zone_id);return;
      }
      load(view.mode,Number(zone.value));
    };
    if(!view.enemy)return;
    bindSort(root,'warroom-own',render);
    bindSort(root,'warroom-enemy',render);
    root.querySelectorAll('[data-pb-slot]').forEach(slot=>{
      const index=Number(slot.dataset.pbSlot);
      slot.querySelector('[data-pb-member]').onchange=e=>{
        const target=Number(e.target.value);
        const entries=Array.from({length:8},(_,i)=>plan.formation[i]||empty());
        const existing=entries[index];
        if(!target){entries[index]=empty();}
        else {
          const member=roster().find(f=>f.id===target&&f.available);
          if(!member){notice('출전 가능한 문파원을 선택하세요.');render();return;}
          const conflict=entries.findIndex((f,i)=>i!==index&&f.id===target);
          if(conflict>=0)entries[conflict]=existing.id?existing:empty();
          entries[index]={id:target,row:existing.row,
                          skills:member.equipped.length?[...member.equipped]:member.skills.slice(0,1).map(x=>x.id)};
        }
        plan.formation=entries;
        const ids=selected().map(f=>f.id);
        if(!ids.includes(plan.captain))plan.captain=ids[0]||null;
        if(!ids.includes(plan.deputy)||plan.deputy===plan.captain)
          plan.deputy=ids.find(id=>id!==plan.captain)||null;
        updated();
      };
      const row=slot.querySelector('[data-pb-row]');
      if(row)row.onchange=e=>{
        const entry=plan.formation[index];
        if(entry){entry.row=e.target.value;updated();}
      };
      slot.querySelectorAll('[data-pb-skill]').forEach(input=>input.onchange=e=>{
        const entry=plan.formation[index],fighter=roster().find(f=>f.id===entry.id);
        const key=e.target.dataset.pbSkill;
        if(e.target.checked){
          if(entry.skills.length>=fighter.slots){e.target.checked=false;notice('이 문파원의 무공 슬롯이 가득 찼습니다.');return;}
          if(!entry.skills.includes(key))entry.skills.push(key);
        }else entry.skills=entry.skills.filter(x=>x!==key);
        updated();
      });
    });
    root.querySelector('#pb-captain').onchange=e=>{
      plan.captain=Number(e.target.value)||null;
      if(plan.captain===plan.deputy)plan.deputy=selected().find(x=>x.id!==plan.captain)?.id||null;
      updated();
    };
    root.querySelector('#pb-deputy').onchange=e=>{
      plan.deputy=Number(e.target.value)||null;
      if(plan.captain===plan.deputy)plan.captain=selected().find(x=>x.id!==plan.deputy)?.id||null;
      updated();
    };
    root.querySelector('#pb-auto').onclick=()=>runMarket('prebattle_auto',
      {mode:view.mode,zone_id:view.zone_id},result=>{
        plan=clone(result.plan);
        briefing=result.plan.briefing;
        diagnosis=null;dirty=true;
        render();notice('부문주가 진형·역할 구성만 참고해 기본 편성을 제안했습니다.');
      });
    root.querySelector('#pb-preview').onclick=()=>runMarket('prebattle_preview',payload(),result=>{
      diagnosis=result.diagnosis;render();notice('현재 편성의 특성을 분석했습니다.');
    });
    root.querySelector('#pb-save').onclick=()=>runMarket('prebattle_save',payload(),result=>{
      view=result.view;plan=clone(result.view.plan);
      diagnosis=result.diagnosis;dirty=false;
      render();notice(view.mode==='attack'?'점령대 편성을 저장했습니다. 주간 운영에서 해당 구역을 선택하고 추천 편성을 누르세요.':'8대8 방어 편성을 저장했습니다.');
    });
    root.querySelector('#pb-export').onclick=()=>runMarket('prebattle_preview',payload(),result=>{
      diagnosis=result.diagnosis;
      const file=new Blob([JSON.stringify(result.packet,null,2)],{type:'application/json'});
      const href=URL.createObjectURL(file);
      const link=document.createElement('a');
      link.href=href;link.download='moonpa-prebattle-'+view.mode+'-'+view.zone_id+'.json';
      document.body.append(link);link.click();link.remove();
      setTimeout(()=>URL.revokeObjectURL(href),500);
      render();notice('전투 입력 패킷을 내보냈습니다. 전투·보상 정산은 수행되지 않았습니다.');
    });
  }
  return {load};
})();
