"""Versioned, safe JSON graph saves for the complete in-memory campaign.

No pickle, executable Python, dynamic imports, or arbitrary class names from
save files. Object references preserve shared fighters, the live ledger, draft
order, pending weekly assignment and in-progress battles.
"""
from __future__ import annotations

import base64
import collections
from dataclasses import fields, is_dataclass
import hashlib
import json
import math
import random
import re
import zlib

from campaign import Campaign
from combat import Battle, Unit
from moonpa_world_v15 import Fighter, Guild, Zone
from moonpa_growth import Development, Trait
from moonpa_economy_v15_1 import World15, Ledger, Debt, assert_world
from moonpa_names import NameRegistry
from moonpa_tracking import Ownership

FORMAT = 'moonpa-v3-save'
VERSION = 1
MAX_FILE_CHARS = 12_000_000
MAX_RAW_BYTES = 40_000_000
MAX_NODES = 200_000
MAX_DEPTH = 150
CLASSES = {cls.__name__: cls for cls in (
    Campaign, World15, Ledger, Debt, Fighter, Guild, Zone,
    Development, Trait, Ownership, NameRegistry, Battle, Unit,
)}
# The only non-dataclass object layouts allowed by the decoder.
ATTRS = {
    'Campaign': {'seed','world','guild','interactive','phase','draft_pool',
                 'draft_order','draft_cursor','draft_round','draft_picks',
                 'season','week','battle','zone','result','practice',
                 'pending_week','week_report','recruitment_attempts'},
    'NameRegistry': {'rng','used_people','used_sects'},
    'Battle': {'units','seed','round','winner','events','frames','orders'},
    'Ledger': {'world','capture','entries','stats','categories','by_season',
               'opening','source','sink','transfer_in','transfer_out','transactions',
               'accrued','transfer_id'},
    'World15': {
        'seed','rng','strategy','guilds','zones','fa','new_fid','player','stats',
        'yearly','globalweek','player_reached_1','names','conservative','mentors',
        'spells','closed_spells','player_snapshots','player_best_division',
        'player_titles','debts','season_active','week_active','player_id',
        'player_bankrupted','player_bankrupt_season','capture_ledger','money',
        'roster_overflow_events','roster_auto_releases','accrued_unpaid',
        'bankruptcies','season_data','unemployment_exit','freeagent_weekly',
        'severance_total','checkpoints','new_foundations','missed_wages_weeks',
        'loan_balance','trade_swaps','transfer_banned_attempts','long_missions',
        'long_completed','long_abandoned','kiyun_manuals','kiyun_bonds',
        'elite_completed','facilities'
    },
}
for _name, _cls in CLASSES.items():
    if is_dataclass(_cls):
        ATTRS[_name] = {field.name for field in fields(_cls)}
FACTORIES = {'Counter': collections.Counter, 'dict': dict,
             'list': list, 'int': int, 'set': set, 'none': None}


class SaveError(ValueError):
    """User-visible save/import problem. The running campaign stays intact."""


