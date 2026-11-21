/* v10 market UI. Filtering and sorting are entirely local and pure.
   Combat, market offers and permanent lineup state remain engine-owned. */
const MARKET_ROLE_LABELS=['수호','무인','사수','주술','치유','암살'];
const MARKET_RARITY_LABELS={all:'전체',normal:'일반',named:'네임드',legend:'전설',rareplus:'네임드 이상'};
const MARKET_RARITY_WEIGHT={normal:0,named:1,legend:2};
const MARKET_STATS=['strength','defense','stamina','agility','inner_power','sorcery','insight','willpower'];
const MARKET_STAT_NAMES={strength:'근력',defense:'방어',stamina:'체력',agility:'민첩',inner_power:'내공',sorcery:'술법',insight:'통찰',willpower:'정신력'};
const MARKET_METRICS={frontline:'전선 유지력',rear_protection:'후열 보호력',breakthrough:'돌파력',ranged_fire:'원거리 화력'};

function marketFilterCandidates(candidates,filter,roleNeeds={}){
  const num=(v)=>v===''||v==null?null:Number(v);
  const inRange=(v,min,max)=>{
    const lo=num(min),hi=num(max);
    return Number.isFinite(Number(v))&&(lo===null||Number(v)>=lo)&&(hi===null||Number(v)<=hi);
  };
  const keep=candidates.filter(f=>{
    if(filter.rarity==='rareplus'&&f.rarity==='normal')return false;
    if(!['all','rareplus'].includes(filter.rarity)&&f.rarity!==filter.rarity)return false;
    if(filter.role!=='all'&&f.role_id!==Number(filter.role))return false;
    if(filter.eligibleOnly&&!f.eligible)return false;
    if(!inRange(f.ca,filter.minCA,filter.maxCA))return false;
    if(!inRange(f.pa,filter.minPA,filter.maxPA))return false;
    if(!inRange(f.growth_gap,filter.minGap,''))return false;
    for(const stat of MARKET_STATS){
      const range=filter.ranges?.[stat]||{};
      if(!inRange(f.attrs?.[stat],range.min??'',range.max??''))return false;
    }
    return true;
  });
  const key=filter.sort||'pa';
  const dir=filter.ascending?1:-1;
  const value=f=>{
    if(key==='rarity')return MARKET_RARITY_WEIGHT[f.rarity]||0;
    if(key==='need')return roleNeeds[String(f.role_id)]||0;
    if(key==='growth')return f.growth_gap;
    if(key.startsWith('stat:'))return f.attrs?.[key.slice(5)]??0;
    return f[key];
  };
  return keep.sort((a,b)=>{
    const av=value(a),bv=value(b);
    const result=typeof av==='number'&&typeof bv==='number'?av-bv:
        String(av??'').localeCompare(String(bv??''),'ko');
    return dir*result||(key==='need'?b.ca-a.ca:0)||a.id-b.id;
  });
}
function marketRarityCounts(rows){
  return {all:rows.length,normal:rows.filter(f=>f.rarity==='normal').length,
    named:rows.filter(f=>f.rarity==='named').length,legend:rows.filter(f=>f.rarity==='legend').length,
    rareplus:rows.filter(f=>f.rarity==='named'||f.rarity==='legend').length};
}
const marketUI=(()=>{
  let market=null,selectedCompareIds=[],baselineMemberId=null,compareResult=null;
  let lastArrivalIds=[],unread=[];
  let scope='',seen=new Set();
  const filters={rarity:'all',role:'all',minCA:'',maxCA:'',minPA:'',maxPA:'',minGap:'',
    eligibleOnly:false,sort:'pa',ascending:false,
    ranges:Object.fromEntries(MARKET_STATS.map(key=>[key,{min:'',max:''}]))};
  const esc=v=>escapeText(v??'');
  const format=(v)=>Number(v).toLocaleString('ko-KR',{maximumFractionDigits:1});
  const offset=(v)=>v>0?'+'+format(v):format(v);
  const role=f=>MARKET_ROLE_LABELS[f.role_id]||f.role||'';
  const rarity=f=>f.rarity==='legend'?'전설':f.rarity==='named'?'네임드':'일반';
  const readStore=key=>{try{return new Set(JSON.parse(sessionStorage.getItem(key)||'[]'));}catch{return new Set();}};
  const writeStore=()=>{try{sessionStorage.setItem(scope,JSON.stringify([...seen]));}catch{}};
  function observe(game){
    const nextScope='moonpa:v10:market-seen:'+game.seed+':'+game.guild+':'+game.guild_name;
    if(nextScope!==scope){scope=nextScope;seen=readStore(scope);}
    unread=(game.market_notables||[]).filter(f=>!seen.has(f.id));
  }
  function unreadCount(){return unread.length;}
  function banner(){
    if(!unread.length||currentTab==='free'||!['ready','fa'].includes(state.phase))return '';
    const highlighted=unread.slice(0,3).map(x=>esc(x.name)).join(' · ');
    return `<div class="market-soft-alert" role="status">
      <strong>네임드 낭인 신규 등장 ${unread.length}명</strong>
      <small>${highlighted}${unread.length>3?' 외':''} · 전투 화면에서는 알림을 표시하지 않습니다.</small>
      <button type="button" id="market-alert-open">낭인 시장 확인</button>
    </div>`;
  }
  function bindBanner(){
    screen.querySelector('#market-alert-open')?.addEventListener('click',()=>{
      currentTab='free';management();
    });
  }
  function markRead(){
    lastArrivalIds=unread.map(x=>x.id);
    for(const info of unread)seen.add(info.id);
    unread=[];
    writeStore();
  }
  function clearFilters(){
    filters.rarity='all';filters.role='all';filters.minCA=filters.maxCA='';
    filters.minPA=filters.maxPA=filters.minGap='';
    filters.eligibleOnly=false;filters.sort='pa';filters.ascending=false;
    for(const stat of MARKET_STATS)filters.ranges[stat]={min:'',max:''};
    render();
  }
  function filterInputs(){
    return `<div class="market-filter-box">
      <h3>희귀도 · 역할 검색</h3>
      <div class="market-filter-chips" id="market-rarity"></div>
      <div class="market-filter-chips market-role-chips" id="market-roles"></div>
      <div class="market-number-fields">
        <label>현재 전력 (CA) 최소 <input type="number" min="0" max="200" step="1" data-market-min="minCA" value="${esc(filters.minCA)}" placeholder="무관"></label>
        <label>현재 전력 (CA) 최대 <input type="number" min="0" max="200" step="1" data-market-min="maxCA" value="${esc(filters.maxCA)}" placeholder="무관"></label>
        <label>관측 잠재력 (PA) 최소 <input type="number" min="0" max="200" step="1" data-market-min="minPA" value="${esc(filters.minPA)}" placeholder="무관"></label>
        <label>관측 잠재력 (PA) 최대 <input type="number" min="0" max="200" step="1" data-market-min="maxPA" value="${esc(filters.maxPA)}" placeholder="무관"></label>
        <label>성장 여지 (추정 PA−CA) 최소 <input type="number" min="0" max="200" step="1" data-market-min="minGap" value="${esc(filters.minGap)}" placeholder="무관"></label>
      </div>
      <details class="market-advanced"><summary>세부 능력치 8종 범위 검색 · 근력/방어/체력/민첩/내공/술법/통찰/정신력</summary>
        <p class="muted-copy">실제 현재 능력치 기준으로 각각 최소·최대를 지정할 수 있습니다. 입력은 동시에 적용됩니다.</p>
        <div class="market-attr-filter-grid">${MARKET_STATS.map(stat=>`<div class="market-attr-filter">
          <strong>${MARKET_STAT_NAMES[stat]}</strong>
          <label>최소<input type="number" min="0" max="200" step="1" data-market-stat="${stat}" data-market-bound="min"
            value="${esc(filters.ranges[stat].min)}" placeholder="무관"></label>
          <label>최대<input type="number" min="0" max="200" step="1" data-market-stat="${stat}" data-market-bound="max"
            value="${esc(filters.ranges[stat].max)}" placeholder="무관"></label>
        </div>`).join('')}</div>
      </details>
      <div class="market-order-toolbar">
        <label>정렬 <select id="market-sort">
          ${[['pa','관측 잠재력'],['ca','현재 전력'],['growth','성장 여지'],['rarity','희귀도'],
             ['need','주력 8인 부족 역할'],['fee','계약금'],['wage','주급'],['age','나이'],['name','이름'],
             ...MARKET_STATS.map(k=>['stat:'+k,MARKET_STAT_NAMES[k]+' 능력치'])].map(([value,label])=>
             `<option value="${value}" ${filters.sort===value?'selected':''}>${label}</option>`).join('')}
        </select></label>
        <button type="button" id="market-sort-dir">${filters.ascending?'오름차순':'내림차순'}</button>
        <label class="market-eligible"><input type="checkbox" id="market-eligible" ${filters.eligibleOnly?'checked':''}>지금 영입 가능한 후보만</label>
        <button type="button" id="market-reset">조건 초기화</button>
      </div>
      <small class="muted-copy">낭인 PA는 정찰로 관측한 추정치이며 실제 숨겨진 잠재력을 공개하지 않습니다. 다른 조건과 모두 AND로 결합됩니다.</small>
    </div>`;
  }
  function show(data){
    market=data;
    selectedCompareIds=selectedCompareIds.filter(id=>market.candidates.some(x=>x.id===id));
    if(baselineMemberId&&!market.team.members.some(x=>x.id===baselineMemberId))
      baselineMemberId=null;
    markRead();
    compareResult=null;
    render();
  }
  function render(){
    if(currentTab!=='free'||!market)return;
    const count=market.candidates.length;
    const arrivals=market.candidates.filter(f=>lastArrivalIds.includes(f.id));
    panel().innerHTML=`<section class="wood market-page">
      <div class="office-title"><div><small>자유 낭인 · 계약 시장</small><h2>낭인 시장</h2></div>
        <small>총 매물 ${count}명 · 출전 문파원 ${market.roster_count}/${market.normal_roster_limit}명
          (최대 ${market.roster_limit}명)</small></div>
      ${arrivals.length?`<div class="market-arrival-banner">
        <strong>[네임드 출현!] 새로운 무인 ${arrivals.length}명</strong>
        <span>${arrivals.map(f=>esc(f.name)+' ('+rarity(f)+')').join(' · ')}</span>
        <small>현재 시장에서 확인 완료 · 다시 알림은 뜨지 않습니다.</small>
      </div>`:''}
      <p class="muted-copy">${esc(market.refresh_note)}</p>
      ${filterInputs()}
      <section class="market-tactical-gap">
        <div class="office-title"><h3>현재 주력 8인 전술 진단</h3><small>${esc(market.team.source)}</small></div>
        ${market.team.members.length?`<p>전열 ${market.team.members.filter(x=>x.row==='front').length}명 ·
          후열 ${market.team.members.filter(x=>x.row==='back').length}명
          · 수호형 ${market.team.role_counts['0']}명 · 치유형 ${market.team.role_counts['4']}명</p>`:''}
        <p>${market.team.needs.map(esc).join(' / ')}</p>
        <small>${esc(market.team.note)}</small>
      </section>
      <div class="market-results-heading"><h3>검색 결과 <span id="market-result-count"></span></h3>
        <small>비교 최대 3명 · 선별 후 실제 영입 판단</small></div>
      <div class="table-scroll"><table class="market-results">
        <thead><tr><th>후보</th><th>역할·전술</th><th>현재 CA</th><th>관측 PA</th><th>성장 여지</th>
          <th>세부 능력</th><th>계약금</th><th>주급</th><th>비교 / 영입</th></tr></thead>
        <tbody id="market-results-body"></tbody>
      </table></div>
      <div id="market-compare-panel"></div>
      ${state.phase==='fa'?'<div class="controls"><button type="button" class="primary" id="market-start-season">드래프트 마무리 · 시즌 시작</button></div>':''}
    </section>`;
    bind();
    updateResults();
    renderCompare();
  }
  function updateFilterChips(){
    const root=panel();
    const counts=marketRarityCounts(market.candidates);
    root.querySelector('#market-rarity').innerHTML=Object.entries(MARKET_RARITY_LABELS)
      .map(([key,label])=>`<button type="button" data-market-rarity="${key}" aria-pressed="${filters.rarity===key}">
        ${label} <span class="market-count">${counts[key]}</span></button>`).join('');
    const scoped=market.candidates.filter(x=>filters.rarity==='all'||
      filters.rarity==='rareplus'&&x.rarity!=='normal'||x.rarity===filters.rarity);
    const roles=[['all','전체 역할'],...MARKET_ROLE_LABELS.map((name,id)=>[String(id),name])];
    root.querySelector('#market-roles').innerHTML=roles.map(([key,label])=>`<button type="button"
      data-market-role="${key}" aria-pressed="${filters.role===key}">${label}
      <span class="market-count">${key==='all'?scoped.length:scoped.filter(x=>x.role_id===Number(key)).length}</span></button>`).join('');
    root.querySelectorAll('[data-market-rarity]').forEach(btn=>btn.onclick=()=>{
      filters.rarity=btn.dataset.marketRarity;updateResults();
    });
    root.querySelectorAll('[data-market-role]').forEach(btn=>btn.onclick=()=>{
      filters.role=btn.dataset.marketRole;updateResults();
    });
  }
  function updateResults(){
    const root=panel();
    if(!root||!root.querySelector('#market-results-body'))return;
    updateFilterChips();
    const rows=marketFilterCandidates(market.candidates,filters,market.team.role_needs);
    root.querySelector('#market-result-count').textContent=rows.length+' / '+market.candidates.length+'명';
    root.querySelector('#market-results-body').innerHTML=rows.length?rows.map(f=>`<tr data-market-id="${f.id}"
      class="${f.rarity==='legend'?'market-legend':f.rarity==='named'?'market-named':''}">
      <th scope="row"><div class="market-hero-name">${portrait(f)}<span><strong>${esc(f.name)}</strong>
        ${heroTag(f)}<small>${f.level}레벨 · ${f.age}세</small></span></div></th>
      <td><strong>${role(f)}형</strong><small>${f.tags.map(esc).join(' · ')}</small></td>
      <td class="market-numeric"><strong>${format(f.ca)}</strong></td>
      <td class="market-numeric"><strong>${format(f.pa)}</strong><small>추정치</small></td>
      <td class="market-numeric">${offset(f.growth_gap)}</td>
      <td><details><summary>8종 보기</summary><div class="market-mini-attrs">
        ${MARKET_STATS.map(key=>`<span>${MARKET_STAT_NAMES[key]} <b>${format(f.attrs[key])}</b></span>`).join('')}</div>
        <p><small>무공: ${f.equipped.map(x=>esc(x.name)).join(' · ')||'미장착'}</small></p>
        <p><small>대장: ${esc(f.captain_ability.label)}</small></p>
        <p><small>부대장: ${esc(f.deputy_ability.label)}</small></p>
      </details></td>
      <td>${money(f.fee)}</td><td>${money(f.wage)}</td>
      <td><div class="market-actions">
        <label><input type="checkbox" data-market-compare="${f.id}"
          ${selectedCompareIds.includes(f.id)?'checked':''}>비교 담기</label>
        ${f.eligible?`<div class="inline-controls"><select class="years" aria-label="${esc(f.name)} 계약기간">
            ${market.terms_years.map(y=>`<option value="${y}">${y}시즌</option>`).join('')}</select>
          <button type="button" class="market-hire">영입</button></div>`:
          `<small>${esc(decisions[f.reason]||'영입 불가')}</small>`}</div></td>
    </tr>`).join(''):
    '<tr><td colspan="9" class="market-empty">설정한 조건에 맞는 낭인이 없습니다. 필터를 완화하거나 조건 초기화를 눌러 보세요.</td></tr>';
    root.querySelectorAll('[data-market-compare]').forEach(input=>input.onchange=e=>{
      const id=Number(e.target.dataset.marketCompare);
      if(e.target.checked){
        if(selectedCompareIds.length>=3){e.target.checked=false;notice('후보 비교는 최대 3명까지 가능합니다.');return;}
        selectedCompareIds.push(id);
      }else selectedCompareIds=selectedCompareIds.filter(x=>x!==id);
      compareResult=null;renderCompare();fetchCompare();
    });
    root.querySelectorAll('.market-hire').forEach(button=>button.onclick=()=>{
      const row=button.closest('[data-market-id]');
      const candidate=market.candidates.find(f=>f.id===Number(row.dataset.marketId));
      const years=Number(row.querySelector('select.years').value);
      if(!confirm(candidate.name+' · '+years+'시즌 계약\n계약금 '+money(candidate.fee)+' · 주급 '+money(candidate.wage)))return;
      runMarket('recruit',{season:market.season,week:market.week,id:candidate.id,years},result=>{
        state=result.state;
        selectedCompareIds=selectedCompareIds.filter(id=>id!==candidate.id);
        queueMicrotask(()=>management(result.recruitment.status==='signed'?
          candidate.name+' 영입 완료':decisions[result.recruitment.status]));
      });
    });
  }
  function renderCompare(){
    const root=panel()?.querySelector('#market-compare-panel');
    if(!root)return;
    if(!selectedCompareIds.length){
      root.innerHTML='<section class="market-comparison-empty"><strong>후보 비교</strong> · 위 표에서 낭인을 1~3명 선택하면 현재 8인 출전진과 비교합니다.</section>';
      return;
    }
    const available=selectedCompareIds.map(id=>market.candidates.find(x=>x.id===id)).filter(Boolean);
    const team=market.team;
    root.innerHTML=`<section class="market-comparison">
      <div class="office-title"><h3>낭인 후보 비교 · ${available.length}/3명</h3>
        <button type="button" id="market-compare-clear">비교 비우기</button></div>
      <label>교체 기준 문파원 <select id="market-baseline">
        <option value="">자동 추천 · 같은 역할이나 전후열 최저 전력 우선</option>
        ${team.members.map(f=>`<option value="${f.id}" ${baselineMemberId===f.id?'selected':''}>${esc(f.name)}
          · ${esc(f.role)} · ${f.row==='front'?'전열':'후열'} · CA ${f.ca}</option>`).join('')}
      </select></label>
      <div class="market-comparison-grid">${available.map(f=>{
        const cmp=compareResult?.comparisons.find(x=>x.candidate.id===f.id);
        return `<article class="market-comparison-card ${f.rarity==='legend'?'market-legend':f.rarity==='named'?'market-named':''}">
          <div class="market-compare-header"><strong>${esc(f.name)}</strong><small>${rarity(f)} · ${role(f)}형</small></div>
          <p>CA <strong>${format(f.ca)}</strong> · 관측 PA <strong>${format(f.pa)}</strong>
            · 성장 여지 <strong>${offset(f.growth_gap)}</strong></p>
          <p>주요 능력: ${MARKET_STATS.map(key=>esc(MARKET_STAT_NAMES[key])+' '+format(f.attrs[key])).join(' · ')}</p>
          <p>고유 지휘 효과: ${esc(f.captain_ability.label)} / ${esc(f.deputy_ability.label)}</p>
          <p>장착 무공: ${f.equipped.map(x=>esc(x.name)).join(' · ')||'없음'}</p>
          ${cmp?`<div class="market-delta">
            <p><strong>가상 교체:</strong> ${esc(cmp.replacement?.name||'비교할 주력 8인 없음')}
              ${cmp.replacement?' · 현재 CA '+cmp.replaced_ca+' / PA '+cmp.replaced_pa:''}</p>
            ${cmp.delta?Object.entries(MARKET_METRICS).map(([key,label])=>`<div class="market-delta-row">
              <span>${label}</span><strong class="${cmp.delta[key]>0?'positive':cmp.delta[key]<0?'negative':'neutral'}">${offset(cmp.delta[key])}</strong></div>`).join(''):
              '<p>가용 8인 편성이 없어 교체 예측을 제공하지 않습니다.</p>'}
            <small>${esc(cmp.note)}</small>${cmp.warning?`<p class="market-warning">${esc(cmp.warning)}</p>`:''}
          </div>`:'<p class="muted-copy">교체 전술 점수 계산 중…</p>'}
        </article>`;
      }).join('')}</div>
      <p class="muted-copy">${compareResult?esc(compareResult.disclaimer):
        '실제 영입이나 출전 명단을 변경하지 않습니다. 비교는 8인 전술 진단에 기반합니다.'}</p>
    </section>`;
    root.querySelector('#market-compare-clear').onclick=()=>{
      selectedCompareIds=[];compareResult=null;
      updateResults();renderCompare();
    };
    root.querySelector('#market-baseline').onchange=e=>{
      baselineMemberId=e.target.value===''?null:Number(e.target.value);
      compareResult=null;renderCompare();fetchCompare();
    };
  }
  function fetchCompare(){
    if(!selectedCompareIds.length)return;
    const ids=[...selectedCompareIds],replacement=baselineMemberId;
    runMarket('market_compare',{ids,replace_id:replacement},result=>{
      if(ids.join(',')!==selectedCompareIds.join(',')||baselineMemberId!==replacement)return;
      compareResult=result;renderCompare();
    });
  }
  function bind(){
    const root=panel();
    root.querySelectorAll('[data-market-min]').forEach(input=>input.oninput=e=>{
      filters[e.target.dataset.marketMin]=e.target.value;updateResults();
    });
    root.querySelectorAll('[data-market-stat]').forEach(input=>input.oninput=e=>{
      filters.ranges[e.target.dataset.marketStat][e.target.dataset.marketBound]=e.target.value;updateResults();
    });
    root.querySelector('#market-sort').onchange=e=>{filters.sort=e.target.value;updateResults()};
    root.querySelector('#market-sort-dir').onclick=()=>{
      filters.ascending=!filters.ascending;
      root.querySelector('#market-sort-dir').textContent=filters.ascending?'오름차순':'내림차순';
      updateResults();
    };
    root.querySelector('#market-eligible').onchange=e=>{
      filters.eligibleOnly=e.target.checked;updateResults();
    };
    root.querySelector('#market-reset').onclick=clearFilters;
    root.querySelector('#market-start-season')?.addEventListener('click',advancePhase);
  }
  return {observe,unreadCount,banner,bindBanner,show,filterCandidates:marketFilterCandidates,counts:marketRarityCounts};
})();
if(typeof module!=='undefined'){
  module.exports={marketFilterCandidates,marketRarityCounts,MARKET_STATS};
}
