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
      ].join('') : '<p class="finance-estimate-note">첫 월간 결산 전에는 확정 수입·지출 내역이 없습니다. 기본 예상치는 임무 보상·훈련비·투자·부채 상환·전투 결과를 제외합니다.</p>',
      '<div class="finance-footer"><span>구역 기본 수익 ' + money(f.zone) + '/주</span>',
      '<span>장원·후원 수입 ' + money(Number(f.estate)+Number(f.sponsor)) + '/주</span>',
      '<span>월간 진행: ' + (overview.month_weeks || 1) + '주 남음</span></div>',
      '</section>'
    ].join('');
  }
  return {render, status, entries};
})();