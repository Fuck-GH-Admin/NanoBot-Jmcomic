import os
import re
import shutil
import zipfile
from pathlib import Path
from typing import List, Dict, Any, Optional
from nonebot.log import logger

from ..config import plugin_config


class JmOptionCache:
    _instance = None
    _option = None
    _mtime = 0

    @classmethod
    def get_option(cls, option_path: Path):
        import jmcomic
        current_mtime = option_path.stat().st_mtime if option_path.exists() else 0
        if cls._option is None or current_mtime != cls._mtime:
            cls._option = jmcomic.JmOption.from_file(str(option_path))
            cls._mtime = current_mtime
            logger.info(f"[JmCache] 已加载 option.yml (mtime={current_mtime})")
        return cls._option

    @classmethod
    def invalidate(cls):
        cls._option = None
        cls._mtime = 0


class JmDownloader:
    def __init__(self, temp_dir: Path, option_path: Path, books_dir: Path):
        self.temp_dir = temp_dir
        self.option_path = option_path
        self.books_dir = books_dir

    def _find_local_zip(self, album_id: str) -> Optional[Path]:
        if not self.books_dir.exists():
            return None
        escaped = re.escape(album_id)
        pattern = re.compile(rf'^{escaped}(_|$)')
        for f in self.books_dir.iterdir():
            if f.suffix == '.zip' and pattern.match(f.stem):
                return f
        return None

    def download_album(self, album_id: str) -> List[Dict[str, Any]]:
        import jmcomic
        results = []
        try:
            existing = self._find_local_zip(album_id)
            if existing:
                logger.info(f"[JmDL] 本地已有 {existing.name}，跳过下载")
                return [{'id': album_id, 'title': existing.stem, 'path': existing, 'series_ids': []}]

            option = JmOptionCache.get_option(self.option_path)
            option.dir_rule.base_dir = str(self.temp_dir)
            downloader = jmcomic.JmDownloader(option)

            album = None
            try:
                album = downloader.client.get_album_detail(album_id)
                title = album.title
            except Exception:
                logger.exception(f"[JmDL] 获取本子详情失败 {album_id}")
                title = f"JM_{album_id}"

            series_ids = []
            if album and len(album.episode_list) > 1:
                for ep in album.episode_list:
                    photo_id = ep[0]
                    if photo_id != album_id:
                        series_ids.append(photo_id)
                logger.info(f"[JmDL] 系列本 {album_id}，关联ID: {series_ids}")

            chapter_dirs = self._find_chapter_dirs(album_id)
            if not chapter_dirs:
                logger.info(f"[JmDL] 下载中: {album_id}")
                downloader.download_album(album_id)
                chapter_dirs = self._find_chapter_dirs(album_id)

            if not chapter_dirs:
                logger.warning(f"[JmDL] 未找到下载内容: {album_id}")
                return results

            for c_dir in chapter_dirs:
                c_name = os.path.basename(c_dir)
                zip_path = self.books_dir / f"{c_name}.zip"

                if not zip_path.exists():
                    self._zip_folder(c_dir, zip_path)
                    if zip_path.exists():
                        try:
                            shutil.rmtree(c_dir)
                        except Exception:
                            logger.exception(f"[JmDL] 清理源文件失败 {c_name}")

                if zip_path.exists():
                    results.append({
                        'id': album_id,
                        'title': title,
                        'path': zip_path,
                        'series_ids': series_ids
                    })

        except Exception:
            logger.exception(f"[JmDL] 下载失败 {album_id}")

        return results

    def _find_chapter_dirs(self, aid: str) -> List[str]:
        found = []
        if self.temp_dir.exists():
            for d in os.listdir(self.temp_dir):
                full = self.temp_dir / d
                if full.is_dir() and (d == aid or d.startswith(aid + '_')):
                    found.append(str(full))
        return found

    @staticmethod
    def _zip_folder(folder_path: str, output_path: Path):
        try:
            with zipfile.ZipFile(output_path, 'w', zipfile.ZIP_DEFLATED) as zf:
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        p = os.path.join(root, file)
                        arcname = os.path.relpath(p, os.path.dirname(folder_path))
                        zf.write(p, arcname)
        except Exception:
            logger.exception("ZIP打包失败")
