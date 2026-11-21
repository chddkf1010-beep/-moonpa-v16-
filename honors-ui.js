/* v9: read-only, cross-linked sect chronicle and honor/epithet codex. */
const honorsUI=(()=>{
  let selectedSeason=null,lastGuild=null,filter='all',focus=null;
  const safe=x=>escapeText(String(x??''));
  const visit=(tab,gid=null,season=null,titleId=null)=>{
    currentTab=tab;lastGuild=gid??state.guild;
    if(season!=null)selectedSeason=Number(season);
    if(titleId!=null){focus=titleId;filter='all';}
    management();
  };
  const currentHonor=()=>state.current_rank_honor;
  const seasonLabel=row=>`${row.tier}부 ${row.rank}위 · ${safe(row.result)}`;
  function showHistory(gid=null,season=null){
    const target=gid??lastGuild??state.guild;
    lastGuild=target;
    runMarket('honors_history',{guild_id:target},h=>{
      const entries=h.entries||[];
      if(season!=null)selectedSeason=Number(season);
      if(!entries.some(x=>x.season===selectedSeason))selectedSeason=entries.at(-1)?.season??null;
      const chosen=entries.find(x=>x.season===selectedSeason);
      const rows=entries.slice().reverse();
      panel().innerHTML=`<div class="honors-page">
        <section class="wood honors-header">
          <div class="honors-emblem" aria-hidden="true"><span>門</span></div>
          <div class="honors-header-main"><small>문파 연대기</small>
            <h2>${safe(h.display_name)}</h2>
            <p>${h.tier}부 · 최고 ${h.best_tier}부 · 통산 승격 ${h.promotions}회 · 1부 우승 ${h.championships}회</p>
            <p>현재 순위 존호: <strong>${safe(h.current_rank?.name||'없음')}</strong>
              ${h.current_rank?`<small> · ${h.current_rank.valid_season}시즌까지 유효</small>`:''}</p>
            <p>획득한 공식·특별 존호 ${h.title_count}종 · 수집한 무인 별호 ${h.epithet_count}종</p>
          </div>
          <div class="controls"><button type="button" id="honors-to-codex">강호 명예록</button>
            ${target!==state.guild?'<button type="button" id="honors-home">내 문파 연대기</button>':''}</div>
        </section>
        <div class="honors-columns">
          <section class="wood"><h3>시즌 타임라인</h3>
            <div class="honors-timeline">
              ${rows.length?rows.map(entry=>`<button type="button" data-history-season="${entry.season}"
                  aria-pressed="${entry.season===selectedSeason}"
                  class="honors-season ${entry.result==='승격'?'up':entry.result==='강등'?'down':'steady'}">
                <span class="honors-node">${entry.result==='승격'?'↑':entry.result==='강등'?'↓':'◆'}</span>
                <span><strong>${entry.season}시즌</strong><small>${seasonLabel(entry)}</small>
                 ${entry.titles.length?`<small class="honors-award">획득 · ${entry.titles.map(safe).join(' · ')}</small>`:''}</span>
              </button>`).join(''):
              '<p class="muted-copy">시즌이 끝나면 이곳에 순위·승강·존호가 누적됩니다.</p>'}
            </div>
          </section>
          <section class="wood honors-season-detail">
            <h3>${chosen?chosen.season+'시즌 천하 결산':'기록 대기'}</h3>
            ${chosen?`<div class="honors-rank"><strong>${chosen.tier}부 ${chosen.rank}위</strong>
              <span>${safe(chosen.result)} · 다음 시즌 ${chosen.next_tier}부</span></div>
              <p>최종 시즌 점수 <strong>${chosen.score}</strong> · 점령전 ${chosen.season_wins}/${chosen.season_attacks}승
                · 방어전 ${chosen.season_defenses}승</p>
              <h3>이번 시즌 획득 명예</h3>
              <div class="honors-won">${chosen.titles.length?chosen.titles.map(t=>`<button type="button" data-honor-title="${safe(t)}">
                <span aria-hidden="true">✦</span> ${safe(t)} <small>도감에서 보기</small></button>`).join(''):'<p>이번 시즌 수여된 존호가 없습니다.</p>'}</div>
              <h3>이번 시즌 무인 별호</h3>
              <div class="honors-won">@{chosen.epithet_awards?.length?chosen.epithet_awards.map(t=>§<button type="button" data-epithet-id="@{safe(t.id)}">
                @{safe(t.fighter_name)} · @{safe(t.name)} <small>도감에서 보기</small></button>§).join(''):
                '<p class="muted-copy">이번 시즌 신규 획득 별호 없음</p>'}</div>
              <h3>당시 리그 최종 순위</h3>
              <div class="table-scroll"><table class="honors-mini-standings">
                <thead><tr><th>순위</th><th>문파</th><th>점수</th><th>전력</th></tr></thead>
                <tbody>${chosen.standings.map(x=>`<tr class="${x.id===h.id?'player-row':''}">
                  <td>${x.rank}</td><td>${safe(x.name)}</td><td>${x.score}</td><td>${x.ca}</td></tr>`).join('')}</tbody>
              </table></div>`:'<p>최초 시즌을 마무리하면 승강과 시즌 기록을 확인할 수 있습니다.</p>'}
          </section>
        </div>
        <section class="wood"><div class="office-title"><h3>영구 특별 존호</h3>
          <button type="button" id="honors-special-link">강호 명예록에서 보기</button></div>
          <div class="honors-cards">${h.specials.length?h.specials.map(t=>
            `<button type="button" data-honor-id="${safe(t.id)}"><b>${safe(t.name)}</b><small>획득 ${t.count}시즌 · 최초 ${t.first_season}시즌</small></button>`).join(''):
              '<p class="muted-copy">특별 존호를 달성하면 여기에서 영구 확인할 수 있습니다.</p>'}</div>
        </section>
      </div>`;
      panel().querySelectorAll('[data-history-season]').forEach(btn=>btn.onclick=()=>showHistory(target,Number(btn.dataset.historySeason)));
      panel().querySelectorAll('[data-honor-title]').forEach(btn=>btn.onclick=()=>visit('honors',target,null,btn.dataset.honorTitle));
      panel().querySelectorAll('[data-epithet-id]').forEach(btn=>btn.onclick=()=>visit('honors',target,null,btn.dataset.epithetId));
      panel().querySelectorAll('[data-honor-id]').forEach(btn=>btn.onclick=()=>visit('honors',target,null,btn.dataset.honorId));
      panel().querySelector('#honors-to-codex').onclick=()=>visit('honors',target);
      panel().querySelector('#honors-special-link').onclick=()=>visit('honors',target);
      panel().querySelector('#honors-home')?.addEventListener('click',()=>visit('history',state.guild));
    });
  }
  function showCodex(gid=null,requested=null){
    const target=gid??lastGuild??state.guild;lastGuild=target;
    if(requested!=null)focus=requested;
    runMarket('honors_codex',{guild_id:target},codex=>{
      const tabs=[['all','전체'],['rank','순위 존호'],['special','특별 존호'],['nicknames','무인 별호']];
      const categories=[...new Set(codex.nicknames.map(x=>x.category))];
      const selected=filter==='rank'?codex.rank:filter==='special'?codex.special:
        filter==='nicknames'?codex.nicknames:
        [...codex.rank,...codex.special,...codex.nicknames];
      const rankIds=new Set(codex.rank.map(x=>x.id)),specialIds=new Set(codex.special.map(x=>x.id));
      const type=item=>rankIds.has(item.id)?'순위 존호':specialIds.has(item.id)?'특별 존호':'무인 별호';
      panel().innerHTML=`<div class="honors-page">
        <section class="wood"><div class="office-title"><div><small>강호 명예록 · 영구 수집</small><h2>${safe(codex.name)}의 명예록</h2></div>
          <button id="codex-to-history" type="button">문파 연대기로</button></div>
          <div class="honors-totals">
            <div><small>순위 존호</small><strong>${codex.totals.rank}/${codex.rank.length}</strong></div>
            <div><small>특별 존호</small><strong>${codex.totals.special}/${codex.special.length}</strong></div>
            <div><small>무인 별호</small><strong>${codex.totals.nicknames}/${codex.nicknames.length}</strong></div>
          </div>
          <p class="muted-copy">순위 존호의 사용 기간은 수상 다음 1시즌뿐입니다. 만료해도 획득 기록과 도감은 보존됩니다.</p>
          <div class="honors-filters">${tabs.map(([id,label])=>`<button type="button" data-codex-filter="${id}" aria-pressed="${filter===id}">${label}</button>`).join('')}</div>
          <p class="muted-copy">${safe(codex.status_note)}</p>
        </section>
        <section class="wood"><h3>존호·별호 목록 · ${selected.length}종</h3>
          <div class="honors-cards honors-grid">${selected.map(t=>{
            const rank=rankIds.has(t.id),special=specialIds.has(t.id);
            const unlocked=rank?t.unlocked:special?t.unlocked:t.status==='획득';
            const status=rank?(t.current?'현재 사용 중':t.unlocked?'과거 획득':'미획득'):unlocked?'획득':'미획득';
            const firstSeason=t.seasons?.[0];
            return `<article class="honors-card ${unlocked?'unlocked':'locked'}" id="honor-${safe(t.id)}">
              <div class="honors-card-head"><small>${type(t)} ${t.grade?'· '+safe(t.grade):''}</small>
                <small>${status}</small></div>
              <h3>${safe(t.name)}</h3>
              ${!rank?`<p>${safe(t.condition)}</p>`:`<p>${t.tier}부 ${t.rank}위 · 수상 후 다음 시즌에만 사용</p>`}
              ${!rank&&!t.available?'<small>추가 전투·대회 콘텐츠 연동 예정</small>':''}
              ${t.count?`<p>획득 횟수 ${t.count}회</p>`:''}
              ${!rank&&t.holders?.length?`<p>현재 보유 무인 · ${t.holders.map(x=>safe(x.name)+' ×'+x.count).join(' / ')}</p>`:''}
              ${firstSeason?`<button type="button" data-codex-season="${firstSeason}">첫 획득 ${firstSeason}시즌 연대기로</button>`:''}
            </article>`;
          }).join('')}</div>
        </section>
      </div>`;
      panel().querySelector('#codex-to-history').onclick=()=>visit('history',target);
      panel().querySelectorAll('[data-codex-filter]').forEach(btn=>btn.onclick=()=>{
        filter=btn.dataset.codexFilter;focus=null;showCodex(target);
      });
      panel().querySelectorAll('[data-codex-season]').forEach(btn=>btn.onclick=()=>visit('history',target,Number(btn.dataset.codexSeason)));
      if(focus){
        const matched=[...panel().querySelectorAll('.honors-card')].find(card=>
          card.id==='honor-'+focus || card.querySelector('h3')?.textContent===focus);
        if(matched)matched.scrollIntoView({block:'center',behavior:'smooth'});
        focus=null;
      }
    });
  }
  return {showHistory,showCodex,visit};
})();
