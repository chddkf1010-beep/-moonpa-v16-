// No third-party deps: Node tests for browser save manager logic.
import {readFileSync} from 'node:fs';
import {strict as assert} from 'node:assert';
import {test} from 'node:test';
import vm from 'node:vm';

const source=readFileSync(new URL('../save-manager.js',import.meta.url),'utf8');

function sandbox() {
  const cache=new Map();
  const makeElement=()=>({
    disabled:false,open:false,files:[],value:'',textContent:'',dataset:{},children:[],
    onclick:null,onchange:null,
    append(...elements){this.children.push(...elements);},
    replaceChildren(...elements){this.children=[...elements];},
    querySelectorAll(){return [];},
    showModal(){this.open=true;},
    close(){this.open=false;},
    click(){this.clicked=true;},
  });
  const elements=Object.fromEntries([
    '#save-menu','#save-status','#save-dialog','#save-feedback','#save-slots',
    '#save-file','#save-close','#save-export','#save-import','#save-reset',
    '#error',
  ].map(key=>[key,makeElement()]));
  const storage=new Map();
  const localStorage={
    getItem(key){return storage.has(key)?storage.get(key):null;},
    setItem(key,value){storage.set(key,value);},
    removeItem(key){storage.delete(key);}
  };
  const confirm=()=>true;
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
    if(path==='export_save')return sample();
    if(path==='import_save'){
      if(!payload.save || payload.save.format!=='moonpa-v3-save')
        throw Error('잘못된 세이브 파일입니다.');
      active={week:payload.save.meta.week};
      return active;
    }
    if(path==='new_game'){
      active={week:1};
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
  return {manager,storage,elements,sample,game};
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

test('explicitly confirmed new game starts cleanly',async()=>{
  const {manager,game,elements}=sandbox();
  await manager.boot();
  manager.show();
  await manager.resetGame();
  assert.equal(game.state.week,1);
  assert.equal(elements['#save-dialog'].open,false);
});
