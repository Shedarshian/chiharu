import contextlib
from os import path
from nonebot.adapters.discord.commands.matcher import ApplicationCommandMatcher
from nonebot.matcher import Matcher

PATH = "C:\\coolq_data\\"
PATH_IMG = "C:\\go\\data\\images"
PATH_REC = "C:\\Users\\Administrator\\Downloads\\CQP-xiaoi\\酷Q Pro\\data\\record"
PATH_PAGE = "C:\\games"

def rel(rel_path: str):
    return path.join(PATH, rel_path)
def img(rel_path: str):
    return path.join(PATH_IMG, rel_path)
def rec(rel_path: str):
    return path.join(PATH_REC, rel_path)
def pag(rel_path: str):
    return path.join(PATH_PAGE, rel_path)

@contextlib.asynccontextmanager
async def Waiting(matcher: type[ApplicationCommandMatcher]):
    try:
        await matcher.send_deferred_response()
        yield
    except Exception:
        await matcher.edit_response("出现了异常，没有返回！")
        raise

# @contextlib.asynccontextmanager
# async def WaitingMessage(matcher: type[Matcher]):
#     try:
#         await matcher.send()
#         yield
#     except Exception:
#         await matcher.edit_response("出现了异常，没有返回！")
#         raise
