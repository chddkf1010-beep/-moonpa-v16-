import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const require=createRequire(import.meta.url);
const {marketFilterCandidates,marketRarityCounts,MARKET_STATS}=require('../market-ui.js');
const full={strength:100,defense:100,stamina:100,agility:100,inner_power:100,sorcery:100,insight:100,willpower:100};
const rows=[
  {id:1,name:'A',role_id:0,rarity:'normal',ca:125,pa:170,growth_gap:45,
   attrs:{...full,strength:130,defense:155,stamina:145},eligible:true,fee:100,wage:12,age:29},
  {id:2,name:'B',role_id:4,rarity:'named',ca:95,pa:190,growth_gap:95,
   attrs:{...full,strength:50,defense:55,sorcery:130,inner_power:180},eligible:true,fee:120,wage:15,age:23},
  {id:3,name:'C',role_id:0,rarity:'legend',ca:180,pa:190,growth_gap:10,
   attrs:{...full,strength:180,defense:170,stamina:190},eligible:false,fee:300,wage:35,age:35},
  {id:4,name:'D',role_id:2,rarity:'normal',ca:135,pa:150,growth_gap:15,
   attrs:{...full,agility:185,insight:178},eligible:true,fee:110,wage:17,age:22}
];
const basic=()=>({rarity:'all',role:'all',minCA:'',maxCA:'',minPA:'',maxPA:'',minGap:'',
  eligibleOnly:false,sort:'pa',ascending:false,
  ranges:Object.fromEntries(MARKET_STATS.map(x=>[x,{min:'',max:''}]))});
test('rarity badges count current pool, and named+legend are filterable',()=>{
  assert.deepEqual(marketRarityCounts(rows),{all:4,normal:2,named:1,legend:1,rareplus:2});
  const filter=basic();filter.rarity='rareplus';
  assert.deepEqual(marketFilterCandidates(rows,filter).map(x=>x.id),[2,3]);
  filter.rarity='legend';
  assert.deepEqual(marketFilterCandidates(rows,filter).map(x=>x.id),[3]);
});
test('current CA and observed PA are independent min/max filters',()=>{
  const filter=basic();filter.minCA='120';filter.maxCA='140';filter.minPA='150';filter.maxPA='180';
  assert.deepEqual(marketFilterCandidates(rows,filter).map(x=>x.id),[1,4]);
  filter.minPA='160';
  assert.deepEqual(marketFilterCandidates(rows,filter).map(x=>x.id),[1]);
  filter.maxPA='160';
  assert.equal(marketFilterCandidates(rows,filter).length,0);
  filter.maxPA='';
  assert.equal(marketFilterCandidates(rows,filter).length,1);
});
test('eight independent attributes apply AND with rarity and roles',()=>{
  const filter=basic();filter.rarity='rareplus';filter.role='0';
  filter.ranges.strength.min='170';
  filter.ranges.defense.min='150';
  filter.ranges.stamina.max='200';
  assert.deepEqual(marketFilterCandidates(rows,filter).map(x=>x.id),[3]);
  filter.ranges.stamina.max='120';
  assert.equal(marketFilterCandidates(rows,filter).length,0);
  filter.ranges.stamina.max='';
  filter.ranges.inner_power.min='190';
  assert.equal(marketFilterCandidates(rows,filter).length,0);
});
test('growth potential gap, availability and per-attribute ordering',()=>{
  const filter=basic();filter.minGap='30';filter.eligibleOnly=true;
  assert.deepEqual(marketFilterCandidates(rows,filter).map(x=>x.id),[2,1]);
  filter.sort='stat:defense';
  assert.deepEqual(marketFilterCandidates(rows,filter).map(x=>x.id),[1,2]);
  filter.ascending=true;
  assert.deepEqual(marketFilterCandidates(rows,filter).map(x=>x.id),[2,1]);
});
test('team role gap sort favors missing roles, not simply CA',()=>{
  const filter=basic();filter.sort='need';
  const order=marketFilterCandidates(rows,filter,{'0':0,'2':2,'4':5}).map(x=>x.id);
  assert.deepEqual(order,[2,4,3,1]);
});
test('pure client filtering never mutates FA market roster or incoming filters',()=>{
  const filter=basic(),saved=JSON.stringify([rows,filter]);
  marketFilterCandidates(rows,filter,{'0':1});
  marketRarityCounts(rows);
  assert.equal(JSON.stringify([rows,filter]),saved);
});
