"""Celery应用配置"""
from celery import Celery
import logging
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

# 创建Celery实例
celery_app = Celery(
    "enterprise_kb",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "enterprise_kb.tasks.document_tasks"
    ]
)

# Celery配置
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
    worker_max_tasks_per_child=200,  # 处理200个任务后重启worker以防内存泄漏
    task_acks_late=settings.CELERY_TASK_ACKS_LATE,
    task_routes={
        "enterprise_kb.tasks.document_tasks.*": {"queue": "document_processing"}
    }
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