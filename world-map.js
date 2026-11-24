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
const WORLD_MAP_MODES = {owner:'세력', income:'수익', power:'수비'};
const WORLD_MAP_PLATES = {
  1:{file:'imperial', seats:[[60,705,313],[61,205,326],[62,894,552]]},
  2:{file:'river-trade', seats:[[98,250,218],[99,417,428],[96,875,353]]},
  3:{file:'hill-towns', seats:[[112,210,223],[110,715,321],[113,938,103]]},
  4:{file:'frontier', seats:[[119,660,302],[118,852,540],[116,195,389]]},
};
let worldMapAllNames = false;

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

// Place the principal sites near the settlements in their illustrated plates.
function worldMapPositions(sites) {
  const cols=sites.length>=30?7:6;
  const rows=Math.ceil(sites.length/cols);
  const slots=sites.map((_,index)=>{
    const row=Math.floor(index/cols);
    const col=index%cols;
    const rowCount=Math.min(cols,sites.length-row*cols);
    return {x:58+(col+(cols-rowCount)/2+.5)*984/cols,
            y:44+(row+.5)*610/rows};
  });
  const seats=new Map();
  for(const [id,x,y] of WORLD_MAP_PLATES[sites[0]?.tier]?.seats||[]){
    if(!sites.some(site=>site.id===id)) continue;
    const distance=slot=>Math.hypot(slot.x-x,slot.y-y);
    const nearest=slots.reduce((best,slot,index)=>
      distance(slot)<distance(slots[best])?index:best,0);
    const anchor=slots.splice(nearest,1)[0];
    // Keep names separated even when a painted landmark is close to its neighbor.
    seats.set(id,{x:anchor.x+(x-anchor.x)*.65,y:anchor.y+(y-anchor.y)*.65,major:true});
  }
  return sites.map(site=>{
    const seat=seats.get(site.id);
    if(seat) return {site,...seat};
    const slot=slots.shift();
    const jitterX=(site.id*73)%23-11;
    const jitterY=(site.id*31)%37-18;
    return {site,x:slot.x+jitterX,y:slot.y+jitterY,major:false};
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
    {x:0,y:0},{x:1100,y:0},{x:1100,y:734},{x:0,y:734}
  ];
  for (const other of positions) {
    if (other===point) continue;
    polygon=worldMapClip(polygon,point,other);
    if (!polygon.length) break;
  }
  return polygon.length ? 'M'+polygon.map(p=>p.x.toFixed(1)+' '+p.y.toFixed(1)).join('L')+'Z' : '';
}

function worldMapEmblem(zone,x,y,major,ranges) {
  const color=worldMapMode==='owner'?worldMapOwnerColor(zone):worldMapFill(zone,ranges);
  return '<g class="world-map-emblem" transform="translate('+x.toFixed(1)+' '+y.toFixed(1)+')">'+
    '<circle class="world-map-halo" r="'+(major?17:12)+'"/>'+
    (major?'<path class="world-map-pin" fill="'+color+'" d="M0 -9L9 0L0 9L-9 0Z"/>':
      '<circle class="world-map-pin" fill="'+color+'" r="5.5"/>')+
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
  const plate=WORLD_MAP_PLATES[leagueTier];
  const positions=worldMapPositions(sites);
  const ranges={income:worldMapRange(sites,'weekly_net'),power:worldMapRange(sites,'defense_power')};
  const provinces=positions.map(point=>{
    const site=point.site;
    const status=worldMapStatus(site);
    const selectedClass=site.id===worldMapSelectedId?' selected':'';
    const label=site.name+' · '+site.owner_name+' · 수비 '+powerLabel(site.defense_power)+' · 주간 순수입 '+money(site.weekly_net);
    return '<g class="world-map-node '+status+selectedClass+(point.major?' major':'')+'" data-world-zone="'+site.id+'" role="button" tabindex="0" aria-pressed="'+
      (site.id===worldMapSelectedId)+'" aria-label="'+escapeText(label)+'">'+
      '<title>'+escapeText(label)+'</title>'+
      '<path class="world-map-province" fill="'+worldMapFill(site,ranges)+'" d="'+worldMapProvincePath(point,positions)+'"/>'+
      worldMapEmblem(site,point.x,point.y,point.major,ranges)+
      '<text class="world-map-site-name" x="'+point.x.toFixed(1)+'" y="'+(point.y+25).toFixed(1)+'">'+escapeText(worldMapBriefName(site.name))+'</text>'+
      '<text class="world-map-site-sub" x="'+point.x.toFixed(1)+'" y="'+(point.y+43).toFixed(1)+'">'+escapeText(worldMapLabel(site))+'</text>'+
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
    '<div class="world-map-head"><h3>패권지도 · '+leagueTier+'부</h3>'+
    '<div class="world-map-counts"><span><small>내 문파 거점</small><b>'+owned.length+'곳</b></span>'+
    '<span><small>경쟁 세력 거점</small><b>'+rivals+'곳</b></span>'+
    '<span><small>무주지</small><b>'+neutral+'곳</b></span>'+
    '<span class="world-map-income-summary"><small>내 거점 주간 순수익</small><b>'+money(weeklyIncome)+'</b></span></div></div>'+
    '<div class="world-map-toolbar"><span class="world-map-toolbar-label">지도 표시</span>'+
    '<div class="world-map-mode-group" role="group" aria-label="패권 지도 표시 모드">'+modes+'</div>'+
    '<button type="button" class="world-map-names" data-world-map-names aria-pressed="'+worldMapAllNames+'">전체 지명</button></div>'+
    '<div class="world-map-layout"><div class="world-map-canvas">'+
    '<div class="world-map-mapframe"><svg class="world-map-svg mode-'+worldMapMode+(worldMapAllNames?' show-names':'')+'" viewBox="0 0 1100 734" role="group" aria-label="'+leagueTier+'부 패권지도">'+
    '<image class="world-map-art" href="assets/maps/'+plate.file+'.webp" width="1100" height="734" preserveAspectRatio="none" aria-hidden="true"/>'+
    '<g class="world-map-provinces">'+provinces+'</g>'+
    '</svg></div>'+
    '<div class="world-map-legend">'+legend+'</div>'+
    '<p class="world-map-footnote">배경 지형은 권역의 분위기를 표현합니다. 거점의 실제 전장 지형은 상세에서 확인할 수 있습니다.</p>'+
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
      if(item.tagName.toLowerCase()==='g') item.classList.toggle('selected',active);
      else item.closest('tr')?.classList.toggle('world-map-row-selected',active);
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
  root.querySelector('[data-world-map-names]')?.addEventListener('click',event=>{
    worldMapAllNames=!worldMapAllNames;
    event.currentTarget.setAttribute('aria-pressed',String(worldMapAllNames));
    root.querySelector('.world-map-svg')?.classList.toggle('show-names',worldMapAllNames);
  });
  root.querySelectorAll('[data-world-map-mode]').forEach(button=>{
    if (!button.dataset.worldMapMode) return;
    button.addEventListener('click',()=>{
      if (!WORLD_MAP_MODES[button.dataset.worldMapMode]||worldMapMode===button.dataset.worldMapMode) return;
      worldMapMode=button.dataset.worldMapMode;
      const scrollLeft=root.querySelector('.world-map-mapframe')?.scrollLeft??0;
      root.outerHTML=renderWorldMap();
      bindWorldMap();
      const frame=panel().querySelector('.world-map-mapframe');
      if(frame) frame.scrollLeft=scrollLeft;
      panel().querySelector('[data-world-map-mode="'+worldMapMode+'"]')?.focus({preventScroll:true});
    });
  });
  bindDetails();
}
