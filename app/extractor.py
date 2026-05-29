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
    """视频链接提取器，支持静态和动态页面"""
    
    def __init__(self, config: Dict):
        self.config = config
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
        """获取页面中的所有视频链接"""
        html = self._fetch_page(url)
        if not html:
            return []
        
        soup = BeautifulSoup(html, 'lxml')
        video_links = []
        
        for selector in self.config.get('video_selectors', []):
            links = self._extract_with_selector(soup, selector, url)
            video_links.extend(links)
        
        # 去重并排序
        unique_links = {}
        for link in video_links:
            if link['url'] not in unique_links:
                unique_links[link['url']] = link
        
        result = sorted(unique_links.values(), key=lambda x: x.get('episode_id', ''))
        logger.info(f"Found {len(result)} video links")
        return result
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """获取页面内容，优先使用 Selenium"""
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
    
    def close(self):
        if self.driver:
            self.driver.quit()
