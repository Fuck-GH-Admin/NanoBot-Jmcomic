# src/plugins/chatbot/matchers/private_chat.py

import re
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, PrivateMessageEvent
from nonebot.params import EventPlainText
from nonebot.rule import Rule
from nonebot.log import logger
from nonebot.exception import FinishedException

from ..services import book_srv

# 只响应私聊消息
async def _is_private(event: PrivateMessageEvent) -> bool:
    return True

private_chat = on_message(rule=Rule(_is_private), priority=1, block=True)

@private_chat.handle()
async def handle_private(bot: Bot, event: PrivateMessageEvent, text: str = EventPlainText()):
    text = text.strip()
    if not text:
        return
    
    user_id = str(event.user_id)
    logger.info(f"[JM] 收到私聊消息: User:{user_id} | Text:{text}")
    
    # 处理 /jm 指令
    jm_pattern = r'(?:^/jm|^jm|^下载本子|^禁漫)\s*(\d[\d\s]*)'
    match = re.match(jm_pattern, text, re.IGNORECASE)
    
    if match:
        ids = re.findall(r'\d+', match.group(1))
        if ids:
            await private_chat.send(f"⏳ [私聊] 正在调度下载任务: {ids}")
            try:
                res = await book_srv.handle_jm_download(
                    bot=bot, 
                    target_id=event.user_id, 
                    message_type="private", 
                    ids=ids
                )
                await private_chat.finish(res)
            except FinishedException:
                raise  # 不捕获FinishedException
            except Exception as e:
                logger.error(f"[JM] 私聊下载任务执行失败: {e}")
                await private_chat.finish(f"下载任务执行失败: {str(e)}")
        else:
            await private_chat.finish("没有识别到有效的数字ID哦")
        return
    
    # 如果不是JM相关指令，忽略消息
    logger.debug(f"[JM] 忽略非JM私聊消息: {text}")