/* Jianghu territory atlas. All ownership, income and defense values come from
 * Campaign.world_map_view; the SVG topology is a deterministic visual aid only.
 * Do not infer routes, adjacency or combat odds from the ornamental map.
 */
let worldMapSelectedId = null;
let worldMapMode = 'owner';

const WORLD_MAP_FACTION_PALETTE = [
  '#587c83', '#986f68', '#7c759b', '#64896e',
  '#9b8058', '#a06d85', '#6b82a1', '#89905e',
  '#987e7d', '#607e78', '#8d7390', '#a1845b'
];
const WORLD_MAP_MODES = {owner:'세력', income:'수익', power:'전력'};

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

function worldMapOwnerColor(zone) {
  if (zone.owner === state.guild) return '#d2ac61';
  if (zone.owner === null) return '#798c88';
  const index = (((Number(zone.owner) || 0) * 17 + 3) >>> 0) % WORLD_MAP_FACTION_PALETTE.length;
  return WORLD_MAP_FACTION_PALETTE[index];
}

function worldMapStatus(zone) {
  return zone.owner === state.guild ? 'ally' : zone.owner === null ? 'neutral' : 'rival';
}

function worldMapFinite(value, fallback) {
  return Number.isFinite(Number(value)) ? Number(value) : fallback;
}

function worldMapBand(value, min, max) {
  if (max <= min) return 0.5;
  return Math.max(0, Math.min(1, (value - min) / (max - min)));
}

function worldMapRange(sites, key) {
  const values = sites.map(site => worldMapFinite(site[key], 0));
  return {min:Math.min(...values),max:Math.max(...values)};
}

function worldMapFill(site, ranges) {
  if (worldMapMode === 'owner') {
    if (site.owner === state.guild) return '#8a723e';
    if (site.owner === null) return '#4e605c';
    return worldMapOwnerColor(site);
  }
  if (worldMapMode === 'income') {
    if (worldMapFinite(site.weekly_net, 0) < 0) return '#87534a';
    const v = worldMapBand(worldMapFinite(site.weekly_net,0),ranges.income.min,ranges.income.max);
    return ['#3f5048','#5f6a4e','#858052','#aa9154','#d0ad64'][Math.min(4,Math.floor(v*5))];
  }
  const v = worldMapBand(worldMapFinite(site.defense_power,0),ranges.power.min,ranges.power.max);
  return ['#456f68','#628679','#9a9366','#a37656','#ad5f5b'][Math.min(4,Math.floor(v*5))];
}

function worldMapLabel(site) {
  if (worldMapMode === 'income') {
    const value = worldMapFinite(site.weekly_net,0);
    return (value >= 0 ? '+' : '') + number(value) + '냥/주';
  }
  if (worldMapMode === 'power') return '수비 ' + powerLabel(site.defense_power);
  return site.owner === null ? '수비대' : String(site.owner_name || '불명').slice(0,7);
}

function worldMapBriefName(name) {
  const value = String(name || '');
  return value.length > 9 ? value.slice(0,8) + '…' : value;
}

/* Generate a clipped Voronoi atlas from stable site indices.
 * A zone has no adjacency game rules; polygons only convey visual ownership.
 */
function worldMapPositions(sites) {
  const total = sites.length;
  const cols = total >= 30 ? 7 : 6;
  const rows = Math.ceil(total / cols);
  const width = 1020 / cols;
  const height = 570 / rows;
  return sites.map((site,index) => {
    const row = Math.floor(index / cols);
    const col = index % cols;
    const rowCount = Math.min(cols,total-row*cols);
    const center = (cols-rowCount) / 2;
    const hash = ((site.id + 11) * 73 + index * 37) >>> 0;
    const jitterX = ((hash % 19)-9) * Math.min(0.95,width/105);
    const jitterY = (((hash >>> 3) % 17)-8) * Math.min(0.8,height/90);
    return {site,x:40 + (col + center + .5)*width + jitterX,
            y:42 + (row+.5)*height + jitterY};
  });
}

