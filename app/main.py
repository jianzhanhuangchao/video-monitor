#!/usr/bin/env python3
import os
import sys
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.config import Config
from app.monitor import VideoMonitor

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler()]
    )

def main():
    parser = argparse.ArgumentParser(description='Video Monitor')
    parser.add_argument('-c', '--config', help='Config file path or URL')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger(__name__)
    
    config_source = args.config or os.getenv('CONFIG_SOURCE', '/config/config.yaml')
    cfg = Config(config_source)
    
    monitor = VideoMonitor(cfg)
    
    if args.once:
        monitor.run_once()
    else:
        monitor.run_loop()

if __name__ == '__main__':
    main()
