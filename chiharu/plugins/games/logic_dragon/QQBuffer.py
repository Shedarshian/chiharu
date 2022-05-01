from typing import *
from .Helper import Buffer
from .Types import ProtocolData
from nonebot.command import CommandSession

class QQBuffer(Buffer):
    def __init__(self, qq: int, session: CommandSession) -> None:
        self.session = session
        super().__init__(qq)
    async def selfFlush(self):
        prompt = ""
        for data in self.dataBuffer:
            char = "你" if data.get("qq") == self.qq else "龙" if data.get("qq") == 1 else "该玩家"
            match data.get("type"):
                case "failed":
                    match data.get("error_code"):
                        case -1:
                            prompt += "未知设计错误。"
                        case 0:
                            prompt += f"运行时错误：{data.get('error_msg')}。"
                        case 1:
                            prompt += "响应参数不匹配。"
                        case 100:
                            prompt += "接龙节点未找到。"
                        case 101:
                            prompt += "节点已分叉。"
                        case 102:
                            prompt += "节点不可分叉。"
                
                case "choose_failed":
                    pass
                case "response_invalid":
                    pass
                case "update_begin_word":
                    pass
                case "update_keyword":
                    pass
                case "update_hidden_keyword":
                    pass
                case "OnKeyword":
                    pass
                case "OnHiddenKeyword":
                    pass
                case "OnDuplicatedWord":
                    pass
                case "OnBombed":
                    pass
                case "OnDragoned":
                    pass
                case "OnStatusAdd":
                    pass
                case "OnStatusRemove":
                    pass
                case "OnJibiChange":
                    pass
                case "OnEventPtChange":
                    pass
                case "OnDeath":
                    pass
                case "attacked":
                    pass

                case "draw_and_use":
                    pass
                case "use_card":
                    pass
                case "draw_cards":
                    pass
                case "discard_cards":
                    pass
                case "remove_cards":
                    pass
                case "get_item":
                    pass
                case "use_item":
                    pass

                case "card_effect":
                    card = data.get("card")
                    if not isinstance(card, dict) or card.get("type") != "card":
                        continue
                    match card.get("id"):
                        case 73:
                            prompt += char + "今天幸运护符的使用卡牌次数已完。"
                        case _:
                            pass
                case "status_effect":
                    status = data.get("status")
                    if not isinstance(status, dict) or status.get("type") != "status":
                        continue
                    match status.get("id"):
                        case -1:
                            prompt += char + "死了，不能接龙。"
                        case 0:
                            prompt += char + "太笨了，这张卡的使用无效。"
                        case 1:
                            prompt += char + f"太疲劳了，不能使用卡牌【{data.get('forbiddencard').get('name')}】。"
                        case 3:
                            prompt += char + f"完成了任务：{data.get('mission')}\n获得了{data.get('jibi')}击毙。该任务还可以完成{data.get('remain')}次。"
                        case 5:
                            if data.get('time') == "BeforeDragoned":
                                prompt += "教皇说，你需要首尾接龙，接龙失败。"
                            elif data.get('time') == "OnDragoned":
                                prompt += char + "收到了教皇奖励你的2击毙。"
                        case 6:
                            if data.get('time') == "BeforeDragoned":
                                prompt += "教皇说，你需要尾首接龙，接龙失败。"
                            elif data.get('time') == "OnDragoned":
                                prompt += char + "被教皇扣除了2击毙。"
                        case 9:
                            if data.get('time') == "OnDuplicatedWord":
                                prompt += "触发了IX - 隐者的效果，没死。"
                            elif data.get('time') == "OnBombed":
                                prompt += "触发了IX - 隐者的效果，没死。"
                        case 12:
                            prompt += char + "触发了免死的效果，免除死亡。"
                        case 13:
                            prompt += f"因XIII - 死神，死亡时间加倍了{data.get('count')}次。"
                        case 14:
                            prompt += char + "因XIV - 节制的效果，不能使用除胶带外的卡牌。"
                        case 17:
                            pass
                        case 30:
                            prompt += char + "病了，不能接龙。"
                        case 50:
                            prompt += char + "触发了死秽回避之药的效果，扣除5击毙，免除死亡。"
                        case 53:
                            prompt += char + f"触发了反转·死秽回避之药的效果，获得{5 * data.get('count')}击毙但死亡时间增加{2 * data.get('count')}h。"
                        case 52:
                            prompt += char + f"触发了辉夜姬的秘密宝箱的效果，抽{data.get('count')}张卡。"
                        case 54:
                            prompt += char + f"触发了反转·辉夜姬的秘密宝箱的效果，弃掉了{f"【{card.get('name')}】" for card in data.get('cards')}。"
                        case 60:
                            prompt += char + f"触发了+2的效果，摸{count := data.get('count')}张非负面卡和{count}张非正面卡。"
                        case 73:
                            prompt += char + "不能使用除幸运护符之外的卡牌。"
                        case 74:
                            prompt += char + "触发了极速装置。"
                        case 93:
                            prompt += char + f"触发了{data.get('count')}次变压器（♣10）的效果，击毙变化量变更为{data.get('njibi')}。"
                        case 92:
                            prompt += char + f"触发了{data.get('count')}次反转·变压器（♣10）的效果，击毙变化量变更为{data.get('njibi')}。"
                        case 100:
                            sname = data.get('rstatus').get('name')
                            scount = data.get('rstatus').get('count')
                            if data.get('flag') == 'all':
                                sdes = f"触发了胶带的效果，完全防住了{f"{count}层" if count > 1 else ''}【{sname}】。"
                            elif data.get('flag') == 'part':
                                sdes = f"触发了胶带的效果，防住了{f"{count}层" if count > 1 else ''}【{sname}】，但没有完全防住。"
                            prompt += char + sdes
                        case 90:
                            sname = data.get('rstatus').get('name')
                            scount = data.get('rstatus').get('count')
                            if data.get('flag') == 'all':
                                sdes = f"触发了反转·胶带的效果，完全防住了{f"{count}层" if count > 1 else ''}【{sname}】。"
                            elif data.get('flag') == 'part':
                                sdes = f"触发了反转·胶带的效果，防住了{f"{count}层" if count > 1 else ''}【{sname}】，但没有完全防住。"
                            prompt += char + sdes
                        case 101:
                            if time := data.get('time') == 'OnDragoned':
                                prompt += char + "因零点模块奖励1击毙。"
                            elif time == 'AfterJibiChange':
                                prompt += char + "不再需要零点模块了。"
                        case 102:
                            prompt += char + "因此攻击同时对多人生效而无效了此攻击。"
                        case 109:
                            prompt += char + "因蚺虵法术需要首尾接龙。"
                        case 108:
                            prompt += char + "因反转·蚺虵法术需尾首接龙。"
                        case 110:
                            prompt += char + "因月下彼岸花扣除1击毙。"
                        case 105:
                            prompt += char + "因反转·月下彼岸花获得1击毙。"
                        case 111 or 106 or 112 or 107:
                            prompt += char + "判决重合，被判处死刑，陷入无法战斗状态。"
                        case 108:
                            prompt += char + "无法战斗，不能接龙。"
                        case 95:
                            prompt += char + "因衰弱，获得击毙减少。"
                        case 113:
                            prompt += f"{"大地摇动被触发了，\n"if "大地摇动被触发了" not in prompt else ''}玩家{data.get('userQQ')}被扣除了{4 * data.get('count')}击毙。"
                        case 114:
                            pass
                        case 116:
                            prompt += char + f"触发了告解，多获得{data.get('count')}击毙。"
                        case 94:
                            prompt += char + f"触发了反转·告解，少获得{data.get('count')}击毙。"
                        case 117:
                            prompt += char + "触发了深谋远虑之策，本次免单。"
                        case 119:
                            sname = data.get('rstatus').get('name')
                            scount = data.get('rstatus').get('count')
                            if flag := data.get('flag') == 'ill':
                                sdes = f"触发了光阴神的礼赞凯歌，免除生病。"
                            elif flag == 'all':
                                sdes = f"触发了凯歌的效果，完全防住了{f"{count}层" if count > 1 else ''}【{sname}】。"
                            elif flag == 'part':
                                sdes = f"触发了凯歌的效果，防住了{f"{count}层" if count > 1 else ''}【{sname}】，但没有完全防住。"
                        case _:
                            pass
                case "card_use":
                    card = data.get("card")
                    if not isinstance(card, dict) or card.get("type") != "card":
                        continue
                    match card.get("id"):
                        case 1:
                            prompt += "请选择一张手牌："
                        case 2:
                            if len(ql := data.get("userIDs")) == 1:
                                prompt += f"当前周期内接龙次数最多的玩家是[CQ:at,qq={ql[0]}]。"
                            else:
                                prompt += f"当前周期内接龙次数最多的玩家有{''.join(f'[CQ:at,qq={q}]' for q in ql)}。"
                        case 6:
                            prompt += "请选择一名玩家复活："
                        case 7:
                            if len(tk := data.get('to_kill')) == 0:
                                prompt += "但什么人都没有车到。"
                            else:
                                prompt += char + f"车到了{''.join(f'[CQ:at,qq={q}]' for q in tk)}。"
                        case 15:
                            prompt += f"上一位使用卡牌的人是[CQ:at,qq={data.get('userQQ')}]。"
                        case 16:
                            prompt += f"随机被击毙的玩家是{''.join(f'[CQ:at,qq={q}' for q in data.get('qqlist'))}。"
                        case 19:
                            prompt += char + f"揭示的隐藏奖励词是： {data.get('hiddenKeyword')} 。"
                        case 20:
                            match data.get('flag'):
                                case '-':
                                    prompt += char + "因审判扣除20击毙。"
                                case '+':
                                    prompt += char + "因审判获得20击毙。"
                                case '0':
                                    prompt += "但无事发生。"
                                case _:
                                    pass
                        case 53:
                            if len(cards := data.get('cards')) > 0:
                                prompt += char + f"失去了手牌{''.join(f"【{card.get('name')}】" for card in cards)}。"
                        case 81:
                            prompt += f"今天接龙的所有人都赢了。恭喜你们。"
                        case 95:
                            if data.get('choose'):
                                prompt += "请选择一张手牌："
                            else:
                                prompt += char + f"使用了卡牌【{data.get('card').get('name')}】的效果。"
                        case 100:
                            prompt += f"移除了{data.get('rstatus').get('count')}层【{data.get('rstatus').get('name')}】。"
                        case 105:
                            if data.get('choose'):
                                prompt += "请选择两张手牌："
                            elif data.get('available'):
                                prompt += f"成功合成了id号为{data.get('id')}的卡牌。"
                            else:
                                prompt += f"不存在id号为{data.get('id')}的卡牌。"
                        case 106:
                            if data.get('choose'):
                                prompt += "请选择一张手牌："
                            elif not data.get('available'):
                                prompt += "找不到id之和为所选卡牌id的组合。"
                            else:
                                ids = data.get('ids')
                                prompt += f"成功将所选卡牌分解成了id为{ids[0]}和{ids[1]}的卡牌。"
                        case 107:
                            if len(bombs := data.get('bombs')) == 0:
                                prompt += "没有可用于揭示的雷。"
                            else:
                                prompt += char + f"揭示的雷为： {' '.join(bomb for bomb in bombs)}。"
                        case 108:
                            if data.get('choose'):
                                prompt += "请选择一名玩家或发送qq=2711644761对千春使用："
                            elif data.get('chiharu'):
                                pass#TODO
                        case 119:
                            prompt += char + "移除了自己身上的大病一场。"
                        case _:
                            pass
                case "card_on_draw":
                    card = data.get("card")
                    if not isinstance(card, dict) or card.get("type") != "card":
                        continue
                    match card.get("id"):
                        case _:
                            pass

                case "check":
                    pass

                case _:
                    pass
        await self.session.send(prompt)
    async def GetResponse(self, request: ProtocolData) -> ProtocolData:
        return await super().GetResponse(request)