"""
Gunicorn配置文件
用于在生产环境中启动FastAPI应用
"""
import multiprocessing
import os

# 工作进程数量设置
workers_per_core_str = os.getenv("WORKERS_PER_CORE", "1")
max_workers_str = os.getenv("MAX_WORKERS", "0")
cores = multiprocessing.cpu_count()
workers_per_core = float(workers_per_core_str)
default_web_concurrency = workers_per_core * cores
web_concurrency = max(int(default_web_concurrency), 2)
if max_workers_str:
    max_workers = int(max_workers_str)
    if max_workers > 0:
        web_concurrency = min(web_concurrency, max_workers)

# Gunicorn配置
bind = os.getenv("BIND", "0.0.0.0:8000")
workers = web_concurrency
worker_class = "uvicorn.workers.UvicornWorker"
timeout = int(os.getenv("TIMEOUT", "120"))
keepalive = int(os.getenv("KEEPALIVE", "5"))
graceful_timeout = int(os.getenv("GRACEFUL_TIMEOUT", "30"))

# 日志配置
loglevel = os.getenv("LOG_LEVEL", "info")
accesslog = os.getenv("ACCESS_LOG", "-")
errorlog = os.getenv("ERROR_LOG", "-")

# 进程名称
proc_name = "enterprise_kb_api"

# 预加载应用
preload_app = True

# 以下是可选的高级配置
worker_tmp_dir = "/dev/shm"  # 使用内存临时目录提高性能
max_requests = int(os.getenv("MAX_REQUESTS", "1000"))  # 重启worker的最大请求数
max_requests_jitter = int(os.getenv("MAX_REQUESTS_JITTER", "50"))  # 添加随机抖动防止所有worker同时重启

# 通过注释取消下面的配置以启用HTTPS
# keyfile = "/path/to/key.pem"
# certfile = "/path/to/cert.pem" 