function worldMapClip(polygon,center,other) {
  const dx=other.x-center.x, dy=other.y-center.y;
  const mx=(center.x+other.x)/2, my=(center.y+other.y)/2;
  const signed=point=>(point.x-mx)*dx+(point.y-my)*dy;
  const result=[];
  for (let i=0;i<polygon.length;i++) {
    const a=polygon[i],b=polygon[(i+1)%polygon.length];
    const fa=signed(a),fb=signed(b);
    const ai=fa<=.00001,bi=fb<=.00001;
    if (ai) result.push(a);
    if (ai!==bi) {
      const t=fa/(fa-fb);
      result.push({x:a.x+(b.x-a.x)*t,y:a.y+(b.y-a.y)*t});
    }
  }
  return result;
}

function worldMapProvincePath(point,positions) {
  let polygon=[
    {x:34,y:34},{x:1066,y:34},{x:1066,y:619},{x:34,y:619}
  ];
  for (const other of positions) {
    if (other===point) continue;
    polygon=worldMapClip(polygon,point,other);
    if (!polygon.length) break;
  }
  return polygon.length ? 'M'+polygon.map(p=>p.x.toFixed(1)+' '+p.y.toFixed(1)).join('L')+'Z' : '';
}

function worldMapTerrainMark(site,x,y) {
  const code=site.terrain?.id || '';
  const X=(x+43).toFixed(1),Y=(y+20).toFixed(1);
  let shape;
  switch(code) {
    case 'mountain':
      shape='<path d="M-26 16L-9 -14L9 16 M-4 16L13 -7L29 16 M-16 1L-9 -9L-3 1"/>';
      break;
    case 'forest':
      shape='<path d="M-20 12L-11 -13L-1 12Z M-3 15L10 -20L23 15Z M10 13V22 M-11 12V20"/>';
      break;
    case 'river':
      shape='<path d="M-30 -10Q-20 -18 -10 -10T10 -10T30 -10 M-30 1Q-20 -7 -10 1T10 1T30 1 M-30 12Q-20 4 -10 12T10 12T30 12"/>';
      break;
    case 'fortress':
      shape='<path d="M-23 16V-11H-15V-17H-6V-11H6V-17H15V-11H23V16Z M-6 16V2Q0 -6 6 2V16 M-27 16H27"/>';
      break;
    case 'gorge':
      shape='<path d="M-27 -18L-12 -3L-20 9L-7 22 M27 -18L10 -4L19 10L5 22 M-2 -17L4 -7L-4 5L2 17"/>';
      break;
    default:
      shape='<path d="M-24 14Q-14 -5 -4 14T16 14 M-18 1L-13 -12L-7 1 M9 4L14 -9L20 4"/>';
  }
  return '<g class="world-map-terrain-mark" transform="translate('+X+' '+Y+')">'+shape+'</g>';
}

function worldMapEmblem(zone,x,y) {
  const color=worldMapOwnerColor(zone);
  const glyph=zone.owner === null ? '守' : String(zone.owner_name || '문').slice(0,1);
  return '<g class="world-map-emblem" transform="translate('+x.toFixed(1)+' '+(y-25).toFixed(1)+')">'+
    '<path class="world-map-flagpole" d="M-17 -11V16"/>'+
    '<path class="world-map-flag" fill="'+color+'" d="M-16 -11H13L7 -3L13 6H-16Z"/>'+
    '<text class="world-map-flag-letter" x="-2" y="1">'+escapeText(glyph)+'</text>'+
    '</g>';
}

