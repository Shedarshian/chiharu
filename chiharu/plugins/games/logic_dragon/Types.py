from typing import *
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
if TYPE_CHECKING:
    from .EventListener import IEventListener

ProtocolData = dict[str, Any]
TEventListener = TypeVar('TEventListener', bound='IEventListener')
TEvent = dict[int, list[TEventListener]]

class TUserData(TypedDict):
    qq: int
    jibi: int
    card: str
    status: str
    equipment: str
    card_limit: int
    event_pt: int
    event_stage: int
    event_skill: int
    dead: int
    flags: int
    assembling: int
    hp: int
    mp: int
    maj_quan: int

class TGlobalState(TypedDict):
    last_card_user: int
    supernova_user: List[List[int]]
    used_cards: List[int]
    global_status: List[str]
    observatory: bool
    event_route: List[int]
    bingo_state: List[int]
    sign: int
    current_event: str
    current_shop: str
class TUserState(TypedDict, total=False):
    circus: bool
    mishi_id: int
    dragon_who: int
    branch_removed: bool
    exceed_limit: bool

class TWords(TypedDict):
    keyword: Tuple[str, List[str]]
    hidden: Tuple[List[str], List[str]]
    begin: List[str]
    bombs: List[str]
    last_update_date: str

class Pack(Enum):
    tarot = auto()
    minecraft = auto()
    zhu = auto()
    sanguosha = auto()
    honglongdong = auto()
    uno = auto()
    once_upon_a_time = auto()
    explodes = auto()
    stone_story = auto()
    orange_juice = auto()
    playtest = auto()
    poker = auto()
    gregtech = auto()
    cultist = auto()
    ff14 = auto()
    toaru = auto()
    pvz = auto()
    secret_history = auto()
    misc = auto()
    factorio = auto()
    silly = auto()
    physic = auto()
    stare = auto()
    rusty_lake = auto()
class Sign(IntEnum):
    shiyuan = 0
    jiesha = 1
    tonglin = 2
    momi = 3
    xieshen = 4
    tianqiong = 5
    #feixi = 6
    @classmethod
    def random(cls):
        import random
        return random.choice(list(cls))
    def pack(self):
        return [{Pack.tarot},
            {Pack.zhu, Pack.sanguosha, Pack.uno, Pack.once_upon_a_time, Pack.playtest, Pack.poker},
            {Pack.minecraft, Pack.gregtech, Pack.explodes, Pack.orange_juice, Pack.ff14},
            {Pack.cultist, Pack.secret_history, Pack.pvz, Pack.stone_story},
            {Pack.toaru, Pack.factorio, Pack.physic},
            {Pack.misc},
            {Pack.honglongdong, Pack.silly},
            {Pack.stare, Pack.rusty_lake}][self]
    @property
    def name_ch(self):
        return ["始源座", "皆杀座", "通林座", "墨密座", "械神座", "天穹座", "飞戏座"][self]
    @property
    def contains_ch(self):
        return ["塔罗",
            "逐梦东方圈、三国杀、uno、很久很久以前、试个好游戏、扑克牌",
            "Minecraft、格雷科技、保持说话不会爆炸、100%鲜橙汁、FF14",
            "密教模拟器及其秘史、植物大战僵尸、Stone Story RPG",
            "魔法禁书目录、factorio、近代物理",
            "Misc",
            "东方虹龙洞卡牌、愚蠢",
            "凝视、锈湖"][self]
    @property
    def description(self): # TODO
        return f"卡包：{self.contains_ch}的牌掉率提升。"
    @classmethod
    def description_all(cls):
        return "\n".join(f"{int(i)}. {i.description}" for i in Sign)
    def DumpData(self):
        return {"type": "sign", "id": self.value, "name": self.name_ch, "description": self.description}
    