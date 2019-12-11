import json
import pypinyin
from pypinyin import pinyin
from abc import ABC, abstractmethod
from nonebot import on_command, CommandSession, permission, get_bot, NLPSession
from nonebot.command import call_command
import chiharu.plugins.config as config
from .. import game

class BlackBox(ABC):
    _dict = None
    _dict_ref_count = 0
    _all_box = {}
    def __init_subclass__(cls, id, **kwargs):
        super().__init_subclass__(**kwargs)
        cls.id = id
        BlackBox._all_box[id] = cls
    def __init__(self):
        if self._dict_ref_count == 0:
            with open(config.rel(r'games\dictionary.json'), encoding='utf-8') as f:
                self._dict = json.load(f)
        self._dict_ref_count += 1
        return self._dict
    def __del__(self):
        self._dict_ref_count -= 1
        if self._dict_ref_count == 0:
            del self._dict
            self._dict = None
    def check(self, input_str):
        def _(t):
            raise KeyError
        try:
            for t in input_str:
                pinyin(t, errors=_)
            return len(input_str) != 0
        except KeyError:
            return False
    @abstractmethod
    def process(self, input_str):
        pass

class Box0(BlackBox, id=0):
    describe = '此黑箱供测试人员测试使用，因不稳定的原因请不要随意输入单词以防爆炸。'
    example = (('一方通行', '虹口足球场', '罗巴切夫斯基几何', '电子钢琴'), ('橙', '可乐', '费米子', '电子琴'))
    def process(self, input_str):
        return len(input_str) >= 4
class Box1(BlackBox, id=1):
    describe = '西柚初始纪念版'
    example = (('博丽灵梦', '魂魄妖梦', '海淀黄庄', '北京大学'), ('西行寺幽幽子', '因幡天为', '雍和宫北大街', '惠新西街南口'))
    def process(self, input_str):
        return self._dict[input_str[0]]['structure'] in {'左右', '左中右', '田字'}

def Box(id):
    return BlackBox._all_box[id]()

blackbox = game.GameSameGroup('blackbox', can_private=True)