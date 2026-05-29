import os
import re
import time
import requests
import subprocess
import m3u8
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)

class M3U8Downloader:
    """m3u8 视频下载器，支持嵌套解析和多备用地址"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extract_m3u8_url(self, video_page_url: str, fallback_urls: List[str] = None) -> Optional[str]:
        """从视频页面提取 m3u8 URL，支持多备用地址"""
        all_urls = [video_page_url] + (fallback_urls or [])
        
        for url in all_urls:
            m3u8_url = self._extract_single_page(url)
            if m3u8_url:
                logger.info(f"Found m3u8 URL: {m3u8_url}")
                return m3u8_url
        
        logger.warning("No m3u8 URL found")
        return None
    
    def _extract_single_page(self, url: str) -> Optional[str]:
        """从单个页面提取 m3u8 URL"""
        try:
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            html = resp.text
            
            patterns = [
                r'(?:source|src|url|video)[\s:]*["\'](https?://[^"\']+\.m3u8[^"\']*)["\']',
                r'(https?://[^\s"\']+\.m3u8[^\s"\']*)',
                r'url\s*:\s*"([^"]+\.m3u8[^"]*)"',
                r'src:\s*"([^"]+\.m3u8[^"]*)"'
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    return matches[0]
            
            # 查找 video 或 source 标签
            video_match = re.search(r'<video[^>]+src=["\']([^"\']+\.m3u8[^"\']*)["\']', html, re.IGNORECASE)
            if video_match:
                return video_match.group(1)
            
            return None
        except Exception as e:
            logger.error(f"Extract failed for {url}: {e}")
            return None
    
    def resolve_nested_m3u8(self, m3u8_url: str, max_depth: int = 5) -> Optional[str]:
        """递归解析嵌套 m3u8，返回最终包含 ts 片段的 m3u8"""
        current_url = m3u8_url
        visited = set()
        
        for _ in range(max_depth):
            if current_url in visited:
                break
            visited.add(current_url)
            
            try:
                resp = self.session.get(current_url, timeout=30)
                resp.raise_for_status()
                content = resp.text
                
                playlist = m3u8.loads(content, uri=current_url)
                
                if playlist.segments and len(playlist.segments) > 0:
                    logger.info(f"Resolved to final m3u8: {current_url}")
                    return current_url
                
                if playlist.playlists:
                    # 通常取码率最高的
                    best = max(playlist.playlists, key=lambda p: p.stream_info.bandwidth if p.stream_info.bandwidth else 0)
                    current_url = best.uri
                    if not current_url.startswith('http'):
                        base = current_url.rsplit('/', 1)[0] if '/' in current_url else ''
                        current_url = base + '/' + current_url
                    logger.info(f"Following nested playlist: {current_url}")
                    continue
                
                return current_url
            except Exception as e:
                logger.error(f"Failed to resolve nested m3u8: {e}")
                break
        
        return m3u8_url
    
    def download(self, m3u8_url: str, output_filename: str) -> bool:
        """下载视频，先尝试 ffmpeg，失败则分段下载"""
        output_dir = self.config.get('download.output_dir', '/downloads')
        os.makedirs(output_dir, exist_ok=True)
        safe_name = re.sub(r'[<>:"/\\|?*]', '_', output_filename)
        output_path = os.path.join(output_dir, f"{safe_name}.mp4")
        
        if self._download_with_ffmpeg(m3u8_url, output_path):
            return True
        
        return self._download_with_segments(m3u8_url, output_path)
    
    def _download_with_ffmpeg(self, m3u8_url: str, output_path: str) -> bool:
        try:
            cmd = ['ffmpeg', '-i', m3u8_url, '-c', 'copy', '-bsf:a', 'aac_adtstoasc', '-y', output_path]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            if result.returncode == 0:
                logger.info(f"Downloaded with ffmpeg: {output_path}")
                return True
            logger.error(f"ffmpeg failed: {result.stderr[:200]}")
            return False
        except Exception as e:
            logger.error(f"ffmpeg error: {e}")
            return False
    
    def _download_with_segments(self, m3u8_url: str, output_path: str) -> bool:
        temp_dir = self.config.get('download.temp_dir', '/tmp/video_download')
        os.makedirs(temp_dir, exist_ok=True)
        
        try:
            resp = self.session.get(m3u8_url, timeout=30)
            playlist = m3u8.loads(resp.text, uri=m3u8_url)
            
            if not playlist.segments:
                logger.error("No segments found")
                return False
            
            segments = []
            base_url = m3u8_url.rsplit('/', 1)[0] + '/'
            
            for i, seg in enumerate(playlist.segments):
                ts_url = seg.uri
                if not ts_url.startswith('http'):
                    ts_url = base_url + (ts_url.lstrip('/') if ts_url.startswith('/') else ts_url)
                
                ts_path = os.path.join(temp_dir, f"seg_{i:05d}.ts")
                if self._download_segment(ts_url, ts_path):
                    segments.append(ts_path)
                else:
                    logger.warning(f"Failed to download segment {i}")
            
            if not segments:
                return False
            
            with open(output_path, 'wb') as out:
                for ts_path in segments:
                    with open(ts_path, 'rb') as ts_file:
                        out.write(ts_file.read())
                    os.remove(ts_path)
            
            os.rmdir(temp_dir)
            logger.info(f"Downloaded with segments: {output_path}")
            return True
        except Exception as e:
            logger.error(f"Segment download failed: {e}")
            return False
    
    def _download_segment(self, url: str, path: str, max_retries: int = 3) -> bool:
        for attempt in range(max_retries):
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                with open(path, 'wb') as f:
                    f.write(resp.content)
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
        return False