function worldMapFactionStrip(sites) {
  const owners=new Map();
  sites.forEach(zone => {
    const id=zone.owner === null ? 'neutral' : String(zone.owner);
    if (!owners.has(id)) owners.set(id,{zone,count:0});
    owners.get(id).count++;
  });
  const factions=[...owners.values()].sort((a,b)=>b.count-a.count || String(a.zone.owner_name).localeCompare(String(b.zone.owner_name),'ko'));
  const visible=factions.slice(0,6);
  return '<div class="world-map-faction-strip" aria-label="주요 점령 세력">'+
    visible.map(entry=>
      '<span class="world-map-faction-item"><i style="background:'+worldMapOwnerColor(entry.zone)+'"></i>'+
      escapeText(entry.zone.owner===state.guild?'우리 문파':entry.zone.owner_name)+
      '<b>'+entry.count+'곳</b></span>').join('')+
    (factions.length>visible.length?'<span class="world-map-faction-more">그 외 '+(factions.length-visible.length)+'개 세력</span>':'')+
    '</div>';
}

function worldMapDetails(zone,sites) {
  if (!zone) return '<p>표시할 거점이 없습니다.</p>';
  sites=sites || worldMapSites(leagueTier);
  const owned = zone.owner === state.guild;
  const guild = worldMapGuild(zone);
  const allowed = state.phase === 'ready' && zone.selectable && zone.tier === state.tier;
  const protectedSite = zone.protected_until > (state.operations?.clock ?? 0);
  const status=owned?'아군 점령':protectedSite?'점령 보호 중':allowed?'점령 신청 가능':zone.tier!==state.tier?'타 리그 거점':'현황 조회';
  const rangeIncome=worldMapRange(sites,'weekly_net');
  const rangePower=worldMapRange(sites,'defense_power');
  const incomePercent=Math.round(100*worldMapBand(worldMapFinite(zone.weekly_net,0),rangeIncome.min,rangeIncome.max));
  const powerPercent=Math.round(100*worldMapBand(worldMapFinite(zone.defense_power,0),rangePower.min,rangePower.max));
  const net=worldMapFinite(zone.weekly_net,0);
  return '<div class="world-map-detail-heading">'+
    '<div><span class="world-map-eyebrow">'+zone.tier+'부 · '+escapeText(zone.site_grade)+' · '+escapeText(zone.terrain?.name||'지형 미상')+'</span>'+
    '<h4>'+escapeText(zone.name)+'</h4></div>'+
    '<span class="world-map-status '+worldMapStatus(zone)+'">'+escapeText(status)+'</span></div>'+
    '<div class="world-map-owner-card"><span class="world-map-owner-symbol" style="--owner-color:'+worldMapOwnerColor(zone)+'">'+
    escapeText(zone.owner===null?'守':String(zone.owner_name||'문').slice(0,1))+'</span>'+
    '<div><small>점령 세력</small><strong>'+escapeText(zone.owner_name)+(owned?' · 우리 문파':'')+'</strong></div></div>'+
    '<div class="world-map-highlights">'+
    '<div><small>주간 예상 순수입</small><strong class="'+(net<0?'negative':'positive')+'">'+(net>0?'+':'')+money(net)+'</strong></div>'+
    '<div><small>수비 평균전력</small><strong>'+powerLabel(zone.defense_power)+'</strong></div></div>'+
    '<div class="world-map-comparison"><div><span>리그 내 수익 수준</span><b>'+incomePercent+'%</b></div>'+
    '<div class="world-map-meter"><i style="width:'+Math.max(4,incomePercent)+'%" class="income"></i></div>'+
    '<div><span>리그 내 수비전력 수준</span><b>'+powerPercent+'%</b></div>'+
    '<div class="world-map-meter"><i style="width:'+Math.max(4,powerPercent)+'%" class="power"></i></div></div>'+
    '<dl class="world-map-facts">'+
    '<dt>7일 총수입</dt><dd>'+money(zone.gross)+'</dd>'+
    '<dt>7일 직접 유지비</dt><dd>'+money(zone.upkeep)+'</dd>'+
    (state.month_weeks ? '<dt>이번 달 예상 순수입</dt><dd>'+money(net*state.month_weeks)+'</dd>' : '')+
    '<dt>전장 지형</dt><dd>'+escapeText(zone.terrain?.name || '정보 없음')+'</dd>'+
    (zone.field_layout ? '<dt>전장 편성</dt><dd>폭 '+zone.field_layout.width+' · 전열 '+zone.field_layout.front+
      '칸 · 후열 '+zone.field_layout.back+'칸<br>'+escapeText(zone.field_layout.route)+'</dd>' : '')+
    '<dt>점령 상태</dt><dd>'+escapeText(status)+'</dd>'+
    '</dl>'+
    '<p class="world-map-detail-note">수익·전력 막대는 같은 리그 거점 사이의 상대적 위치입니다. 승률을 뜻하지 않습니다. 수입은 7일 보유 가정이며 점령 첫 주·급여·다른 사업 수지는 제외합니다.</p>'+
    '<div class="world-map-actions">'+
    (guild ? '<button type="button" data-world-sect="'+guild.id+'">점령 문파 상세</button>' : '')+
    (allowed ? '<button type="button" class="primary" data-world-attack="'+zone.id+'">점령전 준비</button>' : '')+
    '</div>';
}

