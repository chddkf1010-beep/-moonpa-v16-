/* Pure helpers shared by the live 8v8 arena and its regression tests.
   The server authorizes bench members; UI swaps cannot add other fighters. */
export function eligibleBench(config, deployed) {
  if (!config || !Array.isArray(config.bench)) return [];
  const active = new Set(deployed.map(member => member.id));
  const allowed = new Map([...(config.team || []), ...config.bench].map(member => [member.id, member]));
  return [...allowed.values()].filter(member => !active.has(member.id));
}

export function replaceDeployed(lineup, config, incomingId, outgoingId) {
  const source = eligibleBench(config,lineup).find(member => member.id === incomingId);
  const index = lineup.findIndex(member => member.id === outgoingId);
  if (!source || index < 0) throw new Error('교체 가능한 대기 인원과 출전 슬롯을 선택하세요.');
  const outgoing = lineup[index];
  const result = lineup.map((member,i) => i === index ?
    {...source,line:outgoing.line,slot:outgoing.slot,
      ...(outgoing.position == null ? {} : {position:{...outgoing.position}})} : {...member});
  if (new Set(result.map(member => member.id)).size !== result.length) {
    throw new Error('문파원을 중복 출전시킬 수 없습니다.');
  }
  return result;
}

export function combatantStats(member) {
  const attributes = member?.attrs && typeof member.attrs === 'object' ? member.attrs : {};
  return {
    id:member.id,name:member.name,role:member.role,level:member.level??null,
    ca:member.ca??null,pa:member.pa??null,attrs:attributes,
    wage:member.wage??null,contractEnd:member.contract_end??null,
    notable:member.notable??null
  };
}
