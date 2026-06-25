# src/plugins/chatbot/tools/registry.py

import json
from typing import Any, Dict, List, Tuple
from nonebot.log import logger

from .base_tool import BaseTool


class ToolRegistry:
    """
    工具注册表
    管理所有可用工具，提供基于权限的动态 schema 输出与执行路由。
    """

    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """注册一个工具"""
        if tool.name in self._tools:
            logger.warning(f"[ToolRegistry] 工具 '{tool.name}' 已存在，将被覆盖。")
        self._tools[tool.name] = tool
        logger.info(f"[ToolRegistry] 注册工具: {tool.name} (权限: {tool.require_permission})")

    def unregister(self, name: str) -> None:
        """移除一个工具"""
        if name in self._tools:
            del self._tools[name]

    def get_all_schemas(self, permissions: Any, user_id: str, is_admin: bool = False) -> List[Dict[str, Any]]:
        """
        根据用户权限返回所有可用工具的 OpenAI Function Schema。
        :param permissions: PermissionService 实例，用于白名单等检查
        :param user_id: 当前用户 QQ 号
        :param is_admin: 是否拥有管理员权限（群主/管理员/超级用户）
        """
        schemas = []
        for tool in self._tools.values():
            allowed = False
            perm = tool.require_permission
            if perm == "user":
                allowed = True
            elif perm == "drawing_whitelist":
                if permissions and hasattr(permissions, "is_user_whitelisted"):
                    allowed = permissions.is_user_whitelisted(user_id, "drawing")
            elif perm == "admin":
                allowed = is_admin
            # 可在此扩展更多权限类型

            if allowed:
                schema = {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.parameters,
                        "require_permission": tool.require_permission  # 仅用于调试，实际 API 可忽略
                    }
                }
                schemas.append(schema)
        return schemas

    async def execute_tool(
        self,
        name: str,
        arguments: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Tuple[str, List[str]]:
        """
        执行指定工具。
        :param name: 工具名称
        :param arguments: 大模型给出的参数
        :param context: 运行时上下文
        :return: (文本结果, 图片路径列表)
        """
        tool = self._tools.get(name)
        if not tool:
            return f"错误：未知工具 '{name}'", []

        # 权限二次校验（防御大模型幻觉调用无权限工具）
        required_perm = tool.require_permission
        if required_perm == "admin":
            if not context.get("is_admin"):
                return "权限不足：只有管理员可以执行此操作。", []
        elif required_perm == "drawing_whitelist":
            perm_srv = context.get("permission_service")
            user_id = context.get("user_id", "")
            if perm_srv and hasattr(perm_srv, "is_user_whitelisted"):
                if not perm_srv.is_user_whitelisted(user_id, "drawing"):
                    return "权限不足：你不在绘图白名单中。", []
            else:
                return "无法进行权限检查，操作拒绝。", []

        try:
            return await tool.execute(arguments, context)
        except Exception as e:
            logger.error(f"[ToolRegistry] 工具 '{name}' 执行异常: {e}")
            return f"工具执行出错：{str(e)}", []