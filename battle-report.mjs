/* Group battle report: derived presentation only, never changes the battle or economy. */
export const SORTS = Object.freeze([
  {id:'score',label:'활약순'}, {id:'damage',label:'준 피해'},
  {id:'taken',label:'받은 피해'}, {id:'healing',label:'치유'},
  {id:'kills',label:'처치'}, {id:'protection',label:'보호'}
]);
const WEIGHTS = Object.freeze({
  guard: {damage:.18,taken:.22,healing:0,kills:.10,protection:.42,actions:.08},
  heal:  {damage:.07,taken:.08,healing:.58,kills:.07,protection:.12,actions:.08},
  hex:   {damage:.40,taken:.08,healing:.05,kills:.27,protection:.08,actions:.12},
  blade: {damage:.44,taken:.08,healing:.03,kills:.30,protection:.05,actions:.10},
  bow:   {damage:.48,taken:.05,healing:.02,kills:.32,protection:.03,actions:.10},
  dash:  {damage:.42,taken:.08,healing:.02,kills:.36,protection:.02,actions:.10}
});
const KEYS=['damage','taken','healing','kills','protection','actions'];
const safeNumber=n=>Number.isFinite(n)&&n>0?n:0;
const sum=(rows,key)=>rows.reduce((acc,row)=>acc+row[key],0);
const numeric=(a,b)=>b-a;
const best=(rows,key)=>rows.filter(x=>x[key]>0).sort((a,b)=>numeric(a[key],b[key])||a.id-b.id)[0]||null;

export function buildBattleReport(game) {
  if(!game || ![8,10].includes(game.mode) || !game.finished)
    throw new Error('종료된 8대8 또는 10대10 전투만 성적표를 작성할 수 있습니다.');
  const fighters=game.units.filter(u=>u.side===0||u.side===1).map(u=>{
    const damage=safeNumber(u.damage??u.damageDealt),taken=safeNumber(u.hitTaken),
      healing=safeNumber(u.healing),kills=safeNumber(u.kills),
      shield=safeNumber(u.absorbed), shieldGiven=safeNumber(u.shieldGiven),
      actions=safeNumber(u.actions);
    return {id:u.id,side:u.side,name:String(u.name||'이름 없음'),
      role:String(u.role||''),portrait:u.portrait||'',line:u.line,
      hp:Math.max(0,Number(u.hp)||0),max:Math.max(0,Number(u.max)||0),
      damage,taken,healing,kills,absorbed:shield,shieldGiven,
      protection:shield+shieldGiven,actions,score:0,
      alive:u.hp>0};
  });
  const sides=[0,1].map(side=>{
    const rows=fighters.filter(u=>u.side===side);
    const max=Object.fromEntries(KEYS.map(key=>[key,Math.max(0,...rows.map(u=>u[key]))]));
    for(const row of rows){
      const weights=WEIGHTS[row.role]||WEIGHTS.blade;
      const score=KEYS.reduce((acc,key)=>acc+(max[key]?row[key]/max[key]*weights[key]:0),0);
      row.score=Math.round(100*score);
    }
    const arts=(game.artEvents||[]).filter(e=>e.side===side);
    const artDamage=arts.reduce((n,e)=>n+safeNumber(e.damage),0);
    const artHealing=arts.reduce((n,e)=>n+safeNumber(e.restored),0);
    const ranked=[...rows].sort((a,b)=>b.score-a.score||b.damage-a.damage||a.id-b.id);
    const active=ranked.some(u=>u.damage+u.taken+u.healing+u.protection+u.actions+u.kills>0);
    return {side,name:String(game.sectNames?.[side]||('제'+(side+1)+'문파')),
      rows,ranked,mvp:active?ranked[0]:null,
      alive:rows.filter(u=>u.alive).length,
      totals:{damage:sum(rows,'damage'),taken:sum(rows,'taken'),
        healing:sum(rows,'healing'),kills:sum(rows,'kills'),
        artDamage,artHealing},
      leaders:{damage:best(rows,'damage'),taken:best(rows,'taken'),
        healing:best(rows,'healing'),kills:best(rows,'kills'),
        protection:best(rows,'protection')}};
  });
  return {mode:game.mode,winner:game.winner,reason:String(game.reason||''),
    time:Math.floor(game.time||0),sides,
    note:'준 피해·받은 피해는 실제 체력 감소량입니다. 보호막 흡수와 부여는 별도 기록합니다. 문파 비기 및 지속 효과는 실제 기여자가 있으면 개인 기록에도 포함되며, 비기 즉시 피해·치유 통계는 개인 수치와 중복될 수 있으므로 합산하지 않습니다. 활약 점수는 같은 편 안에서 역할별 상대적 기여를 비교하는 참고값입니다.'};
}

