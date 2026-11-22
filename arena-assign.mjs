/* Campaign formation-only roster redistribution. Pure, reversible, no combat or RNG. */
export function assignmentPool(config) {
  return new Map([...(config?.team||[]),...(config?.defenseTeam||[]),
                  ...(config?.bench||[])].filter(m=>m.id>0).map(m=>[m.id,m]));
}
export function waitingMembers(config,attack,defense) {
  const active=new Set([...attack,...defense].map(m=>m.id));
  return [...assignmentPool(config).values()].filter(m=>!active.has(m.id));
}
const choices=(member,terrain,taken)=>{
  const rows=['front','back'];
  const primary=rows.includes(member.line)?member.line:
    ['guard','blade','dash'].includes(member.role)?'front':'back';
  const order=[primary,...rows.filter(row=>row!==primary)];
  for(const line of order)for(let slot=0;slot<terrain[line];slot++)
    if(!taken.some(u=>u.line===line&&u.slot===slot))
      return {...member,line,slot,position:undefined};
  return null;
};
export function moveAssignment(config,attack,defense,id,destination,terrain,replaceId=null) {
  const pool=assignmentPool(config);
  if(!pool.has(id))throw Error('허용되지 않은 문파원입니다.');
  if(!['attack','defense','wait'].includes(destination))throw Error('알 수 없는 배치 대상입니다.');
  if(destination==='defense'&&!config.defenseEnabled)throw Error('보유 거점이 없어 방어대에 배치할 수 없습니다.');
  const from=attack.some(m=>m.id===id)?'attack':defense.some(m=>m.id===id)?'defense':'wait';
  if(from===destination)return {attack:[...attack],defense:[...defense]};
  const lists={attack:[...attack],defense:[...defense],wait:waitingMembers(config,attack,defense)};
  const person=lists[from].find(m=>m.id===id);
  lists[from]=lists[from].filter(m=>m.id!==id);
  if(destination!=='wait'){
    const dest=lists[destination];
    if(dest.length>=config.mode){
      if(replaceId===null)throw Error(destination==='attack'?'점령대가 가득 찼습니다. 교체할 점령대원을 선택하세요.':'방어대가 가득 찼습니다. 교체할 방어대원을 선택하세요.');
      const displaced=dest.find(m=>m.id===replaceId);
      if(!displaced)throw Error('교체 대상이 방어대 또는 점령대에 없습니다.');
      lists[destination]=dest.map(m=>m.id===replaceId?
        {...person,line:m.line,slot:m.slot,position:m.position}:m);
      if(from!=='wait')lists[from].push(choices(displaced,terrain,lists[from]));
    }else {
      const placed=choices(person,terrain,dest);
      if(!placed)throw Error('배치할 전열·후열 슬롯이 없습니다.');
      dest.push(placed);
    }
  }
  const ids=[...lists.attack,...lists.defense].map(u=>u.id);
  if(new Set(ids).size!==ids.length)throw Error('점령대와 방어대가 중복 배치되었습니다.');
  return {attack:lists.attack,defense:lists.defense};
}
