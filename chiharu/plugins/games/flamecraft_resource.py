from enum import Enum, IntEnum, auto
from dataclasses import dataclass
from typing import Generator, TypeVar
from collections import Counter

class Resource(IntEnum):
    Bread = 0
    Meat = 1
    Iron = 2
    Potion = 3
    Crystal = 4
    Plant = 5
    Coin = -1
    @staticmethod
    def canPay(resources: 'Counter[Resource]', consume: 'Counter[Resource]'):
        if consume <= resources:
            return True
        if (consume - resources).total() <= (resources - consume)[Resource.Coin]:
            return True
        return False
    @staticmethod
    def pay(resources: 'Counter[Resource]', consume: 'Counter[Resource]'):
        resources.subtract(consume)
        for key in resources:
            if resources[key] < 0:
                resources[Resource.Coin] += resources[key]
                resources[key] = 0

@dataclass
class Award:
    point: int = 0
    coin: int = 0
    fancy: int = 0
    dragon: int = 0

@dataclass
class Spell:
    type: Resource
    price: 'Counter[Resource]'
    award: Award
    maxLevel: int = 0
    noCoin: bool = False
    def resources(self, level: int=0):
        return self.price if self.maxLevel == 0 else Counter({key: num * level for key, num in self.price.items()})

class State(Enum): # 标志当前需要进行何种操作，前端可以直接判断
    End = auto()
    ChooseCrystalArtisan = auto()
    ChooseDragonStack = auto()
    ChooseShop = auto()
    ChooseResourceToGive = auto()
    ChooseMagic = auto()
@dataclass
class Send: # 从游戏发送至前端的数据
    last_err: int # 如果上一次是因为所选选项不符合输入要求而打回，则返回错误代码号
@dataclass
class SendChooseDragonStack(Send): # 从牌堆选择龙
    max_num: int
@dataclass
class SendChooseShop(Send): # 选择商店
    pass
@dataclass
class SendChooseResourceToGive(Send): # 选择一定的资源给一个的玩家
    player_id: int
@dataclass
class Recieve: # 游戏从前端接收回的数据
    pass
@dataclass
class RecieveResources(Recieve): # 由玩家选择任意数量的资源
    resources: 'Counter[Resource]'
@dataclass
class RecieveListInt(Recieve): # 玩家选择的数字
    nums: list[int]
@dataclass
class RecieveInt(Recieve): # 玩家选择的数字
    num: int
@dataclass
class RecieveMagic(Recieve): # 选择第几张魔法卡
    id: int
    level: int

T = TypeVar('T')
TAsync = Generator[Send, Recieve, T]
