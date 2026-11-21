"""JSON adapter for the same campaign engine used by the local HTTP server."""
import json

from campaign import Campaign

game = Campaign(23)


def handle(path, raw_payload):
    body = json.loads(raw_payload)
    if path == 'start':
        game.start(int(body['zone']), body['setup'], bool(body.get('practice')))
    elif path == 'round':
        if game.battle is None or body['round'] != game.battle.round or body['seed'] != game.battle.seed:
            raise ValueError('현재 라운드를 다시 불러오세요.')
        commands = body.get('commands')
        game.step(None if commands is None else {int(k):v for k,v in commands.items()},
                  body.get('style','balanced'), bool(body.get('finish')))
    elif path != 'state':
        raise ValueError('지원하지 않는 명령입니다.')
    return json.dumps(game.overview(), ensure_ascii=False)
