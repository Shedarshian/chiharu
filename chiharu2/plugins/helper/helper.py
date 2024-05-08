import contextlib
from nonebot.adapters.discord.commands.matcher import ApplicationCommandMatcher

@contextlib.asynccontextmanager
async def Waiting(matcher: type[ApplicationCommandMatcher]):
    try:
        await matcher.send_deferred_response()
        yield
    except Exception:
        await matcher.edit_response("出现了异常，没有返回！")
        raise
