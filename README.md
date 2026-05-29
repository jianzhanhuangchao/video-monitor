# Video Monitor

## 简介

本工具监控指定网页的视频更新，自动下载最新的视频（支持 m3u8 格式），并通过邮件通知。  
支持本地/远程配置文件、配置热加载、多备用播放地址、嵌套 m3u8 解析。

## 功能列表

- 每隔指定小时检查网页视频链接（默认4小时）
- 记录历史链接，只下载新发布的视频
- 自动提取 m3u8 链接（支持动态页面）
- 解析嵌套 m3u8（多码率适配）
- 多备用地址：同一视频有多个播放源时，自动按顺序尝试
- 下载方式：优先 ffmpeg，失败降级为分段下载合并
- 配置热加载：修改配置后立即重新检查
- 邮件通知：下载成功或失败时发送邮件
- 配置灵活：支持本地 YAML 文件或远程 HTTP 配置文件
- 通用选择器：可通过配置文件调整视频链接的提取规则

## 快速开始

### 1. 克隆或下载工程

```bash
git clone https://github.com/your-repo/video-monitor.git
cd video-monitor

#本地配置文件
docker build -t video-monitor .
docker run -d \
  -v $(pwd)/config:/config \
  -v $(pwd)/data:/data \
  -v $(pwd)/downloads:/downloads \
  -e CONFIG_SOURCE=/config/config.yaml \
  --name video-monitor \
  video-monitor

#远程配置文件
  docker run -d \
  -v $(pwd)/data:/data \
  -v $(pwd)/downloads:/downloads \
  -e CONFIG_SOURCE=http://example.com/myconfig.yaml \
  --name video-monitor \
  video-monitor
