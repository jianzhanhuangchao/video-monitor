import json
import os
import time
import hashlib
import requests
from datetime import datetime
from typing import List, Dict, Optional
import logging

from app.extractor import VideoExtractor
from app.downloader import M3U8Downloader
from app.notifier import Notifier
from app.config import Config

logger = logging.getLogger(__name__)

class VideoMonitor:
    def __init__(self, config: Config):
        self.config = config
        self.config_source = config.config_source
        self.config_last_state = self._get_config_state()
        self.extractor = VideoExtractor(config.config)
        self.downloader = M3U8Downloader(config.config)
        self.notifier = Notifier(config.config.get('email', {}))
        self.history_file = config.config.get('monitor.history_file', '/data/video_history.json')
        self.video_urls = config.config.get('video_urls', [])
    
    def _get_config_state(self) -> Optional[str]:
        """获取配置文件的唯一标识"""
        source = self.config_source
        if not source:
            return None
        if source.startswith(('http://', 'https://')):
            try:
                resp = requests.head(source, timeout=5)
                etag = resp.headers.get('ETag')
                last_modified = resp.headers.get('Last-Modified')
                return f"{etag or ''}|{last_modified or ''}"
            except:
                return None
        else:
            try:
                stat = os.stat(source)
                return f"{stat.st_mtime}_{stat.st_size}"
            except:
                return None
    
    def _config_changed(self) -> bool:
        new_state = self._get_config_state()
        if new_state and new_state != self.config_last_state:
            self.config_last_state = new_state
            return True
        return False
    
    def _reload_config(self):
        logger.info("Configuration changed, reloading...")
        self.config.load(self.config_source)
        new_cfg = self.config.config
        self.extractor = VideoExtractor(new_cfg)
        self.downloader = M3U8Downloader(new_cfg)
        self.notifier = Notifier(new_cfg.get('email', {}))
        self.history_file = new_cfg.get('monitor.history_file', '/data/video_history.json')
        self.video_urls = new_cfg.get('video_urls', [])
        logger.info("Configuration reloaded")
    
    def load_history(self) -> List[Dict]:
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def save_history(self, links: List[Dict]):
        try:
            with open(self.history_file, 'w', encoding='utf-8') as f:
                json.dump(links, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Save history failed: {e}")
    
    def check_updates(self, current: List[Dict], previous: List[Dict]) -> List[Dict]:
        if not previous:
            return current
        previous_urls = {link['url'] for link in previous}
        return [link for link in current if link['url'] not in previous_urls]
    
    def run_once(self):
        monitor_url = self.config.get('monitor.url')
        if not monitor_url:
            logger.error("No monitor URL configured")
            return
        
        logger.info(f"Checking {monitor_url}")
        current_links = self.extractor.get_video_links(monitor_url)
        if not current_links:
            logger.warning("No video links found")
            return
        
        previous = self.load_history()
        new_links = self.check_updates(current_links, previous)
        
        if new_links:
            logger.info(f"Found {len(new_links)} new video(s)")
            # 只处理最新的一集（最后一个）
            latest = new_links[-1]
            self._process_video(latest)
        else:
            logger.info("No new videos found")
        
        self.save_history(current_links)
    
    def _process_video(self, video: Dict):
        logger.info(f"Processing: {video.get('title')}")
        
        # 构建备用地址
        fallbacks = []
        for v in self.video_urls:
            pattern = v.get('pattern')
            if pattern and re.search(pattern, video['url']):
                fallbacks.extend(v.get('fallbacks', []))
        
        m3u8_url = self.downloader.extract_m3u8_url(video['url'], fallbacks)
        if not m3u8_url:
            logger.error(f"No m3u8 URL found for {video['title']}")
            self.notifier.notify(video['title'], False, "No m3u8 URL found")
            return
        
        resolved_url = self.downloader.resolve_nested_m3u8(m3u8_url)
        success = self.downloader.download(resolved_url, video['title'])
        self.notifier.notify(video['title'], success)
    
    def run_loop(self):
        interval = self.config.get('monitor.interval_hours', 4) * 3600
        logger.info(f"Starting monitor loop, interval: {interval}s")
        self.run_once()  # 启动立即执行一次
        
        while True:
            try:
                time.sleep(interval)
                if self._config_changed():
                    self._reload_config()
                    self.run_once()  # 配置变化立即检查
                else:
                    self.run_once()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(300)
        
        self.extractor.close()