function renderWorldMap() {
  if (!Array.isArray(state.world_map) || !state.world_map.length) {
    return '<section class="wood"><p>거점 정보를 불러오지 못했습니다.</p></section>';
  }
  const sites=worldMapSites(leagueTier);
  if (!sites.length) return '<section class="wood"><p>선택한 리그에 거점이 없습니다.</p></section>';
  const owned=sites.filter(z=>z.owner===state.guild);
  const neutral=sites.filter(z=>z.owner===null).length;
  const rivals=sites.length-owned.length-neutral;
  const weeklyIncome=owned.reduce((total,z)=>total+worldMapFinite(z.weekly_net,0),0);
  const selected=sites.find(z=>z.id===worldMapSelectedId)||owned[0]||sites[0];
  worldMapSelectedId=selected.id;
  if (!WORLD_MAP_MODES[worldMapMode]) worldMapMode='owner';
  const positions=worldMapPositions(sites);
  const ranges={income:worldMapRange(sites,'weekly_net'),power:worldMapRange(sites,'defense_power')};
  const provinces=positions.map(point=>{
    const site=point.site;
    const status=worldMapStatus(site);
    const selectedClass=site.id===worldMapSelectedId?' selected':'';
    const label=site.name+' · '+site.owner_name+' · 수비 '+powerLabel(site.defense_power)+' · 주간 순수입 '+money(site.weekly_net);
    return '<g class="world-map-node '+status+selectedClass+'" data-world-zone="'+site.id+'" role="button" tabindex="0" aria-pressed="'+
      (site.id===worldMapSelectedId)+'" aria-label="'+escapeText(label)+'">'+
      '<title>'+escapeText(label)+'</title>'+
      '<path class="world-map-province" fill="'+worldMapFill(site,ranges)+'" d="'+worldMapProvincePath(point,positions)+'"/>'+
      worldMapTerrainMark(site,point.x,point.y)+
      worldMapEmblem(site,point.x,point.y)+
      '<text class="world-map-site-name" x="'+point.x.toFixed(1)+'" y="'+(point.y+15).toFixed(1)+'">'+escapeText(worldMapBriefName(site.name))+'</text>'+
      '<text class="world-map-site-sub" x="'+point.x.toFixed(1)+'" y="'+(point.y+32).toFixed(1)+'">'+escapeText(worldMapLabel(site))+'</text>'+
      (site.site_grade==='고수익'?'<circle class="world-map-prosperity" cx="'+(point.x-31).toFixed(1)+'" cy="'+(point.y-19).toFixed(1)+'" r="3.5"/>':'')+
      '</g>';
  }).join('');
  const rows=sites.map(site=>{
    const active=site.id===worldMapSelectedId;
    const status=worldMapStatus(site);
    return '<tr class="'+(active?'world-map-row-selected':'')+'"><th><button type="button" class="world-map-site-link" data-world-zone="'+site.id+
      '" aria-pressed="'+active+'">'+escapeText(site.name)+'</button></th>'+
      '<td><span class="world-map-owner '+status+'" style="--owner-color:'+worldMapOwnerColor(site)+'">'+escapeText(site.owner_name)+'</span></td>'+
      '<td class="world-map-number">'+money(site.weekly_net)+'</td>'+
      '<td class="world-map-number">'+powerLabel(site.defense_power)+'</td></tr>';
  }).join('');
  const modes=Object.keys(WORLD_MAP_MODES).map(key=>
    '<button type="button" data-world-map-mode="'+key+'" aria-pressed="'+(key===worldMapMode)+'">'+WORLD_MAP_MODES[key]+'</button>').join('');
  const legend=worldMapMode==='owner'?
    '<span><i style="background:#d2ac61"></i>우리 문파</span><span><i style="background:#798c88"></i>수비대</span><span>문파별 깃발 색상</span>':
    worldMapMode==='income'?
    '<span><i style="background:#3f5048"></i>수익 낮음</span><span><i style="background:#d0ad64"></i>수익 높음</span><span>주간 순수입 기준</span>':
    '<span><i style="background:#456f68"></i>수비 약함</span><span><i style="background:#ad5f5b"></i>수비 강함</span><span>승률 예측 아님</span>';
  return '<section class="wood world-map" id="world-map">'+
    '<div class="world-map-head"><div><p class="world-map-kicker">JIANGHU · TERRITORY ATLAS</p><h3>강호 패권 지도 · '+leagueTier+'부</h3>'+
    '<p class="muted-copy">실제 거점 '+sites.length+'곳의 점령 상태와 경제·수비 정보를 확인하세요.</p></div>'+
    '<div class="world-map-counts"><span><small>내 문파 거점</small><b>'+owned.length+'곳</b></span>'+
    '<span><small>경쟁 세력 거점</small><b>'+rivals+'곳</b></span>'+
    '<span><small>무주지</small><b>'+neutral+'곳</b></span>'+
    '<span class="world-map-income-summary"><small>내 거점 주간 순수익</small><b>'+money(weeklyIncome)+'</b></span></div></div>'+
    '<div class="world-map-toolbar"><span class="world-map-toolbar-label">지도 표시</span>'+
    '<div class="world-map-mode-group" role="group" aria-label="패권 지도 표시 모드">'+modes+'</div>'+
    '<small>거점을 선택하면 세부 정보를 확인할 수 있습니다.</small></div>'+
    '<div class="world-map-layout"><div class="world-map-canvas">'+
    '<div class="world-map-mapframe"><svg class="world-map-svg" viewBox="0 0 1100 656" role="group" aria-label="'+leagueTier+'부 영토형 점령 지도">'+
    '<defs><radialGradient id="world-map-paper"><stop offset="0%" stop-color="#424336"/><stop offset="100%" stop-color="#222b27"/></radialGradient>'+
    '<pattern id="world-map-dust" width="34" height="34" patternUnits="userSpaceOnUse"><path d="M2 11L5 9 M20 27L22 26" stroke="#f1d8a8" stroke-opacity=".09" stroke-width="1"/></pattern></defs>'+
    '<rect x="0" y="0" width="1100" height="656" fill="url(#world-map-paper)"/>'+
    '<path class="world-map-contour" d="M10 115Q115 55 240 125T460 118T700 86T1100 93 M0 480Q95 425 200 492T453 492T740 485T1100 470 M8 555Q145 490 280 550T590 541T900 555T1100 529"/>'+
    '<g class="world-map-provinces">'+provinces+'</g>'+
    '<path class="world-map-river" d="M4 171Q127 216 225 170T432 244T684 252T901 315T1094 395"/>'+
    '<path class="world-map-river-glint" d="M4 171Q127 216 225 170T432 244T684 252T901 315T1094 395"/>'+
    '<path class="world-map-roads" d="M53 479Q202 449 351 469T636 383T1047 490 M42 286Q200 312 315 290T630 308T1046 206"/>'+
    '<rect x="0" y="0" width="1100" height="656" fill="url(#world-map-dust)" pointer-events="none"/>'+
    '<path class="world-map-frame-line" d="M25 25H1075V631H25Z"/>'+
    '<text class="world-map-compass" x="1042" y="72">北</text>'+
    '<path class="world-map-compass-arrow" d="M1042 80V108 M1035 91L1042 80L1049 91"/>'+
    '</svg></div>'+
    '<div class="world-map-legend">'+legend+'</div>'+
    '<p class="world-map-footnote">전략 개념도입니다. 경계·강·길은 장식 요소이며 실제 거리, 인접 거점 효과, 이동 경로를 뜻하지 않습니다. 좁은 화면에서는 지도를 좌우로 이동할 수 있습니다.</p>'+
    '</div><aside id="world-map-detail" class="world-map-detail" aria-live="polite">'+worldMapDetails(selected,sites)+'</aside></div>'+
    worldMapFactionStrip(sites)+
    '<details class="world-map-directory"><summary>전체 거점 목록 · '+sites.length+'곳 <span>이름 / 점령 세력 / 수익 / 전력</span></summary>'+
    '<div class="world-map-list-scroll"><table><thead><tr><th>거점 이름</th><th>점령 세력</th><th>주간 순수입</th><th>수비전력</th></tr></thead><tbody>'+rows+
    '</tbody></table></div></details></section>';
}

