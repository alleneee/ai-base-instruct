#!/usr/bin/env python
"""
启动Celery worker和beat的脚本

使用方法:
    python scripts/start_unified_celery.py worker --queues default,document_processing
    python scripts/start_unified_celery.py beat
    python scripts/start_unified_celery.py flower
"""
import os
import sys
import argparse
import subprocess
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

def start_worker(queues=None, loglevel="INFO", concurrency=None):
    """启动Celery worker
    
    Args:
        queues: 要监听的队列，如果为None则监听所有队列
        loglevel: 日志级别
        concurrency: 并发数，如果为None则使用CPU核心数
    """
    # 默认队列
    default_queues = "default,document_processing,document_splitting,document_segment,document_merging,index,priority"
    
    # 构建命令
    cmd = ["celery", "-A", "enterprise_kb.core.unified_celery", "worker"]
    
    # 添加队列参数
    if queues:
        cmd.extend(["-Q", queues])
    else:
        cmd.extend(["-Q", default_queues])
    
    # 添加日志级别
    cmd.extend(["-l", loglevel])
    
    # 添加并发数
    if concurrency:
        cmd.extend(["--concurrency", str(concurrency)])
    
    # 启动worker
    print(f"启动Celery worker: {' '.join(cmd)}")
    subprocess.run(cmd)

def start_beat(loglevel="INFO"):
    """启动Celery beat
    
    Args:
        loglevel: 日志级别
    """
    # 构建命令
    cmd = ["celery", "-A", "enterprise_kb.core.unified_celery", "beat", "-l", loglevel]
    
    # 启动beat
    print(f"启动Celery beat: {' '.join(cmd)}")
    subprocess.run(cmd)

def start_flower(port=5555):
    """启动Flower监控
    
    Args:
        port: 监控端口
    """
    # 构建命令
    cmd = ["celery", "-A", "enterprise_kb.core.unified_celery", "flower", "--port", str(port)]
    
    # 启动flower
    print(f"启动Flower监控: {' '.join(cmd)}")
    subprocess.run(cmd)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="启动Celery worker和beat")
    parser.add_argument("command", choices=["worker", "beat", "flower"], help="要启动的服务")
    parser.add_argument("--loglevel", default="INFO", help="日志级别")
    parser.add_argument("--concurrency", type=int, help="worker并发数")
    parser.add_argument("--port", type=int, default=5555, help="Flower监控端口")
    parser.add_argument("--queues", help="要监听的队列，逗号分隔")
    
    args = parser.parse_args()
    
    if args.command == "worker":
        start_worker(args.queues, args.loglevel, args.concurrency)
    elif args.command == "beat":
        start_beat(args.loglevel)
    elif args.command == "flower":
        start_flower(args.port)

if __name__ == "__main__":
    main()
