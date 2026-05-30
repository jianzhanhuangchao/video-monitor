import json
import os
import time
import hashlib
import re
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
        self.downloader = M3U8Downloader(config.config)
        self.notifier = Notifier(config.config.get('email', {}))
        self.video_urls = config.config.get('video_urls', [])
    
    def _get_config_state(self) -> Optional[str]:
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
        self.downloader = M3U8Downloader(self.config.config)
        self.notifier = Notifier(self.config.config.get('email', {}))
        self.video_urls = self.config.config.get('video_urls', [])
        logger.info("Configuration reloaded")
    
    def _get_history_file(self, url: str) -> str:
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        history_dir = self.config.get('monitor.history_dir', '/data/history')
        os.makedirs(history_dir, exist_ok=True)
        return os.path.join(history_dir, f"{url_hash}.json")
    
    def load_history_for_url(self, url: str) -> List[Dict]:
        history_file = self._get_history_file(url)
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                pass
        return []
    
    def save_history_for_url(self, url: str, links: List[Dict]):
        history_file = self._get_history_file(url)
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(links, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Save history for {url} failed: {e}")
    
    def check_updates(self, current: List[Dict], previous: List[Dict]) -> List[Dict]:
        if not previous:
            return current
        previous_urls = {link['url'] for link in previous}
        return [link for link in current if link['url'] not in previous_urls]
    
    def _process_video(self, video: Dict, source_url: str):
        logger.info(f"Processing: {video.get('title')} from {source_url}")
        fallbacks = []
        for v in self.video_urls:
            pattern = v.get('pattern')
            if pattern and re.search(pattern, video['url']):
                fallbacks.extend(v.get('fallbacks', []))
        m3u8_url = self.downloader.extract_m3u8_url(video['url'], fallbacks)
        if not m3u8_url:
            logger.error(f"No m3u8 URL found for {video['title']}")
            self.notifier.notify(video['title'], False, "No m3u8 URL found", source_url)
            return
        resolved_url = self.downloader.resolve_nested_m3u8(m3u8_url)
        success = self.downloader.download(resolved_url, video['title'])
        self.notifier.notify(video['title'], success, source_url=source_url)
    
    def run_once(self):
        monitor_configs = self.config.get_monitor_configs()
        if not monitor_configs:
            logger.error("No monitor configurations found")
            return
        
        for cfg in monitor_configs:
            url = cfg['url']
            selectors = cfg['selectors']
            auto_detect = cfg.get('auto_detect', True)
            
            # 如果 auto_detect 为 True 且没有手动选择器，则传入 None 触发自动检测
            if auto_detect and not selectors:
                selectors = None
            
            extractor = VideoExtractor(self.config.config, custom_selectors=selectors)
            try:
                logger.info(f"Checking {url}")
                current_links = extractor.get_video_links(url)
                if not current_links:
                    logger.warning(f"No video links found for {url}")
                    continue
                
                previous = self.load_history_for_url(url)
                new_links = self.check_updates(current_links, previous)
                
                if new_links:
                    logger.info(f"Found {len(new_links)} new video(s) for {url}")
                    latest = new_links[-1]   # 只下载最新一集
                    self._process_video(latest, url)
                else:
                    logger.info(f"No new videos for {url}")
                
                self.save_history_for_url(url, current_links)
            finally:
                extractor.close()
    
    def run_loop(self):
        interval = self.config.get('monitor.interval_hours', 4) * 3600
        logger.info(f"Starting monitor loop, interval: {interval}s")
        self.run_once()
        while True:
            try:
                time.sleep(interval)
                if self._config_changed():
                    self._reload_config()
                    self.run_once()
                else:
                    self.run_once()
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(300)
        self._close()
    
    def _close(self):
        # 注意 extractor 没有持久保存，无需关闭全局；但下载器没有需要关闭的资源
        pass