function bindWorldMap() {
  const root=panel().querySelector('#world-map');
  if (!root) return;
  const select=id=>{
    const zone=worldMapSites(leagueTier).find(site=>site.id===id);
    if (!zone) return;
    worldMapSelectedId=id;
    root.querySelectorAll('[data-world-zone]').forEach(item=>{
      const active=Number(item.dataset.worldZone)===id;
      item.setAttribute('aria-pressed',String(active));
      item.classList.toggle('selected',active);
    });
    root.querySelector('#world-map-detail').innerHTML=worldMapDetails(zone);
    bindDetails();
  };
  const bindDetails=()=>{
    root.querySelector('[data-world-sect]')?.addEventListener('click',event=>
      runMarket('sect_profile',{id:Number(event.currentTarget.dataset.worldSect)},showSectProfile));
    root.querySelector('[data-world-attack]')?.addEventListener('click',event=>{
      const id=Number(event.currentTarget.dataset.worldAttack);
      if (state.phase!=='ready'||!state.zones.some(z=>z.id===id&&z.selectable)) return;
      draft.zone=id;
      currentTab='week';
      management();
      panel().querySelector('#target-zone')?.focus();
    });
  };
  root.querySelectorAll('[data-world-zone]').forEach(item=>{
    item.addEventListener('click',()=>select(Number(item.dataset.worldZone)));
    if (item.tagName.toLowerCase()==='g') {
      item.addEventListener('keydown',event=>{
        if(event.key==='Enter'||event.key===' ') {
          event.preventDefault();
          select(Number(item.dataset.worldZone));
        }
      });
    }
  });
  root.querySelectorAll('[data-world-map-mode]').forEach(button=>{
    if (!button.dataset.worldMapMode) return;
    button.addEventListener('click',()=>{
      if (!WORLD_MAP_MODES[button.dataset.worldMapMode]||worldMapMode===button.dataset.worldMapMode) return;
      worldMapMode=button.dataset.worldMapMode;
      root.outerHTML=renderWorldMap();
      bindWorldMap();
      panel().querySelector('[data-world-map-mode="'+worldMapMode+'"]')?.focus({preventScroll:true});
    });
  });
  bindDetails();
}
