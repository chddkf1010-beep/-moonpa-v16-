import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import {runInNewContext} from 'node:vm';
import {Arena} from '../group-engine.mjs';

const read=path=>readFileSync(new URL('../'+path,import.meta.url),'utf8');
const main=read('game.js');
const ui=read('arena-ui.mjs');
const lineup=Arena.place(Arena.playerTeam('hold',8),Arena.battlefield('field',8));
const match={kind:'territory',match:'1:1:territory',tier:4,zone:35,zoneName:'적벽나루',
  terrain:'field',mode:8,team:lineup,captain:lineup[0].id,deputy:lineup[1].id,
  scenario:'attack',sectNames:['청운문','해남파'],teamPower:87.5,enemyPower:92.4};

function controller(firstMatch) {
  const nodes=new Map();
  const node=key=>{
    if(!nodes.has(key))nodes.set(key,{});
    return nodes.get(key);
  };
  Object.assign(node('dialog'),{addEventListener(){},showModal(){this.open=true;}});
  const screen={querySelector:node,replaceChildren(frame){
    this.iframe=frame;
    frame.isConnected=true;
  }};
  const listeners=new Set(),settled=[],sent=[];
  const context={state:{tier:4,group_play:firstMatch},screen,playback:0,busy:false,
    document:{querySelector:node,createElement:()=>({style:{},contentWindow:{
      postMessage:message=>sent.push(message)
    }})},
    window:{scrollTo(){},addEventListener:(_,fn)=>listeners.add(fn),
      removeEventListener:(_,fn)=>listeners.delete(fn)},
    location:{origin:'https://moonpa.example'},
    siteName:(_,name)=>name,powerLabel:value=>value?.toFixed(1),escapeText:x=>x,
    request:async(...args)=>settled.push(args)};
  runInNewContext(main.slice(main.indexOf('function groupBattle('),main.indexOf('function eliteScene(')),context);
  const receive=async message=>{
    for(const listener of listeners)await listener({
      origin:context.location.origin,source:screen.iframe.contentWindow,data:message
    });
  };
  return {context,node,screen,receive,sent,settled};
}

test('weekly automatic option opens the live arena and submits only on confirmation',async()=>{
  const app=controller(match);
  app.context.groupBattle();
  assert.equal(app.node('dialog').open,true);
  assert.match(app.screen.innerHTML,/4부 · 적벽나루/);
  assert.match(app.screen.innerHTML,/평균 전력 <strong>92\.4/);
  app.node('#group-auto').onclick();
  await app.receive({type:'moonpa-group-ready'});
  assert.equal(app.sent[0].progression,'auto');
  assert.equal(app.sent[0].config,match);
  assert.equal(app.settled.length,0);
  await app.receive({type:'moonpa-group-finish',match:match.match});
  assert.equal(app.settled[0][0],'group_finish');
});

test('a second defense opens its own choice and can start in manual preparation',async()=>{
  const app=controller({...match,kind:'defense',defenseNumber:2,defenseTotal:2});
  app.context.groupBattle();
  assert.match(app.screen.innerHTML,/방어전 2\/2/);
  assert.match(app.screen.innerHTML,/수비대 8명 · 최대 체력/);
  app.node('#group-direct').onclick();
  await app.receive({type:'moonpa-group-ready'});
  assert.equal(app.sent[0].progression,'manual');
  assert.equal(app.settled.length,0);
});

test('the arena ticks a saved formation in automatic mode and waits for manual edits otherwise',()=>{
  const source=ui.slice(ui.indexOf('function prepareCampaignBattle('),ui.indexOf('if (window.parent !== window)'));
  for(const progression of ['auto','manual']){
    const elements=new Map();
    const node=key=>{
      if(!elements.has(key))elements.set(key,{});
      return elements.get(key);
    };
    const context={campaign:null,el:node,document:{querySelector:node},
      terrain:null,mode:null,selected:null,lineup:[],captain:null,deputy:null,chosenArts:[],
      baseArts:Arena.baseArts,setup(){},ready(){node('ready').called=true;}};
    context.battleConfig=()=>({...context.campaign,team:context.lineup,chosenArts:context.chosenArts,loadout:[]});
    let game;
    context.start=config=>{game=Arena.create(config);};
    runInNewContext(source,context);
    context.prepareCampaignBattle({config:match,progression,heading:'점령전'});
    const auto=progression==='auto';
    assert.equal(node('.preparation').hidden,auto);
    assert.equal(Boolean(game),auto);
    assert.equal(Boolean(node('ready').called),!auto);
    assert.notEqual(context.lineup[0],match.team[0]);
    if(auto){
      const selection={lineup:match.team,captain:match.captain,deputy:match.deputy,arts:Arena.baseArts};
      Arena.tick(game);
      assert.ok(game.time>0 && !game.finished);
      while(!game.finished)Arena.tick(game);
      const settled=Arena.settle(match,selection);
      assert.equal(game.winner,settled.winner);
      assert.deepEqual(game.units.filter(u=>u.side===0).map(u=>u.hp),
        settled.units.filter(u=>u.side===0).map(u=>u.hp));
    }
  }
});
