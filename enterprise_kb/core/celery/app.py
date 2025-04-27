"""Celery应用配置"""
from celery import Celery
import logging
import os
from kombu import Exchange, Queue
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

# 定义队列
default_exchange = Exchange('default', type='direct')
document_exchange = Exchange('document', type='direct')
priority_exchange = Exchange('priority', type='direct')

task_queues = [
    Queue('default', default_exchange, routing_key='default'),
    Queue('document_processing', document_exchange, routing_key='document.processing'),
    Queue('document_indexing', document_exchange, routing_key='document.indexing'),
    Queue('priority', priority_exchange, routing_key='priority'),
]

# 定义路由
task_routes = {
    # 原始文档任务
    'enterprise_kb.tasks.document_tasks.process_document_task': {
        'queue': 'document_processing',
        'routing_key': 'document.processing'
    },
    'enterprise_kb.tasks.document_tasks.batch_process_documents_task': {
        'queue': 'document_processing',
        'routing_key': 'document.processing'
    },
    'enterprise_kb.tasks.document_tasks.cleanup_task': {
        'queue': 'default',
        'routing_key': 'default'
    },

    # 改进的文档任务
    'enterprise_kb.tasks.document_tasks_v2.*': {
        'queue': 'document_processing',
        'routing_key': 'document.processing'
    },

    # 文档分段处理任务
    'enterprise_kb.tasks.document_segment_tasks.split_document': {
        'queue': 'document_processing',
        'routing_key': 'document.splitting'
    },
    'enterprise_kb.tasks.document_segment_tasks.process_segment': {
        'queue': 'document_processing',
        'routing_key': 'document.segment'
    },
    'enterprise_kb.tasks.document_segment_tasks.merge_results': {
        'queue': 'document_processing',
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

    # 优先级任务
    'enterprise_kb.tasks.priority_tasks.*': {
        'queue': 'priority',
        'routing_key': 'priority'
    },
}

# 创建Celery实例
celery_app = Celery(
    "enterprise_kb",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "enterprise_kb.tasks.document_tasks",
        "enterprise_kb.tasks.document_tasks_v2",
        "enterprise_kb.tasks.document_segment_tasks"
    ]
)

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
)

# 自定义任务基类
class BaseTask(celery_app.Task):
    """自定义任务基类，添加错误处理和日志"""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败处理"""
        logger.error(f"任务 {task_id} 失败: {exc}", exc_info=einfo)
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """任务成功处理"""
        logger.info(f"任务 {task_id} 完成")
        super().on_success(retval, task_id, args, kwargs)

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """任务重试处理"""
        logger.warning(f"任务 {task_id} 重试: {exc}")
        super().on_retry(exc, task_id, args, kwargs, einfo)

# 设置默认任务基类
celery_app.Task = BaseTask

# 启动时打印配置信息
logger.info(f"Celery配置初始化完成，Broker: {settings.CELERY_BROKER_URL}")