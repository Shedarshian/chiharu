from typing import Callable
import functools
import json
from ..game import GameSameGroup
from .. import config

__all__ = ('achievement',)

# from .games.achievement import achievement
# @achievement.snakebird.progress
# def sb_progress(qq: int):
#     return 0.5
# if achievement.snakebird.get('1569603950'):
#     await session.send(achievement.snakebird.get_str())

_achievement_game = GameSameGroup('achievement')
_open_data = _achievement_game.open_data
_save_data = _achievement_game.save_data

with open(config.rel(r'games\achievement.json'), encoding='utf-8') as f:
    data = json.load(f)

class _achievement:
    def __init__(self, name: str, val: dict):
        self.name = name
        self.val = val
        self.has_progress = val.get('has_progress', False)
    def progress(self, _f: Callable):
        self._progress_get = _f
    def check(self, qq):
        data = _open_data(qq)
        if 'get' in data and self.name in data['get']:
            return True
        return False
    def get(self, qq):
        data = _open_data(qq)
        if 'get' not in data:
            data['get'] = []
        if self.name not in data['get']:
            data['get'].append(self.name)
            _save_data(qq, data)
            return True
        return False
    def get_str(self):
        return f"恭喜您获得成就「{data[self.name]['name']}」！"
    @staticmethod
    def _percent(i):
        return str(int(i * 100)) + '%'
    def get_des(self, qq):
        return f"成就：{self.get_brief(qq)}\n{'隐藏成就描述在获得后显示。' if ('hide_des' in self.val or 'hide' in self.val) and not self.check(qq) else self.val['description']}"
    def get_brief(self, qq):
        return f"{self.val['name']}（{'已获得' if self.check(qq) else _achievement._percent(self._progress_get(qq)) if self.has_progress else '未获得'}）"

_all = {}
for key, val in data.items():
    _all[key] = _achievement(key, val)

class _temp:
    def __call__(self, name):
        return _all[name]
    def __getattr__(self, name):
        return _all[name]
achievement = _temp()

def cp(qq):
    r = config.userdata.execute('select cp from game where qq=?', (qq,)).fetchone()
    if r is None:
        config.userdata.execute('insert into game (qq, cp) values (?, 0)', (qq,))
        return 0
    return r['cp']

def cp_add(qq, cp):
    cp_new = cp + cp(qq)
    config.userdata.execute('update game set cp=? where qq=?', (cp_new, qq))
    return cp_new