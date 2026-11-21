import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs';

const app = (async () => {
  const py = await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'});
  const directory = '/moonpa';
  py.FS.mkdir(directory);
  const revision = new URL(import.meta.url).searchParams.get("v");
  const files = ['combat_environment','combat','campaign','moonpa_world_v15','moonpa_economy_v15_1',
    'moonpa_growth','moonpa_market','moonpa_names','moonpa_portraits','moonpa_missions','moonpa_long_missions','moonpa_elite','moonpa_elite_play','moonpa_sagas','moonpa_tracking','moonpa_savegame','pages_bridge'];
  await Promise.all(files.map(async file => {
    const url = new URL(`./engine/${file}.py`, import.meta.url);
    if (revision) url.searchParams.set("v", revision);
    const response = await fetch(url, {cache:"no-store"});
    if (!response.ok) throw new Error(`게임 파일을 읽지 못했습니다 (${file}).`);
    py.FS.writeFile(`${directory}/${file}.py`, await response.text());
  }));
  return py.runPython(`import sys
sys.path.insert(0, '/moonpa')
from pages_bridge import handle
handle`);
})();

// Snapshot AFTER successful mutations, including mid-battle rounds.
const SAVE_AFTER = new Set([
  'advance_phase','draft_pick','upgrade','equip','train_skill','transfer_accept',
  'recruit','week','start','round','dismiss_battle','new_game','import_save',
  'elite_inspect','elite_decide','elite_finish','found_sect'
]);

self.onmessage = async ({data}) => {
  try {
    const dispatch = await app;
    const state=JSON.parse(dispatch(data.path, JSON.stringify(data.payload ?? {})));
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
