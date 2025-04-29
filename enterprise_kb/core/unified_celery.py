"""
统一的Celery应用配置

本模块提供了统一的Celery应用实例和配置，用于处理异步任务。
它整合了之前分散在多个文件中的Celery配置，消除混淆。
"""
import os
import logging
from typing import Dict, List, Any, Optional
from pathlib import Path
from datetime import timedelta
from functools import lru_cache

from celery import Celery
from celery.schedules import crontab
from celery.signals import task_success, task_failure, worker_ready, setup_logging
from kombu import Exchange, Queue

from enterprise_kb.core.config.settings import settings

# 配置日志
logger = logging.getLogger(__name__)

# 确保日志目录存在
logs_dir = getattr(settings, "LOGS_DIR", "logs")
os.makedirs(logs_dir, exist_ok=True)

# 定义交换机
default_exchange = Exchange('default', type='direct')
document_exchange = Exchange('document', type='direct')
index_exchange = Exchange('index', type='direct')
priority_exchange = Exchange('priority', type='direct')

# 定义队列
task_queues = [
    Queue('default', default_exchange, routing_key='default'),
    # 文档处理队列
    Queue('document_processing', document_exchange, routing_key='document.processing'),
    Queue('document_indexing', document_exchange, routing_key='document.indexing'),
    Queue('document_splitting', document_exchange, routing_key='document.splitting'),
    Queue('document_segment', document_exchange, routing_key='document.segment'),
    Queue('document_merging', document_exchange, routing_key='document.merging'),
    # 索引队列
    Queue('index', index_exchange, routing_key='index'),
    # 优先级队列
    Queue('priority', priority_exchange, routing_key='priority'),
]

# 定义路由
task_routes = {
    # 文档处理任务
    'enterprise_kb.tasks.document_tasks.*': {
        'queue': 'document_processing',
        'routing_key': 'document.processing'
    },
    'enterprise_kb.tasks.document_tasks_v2.*': {
        'queue': 'document_processing',
        'routing_key': 'document.processing'
    },
    'enterprise_kb.services.document.tasks.*': {
        'queue': 'document_processing',
        'routing_key': 'document.processing'
    },
    
    # 文档分段处理任务
    'enterprise_kb.tasks.document_segment_tasks.split_document': {
        'queue': 'document_splitting',
        'routing_key': 'document.splitting'
    },
    'enterprise_kb.tasks.document_segment_tasks.process_segment': {
        'queue': 'document_segment',
        'routing_key': 'document.segment'
    },
    'enterprise_kb.tasks.document_segment_tasks.merge_results': {
        'queue': 'document_merging',
        'routing_key': 'document.merging'
    },
    'enterprise_kb.tasks.document_segment_tasks.process_document_segmented': {
        'queue': 'document_processing',
        'routing_key': 'document.segmented'
    },
    'enterprise_kb.tasks.document_segment_tasks.batch_process_segmented': {
        'queue': 'document_processing',
        'routing_key': 'document.batch'
    },
    
    # 文档块处理任务
    'enterprise_kb.tasks.document_chunk_tasks.*': {
        'queue': 'document_processing',
        'routing_key': 'document.chunk'
    },
    
    # 索引任务
    'enterprise_kb.services.index.tasks.*': {
        'queue': 'index',
        'routing_key': 'index'
    },
    
    # 优先级任务
    'enterprise_kb.tasks.priority_tasks.*': {
        'queue': 'priority',
        'routing_key': 'priority'
    },
}

# 定时任务
beat_schedule = {
    # 每天优化索引
    "optimize-index-daily": {
        "task": "enterprise_kb.services.index.tasks.scheduled_index_optimize",
        "schedule": crontab(hour=2, minute=0),  # 每天凌晨2点
        "options": {"queue": "index"},
    },
    # 每周清理过期文档
    "cleanup-expired-documents-weekly": {
        "task": "enterprise_kb.tasks.document_tasks.cleanup_task",
        "schedule": crontab(day_of_week=0, hour=3, minute=0),  # 每周日凌晨3点
        "options": {"queue": "default"},
    },
}

# 创建Celery实例
celery_app = Celery(
    "enterprise_kb",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# 包含所有任务模块
celery_app.autodiscover_tasks([
    "enterprise_kb.tasks.document_tasks",
    "enterprise_kb.tasks.document_tasks_v2",
    "enterprise_kb.tasks.document_segment_tasks",
    "enterprise_kb.tasks.document_chunk_tasks",
    "enterprise_kb.services.document.tasks",
    "enterprise_kb.services.index.tasks",
    "enterprise_kb.services.tasks",
])

# Celery配置
celery_app.conf.update(
    # 基本配置
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    
    # 任务执行配置
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
    worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
    worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    task_reject_on_worker_lost=True,
    task_acks_on_failure_or_timeout=False,
    
    # 结果配置
    result_expires=settings.CELERY_RESULT_EXPIRES,
    result_persistent=True,
    
    # 队列配置
    task_queues=task_queues,
    task_routes=task_routes,
    task_default_queue='default',
    task_default_exchange='default',
    task_default_routing_key='default',
    
    # 并发配置
    worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
    
    # 日志配置
    worker_log_format='[%(asctime)s: %(levelname)s/%(processName)s] %(message)s',
    worker_task_log_format='[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s',
    
    # 重试配置
    task_default_retry_delay=60,  # 默认重试延迟（秒）
    task_max_retries=3,           # 最大重试次数
    
    # 监控配置
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # 定时任务配置
    beat_schedule=beat_schedule,
    
    # 调试配置
    task_always_eager=settings.CELERY_ALWAYS_EAGER,  # 同步执行任务，用于调试
    task_eager_propagates=True,  # 同步模式下传播异常
)

# 自定义任务基类
class BaseTask(celery_app.Task):
    """自定义任务基类，添加错误处理和日志记录"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的处理"""
        logger.error(f"任务 {self.name}[{task_id}] 失败: {exc}", exc_info=einfo)
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """任务成功时的处理"""
        logger.info(f"任务 {self.name}[{task_id}] 完成成功")
        super().on_success(retval, task_id, args, kwargs)
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试时的处理"""
        logger.warning(f"任务 {self.name}[{task_id}] 重试: {exc}")
        super().on_retry(exc, task_id, args, kwargs, einfo)
    
    def after_return(self, status, retval, task_id, args, kwargs, einfo):
        """任务返回后的处理"""
        logger.debug(f"任务 {self.name}[{task_id}] 返回: {status}")
        super().after_return(status, retval, task_id, args, kwargs, einfo)

# 应用自定义任务基类
celery_app.Task = BaseTask

# 信号处理
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

@celery_app.task(bind=True)
def debug_task(self):
    """调试任务，用于测试Celery配置"""
    logger.info(f"请求信息: {self.request}")
    return {"status": "ok", "message": "调试任务执行成功"}

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

@lru_cache()
def get_celery_app() -> Celery:
    """获取Celery应用实例（单例模式）"""
    return celery_app

# 启动时打印配置信息
logger.info(f"统一Celery配置初始化完成，Broker: {settings.CELERY_BROKER_URL}")

# 启动Celery worker的命令:
# celery -A enterprise_kb.core.unified_celery worker -Q default,document_processing,document_splitting,document_segment,document_merging,index,priority -l info

# 启动Celery beat的命令:
# celery -A enterprise_kb.core.unified_celery beat -l info
