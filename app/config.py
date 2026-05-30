import os
import yaml
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class Config:
    """配置管理类，支持本地文件和远程 HTTP 配置源，以及环境变量覆盖"""
    
    DEFAULT_CONFIG = {
        'monitor': {
            'urls': [],               # 支持字符串或对象
            'interval_hours': 4,
            'history_dir': '/data/history',
            'auto_detect': True
        },
        'video_selectors': [         # 全局默认选择器（自动检测模式忽略）
            {'tag': 'li', 'id_pattern': r'^\d{2}$'},
            {'tag': 'li', 'class_contains': 'episode'},
            {'tag': 'a', 'class_contains': 'play-btn'}
        ],
        'video_urls': [],            # 多播放地址配置
        'download': {
            'output_dir': '/downloads',
            'temp_dir': '/tmp/video_download',
            'max_retries': 3,
            'retry_delay': 5
        },
        'email': {
            'enabled': True,
            'smtp_server': 'smtp.qq.com',
            'smtp_port': 587,
            'sender': '',
            'password': '',
            'receiver': '1072088954@qq.com'
        },
        'selenium': {
            'headless': True,
            'timeout': 30
        }
    }
    
    def __init__(self, config_source: Optional[str] = None):
        self.config_source = config_source
        self.config = self.DEFAULT_CONFIG.copy()
        if config_source:
            self.load(config_source)
        self._apply_env_overrides()
    
    def load(self, source: str):
        """加载配置文件，支持本地路径或 HTTP URL"""
        if source.startswith(('http://', 'https://')):
            self._load_from_remote(source)
        else:
            self._load_from_file(source)
    
    def _load_from_file(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                self._merge_config(user_config)
            logger.info(f"Loaded config from {path}")
        except Exception as e:
            logger.error(f"Failed to load config from {path}: {e}")
    
    def _load_from_remote(self, url: str):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            user_config = yaml.safe_load(resp.text)
            self._merge_config(user_config)
            logger.info(f"Loaded config from remote {url}")
        except Exception as e:
            logger.error(f"Failed to load remote config from {url}: {e}")
    
    def _merge_config(self, user_config: Dict):
        """递归合并配置"""
        def deep_merge(base, update):
            for k, v in update.items():
                if k in base and isinstance(base[k], dict) and isinstance(v, dict):
                    deep_merge(base[k], v)
                else:
                    base[k] = v
        deep_merge(self.config, user_config)
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖（优先级最高）"""
        if os.getenv('MONITOR_URL'):
            # 若设置单个 MONITOR_URL，自动转为列表
            self.config['monitor']['urls'] = [os.getenv('MONITOR_URL')]
        if os.getenv('MONITOR_INTERVAL'):
            self.config['monitor']['interval_hours'] = int(os.getenv('MONITOR_INTERVAL'))
        if os.getenv('DOWNLOAD_DIR'):
            self.config['download']['output_dir'] = os.getenv('DOWNLOAD_DIR')
        if os.getenv('EMAIL_SENDER'):
            self.config['email']['sender'] = os.getenv('EMAIL_SENDER')
        if os.getenv('EMAIL_PASSWORD'):
            self.config['email']['password'] = os.getenv('EMAIL_PASSWORD')
        if os.getenv('EMAIL_RECEIVER'):
            self.config['email']['receiver'] = os.getenv('EMAIL_RECEIVER')
    
    def get(self, key: str, default=None):
        keys = key.split('.')
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def get_monitor_configs(self) -> list:
        """返回监控配置列表，每个元素为 {'url': str, 'selectors': list, 'auto_detect': bool}"""
        urls_config = self.get('monitor.urls')
        if not urls_config:
            # 兼容旧的单个 url 配置（已由环境变量覆盖处理）
            single_url = self.get('monitor.url')
            if single_url:
                urls_config = [single_url]
            else:
                return []
        
        result = []
        global_selectors = self.get('video_selectors', [])
        global_auto = self.get('monitor.auto_detect', True)
        
        for item in urls_config:
            if isinstance(item, str):
                result.append({
                    'url': item,
                    'selectors': global_selectors,
                    'auto_detect': global_auto
                })
            elif isinstance(item, dict):
                url = item.get('url')
                if url:
                    selectors = item.get('selectors', global_selectors)
                    auto_detect = item.get('auto_detect', global_auto)
                    result.append({
                        'url': url,
                        'selectors': selectors,
                        'auto_detect': auto_detect
                    })
        return result
