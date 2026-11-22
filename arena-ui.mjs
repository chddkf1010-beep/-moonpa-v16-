import { Arena, isGroup } from './group-engine.mjs?v=contested1-bench1';
import { eligibleBench, replaceDeployed, combatantStats } from './arena-bench.mjs?v=bench-details1';
import { waitingMembers, moveAssignment } from './arena-assign.mjs?v=dual-deployment1';
import { finishGroupBattleNow } from './arena-skip.mjs?v=battle-skip1';
import { buildBattleReport, renderBattleReport } from './battle-report.mjs?v=battlereport-1';
const el=id=>document.getElementById(id);
const {terrains,roles,skills,roster,arts,baseArts,sects,playerPresets,foesPresets}=Arena;
let campaign=null;
let tacticDirty=false,tacticSavePending=false;
const practiceTactics=()=>campaign?.kind==='training';
const touchTactics=()=>{if(practiceTactics()){
  tacticDirty=true;
  el('tactics-save-status').textContent='저장하지 않은 전술 변경 사항이 있습니다.';
}};
let playerPreset='hold', opponent='tang', logFilter='major';
let terrain='field', mode=8, lineup=Arena.place(Arena.playerTeam(playerPreset),terrains[terrain]);
let captain=0,deputy=2,loadout=['arrow','curse','mend'],speed=1,game=null,recent=null,selected=null;
let swapTarget=null,pendingBench=null;
let defenseLineup=[],pendingTransfer=null,formationDirty=false,formationPending=false,startAfterSave=false;
const dualMode=()=>Boolean(campaign&&!campaign.observer&&
  campaign.team?.every(member=>member.id>0)&&
  ['territory','conquest_duel','defense'].includes(campaign.kind));
const dualAttack=()=>dualMode()&&campaign.kind!=='defense';
const waiting=()=>dualMode()?waitingMembers(campaign,lineup,defenseLineup):
  eligibleBench(campaign,lineup);
