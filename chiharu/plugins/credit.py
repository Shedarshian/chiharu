import datetime
import json
#import config
from . import config
#from nonebot import on_command, CommandSession, on_natural_language, NLPSession, IntentCommand, get_bot, permission

is12to6 = 1#(datetime.time.now().hour < 5)
with open(config.rel('credit.json')) as f:
    credit = json.load(f)

def message(group_id: str, qq: str):
    global credit, is12to6
    if qq not in credit[group_id]:
        credit[group_id][qq] = {'message_night': 0, 'message_day': 0, 'credit': 0}
    credit[group_id][qq]['message_night' if is12to6 else 'message_day'] += 1

def credit(message_night, message_day):
    return 0

def computeCredit():
    global credit
    for group_id, d in credit.items():
        for qq, d2 in d:
            d2['credit'] += credit(d2['message_night'], d2['message_day'])

#@on_natural_language(only_to_me=False, allow_empty_message=True)
#async def _(session: NLPSession):
#    group_id = session.ctx['group_id']
#    qq = session.ctx['user_id']