import asyncio
from .cardboard import CardGame

Zhu = CardGame()

class ActionCard(Zhu.Card('Action')):
    pass

class YingLi(ActionCard, num=4):
    name = '盈利'
    description = '摸两张行动牌。'
    def usage(self):
        return {}
    async def use(self, player):
        player.draw_action(2)

class EventCard(Zhu.Card('Event')):
    def usage(self):
        return {}

class DaBingYiChang(EventCard, num=1):
    name = '大病一场'
    description = '跳过你的回合。'
    def use(self, player):
        pass

class WenHuaZiXin(EventCard, num=1):
    name = '文化自信'
    description = '使社群规模归零。'
    def use(self, player):
        player.board.scale = 0

class ZhuBoard(Zhu.Board):
    def __init__(self):
        super().__init__()
        self.scale = 0
        self.max = 10
        self.min = -10
        self.Deck('Action').shuffle()
        for player in self.players:
            player.draw_action(2)
    async def scale_up(self, num, player):
        if self.scale + num > self.max:
            num = self.max - self.scale
        self.scale += num
        await self.on_scale_up(num, player)
    async def scale_down(self, num, player):
        if self.scale - num < self.min:
            num = self.scale - self.min
        self.scale -= num
        await self.on_scale_down(num, player)
    async def process(self):
        while 1:
            if self.current_player_id == 0:
                # if self2.round_count == 5: #TODO deck!!!
                break
        # 结算

# 选人物 = 设置player的一些method与property
class ZhuPlayer(Zhu.Player):
    responses = ['on_scale_up', 'on_scale_down']
    self_responses = ['on_influence_up', 'on_influence_down']
    def __init__(self):
        super().__init__()
        self.influence = 0
        self.max = 5
        self.min = -5
        self.action_cards = []
        self.event_hand = None
        self.event_down = None
    @property
    def hand_max(self):
        return min(len(self.influence), 1)
    async def influence_up(self, num, player):
        if self.influence + num > self.max:
            num = self.max - self.influence
        self.influence += num
        await self.on_influence_up(num, player)
    async def influence_down(self, num, player):
        if self.influence - num < self.min:
            num = self.influence - self.min
        self.influence -= num
        await self.on_influence_down(num, player)
    async def round(self):
        self.draw_event()
        await self.wait({'return': False})
        if isinstance(self.event_hand, DaBingYiChang):
            pass # use
        else:
            self.draw_action()
            await self.use_action_stage()
            await self.use_event_stage()
            await self.discard_action_stage()
    async def use_action_stage(self):
        while 1:
            ret = await self.wait({'return': True}) # TODO
            # use
            break
    async def use_event_stage(self):
        ret = await self.wait({'return': True}) # TODO
    async def discard_action_stage(self):
        pass
    def draw_action(self, num=1):
        for i in range(num):
            self.action_cards.append(ActionCard.deck.draw())
    def draw_event(self):
        self.event_hand = EventCard.deck.draw()