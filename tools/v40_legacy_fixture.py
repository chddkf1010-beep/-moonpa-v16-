"""Run ONLY with the old main engine on PYTHONPATH."""
import json,sys
from pathlib import Path
from campaign import Campaign
from moonpa_savegame import create_save
from combat import SECRET_SKILLS

out=Path(sys.argv[1]);out.mkdir(parents=True,exist_ok=True)
def emit(label,c):
    g=c.guild;w=c.world
    snapshot=dict(name=g.name,season=c.season,week=c.week,phase=c.phase,cash=g.cash,
        roster=[dict(id=f.fid,name=f.name,portrait=f.portrait_key,wage=f.wage,end=f.contract_end,
            ca=f.ca,pa=f.pa,injured=f.injured,arts=f.development.secret_arts) for f in g.fighters],
        owners=[z.owner for z in w.zones],rng=repr(w.rng.getstate()),
        away=sorted(w.away(g.gid)),group=c.group_play)
    (out/(label+'.json')).write_text(json.dumps(dict(save=create_save(c),snapshot=snapshot),ensure_ascii=False),encoding='utf8')
c=Campaign(23,interactive=True);c.found_sect('구판검증','balanced')
emit('draft',c)
c=Campaign(23,interactive=True);c.phase='ready'
emit('ready',c)
site=next(z for z in c.overview()['zones'] if z['selectable'] and z['owner'] is None)
crew=[dict(id=f.fid) for f in c.guild.fighters if not f.injured][:8]
c.submit_week(1,1,dict(group_mode=True,attack=dict(zone=site['id'],setup=crew)))
assert c.phase=='group'
emit('group',c)
c=Campaign(23);f=c.guild.fighters[0];f.development.secret_arts.append(SECRET_SKILLS[f.role])
offer=next(x for x in c.overview()['long_mission_board'] if x['duration']==2)
c.submit_week(1,1,{'long_orders':[dict(id=offer['id'],members=[f.fid for f in c.guild.fighters[3:6]])]})
assert c.world.away(c.guild.gid)
emit('expedition',c)
print('OLD_MAIN_FIXTURES: draft ready group expedition')
