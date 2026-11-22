// No third-party deps: Node tests for browser save manager logic.
import {readFileSync} from 'node:fs';
import {strict as assert} from 'node:assert';
import {test} from 'node:test';
import vm from 'node:vm';

const source=readFileSync(new URL('../save-manager.js',import.meta.url),'utf8');

function sandbox() {
  const makeElement=()=>({
    disabled:false,open:false,files:[],value:'',textContent:'',dataset:{},children:[],
    onclick:null,onchange:null,
    append(...elements){this.children.push(...elements);},
    replaceChildren(...elements){this.children=[...elements];},
    querySelectorAll(){return [];},
    addEventListener(){},
    showModal(){this.open=true;},
    close(){this.open=false;},
    click(){this.clicked=true;},
  });
  const elements=Object.fromEntries([
    '#save-menu','#save-status','#save-dialog','#save-feedback','#save-slots',
    '#save-file','#save-close','#save-export','#save-import','#save-reset',
    '#save-now','#save-auto-detail','#save-recovery-row','#save-recovery-detail','#save-recover','#error',
  ].map(key=>[key,makeElement()]));
  const storage=new Map();
  const localStorage={
    getItem(key){return storage.has(key)?storage.get(key):null;},
    setItem(key,value){storage.set(key,value);},
    removeItem(key){storage.delete(key);}
  };
  const confirmations=[];
  let accept=true;
  const confirm=message=>{confirmations.push(message);return accept;};
  const context=vm.createContext({
    window:{localStorage,confirm},
    document:{
      querySelector:key=>elements[key],
      createElement:()=>makeElement(),
      body:{append(){}},
    },
    console:{warn(){}},
    URL:{createObjectURL:()=>'/fake',revokeObjectURL(){}},
    Blob:globalThis.Blob, Date, setTimeout,
  });
  vm.runInContext(source+'\n;globalThis.SaveManager=SaveManager;',context);
  const SaveManager=context.SaveManager;
  const sample=() => ({
    format:'moonpa-v3-save',version:1,data:'compressed-example',
    checksum:'0'.repeat(64),
    meta:{guild:'청운문',season:1,week:3,phase:'ready',seed:23}
  });
  let active={week:3},loaded=0,heavy=false;
  const callEngine=async (path,payload)=>{
    if(path==='state')return active;
    if(path==='export_save')return {...sample(),meta:{...sample().meta,week:active.week}};
    if(path==='import_save'){
      if(!payload.save || payload.save.format!=='moonpa-v3-save')
        throw Error('잘못된 세이브 파일입니다.');
      active={week:payload.save.meta.week};
      manager.autosave(payload.save);
      return active;
    }
    if(path==='new_game'){
      active={week:1};
      manager.autosave({...sample(),meta:{...sample().meta,week:1}});
      return active;
    }
    throw Error('unexpected '+path);
  };
  const game={
    get state(){return active;},
    get restored(){return loaded;},
    get busy(){return heavy;},
  };
  const manager=new SaveManager({
    callEngine,
    applyGame:next=>{active=next;loaded++;},
    isBusy:()=>heavy,
    setBusy:value=>{heavy=value;}
  });
  return {manager,storage,elements,sample,game,confirmations,accept:value=>{accept=value;}};
}

test('first boot initializes an autosave, then manual slot can restore',async()=>{
  const {manager,storage,elements,game}=sandbox();
  await manager.boot();
  assert.equal(manager.ready,true);
  assert.equal(elements['#save-menu'].disabled,false);
  const auto=JSON.parse(storage.get('moonpa.v3.autosave'));
  assert.equal(auto.snapshot.format,'moonpa-v3-save');
  manager.show();
  assert.equal(elements['#save-dialog'].open,true);
  await manager.saveSlot(2);
  assert.equal(JSON.parse(storage.get('moonpa.v3.slot.2')).snapshot.meta.week,3);
  await manager.loadSlot(2);
  assert.equal(game.state.week,3);
  assert.equal(elements['#save-dialog'].open,false);
});

test('autosave writes latest snapshot and reload boots it',async()=>{
  const {manager,storage,sample,elements}=sandbox();
  await manager.boot();
  const updated=sample();
  updated.meta.week=7;
  assert.equal(manager.autosave(updated),true);
  assert.equal(JSON.parse(storage.get('moonpa.v3.autosave')).snapshot.meta.week,7);
  assert.match(elements['#save-status'].textContent,/자동저장/);
});

