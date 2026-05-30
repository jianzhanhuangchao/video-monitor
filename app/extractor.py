import re
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)

class VideoExtractor:
    """视频链接提取器，支持静态和动态页面，自动检测链接"""
    
    def __init__(self, config: Dict, custom_selectors: List[Dict] = None):
        self.config = config
        self.selectors = custom_selectors if custom_selectors is not None else config.get('video_selectors', [])
        self.driver = None
        self._init_selenium()
    
    def _init_selenium(self):
        """初始化 Selenium WebDriver"""
        try:
            chrome_options = Options()
            if self.config.get('selenium', {}).get('headless', True):
                chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--disable-gpu")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            self.driver = webdriver.Chrome(options=chrome_options)
            logger.info("Selenium WebDriver initialized")
        except Exception as e:
            logger.warning(f"Selenium init failed: {e}, will use static parsing only")
    
    def get_video_links(self, url: str) -> List[Dict]:
        """获取视频链接，优先使用配置选择器，否则自动检测"""
        html = self._fetch_page(url)
        if not html:
            return []
        soup = BeautifulSoup(html, 'lxml')
        
        # 优先使用配置的选择器
        if self.selectors:
            links = self._extract_with_selectors(soup, url)
            if links:
                logger.info(f"Found {len(links)} links using configured selectors")
                return self._sort_and_deduplicate(links)
        
        # 自动检测模式
        logger.info("No selectors configured or detection enabled, using auto-detection")
        links = self._auto_extract_links(soup, url)
        if links:
            logger.info(f"Auto-detected {len(links)} video links")
        else:
            logger.warning("Auto-detection failed, no links found")
        return links
    
    def _extract_with_selectors(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        links = []
        for selector in self.selectors:
            links.extend(self._extract_with_selector(soup, selector, base_url))
        return links
    
    def _extract_with_selector(self, soup: BeautifulSoup, selector: Dict, base_url: str) -> List[Dict]:
        """根据配置的选择器提取链接"""
        links = []
        tag = selector.get('tag', 'a')
        
        if 'id_pattern' in selector:
            elements = soup.find_all(tag, id=re.compile(selector['id_pattern']))
        elif 'class_contains' in selector:
            elements = soup.find_all(tag, class_=re.compile(selector['class_contains']))
        elif 'attrs' in selector:
            attrs = selector['attrs']
            elements = soup.find_all(tag, attrs=attrs)
        else:
            elements = soup.find_all(tag)
        
        for elem in elements:
            a_tag = elem.find('a') if tag != 'a' else elem
            if a_tag and a_tag.get('href'):
                href = a_tag.get('href')
                if not href.startswith(('http://', 'https://')):
                    if href.startswith('//'):
                        href = 'https:' + href
                    else:
                        href = requests.compat.urljoin(base_url, href)
                
                links.append({
                    'url': href,
                    'title': a_tag.get('title', a_tag.get_text(strip=True)),
                    'episode_id': elem.get('id', '')
                })
        return links
    
    def _auto_extract_links(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """自动检测视频链接"""
        candidates = []
        all_links = soup.find_all('a', href=True)
        
        for a in all_links:
            href = a['href']
            text = a.get_text(strip=True)
            title = a.get('title', '')
            
            # 筛选可能是播放页的链接
            play_keywords = ['play', 'video', 'watch', 'episode', 'view', 'player']
            if not any(keyword in href.lower() for keyword in play_keywords):
                continue
            
            episode_num = self._extract_episode_number(text or title)
            if episode_num is None:
                continue
            
            full_url = href if href.startswith('http') else requests.compat.urljoin(base_url, href)
            candidates.append({
                'url': full_url,
                'title': title or text,
                'episode_id': str(episode_num).zfill(3),
                'episode_num': episode_num
            })
        
        if not candidates:
            candidates = self._fallback_extract(soup, base_url)
        
        return self._sort_and_deduplicate(candidates)
    
    def _extract_episode_number(self, text: str) -> Optional[int]:
        """从文本中提取集数"""
        if not text:
            return None
        patterns = [
            r'第\s*(\d+)\s*[集話话]',
            r'(\d+)\s*[集話话]',
            r'^(\d+)$',
            r'[Ee](\d+)',
            r'第\s*([一二三四五六七八九十百千万]+)\s*[集話话]'
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                num_str = match.group(1)
                if num_str.isdigit():
                    return int(num_str)
                else:
                    return self._chinese_to_int(num_str)
        return None
    
    def _chinese_to_int(self, chinese: str) -> int:
        ch_num = {'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10,
                  '百':100,'千':1000,'万':10000}
        result = 0
        tmp = 0
        for ch in chinese:
            if ch in ch_num:
                num = ch_num[ch]
                if num >= 10:
                    if tmp == 0:
                        tmp = 1
                    result += tmp * num
                    tmp = 0
                else:
                    tmp = tmp * 10 + num
            else:
                tmp = 0
        result += tmp
        return result
    
    def _fallback_extract(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        patterns = [
            ('li', {'id': re.compile(r'^\d{2}$')}),
            ('li', {'class': re.compile(r'episode|item|list')}),
            ('div', {'class': re.compile(r'episode|video-item')}),
            ('a', {'class': re.compile(r'play|watch')})
        ]
        links = []
        for tag, attrs in patterns:
            elements = soup.find_all(tag, attrs=attrs)
            for elem in elements:
                a = elem.find('a') if tag != 'a' else elem
                if a and a.get('href'):
                    href = a['href']
                    full_url = href if href.startswith('http') else requests.compat.urljoin(base_url, href)
                    links.append({
                        'url': full_url,
                        'title': a.get('title', a.get_text(strip=True)),
                        'episode_id': elem.get('id', '')
                    })
            if links:
                break
        return links
    
    def _sort_and_deduplicate(self, links: List[Dict]) -> List[Dict]:
        unique = {}
        for link in links:
            if link['url'] not in unique:
                unique[link['url']] = link
        sorted_links = sorted(unique.values(), key=lambda x: int(x.get('episode_id', 0)) if x.get('episode_id', '').isdigit() else x.get('episode_num', 0))
        return sorted_links
    
    def _fetch_page(self, url: str) -> Optional[str]:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        if self.driver:
            try:
                self.driver.get(url)
                timeout = self.config.get('selenium', {}).get('timeout', 30)
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                return self.driver.page_source
            except Exception as e:
                logger.warning(f"Selenium fetch failed: {e}, falling back to requests")
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return resp.text
        except Exception as e:
            logger.error(f"Failed to fetch page: {e}")
            return None
    
    def close(self):
        if self.driver:
            self.driver.quit()
