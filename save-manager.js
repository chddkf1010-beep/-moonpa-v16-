/* Browser-side save slots. The Python engine is the only source of gameplay state.
 * localStorage contains compressed, versioned JSON saves, never executable data.
 */
class SaveManager {
  static AUTO = 'moonpa.v3.autosave';
  static SLOT = index => 'moonpa.v3.slot.' + index;
  static MAX_FILE_BYTES = 14_000_000;

  constructor({callEngine,applyGame,isBusy,setBusy}) {
    this.callEngine = callEngine;
    this.applyGame = applyGame;
    this.isBusy = isBusy;
    this.setBusy = setBusy;
    this.ready = false;
    this.autoAvailable = true;
    this.button = document.querySelector('#save-menu');
    this.status = document.querySelector('#save-status');
    this.modal = document.querySelector('#save-dialog');
    this.feedback = document.querySelector('#save-feedback');
    this.rows = document.querySelector('#save-slots');
    this.fileInput = document.querySelector('#save-file');
    this.button.disabled = true;
    this.button.onclick = () => this.show();
    document.querySelector('#save-close').onclick = () => this.modal.close();
    document.querySelector('#save-export').onclick = () => this.exportFile();
    document.querySelector('#save-import').onclick = () => this.fileInput.click();
    document.querySelector('#save-reset').onclick = () => this.resetGame();
    this.fileInput.onchange = () => this.loadFile();
  }

