"""
Celery应用配置 (已弃用)

本模块已弃用，请使用enterprise_kb.core.unified_celery。
此模块仅为兼容性保留，将在未来版本中移除。
"""
import warnings
import logging

# 导入兼容层
from enterprise_kb.core.celery_compat import (
    celery_app,
    get_celery_app,
    get_task_info,
    BaseTask,
    debug_task
)

# 设置日志
logger = logging.getLogger(__name__)

# 发出弃用警告
warnings.warn(
    "enterprise_kb.core.celery已弃用，请使用enterprise_kb.core.unified_celery",
    DeprecationWarning,
    stacklevel=2
)

# 记录日志
logger.warning("使用已弃用的enterprise_kb.core.celery模块，请迁移到enterprise_kb.core.unified_celery")