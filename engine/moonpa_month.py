"""Monthly player decisions on the existing 52-week simulation clock."""
from bisect import bisect_left


MONTH_ENDS = (4, 8, 13, 17, 21, 26, 30, 34, 39, 43, 47, 52)


def month_number(week):
    return bisect_left(MONTH_ENDS, week)+1


def summarize(reports, month, end_week):
    first,last=reports[0],reports[-1]
    summary=dict(last,month=month,week=first['week'],end_week=end_week,
                 cash_before=first['cash_before'],battle=first['battle'])
    summary['cash_change']=summary['cash']-summary['cash_before']
    for key in ('income','expenses','investment_paid'):
        summary[key]=sum(report.get(key,0) for report in reports)
    for key in ('entries','missions','long_missions','elite_missions','tactical_defenses','conquest_duels'):
        summary[key]=[dict(row,week=report['week']) if key!='entries' else row
                      for report in reports for row in report.get(key,[])]
    summary['conquest_final']=next((r['conquest_final'] for r in reports if r.get('conquest_final')),None)
    summary['tactical_defense']=next(iter(summary['tactical_defenses']),None)
    assert sum(e['amount'] for e in summary['entries'])==summary['cash_change']
    summary['briefing']=dict(last['briefing'],
        rank_before=first['briefing']['rank_before'],
        tier_before=first['briefing']['tier_before'],
        territories_before=first['briefing']['territories_before'],
        defense_plan=first['briefing']['defense_plan'],
        defenses=[dict(row,week=r['week']) for r in reports for row in r['briefing']['defenses']])

    territories={}
    for report in reports:
        for row in report['territories']:
            aggregate=territories.setdefault(row['zone'],dict(row,days=0,gross=0))
            aggregate['days']+=row['days']
            aggregate['gross']+=row['gross']
    summary['territories']=list(territories.values())

    members={}
    trainees={}
    for report in reports:
        for row in report['members']:
            previous=members.get(row['id'],{})
            members[row['id']]=dict(row,
                ca_change=round(previous.get('ca_change',0)+row['ca_change'],3),
                levels=previous.get('levels',0)+row['levels'],
                xp_before=previous.get('xp_before',row['xp_before']),
                injured_before=previous.get('injured_before',row['injured_before']))
        for row in report['training_report']['rows']:
            previous=trainees.get(row['id'],{})
            trainees[row['id']]=dict(row,paid=previous.get('paid',0)+row['paid'],
                invested=previous.get('invested',0)+row['invested'])
    for fid,row in trainees.items():
        row['ca_change']=members[fid]['ca_change']
    summary['members']=list(members.values())
    summary['new_injuries']=len({row['id'] for r in reports for row in r['members']
                                 if not row['injured_before'] and row['injured']})
    summary['training_report']=dict(
        planned_count=len(trainees), funded_count=sum(row['paid']>0 for row in trainees.values()),
        paid_total=sum(r['training_report']['paid_total'] for r in reports),
        investment_total=sum(r['training_report']['investment_total'] for r in reports),
        rows=sorted(trainees.values(),key=lambda row:(-row['paid'],row['id'])),
        note='CA 변동은 한 달 동안 수행한 모든 활동을 합친 실측치입니다.')
    budgets=[r['budget'] for r in reports if r['budget'] is not None]
    if budgets:
        summary['budget']={key:sum(b[key] for b in budgets) for key in ('fixed','preparation')}
    return summary