class Encoder:
    def __init__(self):
        self.nodes = []
        self.seen = {}

    def value(self, value, depth=0):
        if depth > MAX_DEPTH:
            raise SaveError('게임 기록이 너무 깊어 저장할 수 없습니다.')
        if value is None or type(value) in (str, bool, int):
            return value
        if type(value) is float:
            if not math.isfinite(value):
                raise SaveError('게임 상태에 올바르지 않은 숫자가 있습니다.')
            return value
        if type(value) is tuple:
            return {'tuple': [self.value(x,depth+1) for x in value]}
        identity = id(value)
        if identity in self.seen:
            return {'ref': self.seen[identity]}
        index = len(self.nodes)
        if index >= MAX_NODES:
            raise SaveError('게임 데이터가 저장 한도를 초과했습니다.')
        self.seen[identity] = index
        self.nodes.append(None)
        if type(value) is list:
            node = {'type':'list','values':[self.value(x,depth+1) for x in value]}
        elif type(value) is set:
            node = {'type':'set','values':[self.value(x,depth+1) for x in value]}
        elif type(value) is collections.Counter:
            node = {'type':'counter','items':self.pairs(value,depth)}
        elif type(value) is collections.defaultdict:
            factory = next((k for k,v in FACTORIES.items()
                            if v is value.default_factory),None)
            if factory is None:
                raise SaveError('지원하지 않는 게임 장부 형식입니다.')
            node = {'type':'defaultdict','factory':factory,'items':self.pairs(value,depth)}
        elif type(value) is dict:
            node = {'type':'dict','items':self.pairs(value,depth)}
        elif type(value) is random.Random:
            node = {'type':'random','state':self.value(value.getstate(),depth+1)}
        else:
            kind = type(value).__name__
            if CLASSES.get(kind) is not type(value):
                raise SaveError('저장할 수 없는 게임 객체가 포함되어 있습니다.')
            attributes = ({field.name:getattr(value,field.name) for field in fields(value)}
                          if is_dataclass(value) else vars(value))
            if not set(attributes) <= ATTRS[kind]:
                raise SaveError('알 수 없는 게임 상태 필드가 있습니다.')
            node = {'type':'object','class':kind,
                    'attributes':{k:self.value(v,depth+1) for k,v in attributes.items()}}
        self.nodes[index] = node
        return {'ref':index}

    def pairs(self, mapping, depth):
        return [[self.value(k,depth+1),self.value(v,depth+1)]
                for k,v in mapping.items()]

    def encode(self, game):
        root = self.value(game)
        return {'root':root,'nodes':self.nodes}


