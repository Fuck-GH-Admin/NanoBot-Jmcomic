import re
import asyncio
from nonebot import on_message
from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import Bot, PrivateMessageEvent
from nonebot.params import EventPlainText
from nonebot.log import logger
from nonebot.exception import FinishedException

from ..services import book_srv, perm_srv
from ..models import TaskResult
from ..utils.string_utils import StringUtils
from ..utils.rate_limiter import check as check_rate_limit, remaining as rate_remaining

from .group_chat import _run_download_with_progress, _send_results, _send_progress


async def _is_friend_private(event: PrivateMessageEvent) -> bool:
    return event.sub_type == "friend"


private_chat = on_message(rule=Rule(_is_friend_private), priority=1, block=True)


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

    if re.match(r'^(/jm|jm|帮助|help|\?)$', text.strip(), re.IGNORECASE):
        from ..config import plugin_config
        await private_chat.finish(
            "📖 JM 下载帮助\n"
            f"  /jm <ID>       下载本子\n"
            f"  /jm <ID1 ID2>  批量下载\n"
            f"  苦命鸳鸯       触发彩蛋\n"
            f"🔒 加密密码：{plugin_config.encrypt_password}"
        )
        return

    jm_pattern = r'(?:^/jm|^jm|^下载本子|^禁漫)\s*(\d[\d\s]*)'
    match = re.match(jm_pattern, text, re.IGNORECASE)
    if match:
        ids = re.findall(r'\d+', match.group(1))
        if ids:
            if not check_rate_limit(user_id):
                sec = rate_remaining(user_id)
                await private_chat.finish(f"⏳ 操作过于频繁，请 {sec} 秒后重试")
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
