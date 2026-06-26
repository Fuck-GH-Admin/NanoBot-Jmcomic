import re
import asyncio
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, PrivateMessageEvent
from nonebot.params import EventPlainText
from nonebot.rule import Rule
from nonebot.log import logger
from nonebot.exception import FinishedException

from ..services import book_srv, perm_srv
from ..models import TaskResult

from .group_chat import _run_download_with_progress, _send_results, _send_progress


PRIVATE_LIMIT_PER_MINUTE = 1
_private_usage: dict = {}


def _check_rate_limit(user_id: str) -> bool:
    import time
    now = time.time()
    last = _private_usage.get(user_id, 0)
    if now - last < 60:
        return False
    _private_usage[user_id] = now
    return True


async def _is_private(event: PrivateMessageEvent) -> bool:
    return True


private_chat = on_message(rule=Rule(_is_private), priority=1, block=True)


@private_chat.handle()
async def handle_private(bot: Bot, event: PrivateMessageEvent, text: str = EventPlainText()):
    text = text.strip()
    if not text:
        return

    user_id = str(event.user_id)

    if not perm_srv.is_private_whitelisted(user_id):
        logger.warning(f"[JM] 私聊拒绝 User:{user_id}")
        await private_chat.finish("⛔ 你没有使用权限")
        return

    logger.info(f"[JM] 私聊: User:{user_id} | {text}")

    jm_pattern = r'(?:^/jm|^jm|^下载本子|^禁漫)\s*(\d[\d\s]*)'
    match = re.match(jm_pattern, text, re.IGNORECASE)
    if match:
        ids = re.findall(r'\d+', match.group(1))
        if ids:
            if not _check_rate_limit(user_id):
                await private_chat.finish("⏳ 操作过于频繁，请稍后重试")
            await private_chat.send(f"⏳ [私聊] 正在调度下载任务: {ids}")
            try:
                results = await _run_download_with_progress(bot, user_id, "private",
                    lambda p: _send_progress(bot, user_id, "private", p), ids=ids)
                await _send_results(bot, user_id, "private", results)
                await private_chat.finish()
            except FinishedException:
                raise
            except Exception:
                logger.exception("[JM] 私聊下载失败")
                await private_chat.finish("下载任务执行失败，请稍后重试或检查网络")
        else:
            await private_chat.finish("没有识别到有效的数字ID哦")
        return

    logger.debug(f"[JM] 忽略非JM私聊: {text}")
