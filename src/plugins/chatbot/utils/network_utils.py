import requests
import yaml
from pathlib import Path
from typing import Optional
from nonebot.log import logger

class NetworkUtils:
    """
    网络工具类
    提供网络连通性检测和代理切换功能
    """
    
    # 测试URL（使用常见的可达站点，不暴露敏感域名）
    TEST_URLS = [
        "https://www.baidu.com",
        "https://www.google.com",
        "https://www.cloudflare.com",
    ]
    
    @staticmethod
    def test_connectivity(timeout: int = 5) -> bool:
        """
        测试网络连通性（裸连）
        返回True表示裸连可用，False表示需要代理
        """
        for url in NetworkUtils.TEST_URLS:
            try:
                response = requests.get(url, timeout=timeout, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                if response.status_code == 200:
                    logger.info(f"[Network] 裸连测试成功: {url}")
                    return True
            except Exception as e:
                logger.debug(f"[Network] 裸连测试失败: {url}")
                continue
        
        logger.warning("[Network] 所有裸连测试失败，需要代理")
        return False
    
    @staticmethod
    def test_proxy_connectivity(proxy: str, timeout: int = 5) -> bool:
        """
        测试代理连通性
        返回True表示代理可用，False表示代理不可用
        """
        proxies = {
            "http": proxy,
            "https": proxy
        }
        
        for url in NetworkUtils.TEST_URLS:
            try:
                response = requests.get(url, timeout=timeout, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }, proxies=proxies)
                if response.status_code == 200:
                    logger.info(f"[Network] 代理测试成功: {proxy}")
                    return True
            except Exception as e:
                # 不打印详细错误，只记录URL
                logger.debug(f"[Network] 代理测试失败: {url}")
                continue
        
        logger.warning(f"[Network] 代理测试失败: {proxy}")
        return False
    
    @staticmethod
    def update_option_proxy(option_path: str, enable_proxy: bool, proxy: str = "http://127.0.0.1:7890") -> bool:
        """
        更新option.yml中的代理配置
        """
        try:
            option_file = Path(option_path)
            if not option_file.exists():
                logger.error(f"[Network] option.yml不存在: {option_path}")
                return False
            
            with open(option_file, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
            
            # 确保路径存在
            if 'client' not in config:
                config['client'] = {}
            if 'postman' not in config['client']:
                config['client']['postman'] = {}
            if 'meta_data' not in config['client']['postman']:
                config['client']['postman']['meta_data'] = {}
            
            # 更新代理配置
            if enable_proxy:
                config['client']['postman']['meta_data']['proxies'] = {
                    'http': proxy,
                    'https': proxy
                }
                logger.info(f"[Network] 已启用代理: {proxy}")
            else:
                # 移除代理配置
                if 'proxies' in config['client']['postman']['meta_data']:
                    del config['client']['postman']['meta_data']['proxies']
                logger.info("[Network] 已禁用代理")
            
            with open(option_file, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            
            return True
            
        except Exception as e:
            logger.error(f"[Network] 更新option.yml失败: {e}")
            return False