"""
Celery 配置文件
"""
from datetime import timedelta

from enterprise_kb.core.config.settings import settings

# Broker 设置
broker_url = settings.CELERY_BROKER_URL
result_backend = settings.CELERY_RESULT_BACKEND

# 序列化设置
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "Asia/Shanghai"
enable_utc = True

# 任务设置
task_track_started = True
task_time_limit = 3600  # 1小时
task_soft_time_limit = 3300  # 55分钟
worker_disable_rate_limits = True
worker_prefetch_multiplier = 4

# 结果设置
result_expires = 60 * 60 * 24  # 24小时
result_persistent = True

# 重试设置
broker_connection_retry = True
broker_connection_retry_on_startup = True
broker_connection_max_retries = 5

# 队列设置
task_queues = {
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
    "documents": {
        "exchange": "documents",
        "routing_key": "documents",
    },
    "index": {
        "exchange": "index",
        "routing_key": "index",
    },
}

task_default_queue = "default"
task_default_exchange = "default"
task_default_routing_key = "default"

# 定时任务设置
beat_schedule = {
    "optimize-index-daily": {
        "task": "enterprise_kb.services.document.tasks.scheduled_index_optimize",
        "schedule": timedelta(days=1),
        "options": {"queue": "index"},
    },
}

# 日志设置
worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s:%(task_id)s] %(message)s" 