from typing import Callable
import functools
import json
from ..game import GameSameGroup
from .. import config
from nonebot import on_command, CommandSession, get_bot, permission

__all__ = {'achievement'}

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
    def __init__(self, name: str, has_progress: bool=False):
        self.name = name
        self.has_progress = has_progress
    def progress(self, _f: Callable):
        self._progress_get = _f
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

_all = {}
for key, val in data.items():
    _all[key] = _achievement(key, False if 'has_progress' not in val else val['has_progress'])

@on_command(('achievement', 'check'), only_to_me=False)
@config.ErrorHandle
async def check(session: CommandSession):
    """查看成就信息。"""
    

@on_command(('achievement', 'list'), only_to_me=False)
@config.ErrorHandle
async def check(session: CommandSession):
    """列出已获得成就。"""
    



class _temp:
    def __call__(self, name):
        return _all[name]
    def __getattr__(self, name):
        return _all[name]
achievement = _temp()

