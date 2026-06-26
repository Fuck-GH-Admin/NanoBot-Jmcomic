import os
import asyncio
from pathlib import Path
from typing import List, Optional

from nonebot.log import logger

from ..config import plugin_config
from ..models import TaskResult, ProgressCallback
from ..repositories.book_repo import BookRepository
from ..utils.network_utils import NetworkUtils
from .downloader import JmDownloader, JmOptionCache
from .converter import PDFConverter, PDFEncryptor

try:
    import jmcomic
except ImportError:
    jmcomic = None


def _sanitize_filename(name: str) -> str:
    return "".join(c for c in name if c not in '<>:"/\\|?*') or "untitled"


class BookService:
    def __init__(self):
        self.repo = BookRepository()
        self.temp_dir = Path(plugin_config.jm_download_dir)
        self.option_path = Path(plugin_config.jm_option_path)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self._network_checked = False
        self.dl = JmDownloader(self.temp_dir, self.option_path)
        self.download_timeout = 300
        self.convert_timeout = 300

    def _check_env(self) -> bool:
        return (jmcomic is not None) and self.option_path.exists()

    def check_network(self) -> str:
        if self._network_checked:
            return ""
        if NetworkUtils.test_connectivity(timeout=3):
            self._network_checked = True
            NetworkUtils.update_option_proxy(str(self.option_path), enable_proxy=False)
            return "🌐 网络：直连模式"
        if NetworkUtils.test_proxy_connectivity("http://127.0.0.1:7890", timeout=3):
            self._network_checked = True
            NetworkUtils.update_option_proxy(str(self.option_path), enable_proxy=True)
            return "🌐 网络：代理模式 (127.0.0.1:7890)"
        self._network_checked = True
        return "🌐 网络：不可用，下载可能失败"

    def refresh_paths(self):
        self.temp_dir = Path(plugin_config.jm_download_dir)
        self.option_path = Path(plugin_config.jm_option_path)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.dl = JmDownloader(self.temp_dir, self.option_path)
        JmOptionCache.invalidate()

    async def process_download(
        self, ids: List[str], progress: Optional[ProgressCallback] = None
    ) -> List[TaskResult]:
        if not self._check_env():
            return [TaskResult("", "", False, error_msg="环境配置不完整")]
        if not ids:
            return [TaskResult("", "", False, error_msg="请提供 ID")]

        ids = list(dict.fromkeys(ids))
        request_ids = set(ids)
        loop = asyncio.get_running_loop()
        semaphore = asyncio.Semaphore(3)

        if progress:
            await progress(f"⏳ 开始处理 {len(ids)} 个本子...\n🔒 加密密码：114514")

        net_msg = await loop.run_in_executor(None, self.check_network)
        if net_msg and progress:
            await progress(net_msg)

        results: List[TaskResult] = []
        done_ids = set()

        async def process_one(aid: str):
            async with semaphore:
                try:
                    if progress:
                        await progress(f"📥 正在下载 [{aid}]...")
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

                        if progress:
                            await progress(f"🔄 正在转换PDF [{title}]...")
                        pdf = await asyncio.wait_for(
                            loop.run_in_executor(None, PDFConverter.convert_zip, source, self.repo.output_dir),
                            timeout=self.convert_timeout,
                        )
                        if not pdf:
                            results.append(TaskResult(aid, title, False, error_msg="PDF转换失败"))
                            continue

                        if progress:
                            await progress(f"🔒 正在加密 [{title}]...")
                        enc = await asyncio.wait_for(
                            loop.run_in_executor(None, PDFEncryptor.encrypt, pdf, self.temp_dir),
                            timeout=120,
                        )
                        send_path = enc if (enc and enc.exists()) else pdf

                        results.append(TaskResult(
                            album_id=aid,
                            title=title,
                            success=True,
                            file_path=send_path,
                            series_ids=sids,
                        ))
                        if progress:
                            await progress(f"✅ [{title}] 处理完成，准备发送")

                except asyncio.TimeoutError:
                    logger.exception(f"[JM] 超时 {aid}")
                    results.append(TaskResult(aid, aid, False, error_msg="处理超时"))
                except Exception:
                    logger.exception(f"[JM] 处理失败 {aid}")
                    results.append(TaskResult(aid, aid, False, error_msg="处理异常"))
                finally:
                    done_ids.add(aid)

        tasks = [process_one(aid) for aid in ids]
        await asyncio.gather(*tasks)
        return results

    async def process_bitter_lovebirds(self, progress: Optional[ProgressCallback] = None) -> List[TaskResult]:
        return await self.process_download(["350234", "350235"], progress)
