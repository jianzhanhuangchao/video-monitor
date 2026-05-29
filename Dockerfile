FROM python:3.11-slim

# 设置环境变量，确保Python输出直接打印到控制台
ENV PYTHONUNBUFFERED=1

# 安装必要的系统依赖
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    unzip \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 定义 Chrome for Testing 的版本（latest 表示自动获取最新稳定版）
ENV CHROME_VERSION=latest
ENV CHROME_DRIVER_VERSION=latest

# 下载并安装 Chrome for Testing 和 ChromeDriver
RUN set -ex \
    && LATEST_STABLE_JSON=$(curl -s https://googlechromelabs.github.io/chrome-for-testing/latest-known-good-versions-with-downloads.json) \
    && if [ "$CHROME_VERSION" = "latest" ]; then \
        CHROME_VERSION=$(echo $LATEST_STABLE_JSON | grep -oP '"Stable":\{"channel":"Stable","version":"\K[0-9.]+'); \
    fi \
    && if [ "$CHROME_DRIVER_VERSION" = "latest" ]; then \
        CHROME_DRIVER_VERSION=$CHROME_VERSION; \
    fi \
    # 下载 Chrome
    && CHROME_URL=$(echo $LATEST_STABLE_JSON | grep -oP "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_VERSION}/linux64/chrome-linux64.zip") \
    && if [ -z "$CHROME_URL" ]; then \
        echo "Failed to find Chrome URL for version ${CHROME_VERSION}"; exit 1; \
    fi \
    && wget -q -O chrome.zip "$CHROME_URL" \
    && unzip chrome.zip -d /opt \
    && chmod +x /opt/chrome-linux64/chrome \
    && ln -sf /opt/chrome-linux64/chrome /usr/local/bin/google-chrome \
    # 下载 ChromeDriver
    && DRIVER_URL=$(echo $LATEST_STABLE_JSON | grep -oP "https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/${CHROME_DRIVER_VERSION}/linux64/chromedriver-linux64.zip") \
    && if [ -z "$DRIVER_URL" ]; then \
        echo "Failed to find ChromeDriver URL for version ${CHROME_DRIVER_VERSION}"; exit 1; \
    fi \
    && wget -q -O chromedriver.zip "$DRIVER_URL" \
    && unzip chromedriver.zip -d /opt \
    && chmod +x /opt/chromedriver-linux64/chromedriver \
    && ln -sf /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    # 清理临时文件
    && rm -rf chrome.zip chromedriver.zip

# 设置工作目录
WORKDIR /app

# 复制依赖文件并安装 Python 包
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app/ ./app/
COPY entrypoint.sh /

RUN chmod +x /entrypoint.sh

# 创建数据目录
RUN mkdir -p /data /downloads /config

# 设置入口点
ENTRYPOINT ["/entrypoint.sh"]
