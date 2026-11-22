import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {test} from 'node:test';
import vm from 'node:vm';

const management = readFileSync(new URL('../management.js',import.meta.url),'utf8');
const {sortedMembers,memberSortControl,bindSort,reorderMembers} = vm.runInNewContext(
  management + '\n({sortedMembers,memberSortControl,bindSort,reorderMembers})',
  {busy:false});

test('numeric order is reversible, stable on ties and keeps unknown values last', () => {
  const members=[{id:8,ca:74},{id:2,ca:100},{id:1,ca:74},{id:4,ca:null}];
  const ids=rows=>Array.from(rows,member=>member.id);
  assert.deepEqual(ids(sortedMembers(members,'ca',true)),[1,8,2,4]);
  assert.deepEqual(ids(sortedMembers(members,'ca',false)),[2,1,8,4]);
  assert.deepEqual(ids(members),[8,2,1,4]);
});

test('switching order reuses the same member nodes and preserves weekly assignments', () => {
  const first={id:11,ca:70};
  const second={id:12,ca:95};
  const firstRow={dataset:{sortId:'11'},assignment:'defend'};
  const secondRow={dataset:{sortId:'12'},assignment:'training'};
  const container={
    children:[secondRow,firstRow],
    append(...rows){this.children=rows;}
  };
  const button={focus:()=>{}};
  const select={value:'ca',focus:()=>{}};
  const toolbar={querySelector:selector=>selector==='[data-sort]'?select:button};
  const root={querySelector:selector=>selector.endsWith('[data-sort-direction]')?button:toolbar};
  memberSortControl('test-roster',{ca:'전력'});
  bindSort(root,'test-roster',()=>reorderMembers(container,'test-roster',[first,second]));
  button.onclick();
  assert.deepEqual(container.children,[firstRow,secondRow]);
  assert.equal(container.children[0],firstRow);
  assert.equal(container.children[0].assignment,'defend');
  assert.match(button.textContent,/오름차순/);
});
