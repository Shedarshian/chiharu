from typing import *
from .Types import TCounter, TEvent
if TYPE_CHECKING:
    from .User import User
    from .Card import Card
    from .Attack import Attack
    from .Status import Status
    from .Dragon import Tree, DragonState

class IEventListener:
    @classmethod
    async def OnUserUseCard(cls, user: 'User', card: 'Card') -> Tuple[bool, str]:
        """Called before a user intend to use a card.

        Arguments:
        card: The card to be used.

        Returns:
        bool: represents whether the card can be used;
        str: failure message."""
        pass
    @classmethod
    async def BeforeCardDraw(cls, user: 'User', n: int, positive: Optional[set[int]], extra_lambda: Optional[Callable]) -> Tuple[Optional[list['Card']]]:
        """Called Before a card is drawn in any cases. Includes cards consumed when drawn.

        Arguments:
        n: the number to draw.
        positive: specify 'positive' of the card drawn.
        extra_lambda: extra constraint of the card drawn.
        
        Returns:
        Optional[List[TCard]]: if not None, replace the card drawn, and halt."""
        pass
    @classmethod
    async def BeforeCardUse(cls, user: 'User', card: 'Card') -> Tuple[Optional[Awaitable]]:
        """Called Before a card is used in any cases. Includes cards consumed when drawn.

        Arguments:
        card: The card used.
        
        Returns:
        Optional[Awaitable]: if not None, replace the card use."""
        pass
    @classmethod
    async def AfterCardUse(cls, user: 'User', card: 'Card') -> Tuple[()]:
        """Called After a card is used in any cases.

        Arguments:
        card: The card used."""
        pass
    @classmethod
    async def AfterCardDraw(cls, user: 'User', cards: Iterable['Card']) -> Tuple[()]:
        """Called after cards are drawn.

        Parameters:
        cards: The cards drawn."""
        pass
    @classmethod
    async def AfterCardDiscard(cls, user: 'User', cards: Iterable['Card']) -> Tuple[()]:
        """Called after cards are discarded.

        Parameters:
        cards: The cards discarded."""
        pass
    @classmethod
    async def AfterCardRemove(cls, user: 'User', cards: Iterable['Card']) -> Tuple[()]:
        """Called after cards are removed.

        Parameters:
        cards: The cards removed."""
        pass
    @classmethod
    async def AfterExchange(cls, user: 'User', user2: 'User') -> Tuple[()]:
        """Called after cards are exchanged.

        Parameters:
        user2: The user that cards are exchanged."""
        pass
    @classmethod
    async def OnDeath(cls, user: 'User', killer: 'User', time: int, c: TCounter) -> Tuple[int, bool]:
        """Called when a user is dead.
        
        Arguments:
        killer: Who killed Cock Robin?
        time: The death time, in minute.
        c: The counter object represents the attack result.
        
        Returns:
        int: modified death time;
        bool: represents whether the death is dodged."""
        pass
    @classmethod
    async def OnAttack(cls, user: 'User', attack: 'Attack') -> Tuple[bool]:
        """Called when a user attack other.

        Arguments:
        attack: the Attack object.

        Returns:
        bool: represents whether the attack is dodged."""
        pass
    @classmethod
    async def OnAttacked(cls, user: 'User', attack: 'Attack') -> Tuple[bool]:
        """Called when a user is attacked.

        Arguments:
        attack: the Attack object.

        Returns:
        bool: represents whether the attack is dodged."""
        pass
    @classmethod
    async def OnDodged(cls, user: 'User') -> Tuple[()]:
        pass
    @classmethod
    async def OnStatusAdd(cls, user: 'User', status: 'Status', count2: int) -> Tuple[int]:
        """Called when a status is added.
        
        Arguments:
        status: Statusnull/Statusdaily, or a T_status object.
        count2: the count of the status added.
        
        Returns:
        int: the count of the status really add."""
        pass
    @classmethod
    async def OnStatusRemove(cls, user: 'User', status: 'Status', remove_all: bool) -> Tuple[bool]:
        """Called when a status is removed.
        
        Arguments:
        status: a str for statusnull/statusdaily, or a T_status object.
        remove_all: if remove all this state.
        
        Returns:
        bool: whether the removement is dodged."""
        pass
    @classmethod
    async def AfterStatusRemove(cls, user: 'User', status: 'Status', remove_all: bool) -> Tuple[()]:
        """Called after a status is removed.
        
        Arguments:
        status: a str for statusnull/statusdaily, or a T_status object.
        remove_all: if remove all this state."""
        pass
    @classmethod
    async def CheckJibiSpend(cls, user: 'User', jibi: int) -> Tuple[int]:
        """Called when a user intended to use jibi to buy something.

        Arguments:
        jibi: the amount of jibi needed to buy. always positive.

        Returns:
        int: the modified amount of jibi needed to buy."""
        pass
    @classmethod
    async def OnJibiChange(cls, user: 'User', jibi: int, is_buy: bool) -> Tuple[int]:
        """Called when a user added some jibi or decreased some jibi.

        Arguments:
        jibi: the amount of jibi to add.
        is_buy: True if the decreasement is a buying. A buying will not hold if
            jibi + user.jibi < 0.

        Returns:
        int: the modified amount of jibi to add."""
        pass
    @classmethod
    async def CheckEventptSpend(cls, user: 'User', event_pt: int) -> Tuple[int]:
        """Called when a user intended to use event_pt to buy something.

        Arguments:
        event_pt: the amount of event_pt needed to buy. always positive.

        Returns:
        int: the modified amount of event_pt needed to buy."""
        pass
    @classmethod
    async def OnEventptChange(cls, user: 'User', event_pt: int, is_buy: bool) -> Tuple[int]:
        """Called when a user added some event_pt or decreased some event_pt.

        Arguments:
        event_pt: the amount of event_pt to add.
        is_buy: True if the decreasement is a buying. A buying will not hold if
            event_pt + user.event_pt < 0.

        Returns:
        int: the modified amount of event_pt to add."""
        pass
    @classmethod
    async def BeforeDragoned(cls, user: 'User', state: 'DragonState') -> Tuple[bool, int, str]:
        """Called before a user dragoning.

        Arguments:
        state: contains the dragon word, the parent tree node, and extra info.

        Returns:
        bool: represents whether the user can dragon;
        int: offset to modify the dragon distance allowed;
        str: failure message."""
        pass
    @classmethod
    async def CheckSuguri(cls, user: 'User', state: 'DragonState') -> Tuple[bool]:
        """Called when Suguri's Accelerator is checked to be used.

        Arguments:
        state: contains the dragon word, the parent tree node, and extra info.
        
        Returns:
        bool: represents if accelerated."""
        pass
    @classmethod
    async def OnKeyword(cls, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        """Called when a user hit a keyword.
        
        Arguments:
        word: the dragon word.
        parent: the parent tree node.
        keyword: the keyword.
        
        Returns:
        int: the amount of jibi to add."""
        pass
    @classmethod
    async def OnHiddenKeyword(cls, user: 'User', word: str, parent: 'Tree', keyword: str) -> Tuple[int]:
        """Called when a user hit a hidden keyword.
        
        Arguments:
        word: the dragon word.
        parent: the parent tree node.
        keyword: the hidden keyword.
        
        Returns:
        int: the amount of jibi to add."""
        pass
    @classmethod
    async def OnDuplicatedWord(cls, user: 'User', word: str) -> Tuple[bool]:
        """Called when a user dragoned a duplicated word in one week.
        
        Arguments:
        word: the dragon word.
        
        Returns:
        bool: represents whether the hit is dodged."""
        pass
    @classmethod
    async def OnBombed(cls, user: 'User', word: str) -> Tuple[bool]:
        """Called when a user hit a mine.
        
        Arguments:
        word: the dragon word.
        
        Returns:
        bool: represents whether the hit is dodged."""
        pass
    @classmethod
    async def OnDragoned(cls, user: 'User', branch: 'Tree', first10: bool) -> Tuple[()]:
        """Called when the user complete a dragon.
        
        Arguments:
        branch: the dragon branch.
        first10: if it is the first 10 dragon each day."""
        pass
    @classmethod
    async def OnNewDay(cls, user: 'User') -> Tuple[()]:
        """Called when new day begins."""
        pass
    @classmethod
    def register(cls) -> Iterable[Tuple[int, int]]:
        return []