class Decoder:
    def __init__(self, graph):
        if type(graph) is not dict or set(graph)!={'root','nodes'}:
            raise SaveError('세이브 데이터 구조가 올바르지 않습니다.')
        self.nodes=graph['nodes']
        if type(self.nodes) is not list or not 1<=len(self.nodes)<=MAX_NODES:
            raise SaveError('게임 데이터에 허용되지 않는 객체 수가 있습니다.')
        self.objects=[None]*len(self.nodes)
        self.loaded=set()

    def value(self, value, depth=0):
        if depth>MAX_DEPTH:
            raise SaveError('세이브 데이터의 중첩 단계가 너무 깊습니다.')
        if value is None or type(value) in (bool,int,str):
            return value
        if type(value) is float:
            if not math.isfinite(value):
                raise SaveError('세이브 파일에 유효하지 않은 숫자가 있습니다.')
            return value
        if type(value) is not dict or len(value)!=1:
            raise SaveError('세이브 참조 데이터가 올바르지 않습니다.')
        if 'tuple' in value:
            if type(value['tuple']) is not list:
                raise SaveError('세이브의 순서 정보가 잘못되었습니다.')
            return tuple(self.value(x,depth+1) for x in value['tuple'])
        if 'ref' not in value or type(value['ref']) is not int:
            raise SaveError('세이브 참조 번호가 올바르지 않습니다.')
        index=value['ref']
        if not 0<=index<len(self.nodes):
            raise SaveError('세이브 참조가 유효하지 않습니다.')
        if index in self.loaded:
            return self.objects[index]
        node=self.nodes[index]
        if type(node) is not dict:
            raise SaveError('게임 객체의 정보가 손상됐습니다.')
        kind=node.get('type')
        if kind=='list':
            self.check_keys(node,{'type','values'})
            instance=[]
        elif kind=='set':
            self.check_keys(node,{'type','values'})
            instance=set()
        elif kind in ('dict','counter','defaultdict'):
            required={'type','items'}|({'factory'} if kind=='defaultdict' else set())
            self.check_keys(node,required)
            if kind=='counter':instance=collections.Counter()
            elif kind=='defaultdict':
                if node['factory'] not in FACTORIES:
                    raise SaveError('허용되지 않는 게임 장부 유형입니다.')
                instance=collections.defaultdict(FACTORIES[node['factory']])
            else:instance={}
        elif kind=='random':
            self.check_keys(node,{'type','state'})
            instance=random.Random()
        elif kind=='object':
            self.check_keys(node,{'type','class','attributes'})
            name=node['class']
            if type(name) is not str or name not in CLASSES:
                raise SaveError('지원하지 않는 게임 객체가 있습니다.')
            instance=object.__new__(CLASSES[name])
        else:
            raise SaveError('알 수 없는 게임 객체 종류입니다.')
        self.objects[index]=instance
        self.loaded.add(index)
        if kind in ('list','set'):
            items=node['values']
            if type(items) is not list:
                raise SaveError('게임 객체 목록이 손상됐습니다.')
            for item in items:
                resolved=self.value(item,depth+1)
                if kind=='list':instance.append(resolved)
                else:instance.add(resolved)
        elif kind in ('dict','counter','defaultdict'):
            entries=node['items']
            if type(entries) is not list:
                raise SaveError('게임 장부 내역이 손상됐습니다.')
            for pair in entries:
                if type(pair) is not list or len(pair)!=2:
                    raise SaveError('게임 장부 항목이 잘못되었습니다.')
                key=self.value(pair[0],depth+1)
                instance[key]=self.value(pair[1],depth+1)
        elif kind=='random':
            state=self.value(node['state'],depth+1)
            instance.setstate(state)
        elif kind=='object':
            attributes=node['attributes']
            if type(attributes) is not dict or not set(attributes)<=ATTRS[node['class']]:
                raise SaveError('세이브 파일에 알 수 없는 객체 속성이 있습니다.')
            if is_dataclass(instance):
                if set(attributes)!={field.name for field in fields(instance)}:
                    raise SaveError('게임 데이터 버전이 현재 규칙과 다릅니다.')
            elif node['class'] in ('Campaign','NameRegistry','Battle','Ledger'):
                if set(attributes)!=ATTRS[node['class']]:
                    raise SaveError('게임 상태에 필수 정보가 빠져 있습니다.')
            elif node['class']=='World15':
                # World attributes may gain optional fields in later compatible builds.
                required={'seed','rng','guilds','zones','fa','money','debts',
                          'names','long_missions','spells','kiyun_manuals','kiyun_bonds'}
                if not required<=set(attributes):
                    raise SaveError('게임 세계의 필수 정보가 누락됐습니다.')
            for key,encoded in attributes.items():
                object.__setattr__(instance,key,self.value(encoded,depth+1))
        return instance

    @staticmethod
    def check_keys(node,expected):
        if set(node)!=expected:
            raise SaveError('게임 객체의 구조가 올바르지 않습니다.')


def _validate(game):
    if type(game) is not Campaign or type(game.world) is not World15:
        raise SaveError('문파 게임 세이브 파일이 아닙니다.')
    w=game.world
    if type(game.seed) is not int or game.seed!=w.seed or not 1<=game.season<=10000:
        raise SaveError('게임 시드 또는 시즌 정보가 올바르지 않습니다.')
    if type(game.week) is not int or not 1<=game.week<=51:
        raise SaveError('게임 주차가 올바르지 않습니다.')
    if game.phase not in ('tutorial','draft','fa','ready','report'):
        raise SaveError('지원하지 않는 게임 진행 단계입니다.')
    if type(game.interactive) is not bool or type(w.guilds) is not dict or len(w.guilds)!=32:
        raise SaveError('게임 세계 정보가 올바르지 않습니다.')
    if w.player not in w.guilds or game.guild is not w.guilds[w.player]:
        raise SaveError('문파 소속 정보가 손상됐습니다.')
    if w.money.world is not w:
        raise SaveError('재정 장부의 세계 연결 정보가 손상됐습니다.')
    if type(w.rng) is not random.Random or type(w.names) is not NameRegistry:
        raise SaveError('게임 난수와 작명 기록이 손상됐습니다.')
    if game.battle is not None:
        if type(game.battle) is not Battle or game.zone not in w.zones:
            raise SaveError('진행 중인 전투 정보가 손상됐습니다.')
        if game.pending_week is not None and game.practice:
            raise SaveError('주간 결산과 모의전 정보가 충돌합니다.')
    elif game.pending_week is not None:
        raise SaveError('진행 중인 결산 전투가 없습니다.')
    if any(type(f) is not Fighter or type(f.development) is not Development
           for g in w.guilds.values() for f in g.fighters):
        raise SaveError('문파원 성장 데이터가 손상됐습니다.')
    if any(type(g) is not Guild for g in w.guilds.values()):
        raise SaveError('문파 목록이 손상됐습니다.')
    checkpoint=w.checkpoints
    try:
        assert_world(w)
    except (AssertionError,KeyError,TypeError,ValueError,AttributeError) as error:
        raise SaveError('게임 장부 또는 편성 상태에 오류가 있습니다.') from error
    finally:
        w.checkpoints=checkpoint


