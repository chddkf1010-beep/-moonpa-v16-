/* Roster-only management view. Assignment controls stay in monthly planning. */
const rosterUI = (() => {
  const defaults = () => ({query:'',role:'all',rarity:'all',status:'all',caMin:'',paMin:'',gapMin:'',sort:'ca',density:'comfortable'});
  let filters = defaults();
  const gapOf = member => Math.max(0,Number(member.pa)-Number(member.ca));
  const stateOf = member => member.expedition ? 'expedition' : member.injured ? 'injured' : 'ready';
  const labelOf = member => member.expedition ? '원정 중' : member.injured ? '부상 ' + member.injured + '주' : '정상';
  const rarityOf = member => member.notable?.rarity || 'normal';
  const strengthPercent = value => Math.min(100,Math.max(0,100 * Number(value) / 200)).toFixed(1);
  function filterRows(roster, criteria=filters) {
    const query = String(criteria.query || '').trim().toLocaleLowerCase();
    const results = roster.filter(member => {
      if (query && ![member.name,member.role,member.notable?.title,member.personal_title]
        .some(value => String(value || '').toLocaleLowerCase().includes(query))) return false;
      if (criteria.role !== 'all' && member.role !== criteria.role) return false;
      if (criteria.rarity !== 'all' && rarityOf(member) !== criteria.rarity) return false;
      if (criteria.status !== 'all' && stateOf(member) !== criteria.status) return false;
      if (criteria.caMin !== '' && Number(member.ca) < Number(criteria.caMin)) return false;
      if (criteria.paMin !== '' && Number(member.pa) < Number(criteria.paMin)) return false;
      if (criteria.gapMin !== '' && gapOf(member) < Number(criteria.gapMin)) return false;
      return true;
    });
    const sort = {
      ca:(a,b)=>b.ca-a.ca, pa:(a,b)=>b.pa-a.pa, gap:(a,b)=>gapOf(b)-gapOf(a),
      lv:(a,b)=>b.lv-a.lv, wage:(a,b)=>b.wage-a.wage,
      contract:(a,b)=>a.contract_end-b.contract_end,
      name:(a,b)=>String(a.name).localeCompare(String(b.name),'ko')
    }[criteria.sort] || ((a,b)=>b.ca-a.ca);
    return results.sort((a,b)=>sort(a,b)||Number(a.id)-Number(b.id));
  }
  function option(value,label,current) {
    return '<option value="' + escapeText(value) + '"' + (value === current?' selected':'') + '>' + escapeText(label) + '</option>';
  }
  function meter(value,className,label) {
    return '<span class="roster-meter" role="meter" aria-label="' + escapeText(label) +
      '" aria-valuemin="0" aria-valuemax="200" aria-valuenow="' + Math.min(200,Math.max(0,Number(value))) +
      '"><i class="' + className + '" style="width:' + strengthPercent(value) + '%"></i></span>';
  }
  function row(member,season) {
    const status = stateOf(member);
    const duration = Math.max(0,Number(member.contract_end)-Number(season)+1);
    const near = duration <= 1;
    return '<tr class="roster-rich-row" data-roster-id="' + Number(member.id) + '">' +
      '<th scope="row"><div class="roster-identity"><span class="member-face">' + portrait(member) + '</span>' +
      '<span class="roster-identity-text"><button type="button" class="member-link" data-roster-detail="' + Number(member.id) + '">' +
      escapeText(member.name) + '</button><small>' + escapeText(member.role) +
      (member.personal_title?' · ' + escapeText(member.personal_title):'') + '</small>' +
      (member.notable ? heroTag(member) : '') + '</span></div></th>' +
      '<td><div class="roster-power"><b>' + Number(member.ca).toFixed(1) + '</b>' +
      meter(member.ca,'roster-ca','현재 전력') + '</div></td>' +
      '<td><div class="roster-power"><b>' + Number(member.pa).toFixed(1) + '</b>' +
      meter(member.pa,'roster-pa','잠재력') + '</div></td>' +
      '<td class="roster-gap">+' + gapOf(member).toFixed(1) +
      '<small>Lv ' + Number(member.lv) + '</small></td>' +
      '<td><span class="roster-state ' + status + '">' + escapeText(labelOf(member)) + '</span></td>' +
      '<td><span class="' + (near?'roster-contract-warning':'') + '">' + duration + '시즌</span></td>' +
      '<td>' + money(member.wage) + '<small class="roster-wage-note">주급</small></td>' +
      '<td><button type="button" class="roster-detail-button" data-roster-detail="' + Number(member.id) +
      '" aria-label="' + escapeText(member.name) + ' 상세 보기">상세</button></td></tr>';
  }
  function rowsMarkup(roster,season) {
    const rows = filterRows(roster);
    return '<p class="roster-result-count" aria-live="polite">검색 결과 <strong>' + rows.length +
      '</strong>명 / 전체 ' + roster.length + '명</p>' +
      '<div class="table-scroll roster-rich-scroll"><table class="roster-rich-table ' +
      (filters.density === 'compact' ? 'compact' : 'comfortable') +
      '"><thead><tr><th>문파원</th><th>현재 전력</th><th>잠재력</th><th>성장 여지</th>' +
      '<th>상태</th><th>계약</th><th>봉록</th><th>상세</th></tr></thead><tbody>' +
      (rows.length?rows.map(member=>row(member,season)).join('') :
        '<tr><td colspan="8" class="roster-no-results">조건에 맞는 문파원이 없습니다. 필터를 조정하세요.</td></tr>') +
      '</tbody></table></div>';
  }
  function render(roster,season) {
    const injured=roster.filter(m=>m.injured).length;
    const expedition=roster.filter(m=>m.expedition).length;
    const ready=roster.filter(m=>!m.injured&&!m.expedition).length;
    const contracts=roster.filter(m=>m.contract_end<=season).length;
    const roles=[...new Set(roster.map(m=>m.role))].sort((a,b)=>a.localeCompare(b,'ko'));
    return '<section class="wood roster-board" id="roster-board">' +
      '<header class="roster-board-head"><div><small>제자 성장 · 인재 관리</small><h2>문파원 명부</h2>' +
      '<p class="muted-copy">현재 전력과 잠재력은 실제 게임 수치입니다. 피로도·충성도는 아직 게임에 없는 능력치이므로 표시하지 않습니다.</p></div>' +
      '<button type="button" id="roster-open-growth">주력 8인 육성</button></header>' +
      '<div class="roster-summary">' +
      '<div><small>전체 인원</small><strong>' + roster.length + '명</strong></div>' +
      '<div><small>활동 가능</small><strong>' + ready + '명</strong></div>' +
      '<div><small>부상</small><strong class="negative">' + injured + '명</strong></div>' +
      '<div><small>장기 원정</small><strong>' + expedition + '명</strong></div>' +
      '<div><small>이번 시즌 계약 종료</small><strong class="' + (contracts?'warning':'') + '">' + contracts + '명</strong></div></div>' +
      '<div class="roster-toolbar"><label>이름·역할·칭호 검색<input type="search" data-roster-query placeholder="문파원 검색" value="' + escapeText(filters.query) + '"></label>' +
      '<label>역할<select data-roster-filter="role">' + option('all','전체',filters.role) +
      roles.map(role=>option(role,role,filters.role)).join('') + '</select></label>' +
      '<label>희귀도<select data-roster-filter="rarity">' +
      [['all','전체'],['normal','일반'],['named','네임드'],['legend','전설']].map(pair=>option(pair[0],pair[1],filters.rarity)).join('') + '</select></label>' +
      '<label>상태<select data-roster-filter="status">' +
      [['all','전체'],['ready','정상'],['injured','부상'],['expedition','장기 원정']].map(pair=>option(pair[0],pair[1],filters.status)).join('') + '</select></label>' +
      '<label>CA 이상<input type="number" min="0" max="200" step="1" data-roster-filter="caMin" value="' + escapeText(filters.caMin) + '" placeholder="전체"></label>' +
      '<label>PA 이상<input type="number" min="0" max="200" step="1" data-roster-filter="paMin" value="' + escapeText(filters.paMin) + '" placeholder="전체"></label>' +
      '<label>성장 여지 이상<input type="number" min="0" max="200" step="1" data-roster-filter="gapMin" value="' + escapeText(filters.gapMin) + '" placeholder="전체"></label>' +
      '<label>정렬<select data-roster-filter="sort">' +
      [['ca','현재 전력 높은 순'],['pa','잠재력 높은 순'],['gap','성장 여지 높은 순'],
      ['lv','레벨 높은 순'],['wage','주급 높은 순'],['contract','계약 만료 임박순'],['name','이름순']].map(pair=>option(pair[0],pair[1],filters.sort)).join('') + '</select></label>' +
      '<div class="roster-toolbar-bottom"><span role="group" aria-label="명부 밀도">' +
      '<button type="button" data-roster-density="comfortable" aria-pressed="' + (filters.density==='comfortable') + '">기본 보기</button>' +
      '<button type="button" data-roster-density="compact" aria-pressed="' + (filters.density==='compact') + '">압축 보기</button></span>' +
      '<button type="button" id="roster-reset">필터 초기화</button></div></div>' +
      '<div id="roster-results">' + rowsMarkup(roster,season) + '</div></section>';
  }
  function bind(root,roster,season) {
    const container=root.querySelector('#roster-board');
    if (!container) return;
    const redraw=()=>{
      container.querySelector('#roster-results').innerHTML=rowsMarkup(roster,season);
      container.querySelectorAll('[data-roster-density]').forEach(button =>
        button.setAttribute('aria-pressed',String(button.dataset.rosterDensity===filters.density)));
      bindPortraits();
    };
    container.querySelector('[data-roster-query]').addEventListener('input',event=>{
      filters.query=event.target.value;redraw();
    });
    container.querySelectorAll('[data-roster-filter]').forEach(control=>{
      const handler=event=>{
        filters[event.target.dataset.rosterFilter]=event.target.value;
        redraw();
      };
      control.addEventListener(control.tagName==='SELECT'?'change':'input',handler);
    });
    container.addEventListener('click',event=>{
      const target=event.target.closest('[data-roster-detail]');
      if (target){
        const id=Number(target.dataset.rosterDetail);
        if (roster.some(member=>member.id===id))runMarket('member',{id},showMember);
        return;
      }
      const density=event.target.closest('[data-roster-density]');
      if (density){filters.density=density.dataset.rosterDensity;redraw();return;}
      if (event.target.closest('#roster-reset')){filters=defaults();showRoster();return;}
      if (event.target.closest('#roster-open-growth')){
        currentTab='growth';management();
      }
    });
  }
  return {render,bind,filterRows,reset:()=>{filters=defaults();}};
})();