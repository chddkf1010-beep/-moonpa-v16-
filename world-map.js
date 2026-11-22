/* Read-only territory atlas. Source of truth: Campaign.world_map_view / World15.zones.
 * Never mutate ownership in the browser; existing savegame owns all zone state.
 */
let worldMapSelectedId = null;

function worldMapSites(tier) {
  return (state.world_map || []).filter(zone => zone.tier === tier);
}

function worldMapGuild(zone) {
  if (zone.owner === null) return null;
  for (const group of (state.league?.groups || [])) {
    const guild = group.members.find(item => item.id === zone.owner);
    if (guild) return guild;
  }
  return null;
}

function worldMapDetails(zone) {
  if (!zone) return '<p>표시할 거점이 없습니다.</p>';
  const owned = zone.owner === state.guild;
  const guild = worldMapGuild(zone);
  const allowed = state.phase === 'ready' && zone.selectable && zone.tier === state.tier;
  const protectedSite = zone.protected_until > state.operations.clock;
  return '<h4>' + escapeText(zone.name) + '</h4>' +
    '<p class="world-map-meta">' + zone.tier + '부 · ' + escapeText(zone.site_grade) + '</p>' +
    '<dl class="world-map-facts">' +
    '<dt>점령 세력</dt><dd>' + escapeText(zone.owner_name) + (owned?' (우리 문파)':'') + '</dd>' +
    '<dt>수비 평균전력</dt><dd>' + powerLabel(zone.defense_power) + '</dd>' +
    '<dt>7일 총수입</dt><dd>' + money(zone.gross) + '</dd>' +
    '<dt>7일 직접 유지비</dt><dd>' + money(zone.upkeep) + '</dd>' +
    '<dt>7일 기준 가치</dt><dd>' + money(zone.value) + '</dd>' +
    '<dt>상태</dt><dd>' + (owned?'아군 점령':protectedSite?'점령 보호 중':allowed?'점령 신청 가능':zone.tier!==state.tier?'타 리그 거점':'현황 조회') + '</dd>' +
    '</dl>' +
    '<p class="muted-copy">실제 주간 수익은 점령 기간·추가 관리비·주간 정산에 따라 달라질 수 있습니다.</p>' +
    '<div class="world-map-actions">' +
    (guild ? '<button type="button" data-world-sect="' + guild.id + '">점령 문파 상세</button>' : '') +
    (allowed ? '<button type="button" class="primary" data-world-attack="' + zone.id + '">점령전 준비</button>' : '') +
    '</div>';
}

