from .. import config
from . import zhu_core

# zhu = zhu_core.GamePrivate('zhu')

# @zhu.begin_uncomplete(('play', 'zhu', 'begin'))
# async def zhu_begin_uncomplete(session: CommandSession, data: Dict[str, Any]=(4, 8)):
#     # data: {'players': [qq], 'args': [args], 'anything': anything}
#     # args: -play.maj.begin 'type_str/友人房id'
#     await session.send('已为您参与匹配')