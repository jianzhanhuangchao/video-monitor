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
            'url': '',
            'interval_hours': 4,
            'history_file': '/data/video_history.json'
        },
        'video_selectors': [
            {'tag': 'li', 'id_pattern': r'^\d{2}$'},
            {'tag': 'li', 'class_contains': 'episode'},
            {'tag': 'a', 'class_contains': 'play-btn'}
        ],
        'video_urls': [],
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
            self.config['monitor']['url'] = os.getenv('MONITOR_URL')
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
