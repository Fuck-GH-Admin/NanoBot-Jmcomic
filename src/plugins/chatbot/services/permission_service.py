from typing import Set
from nonebot import get_driver
from ..config import plugin_config


class PermissionService:
    def __init__(self):
        driver = get_driver()
        self.superusers: Set[str] = driver.config.superusers

    def is_superuser(self, user_id: str) -> bool:
        return user_id in self.superusers

    def is_private_whitelisted(self, user_id: str) -> bool:
        if self.is_superuser(user_id):
            return True
        return user_id in plugin_config.private_whitelist

    def is_group_whitelisted(self, group_id: str) -> bool:
        wl = plugin_config.group_whitelist
        if not wl:
            return True
        return group_id in wl