function renderWorldMap() {
  if (!Array.isArray(state.world_map) || !state.world_map.length) {
    return '<section class="wood"><p>거점 정보를 불러오지 못했습니다.</p></section>';
  }
  const sites = worldMapSites(leagueTier);
  const owned = sites.filter(z => z.owner === state.guild).length;
  const neutral = sites.filter(z => z.owner === null).length;
  const rival = sites.length - owned - neutral;
  const selected = sites.find(z => z.id === worldMapSelectedId) || sites[0];
  if (selected) worldMapSelectedId = selected.id;
  const columns = 6;
  const points = sites.map((site,index) => ({
    site,
    x: 98 + index % columns * 178 + (index * 13 % 21) - 10,
    y: 94 + Math.floor(index / columns) * 89 + (index * 11 % 17) - 8
  }));
  const nodes = points.map(({site,x,y}) => {
    const status = site.owner === state.guild ? 'ally' : site.owner === null ? 'neutral' : 'rival';
    const active = site.id === worldMapSelectedId;
    const label = site.name + ' · ' + site.owner_name + ' · 평균전력 ' + powerLabel(site.defense_power);
    return '<g class="world-map-node ' + status + (active?' selected':'') +
      '" data-world-zone="' + site.id + '" role="button" tabindex="0" aria-pressed="' + active +
      '" aria-label="' + escapeText(label) + '">' +
      '<circle class="world-map-ring" cx="' + x + '" cy="' + y + '" r="20" />' +
      '<circle class="world-map-dot" cx="' + x + '" cy="' + y + '" r="12" />' +
      '<text x="' + x + '" y="' + (y+29) + '">' + escapeText(site.name) + '</text></g>';
  }).join('');
  const rows = sites.map(site => {
    const status = site.owner === state.guild ? 'mine' : site.owner === null ? 'neutral' : 'rival';
    return '<tr><td>' + site.tier + '부</td><th><button type="button" class="world-map-site-link" data-world-zone="' + site.id + '" aria-pressed="' + (site.id === worldMapSelectedId) + '">' + escapeText(site.name) + '</button></th>' +
      '<td><span class="world-map-owner ' + status + '">' + escapeText(site.owner_name) + '</span></td>' +
      '<td class="world-map-number">' + powerLabel(site.defense_power) + '</td></tr>';
  }).join('');
  return '<section class="wood world-map" id="world-map">' +
    '<div class="world-map-head"><div><h3>강호 패권 지도 · ' + leagueTier + '부</h3>' +
    '<p class="muted-copy">실제 거점 ' + sites.length + '곳 · 점령 소유권은 게임 기록과 연동됩니다.</p></div>' +
    '<div class="world-map-counts"><span>내 문파 ' + owned + '</span><span>경쟁 문파 ' + rival +
    '</span><span>수비대 ' + neutral + '</span></div></div>' +
    '<div class="world-map-layout"><div class="world-map-canvas">' +
    '<svg viewBox="0 0 1100 710" role="group" aria-label="' + leagueTier + '부 점령 현황 지도">' +
    '<g class="world-map-grid"><path d="M0 165 H1100 M0 345 H1100 M0 525 H1100 M185 0 V710 M550 0 V710 M915 0 V710"/></g>' +
    nodes + '</svg>' +
    '<div class="world-map-legend"><span class="ally">● 아군</span><span class="rival">● 경쟁 문파</span><span class="neutral">● 수비대</span></div>' +
    '<p class="world-map-footnote">전략 배치도입니다. 실제 지리 좌표나 이동 경로를 뜻하지 않습니다.</p>' +
    '</div><aside id="world-map-detail" class="world-map-detail" aria-live="polite">' +
    worldMapDetails(selected) + '</aside></div>' +
    '<details class="world-map-directory"><summary>거점 목록 ' + sites.length + '곳 · 문파/평균전력 보기</summary>' +
    '<div class="world-map-list-scroll"><table><thead><tr><th>리그</th><th>거점 이름</th><th>점령 문파/수비대</th><th>평균전력</th></tr></thead><tbody>' +
    rows + '</tbody></table></div></details></section>';
}

function bindWorldMap() {
  const root = panel().querySelector('#world-map');
  if (!root) return;
  const select = id => {
    const zone = worldMapSites(leagueTier).find(site => site.id === id);
    if (!zone) return;
    worldMapSelectedId = id;
    root.querySelectorAll('[data-world-zone]').forEach(item => {
      const active = Number(item.dataset.worldZone) === id;
      item.setAttribute('aria-pressed', String(active));
      item.classList.toggle('selected', active);
    });
    root.querySelector('#world-map-detail').innerHTML = worldMapDetails(zone);
    bindDetails();
  };
  const bindDetails = () => {
    root.querySelector('[data-world-sect]')?.addEventListener('click', event =>
      runMarket('sect_profile', {id:Number(event.currentTarget.dataset.worldSect)}, showSectProfile));
    root.querySelector('[data-world-attack]')?.addEventListener('click', event => {
      const id = Number(event.currentTarget.dataset.worldAttack);
      if (state.phase !== 'ready' || !state.zones.some(z => z.id === id && z.selectable)) return;
      draft.zone = id;
      currentTab = 'week';
      management();
      panel().querySelector('#target-zone')?.focus();
    });
  };
  root.querySelectorAll('[data-world-zone]').forEach(item => {
    item.addEventListener('click', () => select(Number(item.dataset.worldZone)));
    if (item.tagName.toLowerCase() === 'g') {
      item.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          select(Number(item.dataset.worldZone));
        }
      });
    }
  });
  bindDetails();
}