let chosenArts=[...baseArts];
let elapsed=0,last=0,enemyAt=0,shownLogs=-1,visualTime=0;
const canvas=el('field'),ctx=canvas.getContext('2d');
const html=value=>String(value).replace(/[&<>"']/g,char=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const clock=t=>String(Math.floor(t/60)).padStart(2,'0')+':'+String(Math.floor(t%60)).padStart(2,'0');
const artColors={attack:'#ff9d78',defense:'#9dccff',heal:'#a8efaf',control:'#d6b0ff',formation:'#9ee8eb'};
const artKinds={attack:'공격',defense:'방어',heal:'회복',control:'제어',formation:'진형'};
let seenArts=0,cutins=[],slowUntil=0,wallClock=0;
function resetArts(){
  seenArts=0;cutins=[];slowUntil=0;
  el('art-cutins').replaceChildren();
  el('art-cutins').classList.remove('flash');
}
function artPicker(){
  const enemy=campaign?{name:campaign.sectNames[1],arts:campaign.enemyArts}:foesPresets[opponent];
  el('kit').innerHTML='<h3>문파 무공 · 2종</h3><small>조건이 맞으면 각각 전투당 1회 자동 발동</small>'+
    '<div class="art-picks">'+chosenArts.map((key,i)=>{
      const a=arts[key];
      return '<div class="art-choice art-'+a.kind+'"><select aria-label="문파 무공 '+(i+1)+'" data-art="'+i+'">'+
        Object.entries(arts).map(([k,d])=>'<option value="'+k+'" '+(k===key?'selected':'')+'>'+
          artKinds[d.kind]+' · '+d.name+'</option>').join('')+'</select><small>'+a.trigger+'</small><p>'+a.detail+'</p></div>';
    }).join('')+'</div><details class="enemy-arts"><summary>상대 ' + html(enemy.name) + ' 고정 무공 · '+enemy.arts.map(k=>arts[k].name).join(' / ')+'</summary>'+
    enemy.arts.map(k=>'<p class="art-'+arts[k].kind+'"><b>'+arts[k].name+'</b> · '+arts[k].trigger+' · '+arts[k].detail+'</p>').join('')+'</details>';
  el('kit').querySelectorAll('[data-art]').forEach(select=>select.onchange=()=>{
    const i=Number(select.dataset.art),other=chosenArts.indexOf(select.value);
    if(other!==-1)chosenArts[other]=chosenArts[i];
    chosenArts[i]=select.value;touchTactics();setup();ready();
    el('kit').querySelector('[data-art="'+i+'"]')?.focus();
  });
}
function readArtEvents(now){
  if(game.artEvents.length===seenArts)return;
  const newEvents=game.artEvents.slice(seenArts);
  seenArts=game.artEvents.length;
  slowUntil=now+400;
  for(const event of newEvents)cutins.push({event,at:now});
}
function renderCutins(now){
  cutins=cutins.filter(entry=>now-entry.at<800);
  const layer=el('art-cutins');
  layer.classList.toggle('flash',cutins.length>0);
  for(let side=0;side<2;side++){
    const current=cutins.filter(e=>e.event.side===side);
    let box=layer.querySelector('[data-side="'+side+'"]');
    if(!current.length){box?.remove();continue;}
    const key=current.map(e=>e.event.key).join(',');
    if(box?.dataset.key===key)continue;
    if(!box){box=document.createElement('div');box.dataset.side=side;layer.append(box);}
    box.className='cutin '+(side?'foe':'friend');
    box.dataset.key=key;
    box.innerHTML=current.map(({event})=>'<span class="art-'+event.kind+'"><small>' + html(event.sect) + ' 비기</small> '+event.name+'</span>').join('');
  }
}
function artEffects(now){
  if(!game?.artEvents.length)return;
  for(const event of game.artEvents){
    if(game.time-event.time>event.duration)continue;
    const instant=cutins.find(e=>e.event===event);
    const phase=instant?Math.min(1,(now-instant.at)/800):1;
    const color=artColors[event.kind];
    const live=game.units.filter(u=>event.ids.includes(u.id)&&u.hp>0);
    ctx.save();
    for(const u of live){
      ctx.globalAlpha=.46;
      ctx.setLineDash(event.kind==='control'?[4,4]:[]);
      circle(u.x,u.y+8,19,color,false,2);
      ctx.setLineDash([]);
    }
    if(phase<1){
      ctx.globalAlpha=.72*(1-phase);
      for(const [i,{x,y}] of event.points.entries()){
        if(event.key==='tiger'){
          const dir=event.side?-1:1, sweep=x-dir*(1-phase)*96;
          for(let j=-2;j<=2;j++)stroke(sweep-dir*27,y+j*10,sweep+dir*26,y+j*4,color,4);
          for(let j=0;j<5;j++)stroke(x,y,x+dir*(10+j*4)*phase,y+(j-2)*22*phase,'#fff0ae',2);
        }else if(event.key==='wall'){
          const line=event.side?655:245;
          ctx.fillStyle='#6cbbff';ctx.globalAlpha=.22*(1-phase);ctx.fillRect(line-8,y-36,16,72);
          ctx.globalAlpha=.7*(1-phase);stroke(line,y-42,line,y+42,color,4);
        }else if(event.key==='silence'){
          const impact=y-55+phase*58;
          circle(x,impact,19,color,false,3);
          stroke(x-14,impact-7,x+12,impact+10,'#e1c7ff',3);
          stroke(x-10,impact+11,x+14,impact-6,'#e1c7ff',3);
        }else if(event.kind==='attack'){
          for(let j=0;j<7;j++){
            const offset=j*8-24, q=Math.min(1,phase*1.95+j*.035);
            const tx=x+offset-(1-q)*58,ty=y-(1-q)*128+(i%2)*4;
            stroke(tx-20,ty-38,tx,ty,j%2?color:'#d8a6fb',2.5);
          }
          if(phase>.45)circle(x,y,7+(phase-.45)*54,color,false,2.5);
        }else if(event.kind==='defense'){
          circle(x,y,15+phase*33,color,false,3);
          ctx.beginPath();ctx.arc(x,y,23+phase*20,Math.PI,Math.PI*2);ctx.lineWidth=4;
          ctx.strokeStyle=color;ctx.stroke();
        }else if(event.kind==='heal'){
          circle(x,y,11+phase*35,color,false,2);
          for(let j=0;j<6;j++)circle(x+Math.sin(j*3.4)*18,y+5-phase*(33+j*5),2,color,true);
        }else if(event.kind==='control'){
          for(let j=0;j<6;j++){
            const a=j*Math.PI/3;
            stroke(x,y,x+Math.cos(a)*30,y+Math.sin(a)*25,color,2);
          }
          circle(x,y,18+phase*20,color,false,2);
        }else{
          const dx=event.side?-1:1, length=24+37*phase;
          const rise=event.key==='wing'?(y<215?-32:32):0;
          const toward=event.key==='withdraw'?-dx:dx;
          const tx=x+length*toward,ty=y+rise;
          stroke(x,y,tx,ty,color,4);
          stroke(tx,ty,tx-toward*13,ty-9,color,4);
          stroke(tx,ty,tx-toward*13,ty+9,color,4);
        }
      }
    }
    ctx.restore();
  }
}

const ready=()=>{hideBattleReport();game=null;elapsed=0;shownLogs=-1;resetArts();refresh();};
function updateLeadership(previous=null){
  const view=Arena.leadershipPreview({team:lineup.slice(0,mode),mode,captain,deputy,
    scenario:el('scenario').value,loadout,chosenArts});
  const chips=u=>'<strong>'+html(u.name)+'</strong><small>'+(u.line==='front'?'전열':'후열')+
    ' · '+u.role+' · HP '+u.hp+'</small>';
  const links=u=>u.artLinks.length?'<ul class="command-links">'+u.artLinks.map(art=>
    '<li><b>'+art.name+'</b> · '+art.trigger+'</li>').join('')+'</ul>':'';
  const chief=view.captain,vice=view.deputy;
  const block=el('lead-note');
  if(!chief){block.textContent='출전 가능한 문파원이 없습니다.';return view;}
  block.innerHTML='<article><h3>대장</h3>'+chips(chief)+
    (chief.startingShield?'<p>본인에게 시작 보호막 <b>'+chief.startingShield+'</b></p>':'')+
    '<p>이탈 시 아군 공격력 <b>−'+chief.moraleLoss+'%</b></p>'+links(chief)+'</article>'+
    (vice?'<article><h3>부대장</h3>'+chips(vice)+
      (vice.deputyShield?'<p>생존 중 첫 전열 붕괴 시 후열 보호막 <b>'+vice.deputyShield+'</b></p>':'')+
      (vice.healed?'<p>직접 치유 <b>'+vice.healed[0]+' → '+vice.healed[1]+'</b> (기본 회복량)</p>':
        '<p>직접 치유 무공 없음</p>')+links(vice)+'</article>':'');
  const parts=[];
  if(previous?.captain&&chief&&previous.captain.name!==chief.name)
    parts.push('대장 '+previous.captain.name+' → '+chief.name+
      ' · HP '+previous.captain.hp+' → '+chief.hp+(chief.startingShield?' · 시작 보호막 대상 변경':''));
  if(previous&&previous.deputy&&vice&&previous.deputy.name!==vice.name){
    const healing=vice.healed!==null;
    const priorHealing=previous.deputy.healed!==null;
    parts.push('부대장 '+previous.deputy.name+' → '+vice.name+
      ' · HP '+previous.deputy.hp+' → '+vice.hp+
      (healing!==priorHealing?(healing?' · 직접 치유 보너스 활성':' · 직접 치유 보너스 해제'):''));
  }
  el('lead-diff').textContent=parts.join(' / ');
  return view;
}
function swapPlacement(first,second){
  [first.line,second.line]=[second.line,first.line];
  [first.slot,second.slot]=[second.slot,first.slot];
  [first.position,second.position]=[second.position,first.position];
}

function finishPlacement(message=''){
  if(dualMode())formationDirty=true;
  touchTactics();
  selected=null;
  setup();
  el('deployment-status').textContent=message;
}

function selectPlacement(member){
  const previous=lineup.find(f=>f.id===selected);
  if(previous&&previous!==member){
    swapPlacement(previous,member);
    finishPlacement(previous.name+' ↔ '+member.name+' 자리 교대');
  }else{
    selected=previous?null:member.id;
    setup();
    el('deployment-status').textContent=selected===null?'':member.name+' 선택됨';
  }
}

function deployOnMap(point){
  const member=lineup.find(f=>f.id===selected);
  if(!member)return;
  if(!Arena.canDeploy(terrain,point.x,point.y)){
    el('deployment-status').textContent='아군 쪽의 통과 가능한 땅을 선택하세요.';
    return;
  }
  const occupant=mapMember(point,member.id);
  if(occupant){
    selectPlacement(occupant);
    return;
  }
  member.position=point;
  finishPlacement(member.name+' 배치 완료');
}

function mapMember(point,skip){
  const battlefield=Arena.battlefield(terrain,mode);
  return lineup.filter(member=>member.id!==skip).map(member=>({
    member,...Arena.deployPoint(member,battlefield)
  })).sort((a,b)=>b.y-a.y).find(({x,y})=>
    Math.abs(point.x-x)<=21&&point.y>=y-42&&point.y<=y+12)?.member;
}

function canvasPoint(event){
  const area=canvas.getBoundingClientRect();
  return {
    x:Math.round((event.clientX-area.left)*canvas.width/area.width),
    y:Math.round((event.clientY-area.top)*canvas.height/area.height)
  };
}

let drag=null;
canvas.addEventListener('pointerdown',event=>{
  if(game||!isGroup(mode)||event.button!==0)return;
  const point=canvasPoint(event);
  const member=mapMember(point);
  drag={id:event.pointerId,origin:point,point,member,moved:false};
  canvas.setPointerCapture(event.pointerId);
});
canvas.addEventListener('pointermove',event=>{
  if(drag?.id!==event.pointerId)return;
  drag.point=canvasPoint(event);
  if(drag.member&&Math.hypot(drag.origin.x-drag.point.x,drag.origin.y-drag.point.y)>7)
    drag.moved=true;
});
canvas.addEventListener('pointerup',event=>{
  if(drag?.id!==event.pointerId)return;
  const {member,moved}=drag;
  drag=null;
  if(game)return;
  if(member&&moved){
    selected=member.id;
    setup();
    deployOnMap(canvasPoint(event));
  }else if(member)selectPlacement(member);
  else deployOnMap(canvasPoint(event));
});
canvas.addEventListener('lostpointercapture',()=>{drag=null;});

const statLabels={strength:'근력',defense:'방어',stamina:'체력',agility:'민첩',
  inner_power:'내공',sorcery:'술법',insight:'통찰',willpower:'정신력'};
function fighterInfo(member) {
  const profile=combatantStats(member);
  const modal=el('fighter-stats-dialog');
  if(!modal)return;
  const chosen=campaign && lineup.some(f=>f.id===member.id);
  const isReserve=campaign && waiting().some(f=>f.id===member.id);
  const isDefender=dualAttack()&&defenseLineup.some(f=>f.id===member.id);
  const rarity=profile.notable?.rarity==='legend'?'전설':profile.notable?.rarity==='named'?'네임드':'';
  const bars=Object.entries(profile.attrs).map(([key,value])=>
    '<div class="fighter-stat"><span>'+html(statLabels[key]||key)+'</span>'+
    '<b>'+Number(value).toFixed(1)+'</b><i style="width:'+Math.max(0,Math.min(100,Number(value)/2))+'%"></i></div>').join('');
  el('fighter-stats-content').innerHTML=
    '<div class="fighter-stats-head"><div class="fighter-stats-art"><img src="'+cardArtwork[member.role]+'" alt=""></div>'+
      '<div><small>'+html(roles[member.role]?.name||member.role)+' · '+(profile.level==null?'모의전':'Lv '+profile.level)+'</small>'+
      '<h2>'+html(profile.name)+'</h2>'+(rarity?'<p>'+rarity+' · '+html(profile.notable.title||'')+'</p>':'')+
      (practiceTactics()&&member.reason?'<p class="arena-injury-warning">'+html(member.reason)+
        (member.injured?' '+member.injured+'주':'')+' · 편성 가능 / 실전 출전 불가</p>':'')+
      (profile.ca!=null?'<div class="fighter-stat-power"><strong>현재 전력 '+Number(profile.ca).toFixed(1)+'</strong>'+
      '<strong>잠재력 '+Number(profile.pa).toFixed(1)+'</strong></div>':'')+
      '</div></div>'+
    (bars?'<h3>실제 능력치</h3><div class="fighter-stat-grid">'+bars+'</div>':
      '<p>독립 연무장에서는 상세 성장 능력치를 제공하지 않습니다.</p>')+
    (profile.wage!=null?'<p class="fighter-stats-contract">주급 '+Number(profile.wage).toLocaleString('ko-KR')+
      '냥 · 계약 '+profile.contractEnd+'시즌 만료</p>':'')+
    '<div class="fighter-stats-actions">'+(chosen?'<button type="button" data-stats-action="outgoing" data-stats-id="'+member.id+'">교체할 출전 인원으로 선택</button>':'')+
      (isReserve?'<button type="button" class="stats-primary" data-stats-action="incoming" data-stats-id="'+member.id+'">이 문파원 투입</button>':'')+
      (isDefender?'<button type="button" data-stats-action="defender" data-stats-id="'+member.id+'">점령대로 이동</button>':'')+
      '<button type="button" data-stats-close>닫기</button></div>';
  modal.showModal();
}
function changeRoster(next,message) {
  lineup=next.attack;
  defenseLineup=next.defense;
  selected=null;swapTarget=null;pendingBench=null;pendingTransfer=null;
  formationDirty=true;
  if(game)ready();
  setup();ready();
  el('deployment-status').textContent=message+' · 배치 저장 전입니다.';
}
function moveMember(id,to,replaceId=null) {
  if(!dualMode()||game||formationPending)return;
  try {
    const next=moveAssignment(campaign,lineup,defenseLineup,id,to,Arena.battlefield(terrain,mode),replaceId);
    const person=[...lineup,...defenseLineup,...waiting()].find(u=>u.id===id);
    changeRoster(next,(person?.name||'문파원')+' → '+(to==='defense'?'방어대':to==='attack'?campaign.kind==='defense'?'수비대':'점령대':'대기'));
  }catch(e){
    if(e.message.includes('가득 찼습니다')&&replaceId===null){
      pendingTransfer={id,to};
      setup();
      el('deployment-status').textContent=e.message;
    } else el('deployment-status').textContent=e.message;
  }
}
function saveRosters(thenStart=false) {
  if(!dualMode()||formationPending)return;
  if(lineup.length!==campaign.team.length){
    el('warning').textContent='현재 출전대 '+lineup.length+'/'+campaign.team.length+'명 · 출전 인원을 채운 뒤 저장하세요.';
    el('start').scrollIntoView({block:'nearest'});return;
  }
  if(!lineup.some(u=>u.line==='front')){
    el('warning').textContent='전열에 최소 한 명은 필요합니다.';return;
  }
  formationPending=true;startAfterSave=thenStart;
  el('warning').textContent='점령대·방어대 배치 저장 중…';
  setup();
  window.parent.postMessage({type:'moonpa-group-assign',match:campaign.match,
    team:lineup.map(({id,line,slot,position})=>({
      id,line,slot,...(position==null?{}:{position})})),
    defense:dualAttack()?defenseLineup.map(u=>u.id):[],
    captain,deputy},location.origin);
}
function receiveAssignment(data) {
  formationPending=false;
  if(data.error){
    startAfterSave=false;
    el('warning').textContent='배치 저장 실패: '+data.error;
    setup();return;
  }
  campaign=data.config;
  lineup=campaign.team.map(u=>({...u}));
  defenseLineup=(campaign.defenseTeam||[]).map(u=>({...u}));
  formationDirty=false;pendingTransfer=null;
  setup();ready();
  el('warning').textContent='';
  el('deployment-status').textContent='점령대·방어대 편성이 게임 저장 데이터에 반영됐습니다.';
  if(startAfterSave){startAfterSave=false;start(battleConfig());}
}

function swapBench(incomingId,outgoingId) {
  if(!campaign||game)return;
  try {
    const outgoing=lineup.find(f=>f.id===outgoingId);
    const incoming=waiting().find(f=>f.id===incomingId);
    if(dualMode()){
      changeRoster(moveAssignment(campaign,lineup,defenseLineup,incomingId,'attack',
        Arena.battlefield(terrain,mode),outgoingId),
        outgoing.name+' → '+incoming.name+' 교체');
      return;
    }
    lineup=replaceDeployed(lineup,campaign,incomingId,outgoingId);
    touchTactics();
    if(captain===outgoingId)captain=incomingId;
    if(deputy===outgoingId)deputy=incomingId;
    selected=null;swapTarget=null;pendingBench=null;
    setup();ready();
    el('deployment-status').textContent=outgoing.name+' → '+incoming.name+' 교체 완료 · 전투 준비';
  }catch(error){el('deployment-status').textContent=error.message;}
}
function selectSwapTarget(id) {
  if(game||!campaign)return;
  if(pendingBench!==null){swapBench(pendingBench,id);return;}
  swapTarget=swapTarget===id?null:id;
  setup();
  el('deployment-status').textContent=swapTarget===null?'교체 대상 선택 취소':
    '교체할 대기 문파원을 선택하세요.';
}
function selectBenchMember(id) {
  if(game||!campaign)return;
  if(swapTarget!==null){swapBench(id,swapTarget);return;}
  pendingBench=pendingBench===id?null:id;
  setup();
  el('deployment-status').textContent=pendingBench===null?'대기 인원 선택 취소':
    '교체할 전열·후열 출전 문파원을 선택하세요.';
}
el('fighter-stats-close').onclick=()=>el('fighter-stats-dialog').close();
el('fighter-stats-dialog').addEventListener('click',event=>{
  if(event.target===el('fighter-stats-dialog'))el('fighter-stats-dialog').close();
  const close=event.target.closest('[data-stats-close]');
  if(close){el('fighter-stats-dialog').close();return;}
  const action=event.target.closest('[data-stats-action]');
  if(!action)return;
  el('fighter-stats-dialog').close();
  if(action.dataset.statsAction==='incoming')selectBenchMember(Number(action.dataset.statsId));
  else if(action.dataset.statsAction==='defender')moveMember(Number(action.dataset.statsId),'attack');
  else selectSwapTarget(Number(action.dataset.statsId));
});

function defenseSquadView() {
  if(!dualMode())return '';
  if(!dualAttack())return '<section class="arena-dual-defense"><h3>방어전 배치</h3><p>현재 방어전이 진행 중입니다. 위의 전열·후열이 수비대이며, 대기 인원을 교체할 수 있습니다.</p></section>';
  const enabled=campaign.defenseEnabled;
  return '<section class="arena-dual-defense"><div class="arena-dual-heading"><h3>방어전 배치 · '+defenseLineup.length+'/8명</h3>'+
    '<small>'+(enabled?'보유 거점 수비 · 점령대와 인원 공유':'보유 거점 없음 · 방어대 비활성')+'</small></div>'+
    (enabled?'<div class="arena-defense-list">'+defenseLineup.map(member=>
       '<article class="arena-defense-member">'+
         '<button type="button" class="arena-defense-portrait" data-dual-info="'+member.id+'" aria-label="'+html(member.name)+' 능력치 보기">'+
           '<img src="'+cardArtwork[member.role]+'" alt=""></button>'+
         '<div class="arena-defense-detail"><strong>'+html(member.name)+'</strong><small>'+
           html(roles[member.role]?.name||member.role)+' · 전력 '+Number(member.ca).toFixed(1)+'</small></div>'+
         '<div class="arena-defense-tools"><button type="button" data-dual-move="'+member.id+'" data-dual-to="attack">점령대로</button>'+
           '<button type="button" data-dual-move="'+member.id+'" data-dual-to="wait">대기로</button>'+
           (pendingTransfer?.to==='defense'?'<button type="button" class="arena-target" data-dual-replace="'+member.id+'">교체 대상</button>':'')+'</div>'+
       '</article>').join('')+'</div>'+
       '<p class="arena-bench-hint">점령대원을 방어대로 옮기면 실제 월간 수비대 명단이 바뀝니다. 방어대가 8명일 때는 교체할 문파원을 선택하세요. 점령대는 전투 시작 전에 8명을 유지해야 합니다.</p>'+
       (defenseLineup.length?'':'<p class="arena-bench-hint">지정 수비대가 없습니다. 현재 방어전은 거점 기본 수비대가 담당합니다.</p>'):
       '<p>거점을 점령하면 방어대를 편성할 수 있습니다.</p>')+
    '</section>';
}

function setup(){
  el('tactics-save-pane').hidden=!practiceTactics();
  el('tactics-save-btn').disabled=!practiceTactics()||Boolean(game)||tacticSavePending;
  if(practiceTactics())el('scenario').disabled=Boolean(game)||tacticSavePending;
  const t=Arena.battlefield(terrain,mode);
  const available=lineup.slice(0,mode);
  el('team-controls').hidden=Boolean(campaign)||!isGroup(mode);
  const format=team=>Object.entries(roles).map(([key,r])=>{
    const count=team.filter(u=>u.role===key).length;
    return count?r.name+' '+count:'';
  }).filter(Boolean).join(' · ');
  if(isGroup(mode)){
    el('matchup-info').textContent=(campaign?.sectNames[0]??'청운문')+' '+format(available)+' / '+(campaign?.sectNames[1]??foesPresets[opponent].name)+' '+format(campaign?.enemyRoster??Arena.enemyTeam(opponent,t,mode));
  }
  const cap=line=>isGroup(mode)?t[line]:line==='front'?mode:Math.max(0,mode-1);
  if(!available.some(f=>f.id===captain)) captain=available[0]?.id;
  if(deputy===captain||!available.some(f=>f.id===deputy)) deputy=available.find(f=>f.id!==captain)?.id;
  el('terrain-hint').textContent=isGroup(mode)?
    [campaign?.zone!=null?campaign.zoneName??'구역 '+campaign.zone:'', t.name, '전장 폭 '+t.width, '전열 '+t.front+'칸 / 후열 '+t.back+'칸', t.hint].filter(Boolean).join(' · '):'무공과 대상을 선택하는 턴제 대련';
  canvas.style.aspectRatio=(isGroup(mode)?t.width:900)+' / 430';
  el('formation').innerHTML=['front','back'].map(line=>{
    const team=available.filter(u=>u.line===line);
    const slots=Array.from({length:cap(line)},(_,i)=>{
      const u=isGroup(mode)?team.find(f=>f.slot===i):team[i];
      if(!u)return '<button type="button" class="slot empty" data-line="'+line+'" data-slot="'+i+'" '+(!isGroup(mode)?'disabled':'')+'>빈 슬롯 '+(i+1)+'</button>';
      return '<span class="arena-member-tile'+(swapTarget===u.id?' is-swap-target':'')+'">'+
        '<button type="button" class="slot" data-unit="'+u.id+'" aria-pressed="'+(selected===u.id)+'" data-command="'+
        (u.id===captain?'captain':u.id===deputy?'deputy':'member')+'" '+(mode===1?'disabled':'')+'>'+
        '<img src="'+cardArtwork[u.role]+'" alt=""><span><b>'+roles[u.role].name+
        (practiceTactics()&&u.injured?' · 부상 '+u.injured+'주':'')+
        '</b><i class="slot-name"></i></span></button>'+
        (campaign?'<span class="arena-member-actions"><button type="button" data-swap-out="'+u.id+'">교체</button>'+
          '<button type="button" data-select-place="'+u.id+'">자리</button>'+
          (dualAttack()&&campaign.defenseEnabled?'<button type="button" data-dual-move="'+u.id+'" data-dual-to="defense">방어대로</button>':'')+
          (dualMode()?'<button type="button" data-dual-move="'+u.id+'" data-dual-to="wait">대기로</button>':'')+
          (pendingTransfer?.to==='attack'?'<button type="button" class="arena-target" data-dual-replace="'+u.id+'">교체 대상</button>':'')+
          '</span>':'')+'</span>';
    });
    return '<div class="line"><strong class="line-label">'+(line==='front'?'전열':'후열')+' '+team.length+'/'+cap(line)+'</strong>'+slots.join('')+'</div>';
  }).join('')+'<small>초상화: 능력치 확인 · 자리: 진형 변경 · 점령대↔방어대 이동</small>'+
    defenseSquadView()+
    (campaign?'<section class="arena-bench"><div class="arena-bench-heading"><h3>'+
        (practiceTactics()?'전체 문파원 · 전술 후보':'대기 문파원')+'</h3>'+
      '<small>'+(practiceTactics()?
        '전체 '+(campaign.totalRoster??lineup.length+waiting().length)+'명 · 편성 8명 + 후보 '+waiting().length+'명 · 부상·다른 임무 배치도 포함':
        '출전 가능한 대기 인원 '+waiting().length+'명 · 교체할 인원 선택')+'</small></div>'+
      '<div class="arena-bench-grid">'+waiting().map(member=>
        '<article class="arena-bench-card'+(pendingBench===member.id?' is-pending':'')+'">'+
        '<button type="button" class="arena-bench-portrait" data-bench-info="'+member.id+'" aria-label="'+html(member.name)+' 능력치 보기">'+
        '<img src="'+cardArtwork[member.role]+'" alt=""><span>'+html(member.name)+'</span></button>'+
        '<small>'+html(roles[member.role]?.name||member.role)+' · CA '+Number(member.ca).toFixed(1)+
          (practiceTactics()&&member.reason?' · '+html(member.reason)+(member.injured?' '+member.injured+'주':'')+' (실전 제외)':'')+'</small>'+
        (dualMode()?'<div class="arena-bench-direct">'+
          '<button type="button" data-dual-move="'+member.id+'" data-dual-to="attack">'+(campaign.kind==='defense'?'수비대로':'점령대로')+'</button>'+
          (dualAttack()&&campaign.defenseEnabled?'<button type="button" data-dual-move="'+member.id+'" data-dual-to="defense">방어대로</button>':'')+
          '</div>':
          '<button type="button" class="arena-bench-join" data-bench-join="'+member.id+'"'+(game?' disabled':'')+'>투입</button>')+
        '</article>').join('')+'</div>'+
      '<p class="arena-bench-hint">'+(dualMode()?
        '점령대·방어대·대기 중 배치할 곳을 선택하세요. 다른 임무·원정 인원은 제외하며, 소일거리 인원이 전투에 참가하면 해당 보상은 제외됩니다.':
        practiceTactics()?'부상자나 다른 활동에 배치된 문파원도 전술을 짤 수 있습니다. 실제 월간 전투에는 출전 가능한 인원만 참여합니다.':
        '대기 인원의 [투입] 후 출전 인원의 [교체]를 선택하세요.')+'</p>'+
      '<p class="arena-bench-status" role="status">'+(swapTarget!==null?
        html(lineup.find(u=>u.id===swapTarget)?.name||'문파원')+' 교체 대상 선택됨 · 대기 인원의 [투입]을 누르세요.':
        pendingBench!==null?html(campaign.bench?.concat(campaign.team||[]).find(u=>u.id===pendingBench)?.name||'대기 문파원')+' 투입 대기 · 출전 문파원의 [교체]를 누르세요.':
        '출전 문파원의 [교체] 또는 대기 문파원의 [투입]으로 교체를 시작하세요.')+'</p></section>'+
      (dualMode()?'<section class="arena-squad-save"><strong>'+(campaign.kind==='defense'?'수비대':'점령대')+' '+lineup.length+'/'+campaign.team.length+
        '명 · 방어대 '+(dualAttack()?defenseLineup.length:lineup.length)+'/8명</strong>'+
        '<small>'+(formationDirty?'저장 전 변경 사항이 있습니다.':'저장된 월간 배치를 사용 중입니다.')+'</small>'+
        '<button type="button" data-squad-save'+(formationPending||game?' disabled':'')+'>점령대·방어대 배치 저장</button>'+
        (pendingTransfer?'<p role="status">교체할 '+(pendingTransfer.to==='attack'?'점령대원':'방어대원')+'의 [교체 대상]을 누르세요. <button type="button" data-transfer-cancel>취소</button></p>':'')+'</section>':''):'');
  el('formation').querySelectorAll('[data-unit]').forEach(btn=>{
    const unit=available.find(f=>f.id===Number(btn.dataset.unit));
    btn.querySelector('.slot-name').textContent=unit.name;
    btn.onclick=()=>fighterInfo(unit);
  });
  el('formation').querySelectorAll('[data-select-place]').forEach(btn=>btn.onclick=()=>{
    const member=available.find(f=>f.id===Number(btn.dataset.selectPlace));
    if(member && !game)selectPlacement(member);
  });
  el('formation').querySelectorAll('[data-swap-out]').forEach(btn=>btn.onclick=()=>
    selectSwapTarget(Number(btn.dataset.swapOut)));
  el('formation').querySelectorAll('[data-bench-join]').forEach(btn=>btn.onclick=()=>
    selectBenchMember(Number(btn.dataset.benchJoin)));
  el('formation').querySelectorAll('[data-bench-info]').forEach(btn=>btn.onclick=()=>{
    const member=waiting().find(f=>f.id===Number(btn.dataset.benchInfo));
    if(member)fighterInfo(member);
  });
  el('formation').querySelectorAll('[data-dual-move]').forEach(btn=>btn.onclick=()=>
    moveMember(Number(btn.dataset.dualMove),btn.dataset.dualTo));
  el('formation').querySelectorAll('[data-dual-replace]').forEach(btn=>btn.onclick=()=>{
    if(pendingTransfer)moveMember(pendingTransfer.id,pendingTransfer.to,Number(btn.dataset.dualReplace));
  });
  el('formation').querySelectorAll('[data-dual-info]').forEach(btn=>btn.onclick=()=>{
    const member=defenseLineup.find(f=>f.id===Number(btn.dataset.dualInfo));
    if(member)fighterInfo(member);
  });
  const squadSave=el('formation').querySelector('[data-squad-save]');
  if(squadSave)squadSave.onclick=()=>saveRosters();
  const cancelTransfer=el('formation').querySelector('[data-transfer-cancel]');
  if(cancelTransfer)cancelTransfer.onclick=()=>{pendingTransfer=null;setup();};
  el('formation').querySelectorAll('button[data-line]:not(:disabled)').forEach(btn=>btn.onclick=()=>{
    const member=available.find(f=>f.id===selected);
    if(!member)return;
    member.line=btn.dataset.line;
    member.slot=Number(btn.dataset.slot);
    delete member.position;
    if(game)ready();
    finishPlacement(member.name+' 배치 완료');
  });
  el('deployment-jump').hidden=!isGroup(mode);
  for(const [name,value,disabled] of [['captain',captain,false],['deputy',deputy,mode===1]]){
    el(name).replaceChildren(...(disabled?[new Option('해당 없음','')]:available
      .filter(f=>name==='captain'||f.id!==captain).map(f=>new Option(f.name,f.id))));
    el(name).disabled=disabled; if(value!=null)el(name).value=value;
  }
  updateLeadership();
  if(isGroup(mode))artPicker();
  else {
  el('kit').innerHTML='<h3>개인 무공 3종</h3><div class="kit-actions">'+loadout.map((key,i)=>
    '<select aria-label="무공 '+(i+1)+'" data-kit="'+i+'">'+Object.keys(skills).filter(k=>!['taunt','ambush'].includes(k)).map(k=>
      '<option value="'+k+'" '+(k===key?'selected':'')+'>'+skills[k].name+'</option>').join('')+'</select>').join('')+'</div>';
  el('kit').querySelectorAll('select').forEach(select=>{
    select.title=skills[select.value].hint;
    select.onchange=()=>{
      const i=Number(select.dataset.kit),j=loadout.indexOf(select.value);
      if(j>=0)loadout[j]=loadout[i];
      loadout[i]=select.value;setup();ready();
    };
  });
  }
  el('mode-label').textContent=isGroup(mode)?mode+'대'+mode+(mode===10?' 승강전':el('scenario').value==='defense'?' 방어전':' 점령전')+(campaign&&!game?' · 수동 편성':' · 자동 관전'):mode+'대'+mode+' · 직접 지휘';
}
function start(config){
  if(!isGroup(config.mode)&&!config.loadout.some(key=>skills[key].aim==='foe')){el('warning').textContent='공격 무공을 하나 이상 장착하세요.';return;}
  if(config.team.length&&!config.team.some(u=>u.line==='front')){el('warning').textContent='전열에 문파원을 한 명 이상 배치하세요.';return;}
  hideBattleReport();resetArts();recent=config;game=Arena.create(config);elapsed=0;visualTime=0;enemyAt=performance.now()+420;shownLogs=-1;
  el('warning').textContent='';refresh();
  el('status').closest('.scorebar').scrollIntoView({block:'start'});
}
function resetFormation(){
  selected=null;
  el('deployment-status').textContent='';
  lineup=Arena.place((isGroup(mode)?Arena.playerTeam(playerPreset,mode):roster).slice(0,mode),isGroup(mode)?Arena.battlefield(terrain,mode):{front:Math.ceil(mode/2)});
  setup();ready();
}
el('terrain').replaceChildren(...Object.entries(terrains).map(([k,t])=>new Option(t.name,k)));
el('player-preset').replaceChildren(...Object.entries(playerPresets).map(([k,p])=>new Option(p.name,k)));
el('player-preset').value=playerPreset;
el('player-preset').onchange=e=>{playerPreset=e.target.value;resetFormation();};
el('opponent').replaceChildren(...Object.entries(foesPresets).map(([k,p])=>new Option(p.name,k)));
el('opponent').value=opponent;
el('opponent').onchange=e=>{opponent=e.target.value;setup();ready();};
el('log-filter').onchange=e=>{logFilter=e.target.value;shownLogs=-1;refresh();};
el('terrain').onchange=e=>{terrain=e.target.value;resetFormation();};
el('scenario').onchange=()=>{
  if(!practiceTactics()){setup();ready();return;}
  const next=el('scenario').value;
  if(next===campaign.planMode)return;
  if(game||tacticSavePending){
    el('scenario').value=campaign.planMode;return;
  }
  if(tacticDirty&&!confirm('현재 전술에 저장하지 않은 변경 사항이 있습니다. 다른 전술로 전환하시겠습니까?')){
    el('scenario').value=campaign.planMode;return;
  }
  el('scenario').disabled=true;
  el('tactics-save-status').textContent=(next==='defense'?'방어전':'점령전')+' 전술을 불러오는 중…';
  window.parent.postMessage({type:'moonpa-arena-plan-switch',mode:next},location.origin);
};
el('captain').onchange=e=>{
  if(dualMode())formationDirty=true;
  touchTactics();
  const before=updateLeadership();
  const next=Number(e.target.value);
  if(next===deputy)deputy=captain;
  captain=next;
  setup();updateLeadership(before);ready();el('captain').focus();
};
el('deputy').onchange=e=>{
  if(dualMode())formationDirty=true;
  touchTactics();
  const before=updateLeadership();
  deputy=Number(e.target.value);
  setup();updateLeadership(before);ready();el('deputy').focus();
};
const battleConfig = () => ({...campaign,team:lineup.slice(0,mode).map(f=>({...f})), terrain,mode,captain,deputy,
  scenario:el('scenario').value,opponent,loadout:[...loadout],chosenArts:[...chosenArts]});
el('tactics-save-btn').onclick=()=>{
  if(!practiceTactics()||tacticSavePending||game)return;
  if(lineup.length!==8||new Set(lineup.map(m=>m.id)).size!==8){
    el('tactics-save-status').textContent='실제 문파원 8명을 중복 없이 편성하세요.';return;
  }
  if(!lineup.some(member=>member.id===captain)||!lineup.some(member=>member.id===deputy)||captain===deputy){
    el('tactics-save-status').textContent='서로 다른 출전 문파원을 대장과 부대장으로 지정하세요.';return;
  }
  tacticSavePending=true;
  el('tactics-save-btn').disabled=true;
  el('tactics-save-status').textContent='실제 문파 전술을 게임 세이브에 저장 중…';
  window.parent.postMessage({type:'moonpa-arena-plan-save',mode:campaign.planMode,
    zone_id:campaign.zone,captain,deputy,chosenArts:[...chosenArts],
    team:lineup.map(({id,line,slot,position})=>({
      id,line,slot,...(position?{position}:{} )}))},location.origin);
};
el('tactics-return').onclick=()=>{
  if(tacticDirty&&!confirm('저장하지 않은 연무장 전술 변경 사항이 있습니다. 편성실로 돌아가시겠습니까?'))return;
  window.parent.postMessage({type:'moonpa-arena-plan-back'},location.origin);
};
el('start').onclick=()=>{
  if(dualMode()){
    if(formationPending)return;
    if(formationDirty){saveRosters(true);return;}
    if(lineup.length!==campaign.team.length){el('warning').textContent='현재 출전 인원을 모두 편성하세요.';return;}
  }
  start(battleConfig());
};
el('deployment-jump').onclick=()=>{
  if(game)ready();
  canvas.scrollIntoView({block:'center'});
};
el('edit').onclick=()=>{ready();el('prep-title').scrollIntoView({block:'nearest'});};
el('replay').onclick=()=>{if(recent)start(recent);};
document.querySelectorAll('[data-speed]').forEach(btn=>btn.onclick=()=>{
  speed=Number(btn.dataset.speed);
  document.querySelectorAll('[data-speed]').forEach(b=>b.setAttribute('aria-pressed',b===btn));
});
el('battle-skip').onclick=()=>{
  if(!campaign || !game || game.finished || !isGroup(game.mode))return;
  el('battle-skip').disabled=true;
  // Tick the same running simulation to the end; no reroll or fake outcome.
  // The existing result dialog still requires confirmation before settlement.
  finishGroupBattleNow(game,Arena);
  elapsed=0;
  visualTime=game.time;
  shownLogs=-1;
  refresh();
};
document.querySelectorAll('[data-mode]').forEach(btn=>btn.onclick=()=>{
  mode=Number(btn.dataset.mode);recent=null;
  document.querySelectorAll('[data-mode]').forEach(b=>b.setAttribute('aria-pressed',b===btn));
  resetFormation();
});
let shownResult=null;

let battleReport=null,reportSide=0,reportSort='score',reportReturnFocus=null;
function hideBattleReport(){
  const overlay=el('battle-report-overlay');
  if(!overlay || overlay.hidden)return;
  overlay.hidden=true;
  const focus=reportReturnFocus;
  reportReturnFocus=null;
  if(focus?.isConnected)focus.focus();
}
function confirmCampaignResult(){
  if(!campaign||practiceTactics()||!game?.finished)return;
  const sidebar=el('result-continue'),modal=el('br-confirm');
  if(sidebar?.disabled || modal?.disabled)return;
  if(sidebar)sidebar.disabled=true;
  if(modal)modal.disabled=true;
  window.parent.postMessage({type:'moonpa-group-finish',match:campaign.match,
    lineup:recent.team.map(({id,line,slot,position})=>({id,line,slot,position})),
    captain:recent.captain,deputy:recent.deputy??null,
    arts:recent.chosenArts},location.origin);
}
function renderBattleReportDialog(){
  if(!battleReport)return;
  const root=el('br-content');
  root.innerHTML=renderBattleReport(battleReport,reportSide,reportSort);
  root.querySelectorAll('[data-br-side]').forEach(btn=>btn.onclick=()=>{
    reportSide=Number(btn.dataset.brSide);
    renderBattleReportDialog();
  });
  root.querySelectorAll('[data-br-sort]').forEach(btn=>btn.onclick=()=>{
    reportSort=btn.dataset.brSort;
    renderBattleReportDialog();
  });
}
function openBattleReport(){
  if(!battleReport)return;
  const overlay=el('battle-report-overlay');
  if(overlay.hidden)reportReturnFocus=document.activeElement;
  renderBattleReportDialog();
  overlay.hidden=false;
  const actions=el('br-actions');
  if(campaign&&!practiceTactics()){
    actions.innerHTML='<button type="button" class="br-primary" id="br-confirm">계속 →</button>';
    el('br-confirm').onclick=confirmCampaignResult;
  }else{
    actions.innerHTML='<button type="button" id="br-repeat">같은 편성으로 재전투</button>'+
      '<button type="button" class="br-primary" id="br-reform">편성으로 돌아가기</button>';
    el('br-repeat').onclick=()=>start(recent);
    el('br-reform').onclick=()=>{hideBattleReport();ready();el('start').focus();};
  }
  el('br-close').focus();
}
el('br-close').onclick=hideBattleReport;
el('br-field').onclick=hideBattleReport;
el('battle-report-overlay').addEventListener('keydown',event=>{
  if(event.key==='Escape'){
    event.preventDefault();
    hideBattleReport();
    return;
  }
  if(event.key!=='Tab')return;
  const focusable=[...el('battle-report-overlay').querySelectorAll('button:not(:disabled)')];
  if(!focusable.length)return;
  const current=focusable.indexOf(document.activeElement);
  if(event.shiftKey&&(current<=0)){event.preventDefault();focusable.at(-1).focus();}
  else if(!event.shiftKey&&current===focusable.length-1){event.preventDefault();focusable[0].focus();}
});

function refresh(){
  const positioning=isGroup(mode)&&!game;
  el('deployment-help').hidden=!positioning;
  canvas.classList.toggle('deployment',positioning);
  const units=game?.units||[];
  const count=side=>units.filter(u=>u.side===side&&u.hp>0).length;
  el('ally-name').textContent=game?.sectNames[0]??campaign?.sectNames[0]??'청운문';
  el('enemy-name').textContent=game?.sectNames[1]??campaign?.sectNames[1]??(isGroup(mode)?foesPresets[opponent].name:'적련회');
  el('left-score').textContent=(game?count(0):lineup.length)+' / '+mode+'명';
  el('right-score').textContent=(game?count(1):campaign?.enemyRoster.length??mode)+' / '+mode+'명';
  el('clock').textContent=game&&!isGroup(game.mode)?'R '+Math.min(20,game.round):clock(game?.time||0);
  el('status').textContent=game?.finished?'전투 종료':game?(isGroup(game.mode)?(game.mode===10?'승강전 진행':game.scenario==='attack'?'점령전 진행':'방어전 진행'):'비무 진행'):'편성 대기';
  el('live').textContent=game?.finished?'종료':game?'진행 중':'대기';
  const skipButton=el('battle-skip');
  if(skipButton){
    skipButton.hidden=!campaign || !game || game.finished || !isGroup(game.mode);
    skipButton.disabled=!game || game.finished;
  }
  const length=game?.log.length||0;
  if(shownLogs!==length){
    shownLogs=length;
    const rows=game?.log.filter(row=>!isGroup(game.mode)||logFilter==='all'||(logFilter==='personal'?
      row.type==='personal'||row.type==='skill':row.type!=='personal'))||[];
    el('log').innerHTML=rows.length?rows.slice(-60).reverse().map(row=>
      '<p class="'+row.type+'"><time>'+(isGroup(game.mode)?clock(row.time):'R'+row.round)+'</time>' + html(row.text) + '</p>').join(''):
      game?'<p>선택한 기록이 아직 없습니다.</p>':'<p>전투가 시작되면 핵심 사건이 기록됩니다.</p>';
  }
  el('result').hidden=!game?.finished;
  if(game?.finished&&shownResult!==game){
    shownResult=game;
    const events=game.milestones.filter(row=>row.type!=='result'
      && (game.winner===-1||row.side===1-game.winner)).slice(0,4).sort((a,b)=>a.time-b.time);
    const totals=isGroup(game.mode)?[0,1].map(side=>{
      const names=Object.entries(game.skillCounts[side]).sort((a,b)=>b[1]-a[1]).slice(0,3)
        .map(([key,n])=>skills[key].name+' '+n+'회');
      return '<p><b>'+html(game.sectNames[side])+'</b> · 생존 '+count(side)+'명 · 도발 '+game.taunts[side]+'회 · 후열 타격 '+game.rearStrikes[side]+'회'+
        (names.length?'<br><small>'+names.join(' · ')+'</small>':'')+'</p>';
    }).join(''):'';
    el('result').innerHTML='<h3>'+(game.winner===-1?'무승부':html(game.sectNames[game.winner])+' 승리')+'</h3>'+
      '<p>'+html(game.reason)+'</p>'+totals+events.map(row=>'<p>'+clock(row.time)+' · ' + html(row.text) + '</p>').join('')+
      (isGroup(game.mode)?'<button type="button" id="result-show-report">전투 성적표 다시 보기</button>':'')+
      '<div class="result-actions">'+(campaign&&!practiceTactics()?'<button id="result-continue">계속 →</button>':
      '<button id="result-replay">같은 편성으로 재전투</button><button id="result-edit">편성으로 돌아가기</button>')+'</div>';
    if(campaign&&!practiceTactics())el('result-continue').onclick=confirmCampaignResult;
    else {
      el('result-replay').onclick=()=>start(recent);
      el('result-edit').onclick=()=>{ready();el('start').focus();};
    }
    if(isGroup(game.mode)){
      battleReport=buildBattleReport(game);
      reportSide=0;reportSort='score';
      el('result-show-report').onclick=openBattleReport;
      openBattleReport();
    }
  }
  const guards=isGroup(game?.mode)?game.units.filter(u=>u.role==='guard'&&u.side===0):[];
  el('guard-status').hidden=!guards.length;
  if(guards.length){
    const statuses=guards.map(u=>u.name+' · '+(u.line==='back'?'후열':'전열')+' · '+Arena.tauntStatus(game,u)).join(' / ');
    if(el('guard-status').textContent!==statuses)el('guard-status').textContent=statuses;
  }
  updateCommands();
}
function updateCommands(){
  const panel=el('commands');
  panel.hidden=!game||isGroup(game.mode)||game.finished;
  if(panel.hidden)return;
  const actor=Arena.current(game);
  if(actor.side===1){panel.textContent=actor.name+' · 상대의 행동';return;}
  const kit=game.loadout;
  const key=kit.includes(panel.dataset.skill)?panel.dataset.skill:kit[0];
  panel.innerHTML='<h3>'+html(actor.name)+'의 차례</h3><p>'+game.order.slice(game.turn).filter(u=>u.hp>0).map(u=>html(u.name)).join(' → ')+'</p>'+
    '<div>'+kit.map(k=>'<button data-skill="'+k+'" aria-pressed="'+(k===key)+'">'+skills[k].name+'</button>').join('')+'</div>'+
    '<p>'+skills[key].hint+' · 대상 선택</p><div>'+Arena.targetList(game,actor,key).map(u=>
      '<button data-target="'+u.id+'">'+html(u.name)+' · '+u.hp+' HP</button>').join('')+'</div>';
  panel.querySelectorAll('[data-skill]').forEach(btn=>btn.onclick=()=>{panel.dataset.skill=btn.dataset.skill;updateCommands();});
  panel.querySelectorAll('[data-target]').forEach(btn=>btn.onclick=()=>{
    if(Arena.turn(game,key,Number(btn.dataset.target))){visualTime=game.time;enemyAt=performance.now()+420;refresh();}
  });
}
function stroke(x,y,tx,ty,color,width=1){
  ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();ctx.moveTo(x,y);ctx.lineTo(tx,ty);ctx.stroke();
}
function circle(x,y,r,color,fill=false,width=2){
  ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);
  if(fill){ctx.fillStyle=color;ctx.fill();}else{ctx.strokeStyle=color;ctx.lineWidth=width;ctx.stroke();}
}
function text(value,x,y,size,color){
  ctx.font='700 '+size+'px system-ui,sans-serif';ctx.textAlign='center';
  ctx.strokeStyle='#0f1714';ctx.lineWidth=3;ctx.strokeText(value,x,y);ctx.fillStyle=color;ctx.fillText(value,x,y);
}
const groundPalette={
  field:['#354431','#565039','#574333'],
  forest:['#24392d','#34442e','#453d2d'],
  mountain:['#3e4650','#514b47','#59483e'],
  river:['#344a40','#314950','#584438'],
  gate:['#3c4039','#575249','#584238'],
  gorge:['#463934','#584233','#513832']
};
const obstacles={
  forest:{label:'나무 군락',base:'#21382b',detail:'#46684a',path:'#776446'},
  mountain:{label:'암벽',base:'#434550',detail:'#787b81',path:'#867866'},
  river:{label:'강',base:'#254e65',detail:'#6995a2',path:'#aa8655'},
  gate:{label:'성벽',base:'#555450',detail:'#84827b',path:'#a18c63'},
  gorge:{label:'절벽',base:'#302925',detail:'#8b6d54',path:'#865f46'}
};

function drawObstacle(key,wall){
  const {left,right,openings,halfOpening}=wall;
  const width=right-left;
  const theme=obstacles[key];
  const boundaries=[0,...openings.flatMap(y=>[y-halfOpening,y+halfOpening]),430];
  for(let i=0;i<boundaries.length;i+=2){
    const top=boundaries[i], bottom=boundaries[i+1];
    ctx.save();
    ctx.beginPath();ctx.rect(left,top,width,bottom-top);ctx.clip();
    ctx.fillStyle=theme.base;ctx.fillRect(left,top,width,bottom-top);
    for(let y=top+8;y<bottom;y+=18){
      if(key==='forest'){
        for(let x=left+8;x<right;x+=18)circle(x+(Math.floor(y/18)%2)*5,y,8,theme.detail,true);
      }else if(key==='river'){
        for(let x=left+5;x<right-10;x+=25)stroke(x,y,x+13,y-3,theme.detail,1);
      }else if(key==='gate'){
        stroke(left,y,right,y,theme.detail,1);
        for(let x=left+8+(Math.floor(y/18)%2)*9;x<right;x+=19)stroke(x,y,x,y+18,theme.detail,1);
      }else{
        stroke(left+5,y,left+width*.37,y-5,theme.detail,2);
        stroke(left+width*.37,y-5,right-5,y+5,theme.detail,2);
      }
    }
    ctx.restore();
    if(bottom-top>42)text(theme.label,(left+right)/2,(top+bottom)/2,11,'#ebe2cd');
  }
  for(const y of openings){
    ctx.fillStyle=theme.path;
    ctx.fillRect(left-8,y-halfOpening,width+16,halfOpening*2);
    stroke(left-8,y-halfOpening,right+8,y-halfOpening,'#e5cda0bb');
    stroke(left-8,y+halfOpening,right+8,y+halfOpening,'#e5cda0bb');
  }
}

function ground(){
  const terrainKey=isGroup(game?.mode??mode)?(game?.terrain??terrain):'field';
  const [ally,middle,enemy]=groundPalette[terrainKey];
  const bg=ctx.createLinearGradient(0,0,900,430);
  bg.addColorStop(0,ally);bg.addColorStop(.52,middle);bg.addColorStop(1,enemy);
  ctx.fillStyle=bg;ctx.fillRect(0,0,900,430);
  for(let x=0;x<900;x+=30)stroke(x,0,x,430,'#f7e2b714');
  for(let y=0;y<430;y+=30)stroke(0,y,900,y,'#f7e2b714');
  ctx.fillStyle='#160f1430';ctx.fillRect(0,0,245,430);ctx.fillRect(655,0,245,430);
  const wall=Arena.obstruction(terrainKey);
  if(wall)drawObstacle(terrainKey,wall);
  if(!game&&isGroup(mode)){
    ctx.strokeStyle='#abdfb599';ctx.setLineDash([5,5]);
    ctx.strokeRect(25,78,425,314);ctx.setLineDash([]);
  }
  for(const [x,label] of [[130,'아군 후열'],[322,'아군 전열'],[578,'적군 전열'],[770,'적군 후열']])
    text(label,x,31,13,'#e6d6b7');
}
function frontLines(){
  const fronts=game?.fronts||[{x:390},{x:510}];
  fronts.forEach((front,side)=>{
    const color=front.broken?'#ff7162':side?'#ffa583':'#9ae6bb';
    ctx.setLineDash(front.broken?[11,13,3,13]:[4,7]);
    const x=front.x+(front.broken?Math.sin(visualTime*35)*4:0);
    for(let y=52;y<400;y+=21){
      const opening=game?.lanes[side].some(lane=>lane.open&&Math.abs(lane.y-y-8)<23);
      if(!opening)stroke(x,y,x+Math.sin(y*.034)*6,y+17,color,front.broken?3:2);
    }
    ctx.setLineDash([]);
    for(const lane of game?.lanes[side]||[]){
      if(!lane.open)continue;
      stroke(x-9,lane.y,x+9,lane.y,'#fc9b70',2);
      circle(x,lane.y,5,'#fc9b70');
    }
    text(front.broken?'전선 붕괴':'전선',x,416,12,color);
  });
}
const hues={strike:'#ffe1a5',arrow:'#ffd079',hex:'#db9dff',heal:'#83ffb1',shield:'#8acbff',link:'#ffa080',breach:'#ff5447',miss:'#dce5db',taunt:'#ffc580',ambush:'#ff8bac',trail:'#d9a7fa'};
function effects(now){
  if(!game)return;
  for(const e of game.effects){
    const age=now-e.at;
    if(age<0||age>1.1)continue;
    const color=hues[e.kind];
    ctx.save();ctx.globalAlpha=Math.max(0,1-age/1.15);ctx.shadowColor=color;ctx.shadowBlur=14;
    if(e.kind==='miss'){text('빗나감',e.tx,e.ty-28-age*14,13,color);
    }else if(e.kind==='trail'){
      ctx.globalAlpha*=Math.max(0,1-age/.55)*.55;
      const u=game.units.find(unit=>unit.id===e.actor);
      if(u)sprite(u,e.tx,e.ty,.8);
      stroke(e.x,e.y,e.tx,e.ty,color,4);
    }else if(e.kind==='taunt'){
      circle(e.x,e.y,25+age*75,color,false,3);
      ctx.setLineDash([4,5]);stroke(e.x,e.y,e.tx,e.ty,color,2);ctx.setLineDash([]);
    }else if(e.kind==='ambush'){
      stroke(e.x-10,e.y+9,e.tx+13,e.ty-14,color,4);
      stroke(e.x-4,e.y-16,e.tx+10,e.ty+9,'#ffe4d4',3);
      circle(e.tx,e.ty,12+age*24,color);
    }else if(e.kind==='arrow'){
      const p=Math.min(1,age/.33),x=e.x+(e.tx-e.x)*p,y=e.y+(e.ty-e.y)*p;
      stroke(x-(e.tx-e.x)*.13,y-(e.ty-e.y)*.13,x,y,color,3);circle(x,y,4,color,true);
      if(p===1)circle(e.tx,e.ty,8+age*18,color);
    }else if(e.kind==='breach'){
      const angle=Math.atan2(e.ty-e.y,e.tx-e.x);
      ctx.setLineDash([9,6]);stroke(e.x,e.y,e.tx,e.ty,color,4);ctx.setLineDash([]);
      stroke(e.tx,e.ty,e.tx-20*Math.cos(angle-.48),e.ty-20*Math.sin(angle-.48),color,4);
      stroke(e.tx,e.ty,e.tx-20*Math.cos(angle+.48),e.ty-20*Math.sin(angle+.48),color,4);
    }else if(e.kind==='strike'||e.kind==='link'){
      ctx.beginPath();ctx.arc(e.tx,e.ty,15+age*31,-.95,1.34);ctx.strokeStyle=color;ctx.lineWidth=5;ctx.stroke();
      stroke(e.tx-17,e.ty+12,e.tx+19,e.ty-14,color,2);
      if(e.kind==='link')circle(e.tx,e.ty,9+age*39,color);
    }else{
      stroke(e.x,e.y,e.tx,e.ty,color,e.kind==='heal'?2:1);
      circle(e.tx,e.ty,13+age*35,color,false,e.kind==='shield'?4:2);
      circle(e.tx,e.ty,6+age*26,color);
      if(e.kind==='hex')text('封',e.tx,e.ty+7,20,color);
      if(e.kind==='heal')text('+',e.tx,e.ty+7,20,color);
    }
    ctx.shadowBlur=0;
    if(e.name&&age>.03&&age<.72&&
       game.effects.findLast(other=>other.actor===e.actor&&other.at===e.at)===e)
      text(e.name,e.x,e.y-44-age*13,14,color);
    if(age>.23&&e.value>0)text((e.kind==='heal'?'+':e.kind==='shield'?'◈ ':'−')+e.value,e.tx,e.ty-20-age*38,15,color);
    ctx.restore();
  }
}
function sprite(u,x,y,opacity=1) {
  const palette=u.side?['#d67956','#84372d','#48252d']:['#9bc6a1','#367762','#233d40'];
  const stride=Math.hypot(u.x-u.prevX,u.y-u.prevY)>.25?Math.sin(visualTime*23+u.id):0;
  const acting=game&&visualTime-u.actAt<.28;
  const hit=game&&visualTime-u.hitAt<.16;
  ctx.save();ctx.translate(x,y);
  ctx.globalAlpha*=opacity;
  ctx.fillStyle='#0c1415aa';ctx.beginPath();ctx.ellipse(0,9,15,6,0,0,Math.PI*2);ctx.fill();
  ctx.scale(u.facing,1);
  if(!u.hp)ctx.rotate(-1.3);
  else if(acting)ctx.rotate(.18);
  const body=(points,color)=>{
    ctx.beginPath();points.forEach(([a,b],i)=>i?ctx.lineTo(a,b):ctx.moveTo(a,b));ctx.closePath();
    ctx.fillStyle=color;ctx.fill();ctx.strokeStyle='#101619';ctx.lineWidth=1.55;ctx.stroke();
  };
  const px=acting?8:0;
  stroke(-4,1,-6+stride*6,10,palette[2],5);
  stroke(4,1,6-stride*6,10,palette[2],5);
  stroke(-8+stride*6,10,-3+stride*6,10,'#111818',3);
  stroke(4-stride*6,10,10-stride*6,10,'#111818',3);
  body([[-9,-12],[5,-15],[10,-3],[9,5],[-9,5],[-11,-3]],hit?'#fce1c3':palette[1]);
  body([[-8,-13],[-2,-11],[-4,4],[-12,8],[-11,-1]],palette[2]);
  body([[-5,-13],[1,-13],[8,-7],[3,-3],[-4,-6]],palette[0]);
  stroke(-7,-1,8,-1,'#d2a76b',2);
  circle(0,-19,6.5,'#e7bd92',true);
  body([[-7,-19],[-5,-25],[2,-27],[7,-22],[5,-19],[0,-21],[-2,-16]],'#231e25');
  stroke(-6,-22,4,-23,palette[0],2);
  ctx.fillStyle='#252023';ctx.fillRect(3,-18,2,1.5);
  if(u.role==='guard'){
    body([[9,-14],[18,-10],[18,1],[12,8],[6,1],[6,-10]],'#718c8a');
    body([[10,-10],[15,-8],[15,0],[12,4],[9,0]],'#2e5251');
    stroke(11,-7,12,1,'#f1cc82',2);
  }else if(u.role==='bow'){
    ctx.beginPath();ctx.arc(6+px,-7,11,-1.18,1.18);ctx.strokeStyle='#e7b474';ctx.lineWidth=2;ctx.stroke();
    stroke(10+px,-17,10+px,3,'#e9dac2');
    if(acting)stroke(4,-8,23,-8,'#ffe4a3',2);
  }else if(u.role==='hex'||u.role==='heal'){
    stroke(11,-14,11,9,u.role==='hex'?'#cbb1fb':'#a4e6b4',2);
    circle(11,-15,4,u.role==='hex'?'#dda0ff':'#a5ffba',false,2);
    if(acting)circle(12,-15,9,u.role==='hex'?'#e5a2ff':'#adffbd');
  }else{
    stroke(7,-6,15+px,-14,'#dce1e2',u.role==='dash'?2:3);
    stroke(7,-6,5,-9,'#b78c56',2);
    if(u.role==='dash'){
      body([[-6,-16],[5,-16],[2,-12],[-3,-12]],'#242431');
      stroke(-5,-13,-15-stride*2,-8,'#a688c0',2);
    }
  }
  ctx.restore();
}

const cardArtwork = {"guard":"data:image/webp;base64,UklGRuAQAABXRUJQVlA4INQQAAAwPwCdASpwAIgAPmEokEWkIqGW2hZUQAYEsoBgTDPkKPFD27fvnUtNm9ADpnP8/aa3A38b4H+Sj5z+7+f1iP7DNQX5v+T8e7KJ5Kah3sree7Veg14E8D/V38S67XQG8mj/U8p3197Bwk42o2he/6XkK8o4roIzqgHiyVbitdFoOC1MxJ3v3P4BxZqN/BUhflKCDO2N1MOCJ9ZV0ZZ3GOaHyGu0dH4TXeLXpDgxnVfGKmjIzbcJUI1kcZk9skrSaEiU8TgyLQTS0UzL8swx87taCHqVqdq+wL3xvVhApPEW8lALQyhpoI0yRvXn91IWjQWGmy7yWk/nX3a3+FcnGg6FvI/pNXPKR+ACUVsjrfL543xN3kDmxf/rWnTHJrRU8CgxxUI1YDH3XUJPufQhAQLWla6w1kWZhLLpPhY9nfJvmR78HNeHvL7tlvvdqlwavyYEUs6F/flg6VhPXMnV4+BGEQzCiUjIDTENB5pde8C1wSrgfD9H0uieCTfd28g03DoGCBlSxV9482F1dmfNb8ggxeXvARDCLXS4fWL53E8OxbIEFxO0tu8Uq/hLqqrGNuMGbf9XR/CklIgPvLJ+RUYSN6BPVRL+0fjMz6sCF3l2SmS2bltiOArWIHzUBHz26BrtTYSKiOeGe7vvUXT6A95LRtu2q0Yg/Qt528w4jae+CKt4AP7sExNPUMXx8PLoMO6w7qLvYNmha0sVfXtLJtAqc+9ZYIZUaF2ra9T7pellt+OcpyZv3mT+EmqpwWaFNwAr0SkmIGz6Vsz7fLVkMZgFgAeB2X67d75i0a4rDEVTKK6huH7xf9CfDGcdLj0Ql7+Vwpv2I18dph+toS2Epk29cae6EnqimonM97od5ePbhB3efGRitiu7JT3INGdl8aVuFdwEoH9cApbKC+3e8xb5TodVJUPamSU/25pHdsb+ffXMcUbNiMmZHi1pGMFav8fLIE8IS35rIJd8aRfE5PxDsljTXclA2GamtUGS1LyjyHwIAngYEqy5eTKIEcZyyxzmK6+/xzp2xJc+VG5hthUQoN5Bdm8AkAzmmnaU+GkMzRstnNYvbEjSC9Jfn1PX6OhBXDI8jD2NuHoGInjsI3Bl8XRn7W7NFlU2I0muu3w4Afp9btIDdtmmaIKV/6j1rXF5W6r1F5jDRPgR7wTTGHC15mXbUoE16u0rkX059In8wHQHd0othr46FJK9qpawU9L/KE3RyCoQYM6ytWTCqg/PD7Bd3pLeA1bIKu+DDHtLd45kTf9AMT8YFvTUJXXs9XlovTeV+6lJ2HP1aFXv6I9ZP5pKkllMjZ4BIktS4w7/0mtgaVXMfpi/UXqi3ImFN3eeW0947LTzdyku6SBR3jUK8Y3v4UYoKl7QiPMknXSLUptA61SZG1SQFEKoqXSAlST7Eeoj2j8pXzgN/19qVhDvhvAFUeoGhsGDqm9VoFoia71TRxqVmuNdMdTCd0hQp3ZvK6MZbtVoyse2jVxfMXLxC/Fu8PBxxxwuSX1IBK/C5Huw7U+l8j7vXtPaUfruVFio2Q3NZhOY3VdHyWLgY5vi+Qrfqw9O86e/wAhobvdkgjlw/kZOlLdF/SsjHVJaqoyAEydItud75+6E57iyjvOxAOLiDDmnjilto1uHG1PcW5Dpes/MwlVwyXUdd0EXMwiR0wzdbYEiUj1dTVO/OzZVnOUBfIsxap270AWcP57vhU6PJQOwiTfXmzOkHO5v1daI1b8tBm74IaNB07y1BiLb/O2L14QUSLkGKwQrqvPlgOvwtKDsgXwUs+IJVeVnarZKHVRBYuC5Fr8DflosaIMN08wDj/7NRWsbJKnlVyKLPQNX57MGbKXwhZHxHQg3vRdRfUpOJ91Kh45Mv/1JA2V7ule5kEdMWyFPAkUPdb5szrO4Sh5XWcOV5M6AMA2oi8NWSldHP2zL2D05ibygGdCyIplJpLTmazAyfWehgxBLej5RAQAWSEQk5MALADQzg7IdZriDG9Tpg+qSkZW9AQxibacXMwjMUrfx6X1evCj36riMLxE7D3QOpZ0SjD8R4QU2/QbsE0AUkr9yz7oMQVVfByc37EfKOA35LkuXMcIaes4/OEV6lo4S62tOpWjgLO0/TXYGNjQ2WdL/VsIbvvvc3oPgXYORPBPT0L6ka8Wg/HcXT1tZJqsIwtj5ulLFlu5Nu8TPazLuzebxy23c41Kwd4SYuhOGzSOCGjVbkhCpLveuCiJHauAHBCpSkCT+pd9SWTmAn1+OX4kJO0PDjlDKRE9n0/IkRzYWUN4vM0n8VT/9SKhyRAowMeJrhrqPr5oOkSuNxF/XVC0pl3fmaLdbnCblMVRe5IxFzpaB7+TOz5PgzhYg60cp70j72Ss4wjB9mfStcA4L6mCPweBYlYhUVXZAuicz6hGYyrCD2jAUJvaxiGEYwijVaCN6taxEFfV8vj3eO1XbnX2foxHrj1w1S9vgrE0zQ9TVb61gVc7k613HkIpkJoSTPVtzo/HpFgtRQv8lhIgFazCGiQBgqrv1tr1Z+3CiA4WjsqmlkFI0opZh6katTXExzR5U23ASaNZPuV1mmQQTh6SGY6MMsIoLqeQzdp++pa+jDyOEb+tu2Rxt2UzLjPKo8Bhmxs0k92gecUgtF6JLQWF0xMfE6sVBEaHYH/cZEwldRGjAdTiTs7BcSeGwduxgbiM3JmKwt3U2xh3dlzKnrTyqXPoqws58hZv4TMkiYxg0xriCCRcQmyPHE3Dmk5XZmvKELfcFwUs3gsT7oFzR+JiLCgql8+QJCvbThWA3QALVmfix+WIViRWZqxQiiJXOuYn1ddsKnkShQOWbjLB3pzRotCPz+k218JxecW3epq8WNFVM13A5TJ8NvRCzlOI6EbVnjm9rK+j/W6HzWVZEWUbnIra/W/jE8b/+llwxOImqVjcvNfjkrh6l3pYdqdE7ZmQRfhU5XthxBxxr+WSGyBGKh1s+osuDXeaaEKZCba+kgKEMChtwzAtEacAN71I6y9rqrAYuss9zFHzn6P9i4QYh01kNfs1iQOwezgE1+5kd2QSOCZp99MrmWI8NW4TMws4ohwBkMieLtRbHxRV2Raw3O7ek9SePxcffIl3wN6uaEMcdhLCFoCEHADIyqve91uiqr9Uq60JunlcZkpKh6dID11UYtp/jgYTm6zYo5Mw7lI2xqrHcZ92D5LC+ibYEMF0dcojlarcgNKjNK9Y1RJbyHLpWDqQpLkwSM0r1UDE7CJhO3rlv9mg1PeQa3t0Mfmg8/GB0coypxNjhjaGb7LCqXSht66/MzfdMGwOgCHvuygOWivdb+wTQeVbomN7PWmdPeydtZ+IcTPlsYoXPfdhAzZz34ookNZph5QEoB1BKoBLgWotyjJz7CSGk9mWwGwthqR/lQRNvSSy3AqVZLvpDs/SZ/+i6OJvL/Z3MQ/Rw3EDSCIaWik4mH/MnQ/v/izpMUvqaXSPSSpTNbtqsgnJVpsWv3PG9rpIWEOqljDVRq9zPEpJiJqVtAO7ehjOyC43ljk102LRi6MrhVZePytOvF/lGeE3EzjljbO6tiIqdp4OiOW/m1oiIR1SL9i6TB3JCXWzZc4KzUGyhu+M70gWfM6xi3TjIKlRJ6UpAfq4LZFcycLiRa/vx+wnjm4o3jAJxtaYxz2Pi8TskH68fpjn4D3yZpPNUDQyTV3Rey+3VvcBl9r/dTeCQUbpP8lT3RXbjZ/0MJHmkGqsOEOCKEJ4YifXw6RpL59Ry3cRl3SmVlaOWmzmnT2LIDaYrHrWpuiOkdrhtMlunE0bSf4yCtLEzXu9RRjmb9SQHOLNC+FqOMl3hnAvKhJE321n7vt/Ka71xGkvLsrwrEP43ycDZN/+EslWMOE3ATu5yKDFljjtV9ZsZQOQAG7EOdw21C2HHTZJXfQzXRW+HtSl2T7gBdd/ix8K3pt+ZgbiNEwKg/4U6FnGaESQoIiEkuw59fKQNE/ZR+byjcFGrChxTu8hRUiveFIJORDzeRz4NI3fsgBm/mxfMgvGmGvUDhl8apWUCImU7IWkMH2J38cX4JpKm9mCJ0ZnHcCX28dgjRHz4K2uEl5ydIqSTeD5q2VuNnrehR0bQauQ0j0tp7sIDSzVEMzYXAL+lDCQr6tgHdpv2XyZet9VwFN3kyzyhCL4MRl1k3sTQh1NQFuJZNsh6f/XALDlmqTADtNuAYpG3z86fV7g92YUmXEMzi0h+aXdDnlmMESLu76yrrAOUzrcMJrdG5yGliGLiysIhfr2CGnG9AObBFKeWkDUF4O4fBi6Ja7fue3vf1g/frGrusJkUvijd6H9D5ieT4g3yMCnzvf0ox8xWMYFL7uYBRUUdYvC0RbFHnjLEoDjDDHP1lMwXhbZPdFK47Ydt03LS15sY7mhvbcaBz8IaL+mcLGIqar69LBpbhXhQBFhnT5ztvXWEXMtagUpIIWyK99PssaHYhxr+zEcunV1RXQIS6k1BDtTviSihbaLAWenq/ChVFEFAoxw30UqY96ruLcTJzVTefBA+R8Tpiq/Ip1nVwzy6jFhZZF8/ILc+BRJcfIo8isnlVC2YuLgs09vvlsMw4gl+kO9Ee9eMzMDFfmkJJo10CpbfIxchsyn9p4Eu2TfYP680VYA5megFeM+R1xcCzJdhnCV2JSd3tO7D6XQ4GGgFXYAwDaV+1j429ZtlA5zvEJ1bmoW7G9/4hUl5Ffh6IzK8jUvjKiRDMaWA3XvPH/f0xpo/ssgq6tF9v7uClDJBojENlYeLJApljzpFIg8vQjSmyy8nV0Ej2/6f1f8/Ka0Rf4PuWOSLeT2FzX4GKtvtiJS8xGonvPGfUifdi5i58C4nYRu6SWsdtkera00NJGSYurVFmnjvzSSUVp/HQyUQO16IFRAA1yUnzNI4XfFSFL5potCXiaHPphtoHO9zyP0vAmjV3p9Mn7Gi/ectxsJLBIUu4rwEV2qpSClEDc8vBAQLpjWNwDP80lTI+k1Ttae+UD08sTZLqex22W0h6kkYWFfy34vVHLEZNbUK0lCzU84fLSiVPKD/QivRJ32r3+tASWngWWhl2D5O09BWE9/dCDNkfJlEPF826wqc0vh3ApqtwDD0kR49RGGEtfoZwjjjh8VG6LsV2HsoceOGfJPeIBENHidkaApOek+WNpGGduOC3wu60pse+jawZrj3oZQQejSGoN0GpOJrSpqaFBJEojxkwC3Sth61kIRoeycSsagkDgURYbirsy1DBTCzMETYksWmleaARAugNTyBO3RkgqiQ9tcj4HF1VEE4LulVY8KoI+6lc9vs7cnVuL/PYrU1UDwmspFjScWrP4S36oIdzH1zSksmY0f1aftYxd/qzC6WozHrHW63lUPSJSCHPn7KzFGOxA5kzGkrswIYWqxBnwt0qptz6qpBmYuovEnG+luYQalcFJBrXjjl0SLfWB0mru+raLrl/Fs9pIgq/JNeICQoRlhClYI68jGzHnKCLwqCGBd1MUtONGw8vExZ772yG+sACZuAdXwnj7fFS9CNoU+Tf9ze+DmdP8yOJ9qhriAHYFSX0iMKLoAm+TtzI5//jjxsu2G5EL0ISSYxpX0sr+68yt/pEbdIq1i+hXqpIMxq+713lW51qMj85JFVETyAEI67H8AEUymiPe7z7vf9+k8DqLiIJ4n8KC5EwYA/60i3y4LYeZ+QIzjVLdZCLj0MwJFv+lQEU53Gfxb5AAnCcK11K+cBYEui3559HNCOuOSisB8ivLaxHfdz1O0Ni2UAAAA=","blade":"data:image/webp;base64,UklGRuwUAABXRUJQVlA4IOAUAABQRgCdASpwAIgAPmEmjkUkIiEX294cQAYEoAuKAYVrSveWfH8B/cDzinyPS5t9/Mb5uXpf3nDegLRO3Gfj/AX8e+dfy/9w/dL1ysI/oP9D5hfyn8Cfwf8N6B9+fxS1Bfyb+keC3tErZegX7x/d/+p4furL4T9gL9afT3/peH36D7An6V9WX/H/+nmb+ov/j7h38//t/XP9IAOkzqf+8tANdDdHzRvMjOHY8C6cokyFXkBPLzPctgzF9r9rY265dqfmrjCjPa8v7/zP+caeLu3gxDpVUThqZPizXU+blZMoTEY35FQzbr14HspxuZML5JfyZitwdPMea51q1S7z8bieL3S/CVu2eBHhmss61CLyIF29wXSG4drQWHdxM3BGB99XvkureehmIiTbIT5vpczAAj2mtif7oSHLlitcYtyZI5nNNp1MfJvL2y+k+ol8J75AVce+Jvn6tyClauuOFMDmJ0wzAj45qb0ahVZl8F1iJzPtP6lijBytL5xy62m1B5GomKym5dJS8/dt1pjFZYoG9VHmGIBJiee0k0Z8ud4lKDIT5G6WYgbYQMLKvtKFl6oTqLAAOOV/EUYJA4RKcAH9TGGUOo4MIZ3rKrFov9PNQuWAcQTNxVFbscekeraDo6cjVvnxx7otfT0L+uQ0WuVwctZG2l5BDhgV33/G/6e52/lKSZucaij/3ynEcNE+NmMkxLgSOnVvum6kt89AZpSe1B4+xPkI+wImo3aCKlS6w1yLE7GxZmoDwDiwAPzCckVuB4ZlV6Alm2VhxSR8Q5hrVsKXhyeZ1RWe80HVQCYc5StEi7CnfM/kzWaH6It2D7ISsEHGn7Su5KUieK5r9dufzkmxeXXe4JTsAXBKcFEK/PcmviwDuH6aVftLn3f7ygczKSSMR3xCgeekzVCdQ5Kt7qB+2af55gqCjEZF1mCRpnvYGlrbKA35BlVnxJEJyp6sqn6uRQ9oMDRmyNr8/8gCZA4z/J/zpZudPHepZRVd40I5eUy9ANazx2po/ZtKEBz3gHroGibsZ1FkYJzdQndZzAocb02Kh8Sx0PVkqaELezjSILqwwThTqbJK1/B/UeJgjXWEhz3JzqYqAffepqBTm95xG+tterYKtcOeDLjHQP2H8JyQWsKUisa75Rx9xdxyZZPiWyDkumRaPPP0t8+q0eUpkigT6pJBBs/01x/U8PKhpWSmXXQJrOtKuxoLX4wMi/cvIUhW4A/FoEyqmRMZe4LH3ogonX/C97h4pJZzxaJ5SjdxTxOwMXW+jCxh5aC+4a5Js1gw2kZk4JbG/xrsMuDNml6bvXg4bKHxIgkxaDDtV17yb/N/o8lzU564AtCI7G8twmoTC0lU4Xy/UrpkYermG0sfPNI5RjJfP0j3RUE4JgAUh+c9HvTHV86RC+MAjkb08s0IFgvBlgH+VPeAf59zqLDNcDl9Pt/rjfxt0eLaPezFBUmXPK3k5/HWGBtdpiU2YLIZgyDyGppDKcL3ej2IWVyXuXKlnphwHmDoaWsF3BKdvzImzF/VxgDVcW8Q9M6Z7Ayba3hhyc//rLkl0Nt3E5N6VUM4yAScJ1lFb+PgjrbCQP391/psyZhiayfDT4mo4fogTF7vx4fXKj8Ipq1yIyEhz67d8yfZ1q5YyHvWu0KlpY8swuCBb3fjSXye+KbRMrKJnkuF+hu2EOL4EMhR2ubPFIJqOiWSmupuGR0JfuT2nUsmNkVqokr4iluFWq8MV5g0lxM7yK8n6UzYym7wQcIRU3SInlbf7Df2qXFCAgxbVJDmg5SjSD6DYW+O6Ul1zY2AegrlHwjuAQ+BU0XqeLAR1u5QuedrcWlmE0/S9bl3ymSiTfJfB9kOQKHO8Y6PIX4+eIMXUU4YSt1I8Kq8RfMJP0WbyTOjoMGGoApRL17PlSFDgD0stCdXgLeRk2S8Ym991mVy58T8Mhvq6l1tIi9YLLT4hwQsNZYSNoyliim2SAn6wJTumZjv1FdQWc0NFtUy1Kc24COLp9K6ZXq7233wMxojKv20GqWhCFOh2gL1OeRp5aSZVm3WtBjqsMf7XQ9t4eK/DadfTAVruTWMGELBIwlw2snBm9GFCntrQNMFWqFuwBE6NzSvPzPyTTQc2fvCGeESzV6amD0lHobgZgZZvxxnm/k0Ucg3JhS8z5uNTr2JKUUlIrFT6NyjPbOELNu742px38V0MHm7I8/FENIIQ4sQSJGvUn4Z77QRsnK+dQrzayEwdzzuhuAOuP87bR8dALUSauEI6szVEsIxCvmjRBOGPdgFIkHKtn4t6sVLtouJZmywCxEg1r+NGbBigOMeUC61zBGmLOTa0ZIR4OQgJbB4T7BkwczVOl/kLREXCImNH0ZmKEPx1kr51FRORUzsUesv1rn3P89XAE6qfbXz4jiXZdh2bLQ+FO5SVcHED2KbBoO9U5nanvkfxIxiRnN4TruV9okcMCCEVuu6RHvnsX1Kkjj9AZ3L+o+gVMa29urUc0FutSlJ24+lAYzAjMLUBzDjGwnw5X2dedKr3v6JHnfEK97kOnV0D8e5XHA6hYP1k+5lcq/SFSzAZ4PFTcBXmV40FJAUJqKIkf+w5sATkf1VJO5JKN+vlQ7lB9Hb0nzyIWfURho9Nqbbm/WMo3//Fkki5c6UuhVdUYutW/AyzwMqj5+iUv+GPDlTmypAvKIPfhnd7ELEUpryu+2KhYicJ7yY/Um9LLG3BAN32jTs3oA1IO73M92hJpy/T/647j3JkQvgxVYmbLXLO+juNr5+gHh0IbrUdmjr5cep3p6SPY6lqEudJUXwA/JqlgPfoyXapR+IXUw+UXNeI/X3E7ihmkrQhiA6SOP+Yfwg/kSUw0riri6JajHhYgnBMzFXBVh1gpXRzCE/DDaSxs+U1qTfukkkMzB9uTR0NECb53cGrt+RiX9kE8Rw1XKLtLo54/ogKT3zsi5m1DyDW+mKSf8Ek3MAJI91YnnycIhVi+gxAsRKYV7SgumE4rGgp3dVOLHAfTNBstkoEuDWwGoknWoHmI4zHPUWRiYzo1RnSTYIqOLES3IxxWc45u6+x3GkRTyotE5YralXUDanai7iJwyOa2CeRXdAQGfZv1Z74dEVb9fOXZ/RJ8AghJaxDzz472xdBcRGbz19JCOiDIfekIVd9ubqiLraDE/fOF8OWGxxa5cvff3XzLWNuYhp4BOsVw65LdSxTSIHZTds81/YGOrZV0Ymc0UjWpvXCP8RPDhXmsWdDW3PCWC4dfvooMIoT5uDwCgPBULpuw664/H5sXsOF5vERvsYL6He/QFKSRiL67Ku3OP5xizy4lI9/EuXHZYR7IxKveILottpYl44Et7jLB76p5XIMnyKeGBT1SqQkR3vs88Ahxxc68801yv12kfQJ/7oJcL/EW69y9LzafCSCx8ndH2tnA4pMynk2F9LvrktlWpQH8c3Tyehbz6SS8U90dDmXeFkFntr87Eaht9U4FNGNyI1gO5izJvCycPba+GMZLrBsrbyGczczUGg3BGP+GIctSDlZ9XwGq5WoSN+iSnFNf8Ve7CwYLOA1YyIWiM7X1RVjtjb6hl096dt0gdip4s4eCbJJ5+3vm7nhHgMV5tV3z0GU6oP0JO9fSK3dANwT5vG+CoaJcX9/glWY7zThEvUaDRNmFqB8td4EAp5WKsRuLlyUYkk22230LW5YQi21wiu+rdtmvqhW9wGu9IqsFUGqowFzhKPlx+j8IBfGSP8Nvj79D8YYf3B/De5uSFYPzpNXGm0vIVqBXbfhdSJUATeYqIm8M02SIBaBEv8SalqG0DSD0FemaUYPkFPRdNPkD0fWboK/Go2NSsWWb9qhMoQJMgpodMvAC3n0y61DeZqiq4jPDiULalbrBS/EHK5YvmFNKH3tKm8P/DoY6lDjaXpN3JTFTaYD4KQS5ogrKBe1k9JeekrAbfIYKuRSU+DSnf8IbYPOrwTa5aLAvuKdtWULDL5UYwHcmh5NaTKrnVSU09k+jWVREOJko+lnKs3GXDQmJBLnHg9r6sp9d3E44fI9tUh0wfnUsrmTu4x0pw3Emi8G+1VpaqWLVNhOsS+Sp7IsWydkEH9mHlIT7UYMJlplsMh4io5H+qNH6iFlHYGXAzRx6f9PVoRe1R+0si6DJwSn547o/HTorNjAn8MqGpY18GpMFVtOJIhG8PUmAAA7WAZeHM6NKt01Zj0VhNRtdQovPpVwlRzsLUWyjY8z3vd9uu1a9Saoo1AshqDqtqgd/w3SrOddQWjwI5MDM84pP9PzGMEP0S0CGWtqFp1eWuFUVDUuPGUYEypZckRLlwEywCoGYr23jAdaQaqv/Ob4MLhN8yPfjrnPbQs7Hu9lR3KlgEorN4hyMgzo42jF/u8gOlWP639vxDaqOpKJaNyAupbA/KzNgzhY1LsX9XzS7xEXBa+j6A/InvHsHLSYFvisfjVWKXlHj9Wjnoeil7FBTFEcU7HhwYz4ht5loPxDOK3Z9bjVDMG4piVmz8yyDMOlAM+LfyVI4uTFGjoj/vsB6MPhbfAjP40vV4J5LqdIJlbLpxGjHq0XB+PBh/5CRoVTQKM8FnH2YwuVoMq93pTuZrj6mn5PKFPsYJ7UGqI2FTJCjxbQr2i3Wr4RXeCQqQSry3S6UEl8QhVFbwcH/GmfZFaRoSI5L+2YLmSufHhQbRsbf1OZ5Wni/sE+xrV7rowCgiDSZz4tBopUSDdNIZne2aFSaVd4yXfrc9zn+VTIYvpG+LPQqoMCc9JuDuhkqRTO7q28v9ie+VepUu6Z1s5I4HeFG9fOy2KtBX1SFCA+Q3zl2Nk/KNp4NxLUnbkh1P3XNHts4trAyCfImWKlZ+VmXoFsJeDKW5Hs6uDwR5j7CEDf48//vtHLDzOZ1COGt+uBzj/fgLefcMiEZ8NKFo93Lao4G170DTnPzHhuf52WvbkZqOYzDh638TljsE8O6oZ9Q8r89Ak9oBXx83eG9FwLuR7jrQH2lzF/ePb2pdViF8fKMac6Pofe4afyHXZ9ptA8vtvUIbc2V5SlTJ0p4to9tFGExQ5bj4p7rxTke+VzHr7kG0ldt01Jqnua8DvLu3fzBuv9PPk1pSfDgqavljFqrn5uFUoIneVJaGb1YZ+0X7TQDwTEkkTijb0e6j26t7LTY7Q8Zgrhkmjn+DCetIz4d3UwgmrRVLKAHTS+mF2zE9/Amg0uTnrL+sRiBxpBLxiucWwBXIEit1iRBRuFK6QgRZauVQX8gOJrvPRxyAfZ1Ci1Pt+h1TnihgXjLpnKbWs4Ki1xzwV92E4Q7Sht6DcLfzjHV6ySh9LYd3uxYilfA51G28sey9637iCJbBKMqu/w2t31svX9tUQPT+RHOrDvRT/eOCaBmqjYk6SMx/SuGS4QxX/MPIl4xXC3j3khnUExji9IVgFJOGNcV9+V5fueItp+7K5KRunPYC53Fpe8TuwLsKYWgSHctV8mUx1lZHEadi57LUgCSU8IFoYYisxaNTH5qHHgYZQSPbpi1alZPPXMB5fx04WYuEfXSE6KV/Fn5a7rVidYVEDA3INOoEIY/28Q6qzxuYn/I0KN6K/qRin3hrcoCsfGIlgv94zPbRsV7D5yqsGvZFrv6FG/xKFywkEiZ07kUvBIHVOVFb19/I/ac4LBTaTbucv1R7p9VjDdXRa7SWy9h6loBjLt2gM1HbmVaYWIPWsoopcDQRdjtW8N4gJB4++9B7m2yVfq9yvCzUD5BIfY//ImFwvfOkno/dgAnzTRNecUlrioZNu3S7dTA4P4b2K4b6Jos9xo9IM57dKEj//qm0Qnfv82u8l+woTLhHosws0ij8cXFhkUWpeJlE2j+oHbr2pQ/xy2sBJB9t3+OtDMkF7IyWK+Pm9m1oS3M22FPGaRi1IGLfjB+nzBY1lyEJWNNSazRyDtIJFq+AnS2SgweVUU2CbRnvfJm2mqkvQnjhFJ2lmAsus4bik6YiJ8eUwdycLv0UANqRbcyy51wDvPyZslNaoG0ffaI8Fn2xJz8RRtyEEI3FHWtHa6rXLnPtmofLkLGMBhWcjrRpxKABQCffP1umj+/vuGlqREOvnoePSqJY3xiMkCIupLVcBO4P2GVVpyWBBbwRYF0uTjfHJ7Joipc/xLd06Fk3qLY+vv7bUi4AmpTl5D+YtPqXY3o94g16+WEyGU6TJVzr7hySN349HTSgEhvvqfjgceBZWraGDfrF610uRumtmlhQCLGHeJnYbOrljSMeUMns9unyTTJgrmVfR0/R+F5n9Jx3J7SrpRC5RX7a5wZlHZM7zCvCDVQ5HEhSmnFnjX66ML1K13GvftY70qubv7zqyYkpNJjoYQhZyJglwNglVoGfx5Oa6zWwe4Y/Ly5oENUlvK+n6q07jqHHJHxNcNj4R/vjAyqmOGCE2IYLQvxmXzhV3hY7nlzb+lKON6xhfxImXmdab5Rf4pLq1N9WXcIJxYT8QP0oPy5prqUMgs9d3A6H8reGw6RZMKz/XsFYEcrYB6HDrHpQPpaZc3gT3T8sTnOUG67+QawSCK/hyYXL77Z0sLgIk9XqFmAw5wUILbUicNI23g6p7ybIPa/BIUhbKPkrHno6ZXHlkAiNCy7Uhx0oBED/lCP89+KrFtGxM792oTrLM+t80fMaYm/7wL/QsuuvDsvCS9YIswAQBSfnxTHCVOZod8/uZbj2P1icl0oeFLdpeqmjrHAsCdNgml5Iw3YVNvd0XghEUcSJMGSS1vFYamMzYHJjrxnTXQMAbfe51cEbn3m2ar6M0aANlaXcDa3WJdBJr/4/95H8LUEEuCZA/oICXZt5cylOaSHk0eQ4umg/CemOJU43u2AREXZD5WDCfx6p4TU802E+7VSj4OpCMqxqqb2g3q92TlFpqHyiaqFqhI85DA+goy8+8JC56td7vFXiOmMT9Qgd0lAGAQQOQlA/73nrG6gll/MUttSeS+Y/ya17lQ3f0XY6UcViHGe4JUm1FqOwSS/r6sPPkY4mKuCv4CqgauBJ745zXytVY1PWnC1c5g2ENXMB7V4JKnzUn4k/0HNELB57VMShQLDOjsmrJ9uaHa5VSqEPEe+OQvH8oPD6heNYcoF3xT9e7Dudbe/y9rkSuuRBrvmOXUBURp9+0bahmySLwxkB+//yAAAAA","bow":"data:image/webp;base64,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","hex":"data:image/webp;base64,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","heal":"data:image/webp;base64,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","dash":"data:image/webp;base64,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"};
const portraits=Object.fromEntries(Object.entries(cardArtwork).map(([role,src])=>{
  const image=new Image();image.src=src;return [role,image];
}));
const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
const cardMotion=(u,now,enabled)=>{
  const attack=now-(u.attackAt??-10),hit=now-u.hitAt,breach=now-(u.breachedAt??-10);
  return {
    lunge:enabled&&u.hp&&attack>=0&&attack<.24 ? (u.side?-1:1)*Math.sin(attack/.24*Math.PI)*12 : 0,
    shake:enabled&&u.hp&&hit>=0&&hit<.26 ? Math.sin(hit*83)*(1-hit/.26)*4 : 0,
    flash:u.hp&&hit>=0&&hit<.32 ? (1-hit/.32)*.72 : 0,
    breach:u.hp&&u.exposed>now,
    pulse:enabled&&u.hp&&breach>=0&&breach<1.1 ? (.5-.5*Math.cos(breach/1.1*4*Math.PI))*(1-breach/1.3) : 0
  };
};
function card(u,x,y,leader,now){
  const captain=u.id===leader.captain, deputy=u.id===leader.deputy;
  const motion=cardMotion(u,now,!reducedMotion.matches);
  const large=!isGroup(game?.mode??mode);
  const width=(large?52:40)*(captain?1.07:1),height=(large?62:47)*(captain?1.07:1);
  const center=x+motion.lunge, top=y-height+9+(u.hp?0:4);
  const left=center-width/2;
  const border=!u.hp?'#77847a':motion.breach?'#ff675d':captain?'#f4c76c':deputy?'#7dc9ff':u.side?'#e1866d':'#8cbe9f';
  ctx.save();
  ctx.globalAlpha=u.hp?1:.60;
  ctx.fillStyle='#142019';
  ctx.beginPath();ctx.roundRect(left,top,width,height,5);ctx.fill();
  ctx.save();
  ctx.clip();
  const image=portraits[u.role];
  if(image?.complete&&image.naturalWidth){
    ctx.translate(center+motion.shake,top);
    if(u.side)ctx.scale(-1,1);
    if(!u.hp)ctx.filter='grayscale(100%) brightness(48%)';
    // Bleed past the clip so the shake never reveals an empty card edge.
    ctx.drawImage(image,-width/2-4,-2,width+8,height+4);
  }else{
    text(roles[u.role].icon,center,top+height*.62,19,border);
  }
  ctx.restore();
  if(motion.flash){
    const flash=ctx.createLinearGradient(left,0,left+width,0);
    flash.addColorStop(0,'rgba(255,54,54,'+motion.flash+')');
    flash.addColorStop(.16,'#ff454500');flash.addColorStop(.84,'#ff454500');
    flash.addColorStop(1,'rgba(255,54,54,'+motion.flash+')');
    ctx.fillStyle=flash;
    ctx.beginPath();ctx.roundRect(left,top,width,height,5);ctx.fill();
  }
  ctx.strokeStyle=border;ctx.lineWidth=captain||deputy||motion.breach?2:1;
  if(captain&&u.hp||motion.pulse){ctx.shadowColor=border;ctx.shadowBlur=motion.pulse?7+motion.pulse*9:7;}
  ctx.beginPath();ctx.roundRect(left,top,width,height,5);ctx.stroke();
  ctx.shadowBlur=0;
  ctx.fillStyle='#121815';ctx.fillRect(left,top-5,width,3);
  if(u.hp){ctx.fillStyle=u.side?'#ff9d7d':'#a1e1b8';ctx.fillRect(left,top-5,width*u.hp/u.max,3);}
  if((captain||deputy)&&u.hp)text(captain?'대장':'부대장',center,top-8,10,captain?'#ffdd8b':'#a9d9fe');
  text(u.name,center,top+height+12,11,u.side?'#ffb298':'#cbe5ce');
  ctx.restore();
}

function draw(){
  ground();
  artEffects(wallClock);
  if(isGroup(game?.mode??mode))frontLines();
  const preview=()=>({...Arena.create(battleConfig()), previewKey:JSON.stringify([lineup,terrain,mode,captain,deputy,loadout,opponent])});
  const view=game||idle|| (idle=preview());
  for(const u of [...view.units].sort((a,b)=>a.y-b.y)){
    const blend=isGroup(game?.mode)&&!game.finished?Math.min(1,elapsed/Arena.TICK):1;
    const x=u.prevX+(u.x-u.prevX)*blend,y=u.prevY+(u.y-u.prevY)*blend;
    if(u.shield>0||(u.barrier?.hp>0&&u.barrier.until>view.time))circle(x,y-10,24,'#94d4ff',false,2);
    card(u,x,y,view.leaders[u.side],game?visualTime:0);
    if(!game&&isGroup(mode)&&u.side===0&&(selected===u.id||drag?.member?.id===u.id)){
      ctx.strokeStyle='#ffe095';ctx.lineWidth=2;
      ctx.strokeRect(x-24,y-46,48,61);
    }
    if(u.cast&&!game?.finished){
      ctx.fillStyle='#191724';ctx.fillRect(x-15,y+24,30,3);
      ctx.fillStyle='#d6b0ff';ctx.fillRect(x-15,y+24,30*Math.max(0,1-(u.cast.until-view.time)/.45),3);
    }
    if(game&&u.hp&&u.tauntUntil>game.time){
      const guard=game.units.find(f=>f.id===u.tauntedBy&&f.hp);
      if(guard){stroke(x,y+8,guard.x,guard.y+8,'#ffc580ad',1);text('도발',x,y+38,13,'#ffc580');}
    }else if(game&&u.hp&&u.stun>game.time)text('행동 중단!',x,y+38,13,'#ff9aae');
    else if(game&&u.hp&&u.exposed>game.time)text(u.role==='bow'?'사수 노출!':'후열 침투!',x,y+46,13,'#ff967d');
    else if(game&&u.hp&&u.weak>game.time)text('방어력 감소!',x,y+46,12,'#e1b3ff');
    else if(game&&u.last==='heal'&&game.effects.some(e=>e.tx===u.x&&e.ty===u.y&&e.kind==='heal'&&visualTime-e.at<.65))
      text('체력 회복!',x,y+46,12,'#a9ffc6');
  }
  if(!game&&drag?.moved){
    const {x,y}=drag.point;
    circle(x,y,11,Arena.canDeploy(terrain,x,y)?'#ffd896':'#fd7164',false,3);
    stroke(x-5,y,x+5,y,'#fff0d1',1);
    stroke(x,y-5,x,y+5,'#fff0d1',1);
  }
  ctx.globalAlpha=1;
  effects(visualTime);
  const recentAlarms=game?.milestones.filter(row=>visualTime-row.time<2.5)||[];
  const alarm=recentAlarms.findLast(row=>row.type==='break'&&visualTime-row.time<1.05)||recentAlarms.findLast(row=>['break','infiltrate'].includes(row.type));
  el('alarm').hidden=!alarm;
  if(alarm)el('alarm').textContent=alarm.type==='break'?'⚠ '+alarm.text.split('!')[0]+'!':'⚠ 후열 침투!';
}
let idle=null;
function frame(now){
  wallClock=now;
  const delta=Math.min(.1,(now-(last||now))/1000);last=now;
  if(game&&isGroup(game.mode)&&!game.finished){
    elapsed+=delta*(now<slowUntil?.2:speed);
    while(elapsed>=Arena.TICK&&!game.finished){
      Arena.tick(game);elapsed-=Arena.TICK;refresh();
      const previous=seenArts;readArtEvents(now);
      if(previous!==seenArts)break;
    }
    visualTime=game.time+elapsed;
  }else if(game&&!isGroup(game.mode)&&!game.finished){
    if(Arena.current(game).side===1&&now>=enemyAt){Arena.enemyTurn(game);visualTime=game.time;enemyAt=now+350/speed;refresh();}
    visualTime=Math.max(game.time,visualTime+delta*speed);
  }else visualTime+=delta*speed;
  if(!game&&idle?.previewKey!==JSON.stringify([lineup,terrain,mode,captain,deputy,loadout,opponent]))idle=null;
  renderCutins(now);draw();requestAnimationFrame(frame);
}
setup();refresh();requestAnimationFrame(frame);

function prepareCampaignBattle({config,progression,heading}) {
  if(campaign&&(!practiceTactics()||game))return;
  campaign=config;
  const autoWatch=config.observer||progression==='auto';
  document.querySelector('.preparation').hidden=autoWatch;
  el('edit').hidden=autoWatch;
  el('replay').hidden=autoWatch;
  document.querySelector('.heading h1').textContent=heading??'전투';
  document.querySelector('.overline').textContent=campaign.zoneName
    ? [campaign.tier==null?'':campaign.tier+'부',campaign.zoneName].filter(Boolean).join(' · ')
    : '리그 일정';
  document.querySelector('.bar').hidden=true;
  ({terrain,mode}=campaign);
  selected=null;
  swapTarget=null;pendingBench=null;
  lineup=campaign.team.map(member=>({...member}));
  defenseLineup=(campaign.defenseTeam||[]).map(member=>({...member}));
  formationDirty=false;formationPending=false;pendingTransfer=null;
  captain=campaign.captain;
  deputy=campaign.deputy;
  chosenArts=[...(config.chosenArts||baseArts)];
  tacticDirty=false;tacticSavePending=false;
  document.querySelector('.modes').hidden=true;
  for(const id of ['terrain','scenario']) {
    el(id).value=id==='terrain'?terrain:campaign.scenario??'attack';
    el(id).disabled=id==='terrain'||config.kind!=='training';
  }
  setup();
  if(config.kind==='training'){
    el('tactics-save-status').textContent=(config.planMode==='defense'?'방어전':'점령전')+
      ' 전술 편성 · 다른 임무/부상 포함 전체 문파원을 교체 후보로 사용할 수 있습니다.';
  }
  if(autoWatch){
    el('mode-label').textContent=mode+'대'+mode+' · 자동 관전';
    start(battleConfig());
  }else{
    el('mode-label').textContent=mode+'대'+mode+' · 수동 편성';
    ready();
  }
}

if (window.parent !== window) {
  window.addEventListener('message',event=>{
    if(event.origin===location.origin&&event.source===window.parent&&
       event.data?.type==='moonpa-arena-plan-switch-result'){
      if(event.data.error){
        el('scenario').value=campaign.planMode;
        el('scenario').disabled=false;
        el('tactics-save-status').textContent='전술 전환 실패: '+event.data.error;
      }else{
        prepareCampaignBattle({config:event.data.config,progression:'manual',heading:event.data.heading});
      }
      return;
    }
    if(event.origin===location.origin&&event.source===window.parent&&
       event.data?.type==='moonpa-arena-plan-result'){
      tacticSavePending=false;
      if(event.data.error){
        el('tactics-save-status').textContent='저장 실패: '+event.data.error;
      }else{
        tacticDirty=false;
        campaign=event.data.config;
        el('tactics-save-status').textContent=event.data.message||'실제 전술을 저장했습니다.';
      }
      el('tactics-save-btn').disabled=Boolean(game);
      return;
    }
    if(event.origin===location.origin&&event.source===window.parent&&
       event.data?.type==='moonpa-group-assignment-result'){
      receiveAssignment(event.data);return;
    }
    if(event.origin===location.origin&&event.source===window.parent&&event.data?.type==='moonpa-group-error'){
      const button=el('result-continue');
      if(button)button.disabled=false;
      const modal=el('br-confirm');
      if(modal)modal.disabled=false;
      return;
    }
    if(event.origin!==location.origin||event.source!==window.parent||event.data?.type!=='moonpa-group-config')return;
    prepareCampaignBattle(event.data);
  });
  window.parent.postMessage({type:'moonpa-group-ready'},location.origin);
}

