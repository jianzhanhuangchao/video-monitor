FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1

# 安装必要工具
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 使用已知稳定版本（2025年6月的最新版，你可以自行更新）
ENV CHROME_VERSION=126.0.6478.126
ENV CHROME_URL=https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chrome-linux64.zip
ENV DRIVER_URL=https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chromedriver-linux64.zip

# 下载并安装 Chrome
RUN wget -q -O chrome.zip "$CHROME_URL" \
    && unzip chrome.zip -d /opt \
    && chmod +x /opt/chrome-linux64/chrome \
    && ln -sf /opt/chrome-linux64/chrome /usr/local/bin/google-chrome

# 下载并安装 ChromeDriver
RUN wget -q -O chromedriver.zip "$DRIVER_URL" \
    && unzip chromedriver.zip -d /opt \
    && chmod +x /opt/chromedriver-linux64/chromedriver \
    && ln -sf /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver

# 清理临时文件
RUN rm -rf chrome.zip chromedriver.zip

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/
COPY entrypoint.sh /

RUN chmod +x /entrypoint.sh

RUN mkdir -p /data /downloads /config

ENTRYPOINT ["/entrypoint.sh"]
