# src/plugins/chatbot/matchers/group_chat.py

import re
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import EventPlainText
from nonebot.log import logger
from nonebot.exception import FinishedException

from ..services import book_srv
from ..consts import JM_TRIGGERS, BITTER_LOVEBIRDS_IDS

# 优先级 10
group_chat = on_message(priority=10, block=False)

@group_chat.handle()
async def handle_group_chat(bot: Bot, event: GroupMessageEvent, text: str = EventPlainText()):
    text = text.strip()
    if not text:
        return

    user_id = str(event.user_id)
    
    # 去掉@bot的部分（如果有）
    # 消息中可能包含 [at:qq=xxx,name=xxx] 格式
    text = re.sub(r'\[at:qq=\d+,name=[^\]]*\]\s*', '', text).strip()
    
    logger.info(f"[JM] 收到群消息: User:{user_id} | Text:{text}")
    
    # 2. 处理苦命鸳鸯彩蛋
    if "苦命鸳鸯" in text:
        try:
            msg = await book_srv.handle_bitter_lovebirds(bot, event.group_id)
            await group_chat.finish(msg)
        except FinishedException:
            raise
        except Exception as e:
            logger.error(f"[JM] 苦命鸳鸯彩蛋触发失败: {e}")
            await group_chat.finish("彩蛋触发失败 QAQ")
        return

    # 3. 严格匹配 /jm 指令（不区分大小写）
    # 格式：/jm 123 或 /jm 123 456
    jm_match = re.match(r'^/jm\s+(\d[\d\s]*)$', text, re.IGNORECASE)
    
    if jm_match:
        ids = re.findall(r'\d+', jm_match.group(1))
        if ids:
            await group_chat.send(f"⏳ 正在调度下载任务: {ids}")
            try:
                res = await book_srv.handle_jm_download(
                    bot=bot, 
                    target_id=event.group_id, 
                    message_type="group", 
                    ids=ids
                )
                await group_chat.finish(res)
            except FinishedException:
                raise
            except Exception as e:
                logger.error(f"[JM] 下载任务执行失败: {e}")
                await group_chat.finish(f"下载任务执行失败: {str(e)}")
        else:
            await group_chat.finish("没有识别到有效的数字ID哦")
        return
    
    # 4. 如果不是JM相关指令，忽略消息
    logger.debug(f"[JM] 忽略非JM消息: {text}")