export const escapeBattleText=value=>String(value??'').replace(/[&<>"']/g,
  char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const format=value=>Math.round(value).toLocaleString('ko-KR');
const roles={guard:'수호형',blade:'무인형',bow:'사수형',hex:'주술형',heal:'치유형',dash:'암살형'};
const portraitRoles={guard:'guardian',blade:'warrior',bow:'archer',hex:'shaman',heal:'healer',dash:'assassin'};

export function fighterPortrait(unit, large=false){
  const portrait=String(unit?.portrait||'');
  const classes='br-face'+(large?' br-face-lg':'')+(unit.alive===false?' br-ko':'');
  const alt=escapeBattleText(unit.name||'문파원');
  let style='', image='';
  const v2=/^assets\/portraits\/diverse\/v2_([0-5])_([0-7])\.webp$/.exec(portrait);
  const v1=/^assets\/portraits\/diverse\/v1_(\d{2})\.webp$/.exec(portrait);
  const founder=/^assets\/portraits\/founders\/seed16_(\d+)\.webp$/.exec(portrait);
  if(v2){
    const index=(Number(v2[1])%2)*8+Number(v2[2]);
    const sheet=Math.floor(Number(v2[1])/2);
    style='background-image:url(assets/portraits/diverse/atlas_v2_'+sheet+'.webp);background-size:400% 400%;background-position:'+(index%4)*100/3+'% '+Math.floor(index/4)*100/3+'%';
  }else if(v1&&Number(v1[1])<16){
    const index=Number(v1[1]);
    style='background-image:url(assets/portraits/diverse/atlas_v1.webp);background-size:400% 400%;background-position:'+(index%4)*100/3+'% '+Math.floor(index/4)*100/3+'%';
  }else if(founder&&Number(founder[1])>=640&&Number(founder[1])<660){
    const index=Number(founder[1])-640;
    style='background-image:url(assets/portraits/founders/founder_atlas.webp);background-size:500% 400%;background-position:'+(index%5)*25+'% '+Math.floor(index/5)*100/3+'%';
  }else{
    const src='assets/portraits/'+(portraitRoles[unit.role]||'warrior')+'_card.webp';
    image='<img src="'+src+'" alt="" loading="lazy">';
  }
  return '<span class="'+classes+'" role="img" aria-label="'+alt+' 초상화"'+(style?' style="'+style+'"':'')+'>'+image+'</span>';
}
const renderNum=n=>'<span class="br-number">'+format(n)+'</span>';
const highlight=(label,u,value)=>'<article class="br-award"><span class="br-award-title">'+label+'</span>'+
  (u?'<div class="br-award-person">'+fighterPortrait(u)+'<span><b>'+escapeBattleText(u.name)+'</b><small>'+value+'</small></span></div>':
     '<span class="br-award-empty">기록 없음</span>')+'</article>';

export function renderBattleReport(report, side=0, sort='score'){
  if(side!==0&&side!==1)throw Error('invalid side');
  if(!SORTS.some(s=>s.id===sort))throw Error('invalid sort');
  const own=report.sides[0],focus=report.sides[side],mvp=own.mvp;
  const winner=report.winner===-1?'무승부':report.winner===0?'승리':'패배';
  const winnerClass=report.winner===0?'win':report.winner===-1?'draw':'lose';
  const awards=[
    highlight('최고 공격',own.leaders.damage,own.leaders.damage?renderNum(own.leaders.damage.damage)+' 피해':''),
    highlight('방어 기여',own.leaders.protection,own.leaders.protection?renderNum(own.leaders.protection.protection)+' 보호':''),
    highlight('최고 치유',own.leaders.healing,own.leaders.healing?renderNum(own.leaders.healing.healing)+' 회복':''),
    highlight('최다 처치',own.leaders.kills,own.leaders.kills?renderNum(own.leaders.kills.kills)+' 킬':'')
  ].join('');
  const rows=[...focus.rows].sort((a,b)=>b[sort]-a[sort]||b.score-a.score||a.id-b.id);
  const body=rows.map(u=>'<tr class="'+(u.alive?'':'br-fallen')+'">'+
    '<th scope="row"><div class="br-unit">'+fighterPortrait(u)+'<span><b>'+escapeBattleText(u.name)+'</b>'+
    '<small>'+escapeBattleText(roles[u.role]||u.role)+' · '+(u.alive?'생존':'전투불능')+'</small></span></div></th>'+
    '<td>'+renderNum(u.damage)+'</td><td>'+renderNum(u.taken)+'</td>'+
    '<td>'+renderNum(u.healing)+'</td><td>'+renderNum(u.kills)+'</td>'+
    '<td>'+renderNum(u.protection)+'</td><td class="br-score-cell">'+renderNum(u.score)+'</td></tr>').join('');
  const title=report.mode===10?'10대10 승강전':'8대8 단체전';
  return '<div class="br-banner '+winnerClass+'"><span class="br-eyebrow">'+title+' · 전투 종료</span>'+
    '<h2 id="br-title">'+winner+'</h2><p>'+escapeBattleText(own.name)+' <span>VS</span> '+escapeBattleText(report.sides[1].name)+'</p>'+
    '<small>'+escapeBattleText(report.reason)+' · 생존 '+own.alive+'/'+own.rows.length+'명</small></div>'+
    '<div class="br-intro"><div class="br-mvp">'+(mvp?fighterPortrait(mvp,true):'<span class="br-mvp-none">—</span>')+
    '<span class="br-mvp-label"><small>우리 문파 MVP</small><strong>'+escapeBattleText(mvp?.name||'선정 없음')+'</strong>'+
    '<span>'+escapeBattleText(mvp?(roles[mvp.role]||mvp.role):'')+'</span></span>'+
    '<div class="br-mvp-score"><b>'+format(mvp?.score||0)+'</b><small>활약 점수</small></div></div>'+
    '<div class="br-awards">'+awards+'</div></div>'+
    '<div class="br-stats-heading"><div><h3>개인 전투 성적표</h3><small>실제 HP 피해와 치유량 기준 · '+focus.rows.length+'명</small></div>'+
    '<div class="br-side-tabs" role="group" aria-label="문파 선택">'+report.sides.map(g=>
      '<button type="button" data-br-side="'+g.side+'" aria-pressed="'+(g.side===side)+'">'+
      escapeBattleText(g.name)+' ('+g.alive+'/'+g.rows.length+')</button>').join('')+'</div></div>'+
    '<div class="br-sort" role="group" aria-label="성적 정렬">'+SORTS.map(s=>
      '<button type="button" data-br-sort="'+s.id+'" aria-pressed="'+(s.id===sort)+'">'+s.label+'</button>').join('')+'</div>'+
    '<div class="br-table-wrap"><table class="br-table"><thead><tr>'+
    '<th scope="col">문파원</th><th scope="col">준 피해</th><th scope="col">받은 피해</th>'+
    '<th scope="col">치유</th><th scope="col">킬</th><th scope="col">보호*</th><th scope="col">활약</th>'+
    '</tr></thead><tbody>'+body+'</tbody></table></div>'+
    '<div class="br-team-totals">선택 문파 집계 · 개인 피해 '+format(focus.totals.damage)+
    ' · 개인 치유 '+format(focus.totals.healing)+
    ' · 비기 즉시 피해(포함) '+format(focus.totals.artDamage)+
    ' · 비기 즉시 회복(포함) '+format(focus.totals.artHealing)+'</div>'+
    '<p class="br-footnote">* 보호는 본인이 흡수한 보호막 피해와 아군에게 부여한 보호막 수치의 합계입니다. '+
    escapeBattleText(report.note)+'</p>';
}
