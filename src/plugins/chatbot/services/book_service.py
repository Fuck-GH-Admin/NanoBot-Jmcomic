# src/plugins/chatbot/services/book_service.py

import os
import asyncio
import zipfile
import uuid
import shutil
from pathlib import Path
from typing import List, Optional, Dict, Any
from nonebot.log import logger
from nonebot.adapters.onebot.v11 import Bot

# 加密依赖
try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    PdfReader = None
    PdfWriter = None

from ..config import plugin_config
from ..repositories.book_repo import BookRepository
from ..utils.pdf_utils import PDFUtils
from ..utils.network_utils import NetworkUtils

# JM 依赖
try:
    import jmcomic
except ImportError:
    jmcomic = None
    logger.warning("未检测到 jmcomic 库，JM 下载功能将不可用")

class BookService:
    """
    书籍业务服务
    职责：
    1. 调度 JM 下载。
    2. 协调 PDF 转换、加密、发送流程。
    3. 处理具体的业务彩蛋（苦命鸳鸯）。
    """
    
    def __init__(self):
        self.repo = BookRepository()
        # 临时下载缓存目录 (JM配置用)
        self.temp_dir = Path(plugin_config.jm_download_dir)
        self.option_yaml_path = Path(plugin_config.jm_option_path)
        
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 网络状态跟踪
        self._network_checked = False
        self._need_proxy = False

    async def handle_jm_download(self, bot: Bot, target_id: int, message_type: str, ids: List[str]) -> str:
        """
        [入口] 普通下载指令
        :param target_id: 群号 或 用户QQ号
        :param message_type: "group" 或 "private"
        :param ids: 本子ID列表
        """
        if not self._check_env():
            return "❌ 环境配置不完整 (缺少库或 option.yml)"

        if not ids:
            return "❌ 请提供 ID"

        # 去重
        ids = list(dict.fromkeys(ids))
        
        logger.info(f"[JM] 开始下载任务: {len(ids)}个本子")
        
        # 先检查一次网络
        self._check_and_update_network()
        
        # 发送处理中消息
        msg_text = f"⏳ 开始处理 {len(ids)} 个本子...\n🔒 加密密码：114514"
        if message_type == "group":
            await bot.send_group_msg(group_id=target_id, message=msg_text)
        else:
            await bot.send_private_msg(user_id=target_id, message=msg_text)
        
        # 流式处理：边下边转换边发
        loop = asyncio.get_running_loop()
        success_count = 0
        failed_ids = []
        series_ids_all = []
        
        async def process_and_send_single(album_id):
            """下载单个本子，转换，发送"""
            nonlocal success_count, failed_ids, series_ids_all
            
            try:
                # 1. 下载（在线程池中执行）
                items = await loop.run_in_executor(None, self._sync_download_single, album_id)
                if not items:
                    failed_ids.append(album_id)
                    return
                
                for item in items:
                    source_path = item['path']
                    title = item.get('title', source_path.stem)
                    series_ids = item.get('series_ids', [])
                    
                    # 收集系列本ID
                    if series_ids:
                        series_ids_all.extend(series_ids)
                    
                    # 2. 转换为PDF
                    target_pdf = source_path
                    if source_path.suffix.lower() != '.pdf':
                        expected_pdf_path = self.repo.get_pdf_output_path(source_path)
                        if expected_pdf_path.exists():
                            target_pdf = expected_pdf_path
                        else:
                            result_str = await loop.run_in_executor(
                                None, PDFUtils.convert_zip_to_pdf,
                                str(source_path), str(self.repo.output_dir)
                            )
                            if result_str and Path(result_str).exists():
                                target_pdf = Path(result_str)
                    
                    # 3. 加密
                    ready_to_send = target_pdf
                    is_temp = False
                    if ready_to_send.suffix.lower() == '.pdf':
                        temp_path = self.temp_dir / f"enc_{uuid.uuid4().hex[:8]}_{target_pdf.name}"
                        enc_path = await loop.run_in_executor(
                            None, self._encrypt_pdf_task, target_pdf, temp_path, "114514"
                        )
                        if enc_path and enc_path.exists():
                            ready_to_send = enc_path
                            is_temp = True
                    
                    # 4. 发送
                    safe_title = "".join(c for c in title if c not in '<>:"/\\|?*') or album_id
                    send_name = f"{safe_title}.pdf"
                    
                    if ready_to_send.exists():
                        file_size = ready_to_send.stat().st_size
                        timeout = 30 + (file_size / (50 * 1024))
                        
                        try:
                            if message_type == "group":
                                await bot.call_api("upload_group_file", group_id=target_id,
                                    file=str(ready_to_send.absolute()), name=send_name, timeout=timeout)
                            else:
                                await bot.call_api("upload_private_file", user_id=target_id,
                                    file=str(ready_to_send.absolute()), name=send_name, timeout=timeout)
                            success_count += 1
                            logger.info(f"[JM] ✅ 发送成功: {send_name}")
                        except Exception as e:
                            logger.error(f"[JM] ❌ 发送失败 {album_id}: {e}")
                            failed_ids.append(album_id)
                        
                        # 清理临时文件
                        if is_temp:
                            await asyncio.sleep(1)
                            try:
                                ready_to_send.unlink()
                            except:
                                pass
                    else:
                        failed_ids.append(album_id)
                        
            except Exception as e:
                logger.error(f"[JM] 处理失败 {album_id}: {e}")
                failed_ids.append(album_id)
        
        # 并行处理所有本子（限制并发数避免过多）
        semaphore = asyncio.Semaphore(5)  # 最多5个并发
        
        async def limited_process(album_id):
            async with semaphore:
                await process_and_send_single(album_id)
        
        tasks = [limited_process(aid) for aid in ids]
        await asyncio.gather(*tasks)
        
        # 发送系列本信息
        if series_ids_all:
            unique_ids = sorted(set(series_ids_all))
            series_msg = f"📚 系列本关联章节ID：\n{', '.join(unique_ids)}"
            try:
                if message_type == "group":
                    await bot.send_group_msg(group_id=target_id, message=series_msg)
                else:
                    await bot.send_private_msg(user_id=target_id, message=series_msg)
            except:
                pass
        
        # 汇总
        msg = f"✅ 任务完成：成功 {success_count}/{len(ids)} 本"
        if failed_ids:
            msg += f"\n❌ 失败：{', '.join(failed_ids[:10])}"
            if len(failed_ids) > 10:
                msg += f" 等{len(failed_ids)}个"
        return msg

    async def handle_bitter_lovebirds(self, bot: Bot, group_id: int) -> str:
        """
        [入口] 苦命鸳鸯彩蛋 (350234, 350235)
        逻辑：
        1. 检查本地是否有这两个 ID 的书。
        2. 缺少的 ID 进行下载。
        3. 汇总列表统一发送。
        """
        if not self._check_env():
            return "❌ 环境不支持，无法触发彩蛋。"

        target_ids = ['350234', '350235']
        logger.info(f"[JM] 触发苦命鸳鸯彩蛋")

        # 直接调用下载功能
        await self.handle_jm_download(bot, group_id, "group", target_ids)

        # 专属结束语
        return "…这何尝不是一种苦命鸳鸯"

    def _encrypt_pdf_task(self, input_path: Path, output_path: Path, password: str) -> Optional[Path]:
        """同步任务：注入随机UUID元数据并加密"""
        if not PdfWriter:
            return None
        try:
            reader = PdfReader(str(input_path))
            writer = PdfWriter()
            
            # 1. 复制页面
            for page in reader.pages:
                writer.add_page(page)
            
            # 2. 注入随机 UUID 到 Metadata
            random_uid = str(uuid.uuid4())
            metadata = reader.metadata
            new_metadata = {k: v for k, v in metadata.items()} if metadata else {}
            new_metadata['/Custom-UUID'] = random_uid 
            new_metadata['/Producer'] = f"JM-Bot-{random_uid[:8]}"
            
            writer.add_metadata(new_metadata)
            
            # 3. 加密
            writer.encrypt(password)
            
            # 4. 输出
            with open(output_path, "wb") as f:
                writer.write(f)
                
            return output_path
        except Exception as e:
            logger.error(f"加密/混淆失败: {e}")
            return None

    def _sync_download_single(self, album_id: str) -> List[Dict[str, Any]]:
        """下载单个本子"""
        results = []
        try:
            option = jmcomic.JmOption.from_file(str(self.option_yaml_path))
            option.dir_rule.base_dir = str(self.temp_dir)
            downloader = jmcomic.JmDownloader(option)

            # 获取本子详情（用于标题和系列本检测）
            album = None
            try:
                album = downloader.client.get_album_detail(album_id)
                title = album.title
            except:
                title = f"JM_{album_id}"
            
            # 检测系列本
            series_ids = []
            if album and len(album.episode_list) > 1:
                # 是系列本，提取所有章节的photo_id
                for ep in album.episode_list:
                    photo_id = ep[0]  # (photo_id, photo_index, photo_title)
                    if photo_id != album_id:
                        series_ids.append(photo_id)
                logger.info(f"[JM] 检测到系列本，共{len(album.episode_list)}章，关联ID: {series_ids}")

            # 0. 先检查最终目录 (Repo) 是否已有该 ID 的 ZIP
            existing_book = self.repo.find_book_by_id_or_name(str(album_id))
            if existing_book:
                logger.info(f"[JM] 本地已存在，跳过下载: {existing_book.name}")
                results.append({
                    'id': str(album_id),
                    'title': title,
                    'path': existing_book,
                    'series_ids': series_ids
                })
                return results
            
            # 1. 检查下载缓存
            chapter_dirs = self._find_chapter_dirs(album_id)
            if not chapter_dirs:
                logger.info(f"[JM] 下载中: {album_id}")
                downloader.download_album(album_id)
                chapter_dirs = self._find_chapter_dirs(album_id)

            if not chapter_dirs:
                logger.warning(f"[JM] 未找到下载内容: {album_id}")
                return results

            # 2. 打包 ZIP
            for c_dir in chapter_dirs:
                c_name = os.path.basename(c_dir)
                zip_path = self.repo.books_dir / f"{c_name}.zip"
                
                if not zip_path.exists():
                    self._zip_folder(c_dir, zip_path)
                    
                    if zip_path.exists():
                        try:
                            shutil.rmtree(c_dir)
                            logger.info(f"[JM] ZIP打包完成，已清理源文件: {c_name}")
                        except Exception as e:
                            logger.warning(f"[JM] 清理源文件失败 {c_name}: {e}")
                
                if zip_path.exists():
                    results.append({
                        'id': str(album_id),
                        'title': title,
                        'path': zip_path,
                        'series_ids': series_ids
                    })

        except Exception as e:
            logger.error(f"[JM] Item Error {album_id}: {e}")
        
        return results

    def _find_chapter_dirs(self, aid: str) -> List[str]:
        """辅助：查找临时目录下的章节文件夹"""
        found = []
        if self.temp_dir.exists():
            for d in os.listdir(self.temp_dir):
                full = self.temp_dir / d
                if str(aid) in d and full.is_dir():
                    found.append(str(full))
        return found

    def _zip_folder(self, folder_path: str, output_path: Path):
        """辅助：打包文件夹"""
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        p = os.path.join(root, file)
                        arcname = os.path.relpath(p, os.path.dirname(folder_path))
                        zf.write(p, arcname)
        except Exception as e:
            logger.error(f"ZIP Error: {e}")

    def _check_env(self) -> bool:
        return (jmcomic is not None) and self.option_yaml_path.exists()
    
    def _check_and_update_network(self):
        """
        检查网络连通性并更新代理配置
        如果裸连可用，则禁用代理；否则启用代理
        """
        if self._network_checked:
            return
        
        logger.info("[JM] 检查网络连通性...")
        
        # 1. 测试裸连
        if NetworkUtils.test_connectivity(timeout=3):
            logger.info("[JM] 裸连可用，禁用代理")
            self._need_proxy = False
            NetworkUtils.update_option_proxy(str(self.option_yaml_path), enable_proxy=False)
        else:
            # 2. 裸连不可用，测试代理
            logger.info("[JM] 裸连不可用，测试代理...")
            if NetworkUtils.test_proxy_connectivity("127.0.0.1:7890", timeout=3):
                logger.info("[JM] 代理可用，启用代理")
                self._need_proxy = True
                NetworkUtils.update_option_proxy(str(self.option_yaml_path), enable_proxy=True)
            else:
                logger.warning("[JM] 裸连和代理都不可用，保持当前配置")
                self._need_proxy = False
        
        self._network_checked = True