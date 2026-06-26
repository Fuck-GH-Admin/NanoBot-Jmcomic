# src/plugins/chatbot/__init__.py
import shutil
from pathlib import Path
from nonebot import get_driver
from nonebot.log import logger
from nonebot.plugin import PluginMetadata

# 引入配置（可选，确保配置被加载）
from .config import Config

# 【关键】从 matchers 包中导入所有事件响应器
# 这样 NoneBot 才能在加载插件时注册这些事件
from .matchers import (
    group_chat,
    private_chat,
)

__plugin_meta__ = PluginMetadata(
    name="Chatbot B",
    description="重构后的聊天机器人插件",
    usage="直接 @Bot 聊天，或发送指令",
    config=Config,
)

from .config import plugin_config, Config

# 获取驱动实例
driver = get_driver()

@driver.on_startup
async def clear_temp_directory():
    """
    Bot 启动时自动清空临时下载目录
    """
    temp_dir = Path(plugin_config.jm_download_dir)
    
    if temp_dir.exists():
        try:
            # 暴力删除整个目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"[Lifecycle] 已清理临时目录: {temp_dir}")
        except Exception:
            logger.exception("[Lifecycle] 清理临时目录失败")
            
    # 重新创建空目录，确保后续下载任务能找到路径
    temp_dir.mkdir(parents=True, exist_ok=True)