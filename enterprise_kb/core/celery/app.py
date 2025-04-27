"""Celery应用配置 (已弃用)

本模块已弃用，请使用enterprise_kb.core.unified_celery。
此模块仅为兼容性保留，将在未来版本中移除。
"""
import logging
import os
import warnings

# 导入兼容层
from enterprise_kb.core.unified_celery import (
    celery_app,
    get_celery_app,
    get_task_info,
    BaseTask,
    debug_task
)

from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

# 发出弃用警告
warnings.warn(
    "enterprise_kb.core.celery.app已弃用，请使用enterprise_kb.core.unified_celery",
    DeprecationWarning,
    stacklevel=2
)

# 记录迁移提示
logger.warning("此模块已弃用，请使用enterprise_kb.core.unified_celery")

# 启动Celery worker的新命令:
# celery -A enterprise_kb.core.unified_celery worker -Q default,document_processing,document_splitting,document_segment,document_merging,index,priority -l info

# 启动时打印配置信息
logger.info(f"请使用统一的Celery配置: enterprise_kb.core.unified_celery")