test('bad import retains the running game and surfaces an error',async()=>{
  const {manager,game,elements}=sandbox();
  await manager.boot();
  manager.show();
  const before=game.state;
  await manager.loadSnapshot({format:'malicious'});
  assert.equal(game.state,before);
  assert.equal(elements['#save-dialog'].open,true);
  assert.match(elements['#save-feedback'].textContent,/잘못된 세이브/);
});

test('quota errors are reported and do not crash gameplay',async()=>{
  const {manager,elements,sample}=sandbox();
  await manager.boot();
  manager.write=()=>{throw Error('QuotaExceededError');};
  assert.equal(manager.autosave(sample()),false);
  assert.equal(elements['#save-status'].dataset.problem,'true');
});

test('new game preserves a separate copy and can restore it without altering manual slots',async()=>{
  const {manager,game,elements,storage}=sandbox();
  await manager.boot();
  manager.show();
  await manager.saveSlot(2);
  const manual=storage.get('moonpa.v3.slot.2');
  assert.equal(elements['#save-recovery-row'].hidden,true);
  await manager.resetGame();
  assert.equal(game.state.week,1);
  assert.equal(elements['#save-dialog'].open,false);
  assert.equal(JSON.parse(storage.get('moonpa.v3.autosave')).snapshot.meta.week,1);
  assert.equal(JSON.parse(storage.get('moonpa.v3.before-new-game')).snapshot.meta.week,3);
  assert.equal(storage.get('moonpa.v3.slot.2'),manual);
  manager.show();
  assert.equal(elements['#save-recovery-row'].hidden,false);
  assert.match(elements['#save-recovery-detail'].textContent,/청운문 · 1시즌 3주/);
  await elements['#save-recover'].onclick();
  assert.equal(game.state.week,3);
  assert.equal(JSON.parse(storage.get('moonpa.v3.autosave')).snapshot.meta.week,3);
});

test('canceling an overwrite preserves the manual slot and previous campaign record',async()=>{
  const {manager,storage,confirmations,accept}=sandbox();
  await manager.boot();
  await manager.saveSlot(2);
  await manager.resetGame();
  const manual=storage.get('moonpa.v3.slot.2');
  const backup=storage.get('moonpa.v3.before-new-game');
  accept(false);
  await manager.saveSlot(2);
  await manager.resetGame();
  assert.equal(storage.get('moonpa.v3.slot.2'),manual);
  assert.equal(storage.get('moonpa.v3.before-new-game'),backup);
  assert.match(confirmations.at(-1),/기존의 새 게임 시작 전 기록 1개는 교체/);
});

test('a failed backup keeps the active campaign and existing saves',async()=>{
  const {manager,game,storage,elements}=sandbox();
  await manager.boot();
  const saved=storage.get('moonpa.v3.autosave');
  manager.write=()=>{throw Error('QuotaExceededError');};
  await manager.resetGame();
  assert.equal(game.state.week,3);
  assert.equal(storage.get('moonpa.v3.autosave'),saved);
  assert.match(elements['#save-feedback'].textContent,/보관할 공간/);
});

test('a failed new game keeps the previous recovery record',async()=>{
  const {manager,storage,sample,elements}=sandbox();
  await manager.boot();
  manager.write('moonpa.v3.before-new-game',sample());
  const previous=storage.get('moonpa.v3.before-new-game');
  const call=manager.callEngine;
  manager.callEngine=(path,payload)=>{
    if(path==='new_game')throw Error('게임 시작 오류');
    return call(path,payload);
  };
  await manager.resetGame();
  assert.equal(storage.get('moonpa.v3.before-new-game'),previous);
  assert.match(elements['#save-feedback'].textContent,/게임 시작 오류/);
});

test('save now refreshes the autosave card with live campaign metadata',async()=>{
  const {manager,elements}=sandbox();
  await manager.boot();
  manager.show();
  await manager.saveNow();
  assert.match(elements['#save-auto-detail'].textContent,/청운문 · 1시즌 3주/);
  assert.match(elements['#save-feedback'].textContent,/자동저장에 기록/);
});
