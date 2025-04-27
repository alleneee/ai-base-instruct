"""
Celery应用创建和配置模块
"""
import os
from pathlib import Path
from logging.config import dictConfig
from typing import Optional, Dict, Any

from celery import Celery
from celery.signals import task_success, task_failure, worker_ready, setup_logging

from enterprise_kb.core.config import settings
from enterprise_kb.utils.logging import get_logger, configure_logging

# 创建日志目录
os.makedirs(settings.LOGS_DIR, exist_ok=True)

# 配置Celery日志
dictConfig({
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s [%(levelname)s] %(name)s [%(module)s:%(lineno)d]: %(message)s'
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'standard',
            'stream': 'ext://sys.stdout',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'level': 'INFO',
            'formatter': 'detailed',
            'filename': settings.LOGS_DIR / "celery.log",
            'maxBytes': 10 * 1024 * 1024,  # 10MB
            'backupCount': 5,
            'encoding': 'utf-8',
        },
    },
    'loggers': {
        'celery': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'enterprise_kb': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
})

logger = get_logger(__name__)

# 创建Celery应用实例
app = Celery(
    "enterprise_kb",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "enterprise_kb.services.document.tasks",
        "enterprise_kb.services.index.tasks",
    ],
)

# Celery配置
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_send_sent_event=True,
    task_default_queue="default",
    task_queues={
        "default": {"exchange": "default", "routing_key": "default"},
        "processing": {"exchange": "processing", "routing_key": "processing"},
        "indexing": {"exchange": "indexing", "routing_key": "indexing"},
    },
    task_routes={
        "document.*": {"queue": "processing"},
        "index.*": {"queue": "indexing"},
    },
)

# 每个任务的默认重试设置
app.conf.task_default_retry_delay = 60  # 重试前等待时间（秒）
app.conf.task_default_max_retries = 3   # 最大重试次数

# 配置Celery的日志
@setup_logging.connect
def setup_celery_logging(**kwargs):
    """配置Celery的日志处理"""
    configure_logging()

@app.task(bind=True)
def debug_task(self):
    """调试任务，用于测试Celery配置"""
    logger.info(f"请求信息: {self.request}")

@task_success.connect
def task_success_handler(sender=None, **kwargs):
    """任务成功处理"""
    logger.info(f"任务 {sender.name}[{kwargs.get('task_id')}] 执行成功")

@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, **kwargs):
    """任务失败处理"""
    logger.error(f"任务 {sender.name}[{task_id}] 执行失败: {exception}")

@worker_ready.connect
def worker_ready_handler(**kwargs):
    """Worker就绪处理"""
    logger.info("Celery worker已就绪")

# 启动Celery worker的命令:
# celery -A enterprise_kb.core.celery_app worker -Q default,processing,indexing -l info

if __name__ == "__main__":
    app.start()

# 允许在应用程序中调用这些函数以访问Celery任务的状态
task_base = app.Task

class BaseTask(task_base):
    """自定义Celery基础任务类"""
    abstract = True
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的处理"""
        # 记录失败日志或发送通知
        logger.error(f"任务 {task_id} 失败: {exc}")
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的处理"""
        # 记录成功日志或执行后续操作
        logger.info(f"任务 {task_id} 成功完成")
        super().on_success(retval, task_id, args, kwargs)

app.Task = BaseTask 

def get_task_info(task_id: str) -> Optional[Dict[str, Any]]:
    """
    获取任务状态和结果
    
    Args:
        task_id: 任务ID
        
    Returns:
        任务信息字典，包含状态和结果
    """
    task = celery_app.AsyncResult(task_id)
    if task.state == 'PENDING':
        # 任务尚未开始
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state == 'FAILURE':
        # 任务失败
        response = {
            'state': task.state,
            'status': str(task.info),
        }
    else:
        # 任务成功或正在执行
        response = {
            'state': task.state,
            'status': task.info if task.info else 'Running...',
        }
    return response 