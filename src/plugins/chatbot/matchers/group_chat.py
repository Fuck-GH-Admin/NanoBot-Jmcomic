import re
import asyncio
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import EventPlainText
from nonebot.log import logger
from nonebot.exception import FinishedException

from ..services import book_srv, perm_srv
from ..models import TaskResult
from ..utils.string_utils import StringUtils
from ..utils.rate_limiter import check as check_rate_limit, remaining as rate_remaining
from ..config import plugin_config


group_chat = on_message(priority=10, block=False)


@group_chat.handle()
async def handle_group_chat(bot: Bot, event: GroupMessageEvent, text: str = EventPlainText()):
    text = text.strip()
    if not text:
        return

    user_id = str(event.user_id)
    group_id = int(event.group_id)

    if not perm_srv.is_group_whitelisted(str(group_id)):
        return

    text = re.sub(r'\[CQ:at,qq=\d+\]\s*', '', text).strip()
    logger.info(f"[JM] 群消息: User:{user_id} Group:{group_id} | {text}")

    if re.match(r'^/?jm\s*(帮助|help|\?)?$', text, re.IGNORECASE):
        await group_chat.finish(
            "📖 JM 下载帮助\n"
            f"  /jm <ID>    下载本子\n"
            f"  /jm <ID1 ID2>  批量下载\n"
            f"  苦命鸳鸯    触发彩蛋\n"
            f"🔒 加密密码：{plugin_config.encrypt_password}"
        )
        return

    if "苦命鸳鸯" in text:
        try:
            if not check_rate_limit(user_id):
                sec = rate_remaining(user_id)
                await group_chat.finish(f"⏳ 操作过于频繁，请 {sec} 秒后重试")
            results = await _run_download_with_progress(bot, group_id, "group",
                lambda p: _send_progress(bot, group_id, "group", p),
                bitter_lovebirds=True)
            await _send_results(bot, group_id, "group", results)
            if any(r.success for r in results):
                await group_chat.finish("…这何尝不是一种苦命鸳鸯")
            await group_chat.finish()
        except FinishedException:
            raise
        except Exception:
            logger.exception("[JM] 彩蛋失败")
            await group_chat.finish("彩蛋触发失败，请稍后重试")
        return

    jm_match = re.match(r'^/jm\s+(\d[\d\s]*)$', text, re.IGNORECASE)
    if jm_match:
        ids = re.findall(r'\d+', jm_match.group(1))
        if ids:
            if not check_rate_limit(user_id):
                sec = rate_remaining(user_id)
                await group_chat.finish(f"⏳ 操作过于频繁，请 {sec} 秒后重试")
            await group_chat.send(f"⏳ 正在调度下载任务: {ids}")
            try:
                results = await _run_download_with_progress(bot, group_id, "group",
                    lambda p: _send_progress(bot, group_id, "group", p), ids=ids)
                await _send_results(bot, group_id, "group", results)
                await group_chat.finish()
            except FinishedException:
                raise
            except Exception:
                logger.exception("[JM] 下载任务失败")
                await group_chat.finish("下载任务执行失败，请稍后重试或检查网络")
        else:
            await group_chat.finish("没有识别到有效的数字ID哦")
        return

    logger.debug(f"[JM] 忽略非JM消息: {text}")


async def _send_progress(bot: Bot, target: int, mtype: str, msg: str):
    try:
        if mtype == "group":
            await bot.send_group_msg(group_id=target, message=msg)
        else:
            await bot.send_private_msg(user_id=target, message=msg)
    except Exception:
        pass


async def _run_download_with_progress(
    bot: Bot, target: int, mtype: str,
    progress_cb, ids=None, bitter_lovebirds=False
) -> list:
    loop = asyncio.get_running_loop()
    if bitter_lovebirds:
        return await book_srv.process_bitter_lovebirds(progress=progress_cb)
    return await book_srv.process_download(ids or [], progress=progress_cb)


async def _cleanup_result(result: TaskResult):
    for p in result.cleanup_paths:
        if p and p.exists():
            try:
                p.unlink()
            except Exception:
                pass


async def _send_results(bot: Bot, target: int, mtype: str, results: list):
    series_ids_all = []
    send_tasks = []

    for r in results:
        if r.success and r.file_path:
            send_tasks.append(_upload_file(bot, target, mtype, r))
            series_ids_all.extend(s for s in r.series_ids if s not in series_ids_all)

    if send_tasks:
        await asyncio.gather(*send_tasks)

    for r in results:
        if r.success:
            await _cleanup_result(r)

    if series_ids_all:
        unique = sorted(set(series_ids_all))
        if len(unique) > 50:
            ids_str = ' '.join(unique[:50]) + f'... 等{len(unique)}个'
        else:
            ids_str = ' '.join(unique)
        try:
            await _send_progress(bot, target, mtype,
                f"📚 该本子属于系列，其他章节：\n/jm {ids_str}\n（复制上方指令可直接下载）")
        except Exception:
            pass

    success = sum(1 for r in results if r.success)
    failed = [r for r in results if not r.success]
    msg = f"✅ 任务完成：成功 {success}/{len(results)} 本"
    if failed:
        unique_f = list(dict.fromkeys(r.album_id for r in failed))[:10]
        msg += f"\n❌ 失败：{', '.join(unique_f)}"
        if len(failed) > 10:
            msg += f" 等{len(failed)}个"
    try:
        if mtype == "group":
            await bot.send_group_msg(group_id=target, message=msg)
        else:
            await bot.send_private_msg(user_id=int(target), message=msg)
    except Exception:
        pass


async def _upload_file(bot: Bot, target: int, mtype: str, result: TaskResult):
    safe_title = StringUtils.sanitize_filename(result.title) or result.album_id
    if safe_title.startswith(f"{result.album_id}_"):
        safe_title = safe_title[len(result.album_id) + 1:]
    send_name = f"{result.album_id}_{safe_title}.pdf"
    fp = result.file_path
    if not fp:
        logger.warning(f"[JM] 跳过发送 {send_name}: file_path 为 None")
        return
    if not fp.exists():
        logger.warning(f"[JM] 跳过发送 {send_name}: 文件不存在 {fp}")
        return
    file_size = fp.stat().st_size
    upload_timeout = 30 + (file_size / (50 * 1024))
    for retry in range(2):
        try:
            api = "upload_group_file" if mtype == "group" else "upload_private_file"
            key = "group_id" if mtype == "group" else "user_id"
            await asyncio.wait_for(
                bot.call_api(api, **{key: target}, file=str(fp.absolute()), name=send_name),
                timeout=upload_timeout,
            )
            logger.info(f"[JM] ✅ 发送成功: {send_name}")
            return
        except asyncio.TimeoutError:
            logger.warning(f"[JM] 发送超时 {send_name} 重试 {retry+1}/2")
            await asyncio.sleep(2)
        except Exception as e:
            logger.warning(f"[JM] 发送失败 {send_name}: {e} 重试 {retry+1}/2")
            await asyncio.sleep(2)
