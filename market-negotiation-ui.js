/* Opposing sects negotiate against real world rosters and economic rules. */
const transferTalkUI=(()=>{
  const esc=value=>escapeText(value??'');
  const memberText=(id,pool)=>{
    const fighter=pool.find(f=>f.id===id);
    return fighter ? fighter.name+' ('+fighter.role+' · CA '+Number(fighter.ca).toFixed(1)+
      ' / PA '+Number(fighter.pa).toFixed(1)+')' : '확인할 수 없는 문파원';
  };
  const statusName={ready:'협상 대기',counter:'상대 역제안',accepted:'제안 수락',
    refused:'협상 거절',closed:'협상 종료',signed:'거래 성립',stale:'조건 변경'};
  function open(info,fighter){
    const box=panel().querySelector('#offer');
    if(busy||!box)return;
    const seller=info.sects.find(s=>s.id===fighter.seller);
    const context={season:info.season,week:info.week,seller:fighter.seller,id:fighter.id};
    const pool=info.exchange_pool;
    const rows=pool.map(member=>'<label class="trade-member-row">'+
      '<input type="checkbox" data-talk-exchange value="'+member.id+'" '+(member.locked?'disabled':'')+'>'+
      '<span>'+esc(member.name)+' · '+esc(member.role)+'</span>'+
      '<small>CA '+Number(member.ca).toFixed(1)+' / PA '+Number(member.pa).toFixed(1)+
      ' · 주급 '+money(member.wage)+'</small></label>').join('');
    box.innerHTML='<div class="trade-heading"><h2 id="trade-title">'+
      esc(seller?.name||'상대 문파')+' · 이적 협상</h2><form method="dialog"><button>닫기</button></form></div>'+
      '<div class="trade-target"><span class="member-face">'+portrait(fighter)+'</span>'+
      '<div><strong>'+esc(fighter.name)+'</strong>'+heroTag(fighter)+
      '<p>'+esc(fighter.role)+' · '+fighter.age+'세 · 현재 '+fighter.ca+
      ' / 잠재력 '+fighter.pa+' · 주급 '+money(fighter.wage)+'</p></div></div>'+
      '<p class="trade-note">상대 문파는 자기 전력과 재정에 따라 거절하거나 특정 문파원·현금을 역제안합니다. 최종 확인 전에는 인원이나 자금이 이동하지 않습니다.</p>'+
      '<div class="trade-turn" id="talk-round" aria-live="polite">협상 상태 확인 중…</div>'+
      '<div id="talk-history" class="trade-history" aria-label="협상 기록"></div>'+
      '<div class="trade-editor">'+
      '<label class="field">제안할 현금 (냥)<input id="talk-fee" type="number" min="0" step="1" max="'+
      Math.max(0,Number(info.cash))+'" value="'+Math.min(Number(fighter.estimate)||0,Number(info.cash))+'"></label>'+
      '<details id="talk-members"><summary>내가 제안할 문파원 (최대 3명)</summary><div class="trade-exchange-list">'+rows+
      '</div></details><div class="controls"><button type="button" class="primary" id="talk-propose">조건 제안하기</button></div>'+
      '</div><div id="talk-response" class="trade-response" aria-live="polite"></div>';
    box.showModal();
    const feeInput=box.querySelector('#talk-fee');
    const checkboxes=[...box.querySelectorAll('[data-talk-exchange]')];
    const proposal=box.querySelector('#talk-propose');
    const transcript=box.querySelector('#talk-history');
    const resultArea=box.querySelector('#talk-response');
    const terms=()=>({fee:Number(feeInput.value),
      exchange:checkboxes.filter(item=>item.checked).map(item=>Number(item.value))});
    const readable=terms=>terms ? '현금 '+money(terms.fee)+
      (terms.exchange?.length?' + '+terms.exchange.map(id=>memberText(id,pool)).join(', '):''):'요구 조건 없음';
    function applyTerms(terms){
      if(!terms)return;
      feeInput.value=String(terms.fee);
      checkboxes.forEach(item=>item.checked=(terms.exchange||[]).includes(Number(item.value)));
      box.querySelector('#talk-members').open=Boolean(terms.exchange?.length);
      feeInput.focus();
    }
    function render(data){
      const ended=['refused','closed','signed'].includes(data.status),count=Number(data.turn||0);
      proposal.disabled=ended||count>=4;
      // The shared async market helper re-enables buttons in finally.
      // Reassert a seller-closed / exhausted session after that cleanup.
      queueMicrotask(()=>{if(box.open)proposal.disabled=ended||count>=4;});
      box.querySelector('#talk-round').textContent=(statusName[data.status]||'협상')+' · '+count+'/4회 제안';
      transcript.innerHTML=(data.history||[]).map(entry=>
        '<div class="trade-chat trade-chat-me"><small>내 제안 · '+entry.turn+'차</small><p>'+esc(readable(entry.offered))+'</p></div>'+
        '<div class="trade-chat trade-chat-rival"><small>상대 문파</small><p>'+esc(entry.message)+'</p></div>'
      ).join('')||'<p class="muted-copy">첫 제안을 입력하면 상대의 답변과 이유가 여기에 나타납니다.</p>';
      resultArea.replaceChildren();
      const heading=document.createElement('strong');
      heading.className='trade-response-status '+(data.status==='accepted'?'positive':data.status==='refused'?'negative':'');
      heading.textContent=statusName[data.status]||'협상';
      const paragraph=document.createElement('p');
      paragraph.textContent=data.message||'현금 또는 문파원을 선택해 제안하세요.';
      resultArea.append(heading,paragraph);
      if(data.terms){
        const card=document.createElement('div');card.className='trade-request';
        const subtitle=document.createElement('small');subtitle.textContent='상대가 제시한 실제 거래 조건';
        const amount=document.createElement('strong');amount.textContent='현금 '+money(data.terms.fee);
        card.append(subtitle,amount);
        for(const id of data.terms.exchange||[]){
          const line=document.createElement('span');
          line.textContent=memberText(id,pool);
          card.append(line);
        }
        resultArea.append(card);
      }
      const actions=document.createElement('div');actions.className='trade-reply-actions';
      if(data.terms && ['counter','accepted'].includes(data.status)){
        const accept=document.createElement('button');
        accept.type='button';accept.className='primary';
        accept.textContent=data.status==='counter'?'역제안 수락 · 거래 확정':'제안 수락 · 거래 확정';
        accept.addEventListener('click',()=>{
          runMarket('transfer_bargain_accept',{...context,revision:data.revision},result=>{
            if(result.talk?.status==='signed'){
              state=result.state;box.close();
              queueMicrotask(()=>management(fighter.name+' 이적 완료'));return;
            }
            if(result.talk?.status==='stale'){
              runMarket('transfer_talk_view',context,render);return;
            }
            render(result.talk||{status:'closed',message:'거래를 완료할 수 없습니다.'});
          });
        });
        actions.append(accept);
        if(data.status==='counter'){
          const use=document.createElement('button');use.type='button';
          use.textContent='상대 요구 조건 입력';
          use.addEventListener('click',()=>applyTerms(data.terms));
          actions.append(use);
        }
      }
      if(!ended&&count<4){
        const edit=document.createElement('button');edit.type='button';
        edit.textContent='다시 제안하기';
        edit.addEventListener('click',()=>feeInput.focus());
        actions.append(edit);
      }
      if(!ended&&count){
        const reject=document.createElement('button');reject.type='button';
        reject.textContent='역제안 거절 · 협상 종료';
        reject.addEventListener('click',()=>runMarket('transfer_bargain_decline',
          {...context,revision:data.revision},render));
        actions.append(reject);
      }
      resultArea.append(actions);
    }
    proposal.addEventListener('click',()=>{
      if(feeInput.value===''||!feeInput.checkValidity()||
          !Number.isSafeInteger(Number(feeInput.value))||
          terms().exchange.length>3){
        resultArea.textContent='현금은 0 이상의 정수, 교환 문파원은 최대 3명만 선택하세요.';return;
      }
      runMarket('transfer_bargain',{...context,...terms()},render);
    });
    runMarket('transfer_talk_view',context,render);
  }
  return {open};
})();
