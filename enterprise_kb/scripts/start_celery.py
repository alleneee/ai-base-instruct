#!/usr/bin/env python3
"""
Celery工作节点和监控启动脚本

用法:
    python -m enterprise_kb.scripts.start_celery [worker|flower] [--loglevel=INFO] [--concurrency=4]
"""

import os
import sys
import subprocess
import argparse
from pathlib import Path

# 添加项目根目录到sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from enterprise_kb.core.config.settings import (
    CELERY_BROKER_URL,
    CELERY_WORKER_CONCURRENCY
)


def start_worker(loglevel="INFO", concurrency=None, queue="default"):
    """启动Celery工作节点"""
    if not concurrency:
        concurrency = CELERY_WORKER_CONCURRENCY
    
    cmd = [
        "celery", "-A", "enterprise_kb.core.celery", "worker",
        "--loglevel", loglevel,
        "-c", str(concurrency),
        "-Q", queue
    ]
    
    print(f"启动Celery工作节点: {' '.join(cmd)}")
    subprocess.run(cmd)


def start_flower(port=5555):
    """启动Flower监控面板"""
    cmd = [
        "celery", "-A", "enterprise_kb.core.celery", "flower",
        "--port", str(port),
        "--broker", CELERY_BROKER_URL
    ]
    
    print(f"启动Flower监控面板: {' '.join(cmd)}")
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(description="启动Celery工作节点或监控面板")
    parser.add_argument("command", choices=["worker", "flower"], help="要启动的服务")
    parser.add_argument("--loglevel", default="INFO", help="日志级别")
    parser.add_argument("--concurrency", type=int, help="工作进程数")
    parser.add_argument("--port", type=int, default=5555, help="Flower监控面板端口")
    parser.add_argument("--queue", default="default", help="工作队列名称")
    
    args = parser.parse_args()
    
    if args.command == "worker":
        start_worker(args.loglevel, args.concurrency, args.queue)
    elif args.command == "flower":
        start_flower(args.port)


if __name__ == "__main__":
    main() 