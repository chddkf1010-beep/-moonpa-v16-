import { Arena } from './group-engine.mjs?v=contested1-bench1-v40phase5b';
import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs';

const app = (async () => {
  const py = await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'});
  const directory = '/moonpa';
  py.FS.mkdir(directory);
  const revision = new URL(import.meta.url).searchParams.get("v");
  const files = ['combat_environment','moonpa_month','moonpa_sites','moonpa_notables','moonpa_notable_combat','combat','campaign','moonpa_world_v15','moonpa_economy_v15_1',
    'moonpa_growth','moonpa_growth_dashboard','moonpa_training_focus','moonpa_training_planner','moonpa_market','moonpa_incoming','moonpa_player_ledger','moonpa_market_intel','moonpa_ai_tactics','moonpa_prebattle','moonpa_honors','moonpa_names','moonpa_portrait_v2','moonpa_portraits','moonpa_missions','moonpa_long_missions','moonpa_elite','moonpa_elite_play','moonpa_sagas','moonpa_tracking','moonpa_savegame','pages_bridge'];
  await Promise.all(files.map(async file => {
    const url = new URL(`./engine/${file}.py`, import.meta.url);
    if (revision) url.searchParams.set("v", revision);
    const response = await fetch(url, {cache:"no-store"});
    if (!response.ok) throw new Error(`게임 파일을 읽지 못했습니다 (${file}).`);
    py.FS.writeFile(`${directory}/${file}.py`, await response.text());
  }));
  py.globals.set('arena_resolve_json', raw=>JSON.stringify(Arena.settle(JSON.parse(raw))));
  return py.runPython(`import sys
sys.path.insert(0, '/moonpa')
from pages_bridge import handle
from campaign import set_arena_resolver
set_arena_resolver(arena_resolve_json)
handle`);
})();

// Snapshot AFTER successful mutations, including mid-battle rounds.
const SAVE_AFTER = new Set([
  'advance_phase','draft_pick','upgrade','group_finish','group_auto','capture_resolve','equip','train_skill','transfer_accept',
  'contract_decision','recruit','month','week','start','round','dismiss_battle','new_game','import_save',
  'elite_inspect','elite_decide','elite_finish','found_sect','treasury_policy','prebattle_save',
  'growth_focus_set','growth_focus_auto','group_assign','prebattle_arena_save',
  'transfer_bargain','transfer_bargain_accept','transfer_bargain_decline','incoming_listing','incoming_respond'
]);

self.onmessage = async ({data}) => {
  try {
    const dispatch = await app;
    let payload = data.payload ?? {};
    const groupAction=data.path==='group_finish'||data.path==='group_auto';
    if(groupAction) {
      const {group_play: match} = JSON.parse(dispatch('state','{}'));
      if(!match || match.captureChoice || match.match!==payload.match) throw new Error('진행 중인 단체전을 다시 불러오세요.');
      const result=Arena.settle(match,data.path==='group_auto'?undefined:payload);
      payload={match:match.match,result};
    }
    const state=JSON.parse(dispatch(groupAction?'group_finish':data.path, JSON.stringify(payload)));
    let save=null, save_error=null;
    if (SAVE_AFTER.has(data.path)) {
      try {
        save=JSON.parse(dispatch('export_save', '{}'));
      } catch (error) {
        // Gameplay succeeded; avoid masking it with a snapshot error.
        save_error='자동저장 생성 실패: '+error.message;
      }
    }
    self.postMessage({state,save,save_error});
  } catch (error) {
    self.postMessage({error:error.message});
  }
};
