from collections import Counter
from enum import Enum, auto
from typing import Callable

class Player:
    def __init__(self, id: int, board: 'Board', isDummy: bool=False) -> None:
        self.id = id
        self.hand: 'list[Dragon]' = []
        self.fancy: 'list[Fancy]' = []
        self.reserved: Spell | None = None
        self.resources: 'Counter[Resource]' = Counter()
        for resource in Resource:
            self.resources[resource] = 0
        self.score: int = 0
        self.place: 'Shop | None' = None
        self.isDummy = isDummy
        self.board = board

        self.step: Player.Step = Player.Step.EndTurn

        self.filledShopThisTurn: int = 0
        self.magiced: bool = False
    def addResource(self, resource: 'Resource'):
        self.resources[resource] += 1
    def addResources(self, resources: 'Counter[Resource]'):
        self.resources.update(resources)
    def setTurnCounter(self):
        self.filledShopThisTurn = 0
        self.magiced = False

    def chooseDragonStack(self, maxNum: int) -> 'TAsync[list[Dragon]]':
        """选择一定张数的龙。可以从牌堆选。"""
        if len(self.board.park) == 0 and len(self.board.dragonDeck) == 0:
            return []
        self.board.state = State.ChooseDragonStack
        last_err: int = 0
        from .flamecraft_resource import SendChooseDragonStack, RecieveListInt
        while 1:
            ret = yield SendChooseDragonStack(last_err, maxNum)
            assert isinstance(ret, RecieveListInt)
            if len(ret.nums) > maxNum:
                last_err = -2 # 选择数量超出要求
                continue
            l = self.board.popDragons(ret.nums)
            if l is None:
                last_err = -1 # 数据不合法，包含超出范围或重复
                continue
            if len(l) == 0:
                last_err = -3 # 牌堆剩余数量不足
                continue
            return l
        return []
    def drawDragon(self, dragons: 'list[Dragon]') -> 'TAsync[None]':
        c: Counter[Resource] = Counter()
        for dragon in dragons:
            c[dragon.color] += dragon.goods
            dragon.goods = 0
            dragon.setParent(self)
        self.addResources(c)
        self.hand.extend(dragons)
        return
        yield

    class Step(Enum):
        ChooseShop = auto()
        ChooseGather = auto()
        PutDragon = auto()
        FireOneDragon = auto()
        ShopAbility = auto()
        ChooseMagic = auto()
        ChooseAnyDragon = auto()
        EndTurn = auto()
        AfterDiscard = auto()
    def turn(self) -> 'TAsync[None]':
        # 第一步，选择去哪个商店，选择给谁商品
        # 第二步，选择收集或魔法，魔法则直接选择魔法卡
        # 第三步，若收集，选择放龙或跳过
        # 第四步，选择火某一个龙或跳过，给火的龙的参数
        # 第五步，商店特效
        # 第六步，若魔法，执行魔法效果
        # 第七步，选择火任一个龙，循环
        # 第八步，结束回合，选择fancy或弃牌或跳过
        yield from self.turnChooseShop()
        spell = yield from self.turnChooseGather()
        if spell is None:
            yield from self.turnGatherResource()
            yield from self.turnPutDragon()
            yield from self.turnFireOne()
            yield from self.turnShopAbility()
        else:
            yield from self.turnMagic(spell)
            self.magiced = True
            yield from self.turnFireAll()
        yield from self.endTurn()
    def turnChooseShop(self) -> 'TAsync[None]':
        self.step = Player.Step.ChooseShop
        self.board.state = State.ChooseShop
        last_err: int = 0
        from .flamecraft_resource import SendChooseShop, RecieveInt
        while 1:
            ret = yield SendChooseShop(last_err)
            assert isinstance(ret, RecieveInt)
            shop = self.board.getShop(ret.num)
            if shop is None:
                last_err = -1 # 不在范围内
                continue
            if self.place is shop:
                last_err = -2 # 不能不动
                continue
            if self.resources.total() < len(shop.players):
                last_err = -3 # 资源不够支付
                continue

            if self.place is not None:
                self.place.players.remove(self)
            self.place = shop
            shop.players.append(self)
            for player in shop.players:
                if player is self:
                    continue
                self.board.state = State.ChooseResourceToGive
                last_err = 0
                from .flamecraft_resource import SendChooseResourceToGive, RecieveResources
                while 1:
                    ret = yield SendChooseResourceToGive(last_err, player.id)
                    assert isinstance(ret, RecieveResources)
                    if ret.resources.total() != 1:
                        last_err = -1 # 选择个数不正确
                        continue
                    if not ret.resources < self.resources:
                        last_err = -2 # 资源不够
                        continue

                    self.resources -= ret.resources
                    player.resources += ret.resources
                    break
            break
    def turnChooseGather(self) -> 'TAsync[Spell | None]':
        last_err: int = 0
        self.board.state = State.ChooseMagic
        from .flamecraft_resource import Send, RecieveMagic
        while 1:
            ret = yield Send(last_err)
            assert isinstance(ret, RecieveMagic)
            if not -1 <= ret.id < len(self.board.spells):
                last_err = -1 # 超出范围
                continue
            if ret.id == -1:
                return None

            spell = self.board.spells[ret.id]
            if spell.maxLevel != 0 and not 1 <= ret.level <= spell.maxLevel:
                last_err = -2 # 等级超出范围
                continue
            consume = spell.resources(ret.level)
            if not Resource.canPay(self.resources, consume):
                last_err = -3 # 资源不够
                continue

            return spell
    def turnGatherResource(self) -> 'TAsync[None]':
        return
        yield
    def turnPutDragon(self) -> 'TAsync[None]':
        return
        yield
    def turnFireOne(self) -> 'TAsync[None]':
        return
        yield
    def turnShopAbility(self) -> 'TAsync[None]':
        return
        yield
    def turnMagic(self, spell: Spell) -> 'TAsync[None]':
        return
        yield
    def turnFireAll(self) -> 'TAsync[None]':
        return
        yield
    def endTurn(self) -> 'TAsync[None]':
        # fancy dragon first
        self.setTurnCounter()
        return
        yield
    def turnCheckFancy(self) -> 'TAsync[None]':
        return
        yield

from .flamecraft_resource import Resource, TAsync, State, Spell
from .flamecraft_artisan import Dragon
from .flamecraft_fancy import Fancy
from .flamecraft_shop import Shop
from .flamecraft_board import Board