import threading
import time
from pathlib import Path
from typing import Set, Optional, Any

import yaml
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# 配置文件路径（可自定义）
CONFIG_FILE = Path("config_bot_base.yaml")


class Config(BaseSettings):
    """配置模型定义（全部从 YAML 读取，无 env 依赖）"""
    model_config = ConfigDict(extra="ignore")

    # JM 相关配置
    jm_download_dir: str = r"data/jm_temp"
    jm_option_path: str = r"option.yml"
    books_folder: str = r"D:\文件\学习资料\本"
    font_path: str = r"C:\Windows\Fonts\msyh.ttc"

    # 权限集合（保留超级用户配置，用于权限控制）
    superusers: Set[str] = set()


class ConfigManager:
    """负责从 YAML 加载配置、热更新、提供统一的属性访问"""

    def __init__(self):
        self._config = Config()
        self._lock = threading.Lock()
        self._observer: Optional[Observer] = None
        self.load_config()
        self._start_watcher()

    def load_config(self):
        """读取 config.yaml 并更新内部 Config 对象"""
        if not CONFIG_FILE.exists():
            self._generate_default_yaml()
            return

        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        with self._lock:
            for key, value in data.items():
                if key not in Config.model_fields:
                    continue
                field_info = Config.model_fields[key]
                target_type = field_info.annotation

                # 类型转换：YAML 读取的值可能不是精确类型
                try:
                    if target_type is Set[str]:
                        if isinstance(value, list):
                            value = set(value)
                        elif isinstance(value, str):
                            value = set(s.strip() for s in value.split(",") if s.strip())
                        else:
                            value = set()
                    elif target_type is bool:
                        value = bool(value)
                    elif target_type is float:
                        value = float(value)
                    elif target_type is int:
                        value = int(value)
                    # 其他情况保持原样（字符串）
                except (ValueError, TypeError):
                    continue  # 类型转换失败则跳过该字段

                setattr(self._config, key, value)

    def _generate_default_yaml(self):
        """生成初始配置文件"""
        default = {
            "jm_download_dir": "data/jm_temp",
            "jm_option_path": "data/option.yml",
            "books_folder": r"D:\文件\学习资料\本",
            "font_path": r"C:\Windows\Fonts\msyh.ttc",
            "superusers": []
        }
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            yaml.dump(default, f, allow_unicode=True, default_flow_style=False)
        self.load_config()

    def _start_watcher(self):
        """监控配置文件变化，自动热更新"""

        class Handler(FileSystemEventHandler):
            def __init__(self, manager):
                self.manager = manager

            def on_modified(self, event):
                if event.src_path.endswith(CONFIG_FILE.name):
                    time.sleep(0.5)
                    self.manager.load_config()

        observer = Observer()
        observer.schedule(Handler(self), path=str(CONFIG_FILE.parent), recursive=False)
        observer.daemon = True
        observer.start()
        self._observer = observer

    # 代理内部 Config 的属性访问（让外部像往常一样 plugin_config.xxx 调用）
    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return getattr(self._config, name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_config", "_lock", "_observer"):
            super().__setattr__(name, value)
        else:
            setattr(self._config, name, value)


# 全局配置实例（替代原来的 plugin_config）
plugin_config = ConfigManager()