import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotAdapter
from nonebot.log import logger

# 1. 初始化 NoneBot 实例（自动加载并解析 .env 文件）
nonebot.init()

# 2. 暴露 ASGI 应用对象（为生产环境的 Uvicorn/Hypercorn 部署做准备）
app = nonebot.get_asgi()

# 3. 注册协议适配器
driver = nonebot.get_driver()
driver.register_adapter(OneBotAdapter)

# 4. 加载插件
# 推荐使用 pyproject.toml 统一管理内置或第三方通用插件
# nonebot.load_from_toml("pyproject.toml")

# 精确加载核心业务插件，并包裹异常处理
try:
    nonebot.load_plugin("src.plugins.chatbot")
    logger.info("核心业务插件 src.plugins.chatbot 加载成功")
except Exception as e:
    logger.opt(exception=e).error("核心业务插件加载失败，请检查依赖或语法错误！")

# 5. 本地开发与测试启动入口
if __name__ == "__main__":
    logger.warning("生产环境中，强烈建议使用 `nb run` 或 ASGI 服务器启动项目。")
    nonebot.run()