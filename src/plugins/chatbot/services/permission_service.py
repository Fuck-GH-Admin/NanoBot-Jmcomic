# src/plugins/chatbot/services/permission_service.py

from typing import Set
from nonebot import get_driver
from ..config import plugin_config

class PermissionService:
    """
    权限服务（简化版）
    只保留私聊白名单检查功能
    """
    
    def __init__(self):
        # 从 NoneBot2 配置中读取超级用户
        driver = get_driver()
        self.superusers: Set[str] = driver.config.superusers
        self.private_whitelist: Set[str] = set()  # 私聊白名单

    def is_superuser(self, user_id: str) -> bool:
        """检查是否为最高权限宿主"""
        return user_id in self.superusers

    def is_private_whitelisted(self, user_id: str) -> bool:
        """检查私聊白名单"""
        # 超级用户始终在白名单中
        if self.is_superuser(user_id):
            return True
        return user_id in self.private_whitelist