# src/plugins/chatbot/services/__init__.py

from .book_service import BookService
from .permission_service import PermissionService

# === 全局单例实例 ===
# 只有在这里实例化，其他文件只导入这些实例，不要自己加括号调用
book_srv = BookService()
perm_srv = PermissionService()

__all__ = [
    "book_srv",
    "perm_srv"
]