  setStatus(message, problem=false) {
    this.status.textContent=message;
    this.status.dataset.problem=problem?'true':'false';
  }
  message(message,problem=false) {
    this.feedback.textContent=message;
    this.feedback.dataset.problem=problem?'true':'false';
    this.setStatus(message,problem);
  }
  read(key) {
    try {
      const text=window.localStorage.getItem(key);
      if(!text) return null;
      const entry=JSON.parse(text);
      if(!entry || typeof entry!=='object' || !entry.snapshot) throw new Error('형식 오류');
      return entry;
    } catch(error) {
      throw new Error('저장 기록을 읽을 수 없습니다: '+error.message);
    }
  }
  write(key,save) {
    const entry={savedAt:new Date().toISOString(),snapshot:save};
    window.localStorage.setItem(key,JSON.stringify(entry));
    return entry;
  }
  autosave(save) {
    try {
      const entry=this.write(SaveManager.AUTO,save);
      this.autoAvailable=true;
      this.setStatus('자동저장 완료 · '+new Date(entry.savedAt).toLocaleTimeString('ko-KR'));
      return true;
    } catch(error) {
      this.autoAvailable=false;
      this.setStatus('자동저장 실패 · 저장 공간 또는 브라우저 권한 확인',true);
      return false;
    }
  }
  async boot() {
    this.setStatus('저장 기록 확인 중…');
    let entry=null, restored=false, invalid=false;
    try {
      entry=this.read(SaveManager.AUTO);
      if(entry) {
        const loaded=await this.callEngine('import_save',{save:entry.snapshot});
        this.applyGame(loaded);
        restored=true;
      }
    } catch(error) {
      invalid=true;
      this.setStatus('자동 복원 실패 · 저장 파일 확인 필요',true);
      console.warn('문파 키우기 저장 복구 실패:',error);
    }
    if(!restored) {
      try {
        this.applyGame(await this.callEngine('state',{}));
        if(!invalid && !entry) {
          const first=await this.callEngine('export_save',{});
          this.autosave(first);
        }
      } catch(error) {
        document.querySelector('#error').textContent='게임 엔진 시작 실패: '+error.message;
        this.setStatus('게임 엔진 오류',true);
        return;
      }
    }
    if(restored)this.setStatus('이전 플레이 자동 복원 완료');
    this.ready=true;
    this.button.disabled=false;
  }
  show() {
    if(!this.ready || this.isBusy())return;
    this.feedback.textContent='';
    this.refresh();
    this.modal.showModal();
  }
  refresh() {
    this.rows.replaceChildren();
    for(let slot=1;slot<=3;slot++) {
      const row=document.createElement('div');
      row.className='save-slot';
      const label=document.createElement('div');
      const title=document.createElement('strong');title.textContent='수동 저장 '+slot;
      const detail=document.createElement('small');
      let entry=null, invalid=false;
      try {entry=this.read(SaveManager.SLOT(slot));}
      catch(error){invalid=true;}
      const meta=entry?.snapshot?.meta;
      detail.textContent=invalid?'저장 정보 오류':
        meta?((meta.guild||'문파')+' · '+meta.season+'시즌 '+meta.week+'주 · '+
              new Date(entry.savedAt).toLocaleString('ko-KR')):'비어 있음';
      label.append(title,detail);
      const save=document.createElement('button');
      save.textContent='저장';
      save.onclick=()=>this.saveSlot(slot);
      const load=document.createElement('button');
      load.textContent='불러오기';
      load.disabled=!entry;
      load.onclick=()=>this.loadSlot(slot);
      row.append(label,save,load);
      this.rows.append(row);
    }
  }
  async withEngine(work) {
    if(this.isBusy() || !this.ready)return;
    this.setBusy(true);
    this.disable(true);
    try {await work();}
    catch(error){this.message(error.message,true);}
    finally {
      this.disable(false);
      this.setBusy(false);
    }
  }
  disable(value) {
    for(const b of this.modal.querySelectorAll('button'))b.disabled=value;
    if(!value)this.refresh();
  }
  async saveSlot(slot) {
    await this.withEngine(async()=>{
      const snapshot=await this.callEngine('export_save',{});
      try {
        this.write(SaveManager.SLOT(slot),snapshot);
      } catch(error) {
        throw new Error('수동 저장 실패: 브라우저 저장 용량과 접근 권한을 확인하세요.');
      }
      this.message('수동 저장 '+slot+' 완료');
    });
  }
  async loadSlot(slot) {
    let entry;
    try {entry=this.read(SaveManager.SLOT(slot));}
    catch(error){this.message(error.message,true);return;}
    if(!entry || !window.confirm('수동 저장 '+slot+'에서 게임을 불러올까요? 현재 자동저장 기록은 교체됩니다.'))return;
    await this.loadSnapshot(entry.snapshot);
  }
  async loadSnapshot(snapshot) {
    let loaded=null;
    await this.withEngine(async()=>{
      // Python validates and creates a detached world; old game survives errors.
      loaded=await this.callEngine('import_save',{save:snapshot});
      this.modal.close();
    });
    // Render after releasing the global busy lock. FA/market screens fetch
    // their listings during render and otherwise would remain blank.
    if(loaded)this.applyGame(loaded);
  }
  async exportFile() {
    await this.withEngine(async()=>{
      const snapshot=await this.callEngine('export_save',{});
      const text=JSON.stringify(snapshot,null,2);
      const name='moonpa-v3-'+snapshot.meta.season+'s-'+snapshot.meta.week+'w.json';
      const url=URL.createObjectURL(new Blob([text],{type:'application/json;charset=utf-8'}));
      const link=document.createElement('a');
      link.href=url;link.download=name;
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(()=>URL.revokeObjectURL(url),1000);
      this.message('세이브 파일을 내보냈습니다. 다운로드 폴더를 확인하세요.');
    });
  }
  async loadFile() {
    const file=this.fileInput.files?.[0];
    this.fileInput.value='';
    if(!file)return;
    if(file.size>SaveManager.MAX_FILE_BYTES) {
      this.message('세이브 파일이 너무 큽니다. 14MB 이하 파일을 선택하세요.',true);
      return;
    }
    let snapshot;
    try {snapshot=JSON.parse(await file.text());}
    catch(error){this.message('올바른 JSON 세이브 파일이 아닙니다.',true);return;}
    if(!window.confirm('선택한 세이브 파일을 불러올까요? 현재 자동저장 기록이 교체됩니다.'))return;
    await this.loadSnapshot(snapshot);
  }
  async resetGame() {
    if(!window.confirm('새 문파로 처음부터 시작할까요? 기존 자동저장은 덮어씌워집니다. 필요한 기록은 먼저 수동 저장하거나 파일로 내보내세요.'))return;
    await this.withEngine(async()=>{
      const replacement=await this.callEngine('new_game',{});
      this.applyGame(replacement);
      this.modal.close();
    });
  }
}
