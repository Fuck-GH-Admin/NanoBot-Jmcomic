import os
import asyncio
import time
from pathlib import Path
from typing import List, Optional

from nonebot.log import logger

from ..config import plugin_config
from ..models import TaskResult, ProgressCallback
from ..repositories.book_repo import BookRepository
from ..utils.network_utils import NetworkUtils
from ..utils.string_utils import StringUtils
from .downloader import JmDownloader, JmOptionCache
from .converter import PDFConverter, PDFEncryptor

try:
    import jmcomic
except ImportError:
    jmcomic = None


class BookService:
    def __init__(self):
        self.repo = BookRepository()
        self.temp_dir = Path(plugin_config.jm_download_dir)
        self.option_path = Path(plugin_config.jm_option_path)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._last_network_check = 0.0
        self._network_msg = ""
        self.dl = JmDownloader(self.temp_dir, self.option_path, self.repo.books_dir)
        self.download_timeout = 300
        self.convert_timeout = 300

    def _check_env(self) -> bool:
        return (jmcomic is not None) and self.option_path.exists()

    def check_network(self) -> str:
        now = time.time()
        if now - self._last_network_check < 300:
            return self._network_msg
        self._last_network_check = now
        changed = False
        if NetworkUtils.test_connectivity(timeout=3):
            NetworkUtils.update_option_proxy(str(self.option_path), enable_proxy=False)
            self._network_msg = "🌐 网络：直连模式"
            changed = True
        elif NetworkUtils.test_proxy_connectivity("http://127.0.0.1:7890", timeout=3):
            NetworkUtils.update_option_proxy(str(self.option_path), enable_proxy=True)
            self._network_msg = "🌐 网络：代理模式 (127.0.0.1:7890)"
            changed = True
        else:
            self._network_msg = "🌐 网络：不可用，下载可能失败"
        if changed:
            JmOptionCache.invalidate()
        return self._network_msg

    def refresh_paths(self):
        self.repo.refresh()
        self.temp_dir = Path(plugin_config.jm_download_dir)
        self.option_path = Path(plugin_config.jm_option_path)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.dl = JmDownloader(self.temp_dir, self.option_path, self.repo.books_dir)
        JmOptionCache.invalidate()

    async def process_download(
        self, ids: List[str], progress: Optional[ProgressCallback] = None,
        on_result: Optional[callable] = None,
    ) -> List[TaskResult]:
        if not self._check_env():
            return [TaskResult("", "", False, error_msg="环境配置不完整")]
        if not ids:
            return [TaskResult("", "", False, error_msg="请提供 ID")]

        ids = list(dict.fromkeys(ids))
        request_ids = set(ids)
        loop = asyncio.get_running_loop()
        semaphore = asyncio.Semaphore(3)
        in_progress: set[str] = set()

        password = plugin_config.encrypt_password
        if progress:
            await progress(f"⏳ 开始处理 {len(ids)} 个本子...\n🔒 加密密码：{password}")

        net_msg = await loop.run_in_executor(None, self.check_network)
        if net_msg and progress:
            await progress(net_msg)

        results: List[TaskResult] = []

        async def process_one(aid: str):
            if aid in in_progress:
                results.append(TaskResult(aid, aid, False, error_msg="已有相同任务进行中"))
                return
            in_progress.add(aid)
            async with semaphore:
                try:
                    items = await asyncio.wait_for(
                        loop.run_in_executor(None, self.dl.download_album, aid),
                        timeout=self.download_timeout,
                    )
                    if not items:
                        results.append(TaskResult(aid, aid, False, error_msg="下载失败，未找到内容"))
                        return

                    for item in items:
                        source = item['path']
                        title = item['title']
                        sids = item['series_ids']
                        sids = [s for s in sids if s not in request_ids]

                        if source.exists() and source.stat().st_size < 10240:
                            results.append(TaskResult(aid, title, False, error_msg="文件过小，视为无效"))
                            continue

                        pdf = await asyncio.wait_for(
                            loop.run_in_executor(None, PDFConverter.convert_zip, source, self.repo.output_dir),
                            timeout=self.convert_timeout,
                        )
                        if not pdf:
                            results.append(TaskResult(aid, title, False, error_msg="PDF转换失败"))
                            continue

                        enc = await asyncio.wait_for(
                            loop.run_in_executor(None, PDFEncryptor.encrypt, pdf, self.temp_dir, password),
                            timeout=120,
                        )
                        send_path = enc if (enc and enc.exists()) else pdf

                        cleanup = []
                        if enc and enc.exists():
                            cleanup.append(enc)

                        tr = TaskResult(
                            album_id=aid,
                            title=title,
                            success=True,
                            file_path=send_path,
                            series_ids=sids,
                            cleanup_paths=cleanup,
                        )
                        results.append(tr)
                        if on_result:
                            await on_result(tr)
                        if progress:
                            await progress(f"✅ [{title}] 处理完成")

                except asyncio.TimeoutError:
                    logger.exception(f"[JM] 超时 {aid}")
                    results.append(TaskResult(aid, aid, False, error_msg="处理超时"))
                except Exception:
                    logger.exception(f"[JM] 处理失败 {aid}")
                    results.append(TaskResult(aid, aid, False, error_msg="处理异常"))
                finally:
                    in_progress.discard(aid)

        tasks = [process_one(aid) for aid in ids]
        await asyncio.gather(*tasks)
        return results

    async def process_bitter_lovebirds(self, progress: Optional[ProgressCallback] = None, on_result: Optional[callable] = None) -> List[TaskResult]:
        return await self.process_download(["350234", "350235"], progress, on_result)
