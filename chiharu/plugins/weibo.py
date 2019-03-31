import re
from nonebot import on_command, CommandSession, scheduler, get_bot
from weibo import Client
import chiharu.plugins.config as config

API_KEY = '3911660282'
API_SECRET = 'aa56e2454428fe39f9af7365cdf07734'
REDIRECT_URI = 'https://api.weibo.com/oauth2/default.html'
token = {'access_token': '2.00JWktUGsWviQE35d4be257etIM3ME', 'remind_in': '157679999', 'uid': '5953373929', 'isRealName': 'true', 'expires_at': 1705125469}

@on_command(('misc', 'bandori', 'manga'), only_to_me=False)
@config.ErrorHandle
async def GetBandoriManga(session: CommandSession):
    listout = await _GetBandoriManga()
    if len(listout) == 0:
        await session.send("No newer manga!")
    else:
        await session.send(listout, auto_escape=True)

@scheduler.scheduled_job('cron', hour='00-21/3')
async def CheckBandoriManga():
    bot = get_bot()
    listout = await _GetBandoriManga()
    if len(listout) != 0:
        for id in config.group_id_dict['bandori_manga']:
            await bot.send_group_msg(group_id=id, message=listout)

async def _GetBandoriManga():
	pagenum = 1
	listout = []
	max_manga = [0, 0]
	client = Client(API_KEY, API_SECRET, REDIRECT_URI, token)
	#client.set_access_token(token['access_token'], token['expires_in'])
	with open(config.rel("bandori_last_manga.txt")) as f:
		bandori_last_manga = [int(f.readline()), int(f.readline())]
	while 1:
		data = client.get('statuses/friends_timeline', page=pagenum)['statuses']
		if data:
			pagenum += 1
		else:
			break
		for weibo in data:
			if weibo['user']['name'] == 'BanGDream每日推' and '#bangdream四格漫画#' in weibo['text']:
				if_2 = 1 if "2nd" in weibo['text'] else 0
				match = re.search('第(.*?)话', weibo['text'])
				if not match:
					continue
				if bandori_last_manga[if_2] < int(match.group(1)):
					listout.append(config.cq.text(("2nd season" if if_2 == 1 else "") + match.group(0) + u'：\n'))
					listout.append(config.cq.img(weibo['original_pic']))
					if max_manga[if_2] < int(match.group(1)):
						max_manga[if_2] = int(match.group(1))
	for i in (0, 1):
		if bandori_last_manga[i] < max_manga[i] and max_manga[i] != 999:
			bandori_last_manga[i] = max_manga[i]
	with open(config.rel("bandori_last_manga.txt"), 'w') as f:
		f.write(str(bandori_last_manga[0]) + '\n')
		f.write(str(bandori_last_manga[1]))
	return listout