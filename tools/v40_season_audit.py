"""Real JS/Python campaign stress smoke. No cash injection; bankruptcy is a measured outcome."""
import json,subprocess,sys
from pathlib import Path
from campaign import Campaign,set_arena_resolver
from moonpa_savegame import create_save,load_save
import moonpa_economy_v15_1 as economy
import moonpa_incoming as incoming

ROOT=Path(__file__).resolve().parents[1]
JS="""import readline from 'node:readline';import {Arena} from './group-engine.mjs';
for await(const raw of readline.createInterface({input:process.stdin,crlfDelay:Infinity})){
try{const c=JSON.parse(raw);console.log(JSON.stringify(Arena.settle(c,{lineup:c.team,captain:c.captain,deputy:c.deputy,arts:c.chosenArts})))}
catch(e){console.log(JSON.stringify({error:e.message}))}}"""
def audit(seed,goal):
    proc=subprocess.Popen(['node','--input-type=module','-e',JS],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
    battles={}; saves=0; rounds=0; transfers=0; listings=0; renewals=0; failures=[]; caps=[]; snapshots=[]
    def resolve(raw):
        cfg=json.loads(raw);kind=cfg['kind'];battles[kind]=battles.get(kind,0)+1
        proc.stdin.write(raw+'\n');proc.stdin.flush()
        r=json.loads(proc.stdout.readline())
        if 'error' in r:raise RuntimeError(r['error'])
        return json.dumps(r,ensure_ascii=False)
    set_arena_resolver(resolve)
    c=Campaign(seed,interactive=True)
    c.found_sect('검증문파'+str(seed),'balanced')
    def check():
        nonlocal c,saves
        w=c.world; economy.assert_world(w)
        assert c.overview()['player_journal']['difference']==0
        blob=create_save(c); restored=load_save(blob)
        assert restored.overview()==c.overview(),(seed,c.season,c.week,c.phase,'snapshot divergence')
        assert restored.world.rng.getstate()==w.rng.getstate()
        c=restored;saves+=1
    try:
        while c.season<=goal and not c.world.player_bankrupted:
            rounds+=1
            if rounds>500:raise RuntimeError('phase loop')
            if c.phase=='draft':
                c.draft_pick(c.season,c.draft_round,None)
            elif c.phase=='fa':
                c.advance_phase('fa')
            elif c.phase=='report':
                if c.season_contracts():
                    for r in c.season_contracts()['pending']:
                        c.decide_contract(c.season,c.week,r['id'],r['contract_end'],action='release')
                        renewals+=1
                if c.week in (1,13,26,39,49,51):check()
                c.advance_phase('report')
            elif c.phase=='group':
                cfg=c.group_play
                if cfg.get('captureChoice'):
                    c.resolve_capture(cfg['match'],'replace',cfg['captureChoice']['replaceable'][0]['id'])
                else:
                    if cfg['kind']=='tournament' or rounds%17==0:check();cfg=c.group_play
                    c.finish_group(cfg['match'],json.loads(resolve(json.dumps(cfg,ensure_ascii=False))))
                c.continue_month()
            elif c.phase=='ready':
                if c.week==1:
                    snapshots.append(dict(season=c.season,cash=c.guild.cash,tier=c.guild.tier,roster=len(c.guild.fighters)))
                # Review feasible current offers; listing is not an automatic transfer.
                offers=c.overview()['incoming']['offers']
                for r in offers:
                    if r['status']=='open' and not r['exchange'] and len(c.guild.fighters)>17:
                        incoming.respond(c,c.season,c.week,r['id'],r['revision'],'accept');transfers+=1;break
                if c.week<49 and len(c.guild.fighters)>17 and listings<c.season:
                    f=next((f for f in sorted(c.guild.fighters,key=lambda x:(x.ca,x.fid)) if incoming.available(c,c.guild,f)),None)
                    if f:
                        incoming.listing(c,c.season,c.week,f.fid,100);listings+=1
                # Keep a healthy offensive roster and target the weakest selectable neutral site.
                available=sorted((f for f in c.guild.fighters if not f.injured and f.fid not in c.world.away(c.guild.gid)),key=lambda f:(-f.ca,f.fid))
                zones=[z for z in c.overview()['zones'] if z['selectable'] and z['owner'] is None]
                a=dict(group_mode=True)
                if c.week<49 and len(available)>=8 and zones:
                    z=min(zones,key=lambda z:z['id'])
                    a['attack']=dict(zone=z['id'],setup=[dict(id=f.fid) for f in available[:8]])
                c.submit_month(c.season,c.week,a)
            else:raise RuntimeError('unexpected phase '+c.phase)
        check()
        result=dict(seed=seed,goal=goal,season=c.season,week=c.week,phase=c.phase,bankrupt=c.world.player_bankrupted,cash=c.guild.cash,debts=c.world.debts[c.guild.gid].total(),roster=len(c.guild.fighters),tier=c.guild.tier,battles=battles,saves=saves,transfers=transfers,listings=listings,contract_releases=renewals,snapshots=snapshots,journal_difference=c.overview()['player_journal']['difference'])
        print('V40_SEASON_AUDIT '+json.dumps(result,ensure_ascii=False),flush=True)
    finally:
        set_arena_resolver(None);proc.stdin.close();proc.terminate();proc.wait(timeout=10)
if __name__=='__main__':
    audit(int(sys.argv[1]),int(sys.argv[2]))
