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
                        case _:
                            pass
                case "status_effect":
                    status = data.get("status")
                    if not isinstance(status, dict) or status.get("type") != "status":
                        continue
                    match status.get("id"):
                        case 0:
                            prompt += char + "太笨了，这张卡的使用无效。"
                        case 1:
                            prompt += char + f"太疲劳了，不能使用卡牌【{data.get('forbiddencard').get('name')}】。"
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