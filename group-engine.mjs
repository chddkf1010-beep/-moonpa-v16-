export const isGroup = mode => mode === 8 || mode === 10;
export const Arena = (() => {
  const terrains = {
    field:{name:'평야',hint:'넓은 개활지 · 전 구간 이동·사격 가능',width:1140,front:5,back:3,y:[.20,.35,.50,.65,.80]},
    forest:{name:'숲길',hint:'나무 군락이 시야를 가림 · 네 갈래 숲길로 우회',width:1020,front:4,back:4,y:[.26,.39,.62,.76],
      barrier:{left:416,right:484,halfOpening:17}},
    mountain:{name:'산악',hint:'암벽을 끼고 세 산길로 이동 · 중턱을 벗어나 우회',width:960,front:3,back:5,y:[.23,.5,.77],
      barrier:{left:397,right:503,halfOpening:14}},
    river:{name:'수변',hint:'강과 나루 · 나루에서만 건널 수 있음',width:900,front:4,back:4,y:[.25,.37,.63,.75],
      barrier:{left:413,right:487,halfOpening:11}},
    gate:{name:'성곽',hint:'좁은 전장 · 성벽의 세 관문이 이동·사격 통로',width:720,front:3,back:5,y:[.34,.50,.66],
      barrier:{left:431,right:469,halfOpening:9}},
    gorge:{name:'협곡',hint:'가장 좁은 전장 · 협곡 중앙의 두 길로 진입',width:660,front:2,back:6,y:[.44,.56],
      barrier:{left:406,right:494,halfOpening:14}}
  };
  function battlefield(key, mode) {
    const terrain = terrains[key];
    return mode === 10 ? {...terrain, front:5, back:5, y:terrains.field.y} : terrain;
  }
  const roles = {
    guard:{name:'수호',icon:'盾',hp:208,power:17,range:42,pace:20,agility:4},
    blade:{name:'무인',icon:'劍',hp:178,power:24,range:43,pace:28,agility:7},
    bow:{name:'사수',icon:'弓',hp:110,power:34,range:270,pace:15,agility:9},
    hex:{name:'주술',icon:'符',hp:108,power:26,range:226,pace:15,agility:6},
    heal:{name:'치유',icon:'藥',hp:112,power:20,range:240,pace:15,agility:5},
    dash:{name:'암살',icon:'影',hp:121,power:34,range:42,pace:34,agility:11}
  };
  const skills = {
    sword:{name:'파군격',kind:'strike',aim:'foe',hint:'강한 근접 공격',factor:1.18},
    arrow:{name:'관월시',kind:'arrow',aim:'foe',hint:'원거리 관통 사격',factor:1.08},
    curse:{name:'쇄맥부',kind:'hex',aim:'foe',hint:'방어 약화와 행동 둔화',factor:.65},
    mend:{name:'회춘결',kind:'heal',aim:'ally',hint:'아군 체력 회복',factor:1},
    taunt:{name:'철벽 도발',kind:'taunt',aim:'foe',hint:'주변 적이 잠시 수호자를 공격',factor:0},
    ambush:{name:'그림자 기습',kind:'ambush',aim:'foe',hint:'후열의 시전과 사격을 끊음',factor:1.12},
    ward:{name:'호신진',kind:'shield',aim:'ally',hint:'아군 보호막',factor:1},
    link:{name:'합격술',kind:'link',aim:'foe',hint:'아군이 남긴 표식에 추가 피해',factor:.89}
  };
  const roster=[
    ['진무혁','blade'],['철무진','guard'],['백소연','heal'],['서린','hex'],
    ['설궁','bow'],['흑영','dash'],['도윤','guard'],['연비','bow'],['문태산','blade'],['유초희','hex']
  ].map(([name,role],id)=>({id,name,role}));
  const rivals=[
    ['적무결','blade'],['석건','guard'],['월하','heal'],['적련','hex'],
    ['한조','bow'],['야귀','dash'],['우강','guard'],['유설','bow'],['묵산','blade'],['하설','hex']
  ].map(([name,role],id)=>({id:id+20,name,role}));
  const playerPresets = {
    balanced:{name:'균형 편성',roleList:null,hint:'수호 2 · 사수 2 · 치유 1 · 암살 1'},
    hold:{name:'수호·치유 중심',roleList:['guard','guard','heal','hex','bow','blade','guard','heal'],hint:'수호 3 · 치유 2 · 암살 없음'},
    raid:{name:'사수·암살 중심',roleList:['blade','guard','heal','hex','bow','dash','dash','bow'],hint:'수호 1 · 사수 2 · 암살 2'}
  };
  const foesPresets = {
    tang:{name:'당문',roleList:['dash','guard','heal','hex','bow','dash','bow','bow'],arts:['rain','poison']},
    shaolin:{name:'소림',roleList:['guard','guard','heal','hex','bow','blade','guard','heal'],arts:['lotus','mercy']},
    wudang:{name:'무당',roleList:['blade','guard','heal','hex','bow','hex','blade','bow'],arts:['wall','silence']}
  };
  const newMembers=['강현','연강','설아','도화','진연','한묵','연진','소하'];
  const rivalNames={
    tang:['당무결','당석건','당월하','당적련','당한조','당야귀','당우강','당유설'],
    shaolin:['혜명','법산','명월','원각','지운','무진','법현','혜광'],
    wudang:['청현','원진','설운','자허','담송','무진','청하','백학']
  };
  const playerTeam=(key='balanced', mode=8)=>roster.slice(0,mode).map((f,i)=>{
    const role=playerPresets[key].roleList?.[i];
    return role&&role!==f.role?{id:i+(key==='hold'?40:60),name:newMembers[i],role}:{...f};
  });
  function enemyTeam(key,terrain,mode=8){
    if(!isGroup(mode))return place(rivals.slice(0,mode),{front:Math.ceil(mode/2)});
    return place(rivals.slice(0,mode).map((f,i)=>({...f,name:rivalNames[key][i]??f.name,role:foesPresets[key].roleList[i]??f.role})),terrain);
  }
  const defaults = {guard:'ward',blade:'sword',bow:'arrow',hex:'curse',heal:'mend',dash:'link'};
  const usedSkill = {guard:['ward','sword'],blade:['sword','link'],bow:['arrow','link'],hex:['curse','arrow'],heal:['mend','ward','sword'],dash:['link','sword']};
  const commandRules={captainShield:12,defenseCaptainShield:20,moraleLoss:.14,deputyShield:18,deputyHeal:.28};
  function leadershipPreview({team,mode,captain,deputy,scenario,loadout,chosenArts}){
    const group=isGroup(mode);
    const describe=(key,id)=>{
      const member=team.find(u=>u.id===id);
      if(!member)return null;
      const usesHeal=(group?usedSkill[member.role]:loadout).includes('mend');
      const baseHeal=(group?25:37)*(member.role==='heal'?1.15:1);
      const keys=key==='captain'?['swordlight','turtle','escort']:['swordlight','medic','wedge'];
      return {
        name:member.name,line:member.line,role:roles[member.role].name,hp:Math.round(roles[member.role].hp*(member.strength??1)),
        startingShield:group?(scenario==='defense'?commandRules.defenseCaptainShield:commandRules.captainShield):0,
        moraleLoss:Math.round(commandRules.moraleLoss*100),deputyShield:group?commandRules.deputyShield:0,
        healed:usesHeal?[Math.round(baseHeal),Math.round(baseHeal*(1+commandRules.deputyHeal))]:null,
        artLinks:group?chosenArts.filter(art=>keys.includes(art)).map(art=>arts[art]):[]
      };
    };
    return {captain:describe('captain',captain),deputy:describe('deputy',deputy)};
  }
  const TICK=.15;
  const active=(g,side)=>g.units.filter(u=>u.side===side&&u.hp>0);
  const distance=(a,b)=>Math.hypot((a.x-b.x)*(a.xScale??1),a.y-b.y);
  const frontOrder = ['guard','blade','dash','hex','bow','heal'];
  function place(team,terrain) {
    const sorted=[...team].sort((a,b)=>frontOrder.indexOf(a.role)-frontOrder.indexOf(b.role));
    return sorted.map((u,i)=>({...u,line:i<terrain.front?'front':'back',slot:i<terrain.front?i:i-terrain.front}));
  }
  function obstruction(key) {
    const terrain=terrains[key];
    return terrain.barrier ? {...terrain.barrier,openings:terrain.y.map(lane=>lane*430)} : null;
  }
  function walkable(wall,x,y) {
    return !wall||x<wall.left||x>wall.right||
      wall.openings.some(center=>Math.abs(y-center)<=wall.halfOpening);
  }

  function clearPath(wall,from,to) {
    if(!wall)return true;
    const minX=Math.max(wall.left,Math.min(from.x,to.x));
    const maxX=Math.min(wall.right,Math.max(from.x,to.x));
    if(minX>maxX)return true;
    const at=x=>from.y+(to.y-from.y)*(x-from.x)/(to.x-from.x);
    const entry=from.x===to.x?from.y:at(minX);
    const exit=from.x===to.x?to.y:at(maxX);
    return wall.openings.some(center=>Math.max(Math.abs(entry-center),Math.abs(exit-center))<=wall.halfOpening);
  }

  function detour(wall,from,to) {
    if(clearPath(wall,from,to))return to;
    // Compare routes through each opening, including the distance on both banks.
    let best=null, length=Infinity;
    for(const y of wall.openings){
      const bank=x=>x<wall.left?wall.left-2:x>wall.right?wall.right+2:x;
      const entry={x:bank(from.x),y};
      const exit={x:bank(to.x),y};
      const cost=distance(from,entry)+Math.hypot((entry.x-exit.x)*from.xScale,entry.y-exit.y)+distance({...from,...exit},to);
      const waypoint=[entry,exit,to].find(point=>Math.hypot(point.x-from.x,point.y-from.y)>.1);
      if(cost<length&&waypoint&&clearPath(wall,from,waypoint)){
        best=waypoint;
        length=cost;
      }
    }
    // A destination in the barrier has no traversable route.
    return best??from;
  }

  function canDeploy(key,x,y) {
    return Number.isFinite(x)&&Number.isFinite(y)&&x>=25&&x<=450&&y>=78&&y<=392&&
      walkable(obstruction(key),x,y);
  }
  function deployPoint(f, terrain) {
    if(f.position)return f.position;
    const front=f.line==='front';
    const y=front?(terrain.y[f.slot]??.5):.18+.64*(f.slot+1)/(terrain.back+1);
    return {x:front?318:192,y:y*430};
  }
  function unit(f,side,i,count,terrain,mode) {
    const role=roles[f.role], front=f.line==='front';
    const hp=Math.round(role.hp*(f.strength??1));
    const point=isGroup(mode)?deployPoint({...f,slot:i},terrain):
      {x:front?318:192,y:(.18+.64*(i+1)/(count+1))*430};
    const x=side?900-point.x:point.x, y=point.y;
    return {...f,side,slot:i,x,y,xScale:isGroup(mode)?terrain.width/900:1,homeX:x,homeY:y,hp,max:hp,
      prevX:x,prevY:y,shield:0,weak:0,mark:0,exposed:0,tauntUntil:0,tauntAt:1.5,stun:0,mods:{},
      actAt:-10,attackAt:-10,hitAt:-10,breachedAt:-10,facing:side?-1:1,cd:side?.02*i:.08*i,actions:0,hitTaken:0,damage:0,healing:0,kills:0,shieldGiven:0,absorbed:0};
  }
  function create({team, terrain='field', mode=8, captain, deputy, scenario='attack', loadout, chosenArts=baseArts, opponent='tang', enemyRoster, sectNames, enemyArts, enemyTactic=null, teamTactic=null, enemyCaptain=null, enemyDeputy=null}) {
    const t=battlefield(terrain,mode);
    const enemy=enemyRoster??enemyTeam(opponent,t,mode);
    if(mode===1) enemy[0].line='front';
    const make=(members,side)=>['front','back'].flatMap(line=>{
      const group=members.filter(f=>f.line===line);
      return group.map((f,i)=>unit(f,side,isGroup(mode)?(f.slot??i):i,group.length,t,mode));
    });
    const g={t,terrain,wall:isGroup(mode)?obstruction(terrain):null,mode,scenario,time:0,ticks:0,units:[...make(team,0),...make(enemy,1)],
      loadout, leaders:[{captain,deputy},{captain:enemyCaptain??(enemyRoster?enemy[0]?.id:20),deputy:enemyDeputy??(enemyRoster?enemy[1]?.id:21)}],
      tactics:[teamTactic,enemyTactic],
      fronts:[{x:390,broken:false},{x:510,broken:false}], effects:[],log:[],milestones:[],
      round:1,turn:0,order:[],events:[],winner:null,finished:false,reason:''};
    g.opponent=opponent;g.sectNames=sectNames??[sects[0],isGroup(mode)?foesPresets[opponent].name:'적련회'];
    g.arts=[Array.from(new Set(chosenArts.filter(k=>arts[k]))).slice(0,2),enemyArts??foesPresets[opponent].arts];
    g.lanes=[0,1].map(side=>{
      const lanes=t.y.map(y=>({y:y*430,open:false,units:[]}));
      for(const u of g.units.filter(u=>u.side===side&&u.line==='front')){
        const lane=lanes.reduce((best, candidate)=>
          Math.abs(candidate.y-u.y)<Math.abs(best.y-u.y)?candidate:best);
        lane.units.push(u.id);
      }
      return lanes;
    });
    g.skillCounts=[{},{}];g.taunts=[0,0];g.rearStrikes=[0,0];
    g.artEvents=[];g.used=[new Set(),new Set()];g.wounds=[[],[]];
    g.initial=[0,1].map(side=>active(g,side).length);
    g.frontMax=[0,1].map(side=>active(g,side).filter(u=>u.line==='front').reduce((sum,u)=>sum+u.max,0));
    if(!isGroup(mode)) nextRound(g);
    else {
      for(const u of g.units) if(u.id===g.leaders[u.side].captain)
        u.shield=scenario==='defense'&&u.side===0?commandRules.defenseCaptainShield:commandRules.captainShield;
      note(g,scenario==='defense'?'수비대가 점령지를 지킵니다.':'양측 전열이 전진합니다.');
    }
    return g;
  }
  function note(g,text,type='info',side=null) {
    g.log.push({time:g.time,round:g.round,text,type,side});
    if(type==='break'||type==='infiltrate'||type==='leader'||type==='result') g.milestones.push(g.log.at(-1));
  }
  function skillOptions(g,u) {
    return isGroup(g.mode)||u.side?usedSkill[u.role]:g.loadout;
  }
  function targetList(g,u,key) {
    return active(g, skills[key].aim==='ally'?u.side:1-u.side);
  }
  function apply(g,u,v,key) {
    const s=skills[key], role=roles[u.role], leader=g.leaders[u.side];
    v.last=s.kind;
    u.actAt=g.time;u.action=s.kind;u.facing=v.x===u.x?u.facing:Math.sign(v.x-u.x);
    const factor=key===defaults[u.role]?1.15:1;
    let value=0,contact=false;
    if(s.kind==='heal'){
      const bonus=leader.deputy===u.id?1+commandRules.deputyHeal:1;
      value=healing(g,v,(isGroup(g.mode)?25:37)*bonus*factor,u);
    } else if(s.kind==='shield'){
      value=Math.min(55-v.shield,Math.round(30*factor));
      v.shield+=value;
      u.shieldGiven+=value;
    } else {
      u.attackAt=g.time;
      const marked=v.mark>g.time;
      const morale=active(g,u.side).some(f=>f.id===leader.captain)?1:1-commandRules.moraleLoss;
      let amount=Math.round((role.power*(u.strength??1)*s.factor+(s.kind==='link'&&marked?16:0))*
        factor*morale*(1+mod(g,u,'power'))*(1-mod(g,u,'powerDown'))*(v.weak>g.time?1.24:1)*(u.weak>g.time?.87:1)*(v.role==='guard'?.83:1));
      if(s.kind==='hex'){
        const fresh=v.weak<=g.time;
        v.weak=g.time+(isGroup(g.mode)?3.4:2.2);
        if(isGroup(g.mode)&&fresh) note(g,u.name+' · 쇄맥부 → '+v.name+' 방어 약화','skill');
      }
      if(s.kind==='link'||s.kind==='strike') v.mark=g.time+3;
      if(mod(g,u,'wedge')&&v.line==='back'&&!u.wedgeHit){u.wedgeHit=true;amount=Math.round(amount*1.25);}
      if(mod(g,u,'miss')&&((g.ticks*71+u.id*29+u.actions*37)%100)/100<mod(g,u,'miss')){
        amount=0;
        g.effects.push({kind:'miss',x:u.x,y:u.y,tx:v.x,ty:v.y,at:g.time});
      }
      const hp=v.hp,shield=v.shield+(v.barrier?.hp??0);
      value=hit(g,v,amount,u);
      contact=v.hp<hp||v.shield+(v.barrier?.hp??0)<shield;
      if(s.kind==='ambush'&&contact&&v.hp){
        disable(g,v,g.time+1.35);
        note(g,u.name+' · 그림자 기습 → '+v.name+' 행동 중단','infiltrate',v.side);
      }
    }
    if(isGroup(g.mode)){
      const counts=g.skillCounts[u.side];
      counts[key]=(counts[key]||0)+1;
      if(contact&&v.line==='back'&&['dash','blade','guard'].includes(u.role)&&
        (g.fronts[v.side].broken||u.breachLane||u.flank==='strike'||mod(g,u,'wedge'))){
        g.rearStrikes[u.side]++;
        if(v.exposed<=g.time)v.breachedAt=g.time;
        v.exposed=g.time+2.8;
        if(!g.fronts[v.side].rearHit){
          g.fronts[v.side].rearHit=true;
          note(g,u.name+' → '+v.name+' 후열 첫 피격','infiltrate',v.side);
        }
      }
      const description=s.kind==='heal'?'체력 +'+value:s.kind==='shield'?'보호막 +'+value:
        '체력 피해 '+value+(s.kind==='hex'?' · 방어 약화':'');
      note(g,u.name+' · '+s.name+' → '+v.name+' · '+description,'personal',u.side);
    }
    const announce=!['strike','arrow'].includes(s.kind)||!isGroup(g.mode)||g.time>=(u.announceAt??0);
    if(announce)u.announceAt=g.time+3.8;
    g.effects.push({kind:s.kind,x:u.x,y:u.y,tx:v.x,ty:v.y,value,at:g.time,name:announce?s.name:null,actor:u.id});
    if(!isGroup(g.mode)) note(g,u.name+' → '+v.name+' · '+s.name+' '+value);
  }
  function finish(g) {
    const a=active(g,0),b=active(g,1),limit=isGroup(g.mode)?g.time>=49:g.round>20;
    if(a.length&&b.length&&!limit) return false;
    const strength=team=>team.reduce((sum,u)=>sum+u.hp,0);
    g.finished=true;
    g.winner=strength(a)===strength(b)?-1:strength(a)>strength(b)?0:1;
    g.reason=limit?'제한 시간 · 잔존 체력 판정':'한쪽 진영 전투불능';
    note(g,g.reason,'result');return true;
  }
  function move(g,u,x,y,step) {
    x=Math.max(25,Math.min(875,x));y=Math.max(78,Math.min(392,y));
    if(!walkable(g.wall,x,y)){
      x=x<(g.wall.left+g.wall.right)/2 ? g.wall.left-2 : g.wall.right+2;
    }
    const next=detour(g.wall,u,{x,y});
    if(Math.abs(next.x-u.x)>1)u.facing=Math.sign(next.x-u.x);
    const gap=distance(u,next);
    if(gap>.001){
      const fraction=Math.min(1,step/gap);
      u.x+=(next.x-u.x)*fraction;
      u.y+=(next.y-u.y)*fraction;
    }
  }
  function target(g,u) {
    const own=active(g,u.side),foes=active(g,1-u.side);
    const open=g.fronts[1-u.side].broken || Boolean(u.breachLane);
    const melee=['guard','blade','dash'].includes(u.role);
    const back=foes.filter(f=>f.line==='back');
    const front=foes.filter(f=>f.line==='front');
    const raider=isGroup(g.mode)&&u.role==='guard'&&u.line==='back'&&
      foes.filter(f=>f.role==='dash'&&f.flank&&distance(f,u)<=125)
          .sort((a,b)=>distance(a,u)-distance(b,u))[0];
    const pool=raider?[raider]:isGroup(g.mode)&&open&&back.length?back:front.length?front:foes;
    const visible=pool.filter(f=>f.flank!=='edge'&&f.flank!=='cross');
    const closest=(isGroup(g.mode)&&visible.length?visible:pool).sort((a,b)=>distance(a,u)-distance(b,u))[0];
    const kit=skillOptions(g,u);
    if(isGroup(g.mode)){
      const doctrine=g.tactics?.[u.side]?.id||'balanced';
      const forced=u.tauntUntil>g.time&&foes.find(f=>f.id===u.tauntedBy);
      if(forced)return [forced,attackSkill(u,kit,melee)];
      // The behavior below changes choices, not just labels or art animations.
      // Use reachable tactical priorities and retain taunt/formation overrides.
      if(doctrine==='ironwall'&&u.role==='guard'&&kit.includes('ward')){
        const friends=own.filter(f=>f.id!==u.id&&f.shield<20&&
          (f.hp/f.max<.90||(f.role==='heal'&&f.hp/f.max<.98)));
        const ally=friends.sort((a,b)=>Number(b.role==='heal')-Number(a.role==='heal')||
          a.hp/a.max-b.hp/b.max||a.id-b.id)[0];
        if(ally&&distance(u,ally)<225)return [ally,'ward'];
      }
      if(doctrine==='archery'&&['bow','hex'].includes(u.role)){
        const ranged=foes.filter(f=>f.flank!=='edge'&&f.flank!=='cross');
        const marked=[...ranged].sort((a,b)=>
          Number(b.role==='heal'||b.role==='hex')-Number(a.role==='heal'||a.role==='hex')||
          a.hp/a.max-b.hp/b.max||distance(a,u)-distance(b,u))[0];
        if(marked&&distance(u,marked)<roles[u.role].range*1.2)
          return [marked,u.role==='hex'&&kit.includes('curse')?'curse':attackSkill(u,kit,false)];
      }
      if(doctrine==='disrupt'&&['hex','bow'].includes(u.role)){
        const disrupt=foes.filter(f=>['heal','hex','bow'].includes(f.role)&&
          f.flank!=='edge'&&f.flank!=='cross');
        const victim=[...disrupt].sort((a,b)=>
          Number(b.role==='heal')-Number(a.role==='heal')||
          a.hp/a.max-b.hp/b.max||distance(a,u)-distance(b,u))[0];
        if(victim&&distance(u,victim)<roles[u.role].range*1.25)
          return [victim,u.role==='hex'&&kit.includes('curse')?'curse':attackSkill(u,kit,false)];
      }
      if(doctrine==='breakthrough'&&melee&&front.length&&!(u.flank==='strike')){
        const weakest=[...front].sort((a,b)=>
          a.hp/a.max-b.hp/b.max||Number(b.role==='guard')-Number(a.role==='guard')||
          distance(a,u)-distance(b,u))[0];
        if(weakest)return [weakest,attackSkill(u,kit,true)];
      }
      if(doctrine==='adaptive'&&['bow','hex'].includes(u.role)&&front.length){
        const vulnerable=[...front].sort((a,b)=>a.hp/a.max-b.hp/b.max||a.id-b.id)[0];
        if(vulnerable&&vulnerable.hp/vulnerable.max<.7)
          return [vulnerable,u.role==='hex'&&kit.includes('curse')?'curse':attackSkill(u,kit,false)];
      }
      if((mod(g,u,'wedge')||u.breachLane)&&back.length)
        return [[...back].sort((a,b)=>distance(a,u)-distance(b,u))[0],attackSkill(u,kit,melee)];
      if(u.role==='hex'){
        const priority=front.filter(f=>f.weak<=g.time&&distance(u,f)<roles.hex.range*1.15);
        if(priority.length)return [priority.sort((a,b)=>a.hp/a.max-b.hp/b.max||distance(a,u)-distance(b,u))[0],'curse'];
        const others=foes.filter(f=>f.role!=='hex');
        if(others.length)return [others.sort((a,b)=>distance(a,u)-distance(b,u))[0],'arrow'];
      }
      if(u.flank==='strike'){
        const victims=back.filter(f=>['bow','hex','heal'].includes(f.role));
        if(victims.length)return [victims.sort((a,b)=>distance(a,u)-distance(b,u))[0],
          u.ambushed?attackSkill(u,kit,melee):'ambush'];
      }
    }
    const healing=own.filter(f=>f.hp/f.max<.8).sort((a,b)=>
      (a.hp/a.max-(a.line==='front'||a.id===g.leaders[u.side].captain?.10:0))-
      (b.hp/b.max-(b.line==='front'||b.id===g.leaders[u.side].captain?.10:0)))[0];
    if(u.role==='heal'&&healing&&kit.includes('mend')&&(!isGroup(g.mode)||distance(u,healing)<=225)) return [healing,'mend'];
    if((u.role==='guard'||u.role==='heal')&&healing&&healing.shield<8&&kit.includes('ward')&&u.actions%3===1) return [healing,'ward'];
    return [closest,attackSkill(u,kit,isGroup(g.mode)&&melee)];
  }
  function attackSkill(u,kit,melee){
    const offense=kit.filter(key=>skills[key].aim==='foe');
    const allowed=melee?offense.filter(k=>k==='sword'||k==='link'):offense;
    return allowed.includes(defaults[u.role])?defaults[u.role]:allowed[0]||'sword';
  }
  function tauntRange(u,f){
    return u.line==='back'&&f.role==='dash'&&f.flank?132:105;
  }
  function threatened(g,u,f){
    return f.role==='dash'&&f.flank || (u.side===0?f.x<275:f.x>625)
      || g.fronts[u.side].broken;
  }
  function tauntCandidates(g,u,foes){
    const rear=u.line==='back';
    return foes.filter(f=>distance(u,f)<=tauntRange(u,f)
      && (f.tauntUntil<=g.time||!active(g,u.side).some(a=>a.id===f.tauntedBy))
      && (!rear||threatened(g,u,f))&&clearPath(g.wall,u,f))
      .sort((a,b)=>Number(b.role==='dash')-Number(a.role==='dash')||distance(u,a)-distance(u,b));
  }
  function tauntStatus(g,u){
    if(!u.hp)return '전투불능';
    if(u.stun>g.time)return '행동 중단';
    if(u.tauntAt>g.time)return '재사용 '+(u.tauntAt-g.time).toFixed(1)+'초';
    return tauntCandidates(g,u,active(g,1-u.side)).length?'사거리 내 적 감지':
      (u.line==='back'?'후열 호위 · 사거리 내 침입자 없음':'사거리 내 도발 대상 없음');
  }
  function taunt(g,u,foes){
    if(u.role!=='guard'||g.time<u.tauntAt)return;
    const nearby=tauntCandidates(g,u,foes).slice(0,2);
    if(!nearby.length)return;
    u.tauntAt=g.time+7;u.actAt=g.time;u.action='taunt';
    g.taunts[u.side]++;
    for(const f of nearby){
      f.tauntedBy=u.id;f.tauntUntil=g.time+2.4;
      if(f.cast&&skills[f.cast.key].aim==='foe')f.cast=null;
      g.effects.push({kind:'taunt',x:u.x,y:u.y,tx:f.x,ty:f.y,at:g.time,name:'철벽 도발',actor:u.id});
    }
    note(g,u.name+' · 철벽 도발 → '+nearby.map(f=>f.name).join(', ')+'의 공격 대상 변경','skill',u.side);
  }
  function laneState(g){
    for(let side=0;side<2;side++)for(const lane of g.lanes[side]){
      const open=g.time>2&&!active(g,side).some(u=>u.line==='front'&&
        (lane.units.includes(u.id)||Math.abs(u.y-lane.y)<21));
      if(open&&!lane.open&&lane.units.length){
        note(g,(side?'적':'아군')+' 전열 · '+(lane.y<172?'상단':lane.y>258?'하단':'중앙')+' 통로 개방','gap',side);
      }
      lane.open=open;
    }
  }
  function useBreach(g,u,foes){
    if(!['blade','dash'].includes(u.role)||u.tauntUntil>g.time||u.line!=='front')return;
    // Defensive schools hold their line instead of making routine raids.
    if(['ironwall','archery'].includes(g.tactics?.[u.side]?.id))return;
    if(u.breachLane&&!u.breachLane.open&&((u.x-450)*(u.side?-1:1)<18))u.breachLane=null;
    if(u.breachLane||u.flank||!foes.some(v=>v.line==='back'))return;
    const lanes=g.lanes[1-u.side];
    u.breachLane=lanes.find(l=>l.open&&Math.abs(l.y-u.y)<62)||null;
  }
  function flank(g,u,foes){
    if(g.tactics?.[u.side]?.id==='ironwall')return false;
    const infiltration=g.tactics?.[u.side]?.id==='flank';
    if(u.role!=='dash'||g.time<(infiltration?.25:.55)||u.tauntUntil>g.time||u.flank==='strike'||
       !foes.some(f=>f.line==='back'&&['bow','hex','heal'].includes(f.role)))return false;
    const dir=u.side?-1:1;
    if(!u.flank){
      u.flank='edge';u.flankY=u.y<215?106:360;
      note(g,u.name+' 측면 우회 시작','skill');
    }
    const crossing=g.wall?(u.flankY<215?g.wall.openings[0]:g.wall.openings.at(-1)):u.flankY;
    const waypoint=u.flank==='edge'?[u.homeX,crossing]:[450+dir*(g.t.width<=720?88:135),crossing];
    move(g,u,...waypoint,roles.dash.pace*TICK*(g.t.width<=720?1.8:2.65)*(infiltration?1.13:1));
    if(Math.hypot(u.x-waypoint[0],u.y-waypoint[1])<3)u.flank=u.flank==='edge'?'cross':'strike';
    if(g.ticks%3===0)g.effects.push({kind:'trail',actor:u.id,x:u.prevX,y:u.prevY,tx:u.x,ty:u.y,at:g.time});
    return true;
  }
  function tick(g) {
    if(g.finished||!isGroup(g.mode))return;
    g.time=++g.ticks*TICK;
    g.effects=g.effects.filter(e=>g.time-e.at<1.25);
    periodic(g);updateArts(g);
    for(let side=0;side<2;side++){
      const own=active(g,side), front=own.filter(u=>u.line==='front');
      const initial=g.units.filter(u=>u.side===side&&u.line==='front').length;
      const stamina=front.reduce((sum,u)=>sum+u.hp/u.max*(1-mod(g,u,'pressure')),0);
      const edge=g.fronts[side];
      const stress=1-stamina/Math.max(1,initial);
      edge.x=(side?510:390)+(side?1:-1)*Math.max(0,stress-.22)*120;
      if(!edge.broken&&g.time>4&&(!front.length||(stress>.66&&front.length<=Math.ceil(initial/2)))){
        edge.broken=true;
        const deputy=own.find(u=>u.id===g.leaders[side].deputy);
        if(deputy){
          for(const ally of own.filter(u=>u.line==='back')){
            ally.shield=Math.min(55,ally.shield+commandRules.deputyShield);
            g.effects.push({kind:'shield',x:deputy.x,y:deputy.y,tx:ally.x,ty:ally.y,value:commandRules.deputyShield,at:g.time});
          }
          note(g,deputy.name+' 부대장 · 비상 보호막 전개','leader',side);
        }
        note(g,(side?'적군':'아군')+' 전열 붕괴! 후열로 진입할 길이 열렸습니다.','break',side);
      }
    }
    laneState(g);
    for(const u of g.units){u.prevX=u.x;u.prevY=u.y;}
    const living=g.units.filter(u=>u.hp>0);
    const guards=living.filter(u=>u.role==='guard'&&u.stun<=g.time)
      .sort((a,b)=>Number(b.line==='back')-Number(a.line==='back'));
    for(const u of guards)taunt(g,u,active(g,1-u.side));

    for(const u of [...living].sort((a,b)=>((a.id+g.ticks)%2)-((b.id+g.ticks)%2))){
      if(u.hp<=0||u.stun>g.time)continue;
      const foes=active(g,1-u.side);
      if(!foes.length)break;
      if(flank(g,u,foes))continue;
      useBreach(g,u,foes);
      if(u.cast){
        if(g.time+1e-7>=u.cast.until){
          const {id,key}=u.cast;
          u.cast=null;
          const victim=g.units.find(v=>v.id===id&&v.hp);
          if(victim)execute(g,u,victim,key);
        }
        continue;
      }
      if(u.order?.until>g.time){
        move(g,u,u.order.x,u.order.y,roles[u.role].pace*TICK*2.4);
        continue;
      }
      const [v,key]=target(g,u);
      if(!v)continue;
      const s=skills[key],role=roles[u.role];
      const range=(s.aim==='ally'?225:key==='ambush'?53:role.range)*(1+mod(g,u,'range'));
      const dir=u.side?-1:1;
      const broken=g.fronts[u.side].broken;
      const enemyBroken=g.fronts[v.side].broken;
      const offense=s.aim==='foe';
      const invading=offense&&v.line==='back'&&(enemyBroken||u.breachLane||u.flank==='strike'||mod(g,u,'wedge'));
      if(invading&&['guard','blade','dash'].includes(u.role)&&!u.invasion){
        u.invasion=true;
        g.effects.push({kind:'breach',x:u.x,y:u.y,tx:v.x,ty:v.y,at:g.time});
        if(!g.fronts[v.side].invaded){
          g.fronts[v.side].invaded=true;
          note(g,u.name+' 돌파 → '+v.name+' 후열 침투!','infiltrate',v.side);
        }
      }
      const speed=role.pace*TICK*(u.weak>g.time?.68:1)*(1-mod(g,u,'slow'))*(1+mod(g,u,'haste'));
      const gap=distance(u,v);
      // Each rear unit retreats for one short window. All surviving units
      // pursue an out-of-range enemy afterwards, including rear-only fights.
      if(broken&&u.line==='back'&&u.retreatEnd===undefined)u.retreatEnd=g.time+1.3;
      const retreat=u.retreatEnd>g.time&&u.tauntUntil<=g.time;
      const guardingRear=u.role==='guard'&&u.line==='back'&&!broken&&!enemyBroken
        && u.tauntUntil<=g.time&&offense&&gap>120;
      if(guardingRear){
        const threat=foes.find(f=>f.role==='dash'&&['cross','strike'].includes(f.flank)
                                 &&(f.x-450)*dir<95);
        move(g,u,u.homeX+dir*46,threat?threat.y:u.homeY,speed*(threat?1.8:1));
      }
      else if(retreat)move(g,u,u.homeX-dir*74,u.homeY,speed*1.25);
      else if(gap>range*.96||!clearPath(g.wall,u,v)){
        move(g,u,v.x,v.y,speed*(key==='ambush'?1.85:invading?1.3:1));
      }
      if(distance(u,v)<=range&&u.cd<=g.time&&clearPath(g.wall,u,v)){
        if(s.kind==='heal'||s.kind==='hex')u.cast={id:v.id,key,until:g.time+.45};
        else execute(g,u,v,key);
      }
    }
    // Separate friendly silhouettes without changing the target or facing.
    for(let i=0;i<living.length;i++)for(let j=i+1;j<living.length;j++){
      const a=living[i],b=living[j];
      if(!a.hp||!b.hp||a.side!==b.side||distance(a,b)>=23)continue;
      const delta=a.y<=b.y?1:-1;
      const separate=(unit,direction)=>{
        const y=Math.max(78,Math.min(392,unit.y+direction*1.1));
        const shifted={x:unit.x,y};
        const previous={x:unit.prevX,y:unit.prevY};
        if(clearPath(g.wall,unit,shifted)&&clearPath(g.wall,previous,shifted))unit.y=y;
      };
      separate(a,-delta);
      separate(b,delta);
    }
    finish(g);
  }
  function execute(g,u,v,key){
    if(!clearPath(g.wall,u,v))return;
    const kind=skills[key].kind;
    apply(g,u,v,key);u.actions++;
    if(key==='ambush')u.ambushed=true;
    u.cd=g.time+((kind==='heal'?2.05:kind==='hex'?2.15:1.12)+(u.weak>g.time?.37:0)+(u.side===0?.08:0))
      *(1+mod(g,u,'silence'))/(1+mod(g,u,'haste'));
  }
  function nextRound(g){
    g.order=g.units.filter(u=>u.hp>0).sort((a,b)=>roles[b.role].agility-roles[a.role].agility||a.id-b.id);
    g.turn=0;
  }
  function current(g){return g.order[g.turn];}
  function turn(g,key,id){
    if(g.finished||isGroup(g.mode))return false;
    const u=current(g);
    if(!u||!skillOptions(g,u).includes(key))return false;
    const v=targetList(g,u,key).find(f=>f.id===id);
    if(!v)return false;
    g.time+=.5;
    apply(g,u,v,key);
    if(!finish(g)){
      do{g.turn++;}while(g.order[g.turn]&&g.order[g.turn].hp<=0);
      if(!current(g)){g.round++;if(!finish(g))nextRound(g);}
    }
    return true;
  }
  function enemyTurn(g){
    const u=current(g);
    if(!u||u.side!==1)return false;
    const kit=skillOptions(g,u),[v,key]=target(g,u);
    return turn(g,kit.includes(key)?key:kit.find(k=>skills[k].aim==='foe'),v.id);
  }
  const art = (name,kind,trigger,detail)=>({name,kind,trigger,detail});
  const arts = {
    rain:art('만천화우','attack','교전 4초 후 아군 사수 2명 생존','최대 5명 타격 · 방어 15% 약화 4초'),
    poison:art('독압정','attack','적 전열 체력 50% 이하','약한 전열과 인접 적 1명 관통 피해 · 받는 치유 40% 감소 5초'),
    tiger:art('파갑맹호격','attack','적 전열과 처음 근접 충돌','적 전열 최대 4명 보호막 파괴 · 방어 30% 약화 6초 · 밀어내기'),
    swordlight:art('천강일섬','attack','아군 지휘관 체력 45% 이하','침투자 우선 강타 · 경직 2.5초'),
    lotus:art('금강불괴진','defense','전열 1~2명 생존 또는 전선 크게 밀림','생존 전열 받는 피해 35% 감소 · 밀림 저항 6초'),
    wall:art('철벽호위진','defense','적 근접 유닛이 아군 후열에 처음 진입','후열 피해 35% 감소 · 진입 적 이동·공격 둔화 5초'),
    turtle:art('현무결계','defense','생존 대장 체력 60% 이하','대장과 주변 아군 최대 3명 보호막 25% · 행동 중단 면역 최대 6초'),
    reflect:art('반탄강기','defense','최근 3초간 전열 체력 피해가 합산 최대 체력의 30% 이상','전열이 실제 받은 피해 25% 반사 · 근접 공격자 공격력 약화 5초'),
    mercy:art('대자대비공','heal','생존 전열 중 체력 35% 이하','전열 즉시 22% 회복 · 4초간 매초 4% 회복'),
    cleanse:art('청심보원단','heal','아군 3명 이상 약화 상태','약화 아군 10% 회복 · 해로운 효과 1종 해제 · 4초간 첫 약화 방어'),
    medic:art('부대장응급조치','heal','생존 부대장 체력 40% 이하','부대장과 가장 약한 다른 아군 30% 회복 · 이동·공격 가속 4초'),
    revive:art('생사구환진','heal','첫 아군 전투불능','체력 비율이 낮은 생존 아군 2명 20% 회복 · 받는 치유 30% 증가 5초'),
    net:art('천라지망','control','적 전열이 아군 전선에 접근','전열과 선두 돌격수 이동 50% 감소 · 회피 판정 없음 · 4초'),
    silence:art('혼원기공장','control','적 후열이 회복 또는 주술을 준비','시전 취소 · 시전자와 인접 적 1명의 재사용 시간 5초간 증가'),
    fog:art('백골독무','control','전투 개시 8초','중앙·전열 적 최대 6명 · 6초간 독 피해 및 명중률 15% 감소'),
    morale:art('사기탈취호령','control','적 대장 또는 부대장이 체력 50% 이하','적 전체 공격력 15% 감소 (지휘관 20%) · 전선 유지력 감소 5초'),
    wing:art('학익진 전개','formation','전투 개시 2초','전열을 양옆으로 펼치고 사수·주술 사거리와 공격력 12% 증가 8초'),
    wedge:art('어린진 돌파','formation','아군 전열 평균 체력 60% 이상 · 적 전열 2명 이하','아군 전열 돌격조와 부대장이 후열로 진입 · 이동 +40%, 첫 타격 +25% · 5초'),
    withdraw:art('후방재배치','formation','아군 전열이 1명으로 줄어듦','생존 전열과 후열 재배치 · 사수·주술 피해 20% 증가 4초'),
    escort:art('대장친위진','formation','대장 체력 50% 이하 · 적 근접 접근','호위 최대 2명이 이동해 대장 체력 피해 40% 분담 6초')
  };
  const fixedArts=['rain','poison'];
  const baseArts=['lotus','cleanse'];
  const sects=['청운문','당문'];
  const ranged=u=>['bow','hex'].includes(u.role);
  const melee=u=>['guard','blade','dash'].includes(u.role);
  const ratio=u=>u.hp/u.max;
  const low=(a,b)=>ratio(a)-ratio(b)||a.id-b.id;
  function buff(g,u,key,seconds,value=1,source=null){
    if(['armor','antiheal','slow','silence','dot','miss','powerDown','pressure'].includes(key)&&mod(g,u,'purity')){
      delete u.mods.purity;
      return;
    }
    u.mods[key]={until:g.time+seconds,value,next:g.time+1,source};
  }
  function mod(g,u,key){
    const item=u.mods[key];
    return item?.until>g.time+1e-7?item.value:0;
  }
  function disable(g,u,until){
    if(!mod(g,u,'immune')){u.stun=Math.max(u.stun,until);u.cast=null;}
  }
  function healing(g,u,amount,source){
    const value=Math.min(u.max-u.hp,Math.round(amount*(1-mod(g,u,'antiheal'))*(1+mod(g,u,'healing'))));
    u.hp+=value;
    if(value&&source){
      source.healing+=value;
      g.events.push({kind:'heal',actor:source.id,amount:value});
    }
    return value;
  }
  function lifeLoss(g,v,amount,attacker,credit=attacker){
    const value=Math.min(v.hp,Math.max(0,Math.round(amount)));
    if(!value)return 0;
    v.hp-=value;v.hitAt=g.time;v.hitTaken+=value;
    if(credit)credit.damage+=value;
    if(isGroup(g.mode)&&v.line==='front')g.wounds[v.side].push({time:g.time,value});
    if(v.hp===0){
      if(credit&&credit.side!==v.side)credit.kills++;
      if(attacker)g.events.push({kind:'knockout',actor:attacker.id});
      note(g,v.name+' 전투불능');
      if(v.id===g.leaders[v.side].captain)note(g,v.name+' 대장 이탈 · 아군 사기 저하','leader',v.side);
    }
    return value;
  }
  function hit(g,v,amount,attacker,{pierce=false,credit=attacker}={}){
    amount=Math.max(0,Math.round(amount*(1-mod(g,v,'guarding'))*(1+mod(g,v,'armor'))));
    if(!pierce){
      const barrier=Math.min(v.barrier?.until>g.time?v.barrier.hp:0,amount);
      if(barrier){v.barrier.hp-=barrier;amount-=barrier;v.hitAt=g.time;}
      const shield=Math.min(v.shield,amount);
      v.shield-=shield;amount-=shield;
      if(shield)v.hitAt=g.time;
      v.absorbed+=barrier+shield;
    }
    const redirect=mod(g,v,'escort');
    if(redirect){
      const guards=active(g,v.side).filter(u=>redirect.includes(u.id));
      const share=guards.length?Math.round(amount*.4/guards.length):0;
      for(const guard of guards)lifeLoss(g,guard,share,null,credit);
      amount-=share*guards.length;
    }
    const value=lifeLoss(g,v,amount,attacker,credit);
    if(value&&attacker&&mod(g,v,'reflect')){
      lifeLoss(g,attacker,value*mod(g,v,'reflect'),null,v);
      if(melee(attacker))buff(g,attacker,'powerDown',2,.15);
    }
    return value;
  }
  function artContext(g,side){
    const own=active(g,side),foes=active(g,1-side);
    const front=own.filter(u=>u.line==='front'),rear=own.filter(u=>u.line==='back');
    const enemy=foes.filter(u=>u.line==='front');
    const invaders=foes.filter(u=>melee(u)&&(side===0?u.x<245:u.x>655));
    const captain=own.find(u=>u.id===g.leaders[side].captain);
    const deputy=own.find(u=>u.id===g.leaders[side].deputy);
    const leaders=g.units.filter(u=>u.side===side&&Object.values(g.leaders[side]).includes(u.id));
    const rivals=g.units.filter(u=>u.side!==side&&Object.values(g.leaders[1-side]).includes(u.id));
    return {own,foes,front,rear,enemy,invaders,captain,deputy,leaders,rivals};
  }
  function artTargets(g,side,key,c){
    const {own,foes,front,rear,enemy,invaders,captain,deputy,leaders,rivals}=c;
    const eBack=foes.filter(u=>u.line==='back');
    const around=(target,team,count=1,range=105)=>target?[target,...team.filter(u=>u!==target&&distance(u,target)<=range)
      .sort((a,b)=>distance(a,target)-distance(b,target)).slice(0,count)]:[];
    switch(key){
      case 'rain':return g.contactAt!=null&&g.time-g.contactAt>=4&&own.filter(u=>u.role==='bow').length>=2?
        [...enemy.slice(0,3),...eBack,...enemy.slice(3)].slice(0,5):[];
      case 'poison':return around([...enemy].filter(u=>ratio(u)<=.5).sort(low)[0],foes);
      case 'tiger':return g.contactAt!=null&&g.contactAt===g.time?enemy.filter(v=>front.some(u=>distance(u,v)<57)).slice(0,4):[];
      case 'swordlight':return leaders.some(u=>ratio(u)<=.45)?[(invaders.length?invaders:foes).reduce((best,u)=>
        !best||roles[u.role].power>roles[best.role].power?u:best,null)].filter(Boolean):[];
      case 'lotus':return front.length<=2||Math.abs(g.fronts[side].x-(side?510:390))>=45?front:[];
      case 'wall':return invaders.length?rear:[];
      case 'turtle':return captain&&ratio(captain)<=.6?around(captain,own,2):[];
      case 'reflect':return g.wounds[side].reduce((sum,e)=>sum+e.value,0)>=.30*g.frontMax[side]?front:[];
      case 'mercy':return front.some(u=>ratio(u)<=.35)?front:[];
      case 'cleanse':{
        const afflicted=own.filter(u=>u.weak>g.time||u.stun>g.time||
          ['armor','antiheal','slow','silence','dot','miss','powerDown','pressure'].some(k=>mod(g,u,k)));
        return afflicted.length>=3?afflicted:[];
      }
      case 'medic':return deputy&&ratio(deputy)<=.4?[deputy,...own.filter(u=>u!==deputy).sort(low).slice(0,1)]:[];
      case 'revive':return own.length<g.initial[side]?[...own].sort(low).slice(0,2):[];
      case 'net':return enemy.some(u=>Math.abs(u.x-g.fronts[side].x)<72)?
        [...enemy,...foes.filter(u=>u.line==='back'&&u.role==='dash'&&Math.abs(u.x-g.fronts[side].x)<90)]:[];
      case 'silence':return around(eBack.find(u=>u.cast),eBack);
      case 'fog':return g.time>=8?[...foes].sort((a,b)=>Math.abs(a.x-450)-Math.abs(b.x-450)).slice(0,6):[];
      case 'morale':return rivals.some(u=>ratio(u)<=.5)?foes:[];
      case 'wing':return g.time>=2?own:[];
      case 'wedge':return front.length&&front.reduce((sum,u)=>sum+ratio(u),0)/front.length>=.6&&enemy.length<=2&&eBack.length?
        own.filter(u=>u===deputy||(u.line==='front'&&melee(u))):[];
      case 'withdraw':return front.length===1&&rear.length?[...front,...rear]:[];
      case 'escort':return captain&&ratio(captain)<=.5&&foes.some(u=>melee(u)&&distance(u,captain)<90)?
        around(captain,own.filter(u=>u===deputy||u.line==='front'),2,180):[];
      default:return [];
    }
  }
  function useArt(g,side,key,targets,c){
    const {name,kind,detail}=arts[key];
    const duration={rain:4,poison:5,tiger:6,swordlight:2.5,lotus:6,wall:5,turtle:6,reflect:5,mercy:4,cleanse:4,
      medic:4,revive:5,net:4,silence:5,fog:6,morale:5,wing:8,wedge:5,withdraw:4,escort:6}[key];
    let damage=0,restored=0,interrupted=0;
    for(const u of targets){
      if(!u.hp)continue;
      const sources=[c.captain,c.deputy,...c.own];
      const credit=sources.find(actor=>actor?.hp&&(u.side===side||clearPath(g.wall,actor,u)));
      switch(key){
        case 'rain':damage+=hit(g,u,29,null,{credit});buff(g,u,'armor',4,.15);break;
        case 'poison':damage+=hit(g,u,24,null,{pierce:true,credit});buff(g,u,'antiheal',5,.4);break;
        case 'tiger':
          u.shield=0;u.barrier=null;buff(g,u,'armor',6,.3);
          const x=u.x+(side?-24:24);
          if(!mod(g,u,'steadfast')&&clearPath(g.wall,u,{x,y:u.y}))u.x=x;
          break;
        case 'swordlight':damage+=hit(g,u,53,null,{credit});disable(g,u,g.time+2.5);break;
        case 'lotus':buff(g,u,'guarding',6,.35);buff(g,u,'steadfast',6);break;
        case 'wall':buff(g,u,'guarding',5,.35);break;
        case 'turtle':u.barrier={hp:Math.round(u.max*.25),until:g.time+6};buff(g,u,'immune',6);break;
        case 'reflect':buff(g,u,'reflect',5,.25);break;
        case 'mercy':restored+=healing(g,u,u.max*.22,credit);buff(g,u,'regen',4,.04,credit);break;
        case 'cleanse':{
          const effects=['antiheal','dot','armor','slow','silence','miss','powerDown','pressure'];
          const bad=effects.find(k=>mod(g,u,k));
          if(bad)delete u.mods[bad];else if(u.stun>g.time)u.stun=g.time;else u.weak=g.time;
          buff(g,u,'purity',4);restored+=healing(g,u,u.max*.1,credit);break;
        }
        case 'medic':restored+=healing(g,u,u.max*.3,credit);buff(g,u,'haste',4,.2);break;
        case 'revive':restored+=healing(g,u,u.max*.2,credit);buff(g,u,'healing',5,.3);break;
        case 'net':buff(g,u,'slow',4,.5);break;
        case 'silence':if(u.cast)interrupted++;u.cast=null;u.cd=Math.max(u.cd,g.time+.7);buff(g,u,'silence',5,.3);break;
        case 'fog':buff(g,u,'dot',6,5,credit);buff(g,u,'miss',6,.15);break;
        case 'morale':
          buff(g,u,'powerDown',5,c.rivals.includes(u)?.20:.15);
          if(u.line==='front')buff(g,u,'pressure',5,.18);
          break;
        case 'wing':
          if(ranged(u)){buff(g,u,'range',8,.12);buff(g,u,'power',8,.12);}
          if(u.line==='front')u.order={x:u.x,y:u.y<215?u.y-26:u.y+26,until:g.time+.85};
          break;
        case 'wedge':buff(g,u,'wedge',5);buff(g,u,'haste',5,.4);break;
        case 'withdraw':
          u.order={x:u.x+(side?67:-67),y:u.y,until:g.time+1.3};
          buff(g,u,'haste',1.3,.4);if(ranged(u))buff(g,u,'power',4,.2);break;
        case 'escort':
          if(u===c.captain)buff(g,u,'escort',6,targets.slice(1).map(f=>f.id));
          else u.order={x:c.captain.x+(side?-34:34),y:c.captain.y+(u===targets[1]?-18:18),until:g.time+1.3};
          break;
      }
    }
    if(key==='wall')for(const u of c.invaders.filter(v=>c.own.some(ally=>clearPath(g.wall,ally,v)))){buff(g,u,'slow',5,.25);buff(g,u,'silence',5,.25);}
    const event={key,name,kind,side,sect:g.sectNames[side],time:g.time,duration,
      damage,restored,interrupted,ids:targets.map(u=>u.id),points:targets.map(({x,y})=>({x,y}))};
    g.artEvents.push(event);
    const actual=[damage?'체력 피해 '+damage:'',restored?'회복 '+restored:'',interrupted?'시전 차단 '+interrupted+'명':''].filter(Boolean);
    note(g,g.sectNames[side]+' · '+name+' 발동 ('+targets.length+'명) · '+detail+
      (actual.length?' · 실제 '+actual.join(' / '):''),'art-'+kind,side);
  }
  function updateArts(g){
    const frontContact=active(g,0).filter(u=>u.line==='front'&&melee(u)).some(u=>
      active(g,1).some(v=>v.line==='front'&&melee(v)&&distance(u,v)<55&&clearPath(g.wall,u,v)));
    if(g.contactAt==null&&frontContact)g.contactAt=g.time;
    for(let side=0;side<2;side++)g.wounds[side]=g.wounds[side].filter(e=>e.time>g.time-3);
    const queue=[];
    for(let side=0;side<2;side++){
      const context=artContext(g,side);
      if(!context.own.length||!context.foes.length)continue;
      for(const key of g.arts[side]){
        if(g.used[side].has(key))continue;
        const targets=artTargets(g,side,key,context).filter(u=>u.side===side||
          context.own.some(ally=>clearPath(g.wall,ally,u)));
        if(targets.length&&(key!=='escort'||targets.length>1))queue.push({side,key,targets,context});
      }
    }
    for(const {side,key,targets,context} of queue){
      if(!targets.some(u=>u.hp))continue;
      g.used[side].add(key);
      useArt(g,side,key,targets,context);
    }
  }
  function periodic(g){
    for(const u of g.units){
      if(!u.hp)continue;
      for(const key of ['regen','dot']){
        const status=u.mods[key];
        if(!status||status.next>g.time+1e-7||status.next>status.until+1e-7)continue;
        status.next+=1;
        if(key==='regen')healing(g,u,u.max*status.value,status.source);
        else hit(g,u,status.value,null,{credit:status.source});
      }
    }
  }
  const portraitRoles=['guard','blade','bow','hex','heal','dash'];
  function settle(config, selection={lineup:config.team,captain:config.captain,
                                      deputy:config.deputy,arts:baseArts}) {
    const terrain = battlefield(config.terrain,config.mode);
    const lineup = selection.lineup;
    const saved = new Map([...(config.team || []),...(config.bench || [])].map(u=>[u.id,u]));
    const lineupIds = new Set(lineup?.map(u=>u.id) || []);
    const captain = selection.captain??null, deputy = selection.deputy??null;
    if (!Array.isArray(lineup)||lineup.length!==config.team.length||
        lineupIds.size!==config.team.length||
        !lineup.every(u=>saved.has(u.id)&&['front','back'].includes(u.line)&&
          Number.isInteger(u.slot)&&u.slot>=0&&u.slot<terrain[u.line]&&
          (u.position==null||canDeploy(config.terrain,u.position.x,u.position.y)))||
        new Set(lineup.map(u=>u.line+u.slot)).size!==config.team.length||
        (config.team.length&&(!lineupIds.has(captain)||!lineup.some(u=>u.line==='front')))||
        (config.team.length>1&&(!lineupIds.has(deputy)||deputy===captain))||
        !Array.isArray(selection.arts)||selection.arts.length!==2||
        new Set(selection.arts).size!==2||!selection.arts.every(key=>Object.hasOwn(arts,key))) {
      throw new Error('진형, 대장·부대장 및 문파 무공을 다시 확인하세요.');
    }
    const team = lineup.map(({id,line,slot,position})=>({...saved.get(id),line,slot,position}));
    const game = create({...config,team,captain,deputy,chosenArts:selection.arts,loadout:[]});
    while (!game.finished) tick(game);
    const performance=game.units.map(u=>({
      id:u.id, name:u.name, side:u.side, role_id:portraitRoles.indexOf(u.role),
      portrait:u.portrait??'', damage:u.damage, hit_taken:u.hitTaken, healing:u.healing,
      kills:u.kills,shield_given:u.shieldGiven,absorbed:u.absorbed,
      hp:u.hp,max_hp:u.max,actions:u.actions
    }));
    return {winner:game.winner,events:game.events,performance,
      units:game.units.filter(u=>u.id>=0).map(u=>({
        id:u.id, side:u.side, hp:u.hp, max_hp:u.max, healing:u.healing,
        hit_taken:u.hitTaken, actions:u.actions,
        kills:u.kills,shield_given:u.shieldGiven,absorbed:u.absorbed
      }))};
  }

  return {settle,battlefield,obstruction,canDeploy,deployPoint,clearPath,leadershipPreview,arts,fixedArts,baseArts,sects,playerPresets,foesPresets,playerTeam,enemyTeam,tauntStatus,terrains,roles,skills,roster,place,create,tick,current,turn,enemyTurn,targetList,TICK};
})();

