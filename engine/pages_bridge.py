"""JSON adapter for the same campaign engine used by the local HTTP server."""
import json

from campaign import Campaign
from moonpa_savegame import create_save, load_save
import moonpa_prebattle as prebattle
import moonpa_honors as honors
import moonpa_growth_dashboard as growth_dashboard
import moonpa_training_focus as training_focus
import moonpa_training_planner as training_planner

game = Campaign(23, interactive=True)


def handle(path, raw_payload):
    global game
    body = json.loads(raw_payload)
    if path == 'export_save':
        return json.dumps(create_save(game),ensure_ascii=False)
    if path == 'import_save':
        loaded = load_save(body['save'])
        game = loaded   # Commit only after all checks pass; existing game is untouched on failure.
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'new_game':
        replacement = Campaign(23, interactive=True)
        game = replacement
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'elite_inspect':
        game.elite_inspect()
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'elite_decide':
        game.elite_decide(body['choice'])
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'elite_finish':
        game.elite_finish()
        game.continue_month()
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'dismiss_battle':
        game.dismiss_battle()
        game.continue_month()
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'found_sect':
        game.found_sect(body['name'],body['strategy'])
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'growth_focus_set':
        result=game.set_training_focus(body['id'],body['focus'])
        return json.dumps(dict(result=result,detail=game.member_detail(body['id']),state=game.overview()),ensure_ascii=False)
    if path == 'growth_focus_preview':
        return json.dumps(game.preview_training_focus(body.get('mode','attack'),body.get('overwrite',False)),ensure_ascii=False)
    if path == 'growth_focus_auto':
        result=game.auto_training_focus(body.get('mode','attack'),body.get('overwrite',False),body.get('expected'))
        return json.dumps(dict(result=result,state=game.overview()),ensure_ascii=False)
    if path == 'growth_training_plan':
        return json.dumps(training_planner.preview(game,body.get('mode','attack'),
                          body.get('assignments',{}),body.get('count',4)),ensure_ascii=False)
    if path == 'growth_view':
        return json.dumps(growth_dashboard.dashboard(game,body.get('mode','attack')),ensure_ascii=False)
    if path == 'honors_history':
        return json.dumps(honors.chronicle(game.world,body.get('guild_id',game.guild.gid),game.season),ensure_ascii=False)
    if path == 'honors_codex':
        return json.dumps(honors.codex(game.world,body.get('guild_id',game.guild.gid),game.season),ensure_ascii=False)
    if path == 'sect_profile':
        return json.dumps(game.sect_profile(body['id']),ensure_ascii=False)
    if path == 'treasury_policy':
        game.set_treasury_policy(body['policy'])
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'prebattle_arena_view':
        return json.dumps(prebattle.arena_view(game,body.get('mode','attack'),body.get('zone_id')),ensure_ascii=False)
    if path == 'prebattle_arena_save':
        return json.dumps(prebattle.arena_save(game,body['mode'],body['zone_id'],
            body['team'],body['captain'],body['deputy'],body['chosenArts']),ensure_ascii=False)
    if path == 'prebattle_view':
        return json.dumps(prebattle.view(game,body.get('mode','attack'),body.get('zone_id')),ensure_ascii=False)
    if path == 'prebattle_auto':
        view=prebattle.view(game,body.get('mode','attack'),body.get('zone_id'))
        if view['enemy'] is None:
            raise ValueError('현재 선택할 수 있는 상대 구역이 없습니다.')
        plan=prebattle.deputy_pick(view['roster'],prebattle.enemy_signals(view['enemy']))
        return json.dumps(dict(view=view,plan=plan),ensure_ascii=False)
    if path == 'prebattle_preview':
        return json.dumps(prebattle.preview(game,body['mode'],body['zone_id'],body['data']),ensure_ascii=False)
    if path == 'prebattle_save':
        return json.dumps(prebattle.save(game,body['mode'],body['zone_id'],body['data']),ensure_ascii=False)
    if path == 'advance_phase':
        game.advance_phase(body['phase'])
        return json.dumps(game.overview(), ensure_ascii=False)
    if path == 'draft_pick':
        game.draft_pick(body['season'],body['round'],body.get('id'))
        return json.dumps(game.overview(), ensure_ascii=False)
    if path == 'upgrade':
        game.upgrade(body['id'])
        return json.dumps(game.overview(), ensure_ascii=False)
    if path == 'equip':
        detail = game.equip(body['id'],body['skills'])
        return json.dumps(dict(detail=detail,state=game.overview()), ensure_ascii=False)
    if path == 'contract_decision':
        result = game.decide_contract(body['season'],body['week'],body['id'],body['expected_end'],
                                      action=body['action'],new_end=body.get('new_end'),
                                      wage=body.get('wage'),expected_attempts=body.get('expected_attempts'))
        state = game.overview()
        detail = game.member_detail(body['id']) if state['contract_review'] is None else None
        return json.dumps(dict(detail=detail,state=state,result=result), ensure_ascii=False)
    if path in ('member', 'train_skill'):
        detail = game.member_detail(body['id']) if path == 'member' else game.train_skill(body['id'], body['skill'])
        return json.dumps(detail, ensure_ascii=False)
    if path == 'scout':
        return json.dumps(game.scouting(body.get('seller')), ensure_ascii=False)
    if path == 'incoming_listing':
        from moonpa_incoming import listing
        listing(game,body['season'],body['week'],body['id'],body.get('price'))
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'incoming_respond':
        from moonpa_incoming import respond
        respond(game,body['season'],body['week'],body['id'],body['revision'],body['choice'],body.get('fee'),body.get('exchange'))
        return json.dumps(game.overview(),ensure_ascii=False)
    if path == 'transfer_talk_view':
        return json.dumps(game.transfer_talk_view(body['season'],body['week'],body['seller'],body['id']),ensure_ascii=False)
    if path == 'transfer_bargain':
        return json.dumps(game.transfer_bargain(body['season'],body['week'],body['seller'],body['id'],body['fee'],body.get('exchange',[])),ensure_ascii=False)
    if path == 'transfer_bargain_accept':
        talk=game.transfer_bargain_accept(body['season'],body['week'],body['seller'],body['id'],body['revision'])
        return json.dumps(dict(talk=talk,state=game.overview()),ensure_ascii=False)
    if path == 'transfer_bargain_decline':
        return json.dumps(game.transfer_bargain_decline(body['season'],body['week'],body['seller'],body['id'],body['revision']),ensure_ascii=False)
    if path == 'transfer_suggestion':
        suggestion = game.transfer_suggestion(body['season'],body['week'],body['seller'],body['id'])
        return json.dumps(suggestion, ensure_ascii=False)
    if path in ('transfer_offer', 'transfer_accept'):
        commit = path == 'transfer_accept'
        transfer = game.transfer(body['season'], body['week'], body['seller'],
                                 body['id'], body['fee'], body.get('exchange', []), commit)
        result = dict(transfer=transfer)
        if commit:
            result['state'] = game.overview()
        return json.dumps(result, ensure_ascii=False)
    if path == 'market_compare':
        return json.dumps(game.market_compare(body['ids'],body.get('replace_id')),ensure_ascii=False)
    if path == 'free_agents':
        return json.dumps(game.free_agents(), ensure_ascii=False)
    if path == 'recruit':
        result = game.recruit(body['season'], body['week'], body['id'], body['years'])
        return json.dumps(dict(recruitment=result, state=game.overview()), ensure_ascii=False)
    if path == 'group_assign':
        game.group_assign(body['match'],body['team'],body['defense'],
                          body['captain'],body['deputy'])
    elif path == 'group_finish':
        game.finish_group(body['match'],body['result'])
        game.continue_month()
    elif path == 'capture_resolve':
        game.resolve_capture(body['match'],body['choice'],body.get('release_zone'))
        game.continue_month()
    elif path == 'month':
        game.submit_month(body['season'], body['week'], body['assignment'])
    elif path == 'week':
        game.submit_week(body['season'], body['week'], body['assignment'])
    elif path == 'start':
        game.start(int(body['zone']), body['setup'], bool(body.get('practice')))
    elif path == 'round':
        if game.battle is None or body['round'] != game.battle.round or body['seed'] != game.battle.seed:
            raise ValueError('현재 라운드를 다시 불러오세요.')
        commands = body.get('commands')
        game.step(None if commands is None else {int(k):v for k,v in commands.items()},
                  body.get('style','balanced'), bool(body.get('finish')))
        if game.battle is None:
            game.continue_month()
    elif path != 'state':
        raise ValueError('지원하지 않는 명령입니다.')
    return json.dumps(game.overview(), ensure_ascii=False)
