from typing import *
from .Priority import UserEvt
if TYPE_CHECKING:
    from .User import User
    from .Card import Card
    from .Attack import Attack, AttackType
    from .Status import Status
    from .Dragon import Tree, DragonState
    from .Types import ProtocolData

class IEventListener:
    async def OnUserUseCard(self, user: 'User', card: 'Card') -> Tuple[bool, bool]:
        """Called before a user intend to use a card.

        Arguments:
        card: The card to be used.

        Returns:
        bool: represents whether the card can be used.
        bool: whether the card use will be blocked."""
        pass
    async def BeforeCardDraw(self, user: 'User', n: int, requirement: Optional[Callable]) -> Optional[list['Card']]:
        """Called Before a card is drawn in any cases. Includes cards consumed when drawn.

        Arguments:
        n: the number to draw.
        positive: specify 'positive' of the card drawn.
        extra_lambda: extra constraint of the card drawn.
        
        Returns:
        Optional[List[TCard]]: if not None, replace the card drawn, and halt."""
        pass
    async def BeforeCardUse(self, user: 'User', card: 'Card') -> Optional[Awaitable]:
        """Called Before a card is used in any cases. Includes cards consumed when drawn.

        Arguments:
        card: The card used.
        
        Returns:
        Optional[Awaitable]: if not None, replace the card use."""
        pass
    async def AfterCardUse(self, user: 'User', card: 'Card') -> None:
        """Called After a card is used in any cases.

        Arguments:
        card: The card used."""
        pass
    async def AfterCardDraw(self, user: 'User', cards: list['Card']) -> None:
        """Called after cards are drawn.

        Parameters:
        cards: The cards drawn."""
        pass
    async def AfterCardDiscard(self, user: 'User', cards: list['Card']) -> None:
        """Called after cards are discarded.

        Parameters:
        cards: The cards discarded."""
        pass
    async def AfterCardRemove(self, user: 'User', cards: list['Card']) -> None:
        """Called after cards are removed.

        Parameters:
        cards: The cards removed."""
        pass
    async def AfterCardGive(self, user: 'User', user2: 'User', card: 'Card') -> None:
        """Called after cards given.

        Parameters:
        user2: The user that cards given.
        card: The card given."""
        pass
    async def OnDeath(self, user: 'User', killer: Optional['User'], time: int, c: 'AttackType') -> Tuple[int, bool]:
        """Called when a user is dead.
        
        Arguments:
        killer: Who killed Cock Robin?
        time: The death time, in minute.
        c: The counter object represents the attack result.
        
        Returns:
        int: modified death time;
        bool: represents whether the death is dodged."""
        pass
    async def OnAttack(self, user: 'User', attack: 'Attack') -> bool:
        """Called when a user attack other.

        Arguments:
        attack: the Attack object.

        Returns:
        bool: represents whether the attack is dodged."""
        pass
    async def OnAttacked(self, user: 'User', attack: 'Attack') -> bool:
        """Called when a user is attacked.

        Arguments:
        attack: the Attack object.

        Returns:
        bool: represents whether the attack is dodged."""
        pass
    async def OnDodged(self, user: 'User') -> None:
        pass
    async def OnStatusAdd(self, user: 'User', status: 'Status') -> bool:
        """Called when a status is added.
        
        Arguments:
        status: Statusnull/Statusdaily, or a T_status object.
        count2: the count of the status added.
        
        Returns:
        bool: True if dodged."""
        pass
    async def OnStatusRemove(self, user: 'User', status: 'Status', remover: 'User' | None=None) -> bool:
        """Called when a status is removed.
        
        Arguments:
        status: a str for statusnull/statusdaily, or a T_status object.
        remover: the remover.
        
        Returns:
        bool: whether the removement is dodged."""
        pass
    async def AfterStatusRemove(self, user: 'User', status: 'Status') -> None:
        """Called after a status is removed.
        
        Arguments:
        status: a str for statusnull/statusdaily, or a T_status object."""
        pass
    async def CheckJibiSpend(self, user: 'User', jibi: int) -> int:
        """Called when a user intended to use jibi to buy something.

        Arguments:
        jibi: the amount of jibi needed to buy. always positive.

        Returns:
        int: the modified amount of jibi needed to buy."""
        pass
    async def OnJibiChange(self, user: 'User', jibi: int, isBuy: bool) -> int:
        """Called when a user added some jibi or decreased some jibi.

        Arguments:
        jibi: the amount of jibi to add.
        is_buy: True if the decreasement is a buying. A buying will not hold if
            jibi + user.jibi < 0.

        Returns:
        int: the modified amount of jibi to add."""
        pass
    async def AfterJibiChange(self, user: 'User', jibi: int) -> None:
        """Called after a user added some jibi or decreased some jibi.

        Arguments:
        jibi: User's final jibi change"""
        pass
    async def CheckEventptSpend(self, user: 'User', eventPt: int) -> int:
        """Called when a user intended to use event_pt to buy something.

        Arguments:
        event_pt: the amount of event_pt needed to buy. always positive.

        Returns:
        int: the modified amount of event_pt needed to buy."""
        pass
    async def OnEventptChange(self, user: 'User', eventPt: int, isBuy: bool) -> int:
        """Called when a user added some event_pt or decreased some event_pt.

        Arguments:
        event_pt: the amount of event_pt to add.
        is_buy: True if the decreasement is a buying. A buying will not hold if
            event_pt + user.event_pt < 0.

        Returns:
        int: the modified amount of event_pt to add."""
        pass
    async def BeforeDragoned(self, user: 'User', state: 'DragonState') -> Tuple[bool, int]:
        """Called before a user dragoning.

        Arguments:
        state: contains the dragon word, the parent tree node, and extra info.

        Returns:
        bool: represents whether the user can dragon;
        int: offset to modify the dragon distance allowed."""
        pass
    async def CheckSuguri(self, user: 'User', state: 'DragonState') -> bool:
        """Called when Suguri's Accelerator is checked to be used.

        Arguments:
        state: contains the dragon word, the parent tree node, and extra info.
        
        Returns:
        bool: represents if accelerated."""
        pass
    async def OnKeyword(self, user: 'User', word: str, parent: 'Tree', keyword: str) -> int:
        """Called when a user hit a keyword.
        
        Arguments:
        word: the dragon word.
        parent: the parent tree node.
        keyword: the keyword.
        
        Returns:
        int: the amount of jibi to add."""
        pass
    async def OnHiddenKeyword(self, user: 'User', word: str, parent: 'Tree', keyword: str) -> int:
        """Called when a user hit a hidden keyword.
        
        Arguments:
        word: the dragon word.
        parent: the parent tree node.
        keyword: the hidden keyword.
        
        Returns:
        int: the amount of jibi to add."""
        pass
    async def OnDuplicatedWord(self, user: 'User', word: str, originalQQ: int) -> bool:
        """Called when a user dragoned a duplicated word in one week.
        
        Arguments:
        word: the dragon word.
        originalQQ: the original user who dragoned this word.
        
        Returns:
        bool: represents whether the hit is dodged."""
        pass
    async def OnBombed(self, user: 'User', word: str) -> bool:
        """Called when a user hit a mine.
        
        Arguments:
        word: the dragon word.
        
        Returns:
        bool: represents whether the hit is dodged."""
        pass
    async def OnDragoned(self, user: 'User', branch: 'Tree', first10: bool) -> None:
        """Called when the user complete a dragon.
        
        Arguments:
        branch: the dragon branch.
        first10: if it is the first 10 dragon each day."""
        pass
    async def OnNewDay(self, user: 'User') -> None:
        """Called when new day begins."""
        pass
    def register(self) -> Dict['UserEvt', int]:
        return {}
    def checkDragonDisplay(self) -> Tuple[int, str, bool, bool]:
        """需返回静态数据，依次为：距离修正值，无法接龙的标志，是否要求首尾，是否要求尾首"""
        raise NotImplementedError
