"""Ten-season smoke simulation of 32 autonomous sects and expeditions.

Run: PYTHONPATH=engine python tools/check_long_mission_10season.py
Checks integrity, not a predetermined player win rate or economy target.
"""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))

from moonpa_economy_v15_1 import World15,one_week,annual_rollover,install_player,assert_world


def run(seed=114):
    w=World15(seed,'balanced')
    for week in range(1,53):one_week(w,0,week)
    annual_rollover(w,0)
    install_player(w,'balanced')
    annual=[]
    for season in range(1,11):
        for week in range(1,53):
            one_week(w,season,week)
        assert all(not tasks for tasks in w.long_missions.values()),'Expedition crossed annual settlement'
        assert_world(w)
        annual.append(dict(season=season,cash=sum(g.cash for g in w.guilds.values()),
                           bankruptcies=w.bankruptcies,completed=w.long_completed,
                           withdrawn=w.long_abandoned))
        annual_rollover(w,season)
    assert w.long_completed>0,'Autonomous AI never completed an expedition'
    assert_world(w)
    return dict(seed=seed,completed=w.long_completed,withdrawn=w.long_abandoned,
                bankruptcies=w.bankruptcies,annual=annual,
                bank_balance_reconciled=True,
                source=w.money.source,sink=w.money.sink)


if __name__=='__main__':
    print(json.dumps(run(),ensure_ascii=False))
