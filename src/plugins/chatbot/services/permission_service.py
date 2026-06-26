# src/plugins/chatbot/services/permission_service.py

from typing import Set
from nonebot import get_driver
from ..config import plugin_config

class PermissionService:
    """
    权限服务
    提供私聊白名单和群聊白名单检查
    """
    
    def __init__(self):
        driver = get_driver()
        self.superusers: Set[str] = driver.config.superusers
        self.private_whitelist: Set[str] = plugin_config.private_whitelist
        self.group_whitelist: Set[str] = plugin_config.group_whitelist

    def is_superuser(self, user_id: str) -> bool:
        return user_id in self.superusers

    def is_private_whitelisted(self, user_id: str) -> bool:
        if self.is_superuser(user_id):
            return True
        return user_id in self.private_whitelist

    def is_group_whitelisted(self, group_id: str) -> bool:
        if not self.group_whitelist:
            return True
        return group_id in self.group_whitelist