def create_save(game):
    """Return a JSON-compatible file envelope. Export must not change gameplay."""
    _validate(game)
    graph=Encoder().encode(game)
    raw=json.dumps(graph,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8')
    if len(raw)>MAX_RAW_BYTES:
        raise SaveError('저장 데이터가 너무 커 파일로 만들 수 없습니다.')
    return dict(format=FORMAT,version=VERSION,
                meta=dict(guild=game.guild.name,seed=game.seed,season=game.season,
                          week=game.week,phase=game.phase),
                checksum=hashlib.sha256(raw).hexdigest(),
                data=base64.b64encode(zlib.compress(raw,6)).decode('ascii'))


def load_save(envelope):
    """Return a fully checked, independent Campaign or raise without mutation."""
    if type(envelope) is not dict or set(envelope)!={'format','version','meta','checksum','data'}:
        raise SaveError('세이브 파일의 머리말이 올바르지 않습니다.')
    if envelope['format']!=FORMAT:
        raise SaveError('문파 키우기 저장 파일이 아닙니다.')
    if type(envelope['version']) is not int or envelope['version']!=VERSION:
        raise SaveError('지원하지 않는 세이브 버전입니다. (v3 파일 형식 1만 지원)')
    payload=envelope['data']
    if type(payload) is not str or len(payload)>MAX_FILE_CHARS:
        raise SaveError('저장 파일이 너무 크거나 데이터가 없습니다.')
    if type(envelope['checksum']) is not str or not re.fullmatch(r'[0-9a-f]{64}',envelope['checksum']):
        raise SaveError('세이브 검증값이 잘못되었습니다.')
    try:
        packed=base64.b64decode(payload,validate=True)
        inflate=zlib.decompressobj()
        raw=inflate.decompress(packed,MAX_RAW_BYTES+1)
        if len(raw)>MAX_RAW_BYTES or inflate.unconsumed_tail or not inflate.eof or inflate.unused_data:
            raise SaveError('저장 파일의 압축 내용이 손상되었거나 제한을 초과했습니다.')
        if hashlib.sha256(raw).hexdigest()!=envelope['checksum']:
            raise SaveError('세이브 파일의 무결성 검증에 실패했습니다.')
        graph=json.loads(raw)
        game=Decoder(graph).value(graph['root'])
        _validate(game)
        if envelope['meta']!=dict(guild=game.guild.name,seed=game.seed,
                                  season=game.season,week=game.week,phase=game.phase):
            raise SaveError('세이브 요약과 실제 게임 데이터가 일치하지 않습니다.')
        return game
    except SaveError:
        raise
    except (ValueError,TypeError,KeyError,AttributeError,OverflowError,IndexError,
            RecursionError,UnicodeError,zlib.error) as error:
        raise SaveError('저장 파일이 손상됐거나 현재 게임에서 읽을 수 없습니다.') from error
