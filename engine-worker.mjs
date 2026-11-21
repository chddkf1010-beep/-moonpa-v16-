import { loadPyodide } from 'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/pyodide.mjs';

const app = (async () => {
  const py = await loadPyodide({indexURL:'https://cdn.jsdelivr.net/pyodide/v0.27.7/full/'});
  const directory = '/moonpa';
  py.FS.mkdir(directory);
  const files = ['combat','campaign','moonpa_world_v15','moonpa_economy_v15_1',
    'moonpa_growth','moonpa_market','moonpa_tracking','pages_bridge'];
  await Promise.all(files.map(async file => {
    const response = await fetch(new URL(`./engine/${file}.py`, import.meta.url));
    if (!response.ok) throw new Error(`게임 파일을 읽지 못했습니다 (${file}).`);
    py.FS.writeFile(`${directory}/${file}.py`, await response.text());
  }));
  return py.runPython(`import sys
sys.path.insert(0, '/moonpa')
from pages_bridge import handle
handle`);
})();

self.onmessage = async ({data}) => {
  try {
    const dispatch = await app;
    self.postMessage({state:JSON.parse(dispatch(data.path, JSON.stringify(data.payload ?? {})))});
  } catch (error) {
    self.postMessage({error:error.message});
  }
};
