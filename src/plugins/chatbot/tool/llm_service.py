# src/plugins/chatbot/services/llm_service.py

import json
import re
import asyncio
import httpx
from typing import List, Dict, Any, Optional, Tuple
from nonebot.log import logger

from ..config import plugin_config
from ..consts import DRAWING_ENHANCE_PROMPT
from ..repositories.memory_repo import MemoryRepository
from ..tools.registry import ToolRegistry
from ..tools.image_tool import GenerateImageTool, SearchAcgImageTool
from ..tools.admin_tool import BanUserTool


class LLMService:
    """
    大模型服务（重构版）
    - 通过 ToolRegistry 管理所有工具
    - 与 Node.js 微服务交互完成 ReAct 循环
    - 不再包含任何具体的业务逻辑
    """

    def __init__(self):
        self.repo = MemoryRepository()
        # DeepSeek API（用于 enhance 等兼容功能）
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {plugin_config.deepseek_api_key}"
        }
        self.node_chat_url = getattr(plugin_config, 'node_chat_url', "http://127.0.0.1:3000/api/chat")

        # 初始化工具注册表并注册所有内置工具
        self.registry = ToolRegistry()
        self._register_builtin_tools()

    def _register_builtin_tools(self):
        """注册所有内置工具，可在此添加新工具"""
        self.registry.register(GenerateImageTool())
        self.registry.register(SearchAcgImageTool())
        self.registry.register(BanUserTool())

    def _get_available_schemas(self, context: Dict[str, Any]) -> List[Dict]:
        """根据 context 获取当前可用的所有工具 schema"""
        perm_srv = context.get("permission_service")
        user_id = context.get("user_id", "")
        is_admin = context.get("is_admin", False)
        return self.registry.get_all_schemas(perm_srv, user_id, is_admin)

    async def _execute_tool_call(self, name: str, arguments: Dict, context: Dict) -> Tuple[str, List[str]]:
        """执行单个工具调用（直接委托给注册表）"""
        return await self.registry.execute_tool(name, arguments, context)

    async def chat(self, user_id: str, text: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        主对话入口（ReAct 循环）
        返回: {"text": "最终回复", "images": ["/path/to/img1", ...]}
        """
        # 1. 加载本地历史（仅用于上下文，记忆管理由 Node 负责）
        mem = await self.repo.load_memory(user_id)
        chat_history = mem.get("history", [])
        existing_summary = mem.get("profile", {})

        # 2. 获取当前允许的工具列表
        available_tools = self._get_available_schemas(context)

        # 3. 构建初始消息
        messages = []
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": text})

        # 4. ReAct 循环 (最多 5 轮工具调用)
        max_turns = 5
        all_images = []
        final_reply = ""

        for _ in range(max_turns):
            payload = {
                "chatHistory": messages,
                "existingSummary": existing_summary,
                "tools": available_tools,
                "user_id": user_id
            }

            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(self.node_chat_url, json=payload)
                if resp.status_code != 200:
                    logger.error(f"[LLM] Node API error {resp.status_code}: {resp.text}")
                    return {"text": "大脑短路了，等一下再试吧...", "images": []}
                node_result = resp.json()
            except Exception as e:
                logger.error(f"[LLM] Node request failed: {e}")
                return {"text": "连接至思考中心失败，请稍后重试。", "images": []}

            choices = node_result.get("choices", [])
            if not choices:
                return {"text": "我没想好怎么回答...", "images": []}

            msg = choices[0].get("message", {})
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])

            if not tool_calls:
                final_reply = content
                messages.append({"role": "assistant", "content": content})
                break

            # 处理工具调用
            messages.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
            for tc in tool_calls:
                tool_id = tc.get("id", "")
                func_name = tc.get("function", {}).get("name", "")
                arguments_str = tc.get("function", {}).get("arguments", "{}")
                try:
                    arguments = json.loads(arguments_str) if isinstance(arguments_str, str) else arguments_str
                except json.JSONDecodeError:
                    arguments = {}

                # 权限二次验证由注册表内部完成，这里不需要额外判断
                tool_content, imgs = await self._execute_tool_call(func_name, arguments, context)
                all_images.extend(imgs)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "name": func_name,
                    "content": tool_content
                })

        if not final_reply:
            last_assistant = next((m for m in reversed(messages) if m.get("role") == "assistant"), None)
            final_reply = last_assistant.get("content", "") if last_assistant else "任务完成。"

        return {"text": final_reply, "images": all_images}

    # ---- 向后兼容的简单文本对话 ----
    async def simple_chat(self, user_id: str, text: str) -> str:
        """不涉及工具的纯文本对话，如 AI 审计"""
        context = {
            "user_id": user_id,
            "is_admin": False,
            "allow_r18": False,
            "group_id": 0,
            "bot": None,
            "permission_service": None,
            "drawing_service": None,
            "image_service": None
        }
        result = await self.chat(user_id, text, context)
        return result["text"]

    # ---- 保留的绘图提示词优化 ----
    async def enhance_drawing_prompt(self, simple_prompt: str) -> str:
        """使用 DeepSeek 优化绘图提示词"""
        messages = [
            {"role": "system", "content": DRAWING_ENHANCE_PROMPT},
            {"role": "user", "content": simple_prompt}
        ]
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    plugin_config.deepseek_api_url,
                    json={
                        "model": plugin_config.deepseek_model_name,
                        "messages": messages,
                        "stream": False,
                        "temperature": 1.3
                    },
                    headers=self.headers
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"].strip()
                else:
                    logger.error(f"DeepSeek enhance error {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.error(f"DeepSeek enhance failed: {e}")
        return simple_prompt

    # 保留原 _call_api 方法（若其他地方引用）
    async def _call_api(self, messages: List[Dict], timeout: float = 30.0, model: str = None) -> str:
        use_model = model if model else plugin_config.deepseek_model_name
        data = {
            "model": use_model,
            "messages": messages,
            "stream": False,
            "temperature": 1.3
        }
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                resp = await client.post(plugin_config.deepseek_api_url, json=data, headers=self.headers)
                if resp.status_code != 200:
                    logger.error(f"[LLM] API Error {resp.status_code}: {resp.text}")
                    return ""
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"[LLM] API Call Failed: {e}")
            return ""