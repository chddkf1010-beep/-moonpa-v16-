/* Browser-side save slots. The Python engine is the only source of gameplay state.
 * localStorage contains compressed, versioned JSON saves, never executable data.
 */
class SaveManager {
  static AUTO = 'moonpa.v3.autosave';
  static SLOT = index => 'moonpa.v3.slot.' + index;
  static RECOVERY = 'moonpa.v3.before-new-game';
  static MAX_FILE_BYTES = 14_000_000;

  constructor({callEngine,applyGame,isBusy,setBusy}) {
    this.callEngine = callEngine;
    this.applyGame = applyGame;
    this.isBusy = isBusy;
    this.setBusy = setBusy;
    this.ready = false;
    this.button = document.querySelector('#save-menu');
    this.status = document.querySelector('#save-status');
    this.modal = document.querySelector('#save-dialog');
    this.feedback = document.querySelector('#save-feedback');
    this.rows = document.querySelector('#save-slots');
    this.autoDetail = document.querySelector('#save-auto-detail');
    this.recoveryRow = document.querySelector('#save-recovery-row');
    this.recoveryDetail = document.querySelector('#save-recovery-detail');
    this.recover = document.querySelector('#save-recover');
    this.fileInput = document.querySelector('#save-file');
    this.button.disabled = true;
    this.button.onclick = () => this.show();
    document.querySelector('#save-close').onclick = () => this.modal.close();
    document.querySelector('#save-now').onclick = () => this.saveNow();
    document.querySelector('#save-export').onclick = () => this.exportFile();
    document.querySelector('#save-import').onclick = () => this.fileInput.click();
    document.querySelector('#save-reset').onclick = () => this.resetGame();
    this.recover.onclick = () => this.loadRecord(SaveManager.RECOVERY,'새 게임 시작 전 기록');
    this.modal.addEventListener('cancel',event=>{
      if(this.isBusy())event.preventDefault();
    });
    this.fileInput.onchange = () => this.loadFile();
  }

  setStatus(message, problem=false) {
    this.status.textContent=message;
    this.status.dataset.problem=problem?'true':'false';
  }
  message(message,problem=false) {
    this.feedback.textContent=message;
    this.feedback.dataset.problem=problem?'true':'false';
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
      this.setStatus('자동저장 완료 · '+new Date(entry.savedAt).toLocaleTimeString('ko-KR'));
      return true;
    } catch(error) {
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
        const screen=document.querySelector('#screen');
        if(screen?.textContent==='전투 엔진 불러오는 중…')
          screen.textContent='페이지를 새로고침해 다시 시도해 주세요.';
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

  describe(key,detail) {
    try {
      const entry=this.read(key);
      const meta=entry?.snapshot?.meta;
      detail.textContent=meta
        ? (meta.guild||'문파')+' · '+meta.season+'시즌 '+(meta.month?meta.month+'개월차':meta.week+'주')+' · '+
          new Date(entry.savedAt).toLocaleString('ko-KR')
        : '비어 있음';
      return {entry,exists:Boolean(entry)};
    } catch(error) {
      detail.textContent='저장 정보를 읽을 수 없음';
      return {entry:null,exists:true};
    }
  }

  refresh() {
    this.describe(SaveManager.AUTO,this.autoDetail);
    const recovery=this.describe(SaveManager.RECOVERY,this.recoveryDetail);
    this.recoveryRow.hidden=!recovery.exists;
    this.recover.disabled=!recovery.entry;
    this.rows.replaceChildren();
    for(let slot=1;slot<=3;slot++) {
      const row=document.createElement('div');
      row.className='save-slot';
      const label=document.createElement('div');
      const title=document.createElement('strong');title.textContent='수동 저장 '+slot;
      const detail=document.createElement('small');
      const {entry}=this.describe(SaveManager.SLOT(slot),detail);
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
  async saveNow() {
    await this.withEngine(async()=>{
      const snapshot=await this.callEngine('export_save',{});
      if(!this.autosave(snapshot))throw new Error('현재 진행을 저장할 수 없습니다. 세이브 파일로 내보낼 수 있어요.');
      this.message('현재 진행을 자동저장에 기록했어요.');
    });
  }

  async saveSlot(slot) {
    await this.withEngine(async()=>{
      const key=SaveManager.SLOT(slot);
      try {
        if(window.localStorage.getItem(key)!==null &&
           !window.confirm('수동 저장 '+slot+'의 기존 기록을 덮어쓸까요?'))return;
        this.write(key,await this.callEngine('export_save',{}));
      } catch(error) {
        throw new Error('수동 저장 실패: 브라우저 저장 용량과 접근 권한을 확인하세요.');
      }
      this.message('수동 저장 '+slot+' 완료');
    });
  }
  async loadSlot(slot) {
    await this.loadRecord(SaveManager.SLOT(slot),'수동 저장 '+slot);
  }

  async loadRecord(key,label) {
    let entry;
    try {entry=this.read(key);}
    catch(error){this.message(error.message,true);return;}
    if(!entry || !window.confirm(label+'을 불러올까요? 현재 자동저장 기록이 교체됩니다.'))return;
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
    let replacement=null;
    await this.withEngine(async()=>{
      // Keep the live campaign even if the latest background autosave failed.
      const key=SaveManager.RECOVERY;
      let previous;
      try {previous=window.localStorage.getItem(key);}
      catch(error){throw new Error('현재 문파를 보관할 수 없습니다. 브라우저 저장 권한을 확인하세요.');}
      const warning=previous===null?'':' 기존의 새 게임 시작 전 기록 1개는 교체됩니다.';
      if(!window.confirm('새 문파로 시작할까요? 현재 문파는 새 게임 시작 전 기록에 보관합니다.'+warning))return;
      const snapshot=await this.callEngine('export_save',{});
      try {this.write(key,snapshot);}
      catch(error){throw new Error('현재 문파를 보관할 공간이 부족합니다. 파일로 내보내거나 브라우저 저장 공간을 확인하세요.');}
      try {replacement=await this.callEngine('new_game',{});}
      catch(error){
        try {
          if(previous===null)window.localStorage.removeItem(key);
          else window.localStorage.setItem(key,previous);
        } catch(storageError) {
          throw new Error(error.message+' · 현재 문파 스냅샷은 새 게임 시작 전 기록에 남아 있습니다.');
        }
        throw error;
      }
      this.modal.close();
    });
    if(replacement)this.applyGame(replacement);
  }
}
