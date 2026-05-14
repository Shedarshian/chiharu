
from nonebot.adapters.discord.commands import CommandOption, on_slash_command, CommandOptionType
from nonebot.adapters.discord.api import SubCommandGroupOption, SubCommandOption, IntegerOption, StringOption, BooleanOption, NumberOption, OptionChoice, File
from nonebot.adapters.discord import Bot, MessageEvent, MessageSegment, Message, InteractionCreateEvent

matcher = on_slash_command(name="dragon",
    description="逻辑接龙",
    options=[
        
    ]
)