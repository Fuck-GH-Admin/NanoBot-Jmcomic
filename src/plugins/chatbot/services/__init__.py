from ..config import plugin_config
from .book_service import BookService
from .permission_service import PermissionService

book_srv = BookService()
perm_srv = PermissionService()
plugin_config.on_change(book_srv.refresh_paths)

__all__ = ["book_srv", "perm_srv"]