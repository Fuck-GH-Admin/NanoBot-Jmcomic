from typing import Set, Optional
from pydantic import Extra
from nonebot import get_plugin_config
from pydantic_settings import BaseSettings

class Config(BaseSettings):
    """全局配置模型"""
    # DeepSeek API
    """
    deepseek_api_key: str = "9260605f-ae53-42fc-b864-06765f313485" # 默认值或从env读取
    deepseek_api_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    deepseek_model_name: str = "deepseek-v3-2-251201"

    """
    deepseek_api_key: str = "sk-d66274af8f7941ab80e90c8868a2a375" # 默认值或从env读取
    deepseek_api_url: str = "https://api.deepseek.com/chat/completions"
    deepseek_model_name: str = "deepseek-v4-flash"

    # SiliconFlow (画图) API
    siliconflow_api_key: str = "sk-wpxxpcdkonqzfvzsbxejvejlsgwhbfefylvipwtmwtzztiqm"
    siliconflow_api_url: str = "https://api.siliconflow.cn/v1"
    siliconflow_model_name: str = "Kwai-Kolors/Kolors"
    #火山9260605f-ae53-42fc-b864-06765f313485
    #火山doubao-seedream-4-5-251128
    #火山deepseek-v3-2-251201
    #火山https://ark.cn-beijing.volces.com/api/v3
    # AI 逻辑开关
    enable_ai_command_fixer: bool = True
    ai_command_timeout: float = 9.0

    # 路径配置
    image_folder: str = r"D:\小项目\pixiv下载图片\pixiv下载图片\最终版\pixiv_downloads"
    books_folder: str = r"D:\文件\学习资料\本"  # 最终Zip存放位置 (对应原 SAVE_DIR)
    excel_path: str = r"D:\小项目\pixiv下载图片\pixiv下载图片\最终版\pixiv_downloads\pixiv_artworks_fix.xlsx"
    
    # JM Config
    jm_download_dir: str = r"data/jm_temp" # 临时下载原图的目录 (对应原 DATA_DIR)
    jm_option_path: str = r"data/option.yml" # JM配置文件路径

    font_path: str = r"C:\Windows\Fonts\msyh.ttc" # 防止PIL报错，可根据环境调整

    # 阈值
    short_message_max_len: int = 2

    # 权限配置 (Set优化查找)
    # 填入你的 QQ 号，支持多个
    superusers: Set[str] = {"2797364016", "123456789"}
    private_whitelist: Set[str] = {"2797364016", "2676329144", "2810778350", "2192695806"}
    ai_admin_qq: Set[str] = {"2797364016", "1145141919810"}
    drawing_whitelist: Set[str] = {"2797364016", "104283107", "1562104125", "3085044807"}
    
    # 欢迎/群管理
    welcome_groups: Set[str] = {"939328978", "1018340499"}
    welcome_mode: str = "all"  # hello, bye, all

    class Config:
        extra = Extra.ignore
        env_prefix = "CHATBOT_"
        env_file = ".env"

plugin_config = get_plugin_config(Config)