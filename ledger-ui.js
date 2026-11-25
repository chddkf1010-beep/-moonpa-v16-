/* Monthly finance overview: pure rendering; balances and transactions come from the engine. */
const ledgerUI = (() => {
  const whole = value => Math.max(0, Number(value) || 0);
  const signed = value => (value > 0 ? '+' : value < 0 ? '-' : '') + money(Math.abs(value));
  const status = weeks => weeks < 4
    ? {label:'위험',className:'danger',description:'필수 비용 충당 여력 4주 미만'}
    : weeks < 8
      ? {label:'주의',className:'warning',description:'필수 비용 충당 여력 8주 미만'}
      : {label:'안정',className:'good',description:'필수 비용 충당 여력 8주 이상'};
  function entries(report,positive) {
    const totals = new Map();
    for (const row of (report?.entries || [])) {
      const value = Number(row.amount);
      if (!Number.isFinite(value) || (positive ? value <= 0 : value >= 0)) continue;
      totals.set(row.category, (totals.get(row.category) || 0) + Math.abs(value));
    }
    return [...totals].sort((a,b)=>b[1]-a[1]);
  }
  function entryList(items,kind) {
    if (!items.length) return '<p class="finance-empty">결산 기록 없음</p>';
    const max = Math.max(1,items[0][1]);
    return '<ul class="finance-breakdown">' + items.slice(0,5).map(([key,value]) =>
      '<li><span class="finance-entry-title">' + escapeText(labels[key] || key) + '</span>' +
      '<strong>' + money(value) + '</strong>' +
      '<span class="finance-track"><i class="' + kind + '" style="width:' +
      Math.max(2,Math.min(100,100*value/max)).toFixed(1) + '%"></i></span></li>'
    ).join('') + '</ul>';
  }
  function render(report, overview) {
    const f = overview.treasury.forecast;
    const fixed = Math.max(1,whole(f.fixed)+whole(f.garrison));
    const cover = Math.max(0,whole(overview.cash) / fixed);
    const health = status(cover);
    const hasReport = !!report;
    const amount = hasReport ? Number(report.cash_change) : Number(f.balance) * (overview.month_weeks || 1);
    const income = hasReport ? Number(report.income) : Number(f.income) * (overview.month_weeks || 1);
    const expenses = hasReport ? Number(report.expenses) : (Number(f.fixed) + Number(f.garrison)) * (overview.month_weeks || 1);
    const summaryLabel = hasReport ? report.season + '시즌 ' + (report.month || overview.month) + '개월차 실제 결산' : '이번 달 기본 예상 수지';
    const cashBefore = hasReport ? Number(report.cash_before) : Number(overview.cash);
    const cashAfter = hasReport ? Number(report.cash) : cashBefore + amount;
    const incomeItems = entries(report,true), expenseItems = entries(report,false);
    const risk = amount < 0 ? 'negative' : amount > 0 ? 'positive' : '';
    const changedText = hasReport ? '확정 결산' : '7일 단위 전망 × 이번 달 남은 ' + (overview.month_weeks || 1) + '주';
    return [
      '<section class="wood finance-dashboard" aria-label="재정 장부 요약">',
      '<div class="finance-heading"><div><small>문파 재정 · 월간 운영</small><h2>재정 장부</h2></div>',
      '<span class="finance-status ' + health.className + '">' + health.label + ' · ' + health.description + '</span></div>',
      '<div class="finance-cards">',
      '<article class="finance-hero"><span class="finance-eyebrow">' + escapeText(summaryLabel) + '</span>',
      '<strong class="finance-primary ' + risk + '">' + signed(amount) + '</strong>',
      '<small>' + escapeText(changedText) + '</small>',
      '<div class="finance-money-pair"><span>수입 <b class="positive">+' + money(income) + '</b></span>',
      '<span>지출 <b class="negative">-' + money(expenses) + '</b></span></div></article>',
      '<article class="finance-balance"><span class="finance-eyebrow">' + (hasReport?'결산 전후 현금 변동':'현재 보유 현금') + '</span>',
      '<strong>' + money(hasReport ? cashAfter : cashBefore) + '</strong>',
      hasReport ? '<div class="finance-cash-flow"><span>결산 전 ' + money(cashBefore) + '</span><span aria-hidden="true">→</span><span>결산 후 ' + money(cashAfter) + '</span></div>' :
        '<div class="finance-cash-flow"><span>기본 전망 후 ' + signed(cashAfter - cashBefore) + '</span></div>',
      '<div class="finance-secondary"><span>미상환 부채 <b>' + money(overview.treasury.debt || 0) + '</b></span>',
      '<span>고정비 대비 현금 <b>' + cover.toFixed(1) + '주분</b></span></div></article>',
      '<article class="finance-risk"><span class="finance-eyebrow">운영 여력</span>',
      '<strong class="' + health.className + '">' + health.label + '</strong>',
      '<div class="finance-risk-track"><i class="' + health.className + '" style="width:' + Math.min(100,cover / 12 * 100).toFixed(1) + '%"></i></div>',
      '<span>필수 주간 비용 ' + money(fixed) + '</span>',
      '<small>급여·문파 및 시설 유지비·기본 주둔비 기준</small></article>',
      '</div>',
      hasReport ? [
        '<div class="finance-breakdowns">',
        '<div class="finance-breakdown-card"><h3>월간 수입 <small>+' + money(income) + '</small></h3>' + entryList(incomeItems,'positive') + '</div>',
        '<div class="finance-breakdown-card"><h3>월간 지출 <small>-' + money(expenses) + '</small></h3>' + entryList(expenseItems,'negative') + '</div>',
        '</div>'
      ].join('') : '<p class="finance-estimate-note">첫 월간 결산 전에는 확정 수입·지출 내역이 없습니다. 기본 예상치는 훈련비·투자·부채 상환·전투 결과를 제외합니다.</p>',
      '<div class="finance-footer"><span>구역 기본 수익 ' + money(f.zone) + '/주</span>',
      '<span>장원·후원·기본 운영수입 ' + money(Number(f.estate)+Number(f.sponsor)+Number(f.basic||0)+Number(f.support||0)) + '/주</span>',
      '<span>월간 진행: ' + (overview.month_weeks || 1) + '주 남음</span></div>',
      '</section>'
    ].join('');
  }
  function showJournal(root, overview) {
    const j=overview.player_journal;
    if(!j){root.textContent='누적 장부가 아직 초기화되지 않았습니다.';return;}
    const e=escapeText, label=key=>e(labels[key]||key);
    const f=overview.treasury.forecast;
    const fixed=Number(f.fixed)+Number(f.garrison);
    const ratio=fixed>0?Number(f.income)/fixed:null;
    const row=(p)=>'<tr><th scope="row">'+p.season+'시즌</th><td>'+money(p.opening)+'</td><td class="positive">+'+money(p.income)+'</td><td class="negative">-'+money(p.expenses)+'</td><td>'+signed(p.income-p.expenses)+'</td><td>'+money(p.closing)+'</td></tr>';
    root.innerHTML='<section class="wood finance-dashboard"><div class="finance-heading"><div><small>실제 현금 거래 · 전체 기록</small><h2>누적 재정 장부</h2></div><span class="finance-status '+(j.difference===0?'good':'danger')+'">장부 차이 '+signed(j.difference)+'</span></div>'+
      '<p class="muted-copy">기록 시작: '+j.start_season+'시즌 '+j.start_week+'주 · '+(j.origin==='migration'?'구 세이브 불러오기 시점부터 실제 기록 (이전 거래 미포함)':'창설 시점 잔액부터 실제 기록')+(j.closed?' · 원 문파 청산 완료':'')+'</p>'+
      '<div class="finance-cards"><article class="finance-hero"><span class="finance-eyebrow">누적 순현금흐름</span><strong class="finance-primary">'+signed(j.income-j.expenses)+'</strong><div class="finance-money-pair"><span>수입 <b class="positive">+'+money(j.income)+'</b></span><span>지출 <b class="negative">-'+money(j.expenses)+'</b></span></div></article>'+
      '<article class="finance-balance"><span class="finance-eyebrow">실제 보유 현금</span><strong>'+money(j.actual)+'</strong><div class="finance-cash-flow"><span>기초 '+money(j.opening)+'</span><span>장부 잔액 '+money(j.expected)+'</span></div><div class="finance-secondary"><span>미상환 부채 <b>'+(j.closed?'청산 종료':money(overview.treasury.debt||0))+'</b></span><span>거래 '+j.count+'건</span></div></article>'+
      '<article class="finance-risk"><span class="finance-eyebrow">주간 고정비 대비 예상수입</span><strong>'+(j.closed||ratio===null?'—':ratio.toFixed(2)+'배')+'</strong><span>'+(j.closed?'청산된 문파':money(f.income)+' / '+money(fixed))+'</span><small>거점 유지 가정 · 수련, 이적, 부채 상환 제외</small></article></div></section>'+
      '<section class="wood"><h2>시즌별 현금 흐름</h2><div class="table-scroll"><table><thead><tr><th>시즌</th><th>기초</th><th>수입</th><th>지출</th><th>순현금흐름</th><th>기말/현재</th></tr></thead><tbody>'+j.periods.map(row).join('')+'</tbody></table></div><label>항목별 내역 시즌 <select id="journal-season">'+j.periods.map(p=>'<option value="'+p.season+'">'+p.season+'시즌</option>').join('')+'</select></label><div id="journal-breakdown"></div></section>'+
      '<section class="wood"><h2>최근 실제 거래</h2><p class="muted-copy">전체 합계는 모두 보존되며 상세 내역은 최근 120건만 유지합니다. 월간 보고와 중복 합산하지 않습니다.</p><div class="controls"><label>구분 <select id="journal-filter"><option value="all">전체</option><option value="income">수입</option><option value="expense">지출</option></select></label><label>항목 <select id="journal-category"><option value="">전체</option>'+[...new Set(j.recent.map(r=>r.category))].map(k=>'<option value="'+e(k)+'">'+label(k)+'</option>').join('')+'</select></label></div><div class="table-scroll"><table><thead><tr><th>시즌·주차</th><th>항목</th><th>금액</th><th>거래 직후 잔액</th></tr></thead><tbody id="journal-rows"></tbody></table></div><p id="journal-count"></p></section>';
    const sel=root.querySelector('#journal-season');
    function breakdown(){
      const p=j.periods.find(x=>String(x.season)===sel.value);
      if(!p)return;
      const items=(obj)=>Object.entries(obj).sort((a,b)=>b[1]-a[1]).map(([k,v])=>'<li><span>'+label(k)+'</span> <strong>'+money(v)+'</strong></li>').join('')||'<li>기록 없음</li>';
      root.querySelector('#journal-breakdown').innerHTML='<div class="finance-breakdowns"><div class="finance-breakdown-card"><h3>수입</h3><ul class="finance-breakdown">'+items(p.income_by)+'</ul></div><div class="finance-breakdown-card"><h3>지출</h3><ul class="finance-breakdown">'+items(p.expense_by)+'</ul></div></div>';
    }
    function transactions(){
      const filter=root.querySelector('#journal-filter').value, cat=root.querySelector('#journal-category').value;
      const rows=j.recent.filter(r=>(!cat||r.category===cat)&&(filter==='all'||(filter==='income'?r.amount>0:r.amount<0)));
      root.querySelector('#journal-rows').innerHTML=rows.map(r=>'<tr><td>'+r.season+'시즌 '+r.week+'주</td><td>'+label(r.category)+'</td><td class="'+(r.amount>0?'positive':'negative')+'">'+signed(r.amount)+'</td><td>'+money(r.after)+'</td></tr>').join('')||'<tr><td colspan="4">표시할 거래가 없습니다.</td></tr>';
      root.querySelector('#journal-count').textContent=rows.length+'건 표시 / 전체 '+j.count+'건';
    }
    sel.onchange=breakdown;root.querySelector('#journal-filter').onchange=transactions;root.querySelector('#journal-category').onchange=transactions;
    breakdown();transactions();
  }
  return {render, status, entries, showJournal};
})();