FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# 安装系统依赖：wget, unzip, ffmpeg, curl, gnupg
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 使用 Python 脚本获取 Chrome for Testing 的最新稳定版本信息并下载
RUN set -ex \
    && python3 -c "
import json, urllib.request, os
url = 'https://googlechromelabs.github.io/chrome-for-testing/latest-known-good-versions-with-downloads.json'
data = json.loads(urllib.request.urlopen(url).read())
stable_version = data['channels']['Stable']['version']
downloads = data['channels']['Stable']['downloads']
chrome_url = next(d for d in downloads['chrome'] if d['platform'] == 'linux64')['url']
driver_url = next(d for d in downloads['chromedriver'] if d['platform'] == 'linux64')['url']
print(f'STABLE_VERSION={stable_version}')
print(f'CHROME_URL={chrome_url}')
print(f'DRIVER_URL={driver_url}')
" > /tmp/chrome_env \
    && . /tmp/chrome_env \
    && wget -q -O chrome.zip "$CHROME_URL" \
    && unzip chrome.zip -d /opt \
    && chmod +x /opt/chrome-linux64/chrome \
    && ln -sf /opt/chrome-linux64/chrome /usr/local/bin/google-chrome \
    && wget -q -O chromedriver.zip "$DRIVER_URL" \
    && unzip chromedriver.zip -d /opt \
    && chmod +x /opt/chromedriver-linux64/chromedriver \
    && ln -sf /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && rm -rf chrome.zip chromedriver.zip /tmp/chrome_env

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY entrypoint.sh /

RUN chmod +x /entrypoint.sh

RUN mkdir -p /data /downloads /config

ENTRYPOINT ["/entrypoint.sh"]
