"""
Celery应用配置

本模块创建并配置Celery应用实例，用于处理异步任务。
"""
from typing import Any, Dict, Optional
import os
from celery import Celery
from celery.schedules import crontab

from enterprise_kb.core.config.settings import settings

# 创建Celery实例
celery_app = Celery(
    "enterprise_kb",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["enterprise_kb.services.tasks"]
)

# 配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    worker_max_tasks_per_child=1000,
    task_time_limit=3600,  # 1小时
    task_soft_time_limit=3540,  # 59分钟
)

# 配置定时任务
celery_app.conf.beat_schedule = {
    "update-all-indexes-daily": {
        "task": "update_vector_index",
        "schedule": crontab(hour=2, minute=0),  # 每天凌晨2点
        "args": (),
    },
}

# 自定义任务基类
class BaseTask(celery_app.Task):
    """自定义任务基类，添加错误处理和日志记录"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的处理"""
        print(f"Task {task_id} failed: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的处理"""
        print(f"Task {task_id} completed successfully")
        super().on_success(retval, task_id, args, kwargs)

# 应用自定义任务基类
celery_app.Task = BaseTask 