"""
Celery应用创建和配置模块 (已弃用)

本模块已弃用，请使用enterprise_kb.core.unified_celery。
此模块仅为兼容性保留，将在未来版本中移除。
"""
import os
import warnings
from pathlib import Path
from logging.config import dictConfig
from typing import Optional, Dict, Any

# 导入兼容层
from enterprise_kb.core.unified_celery import (
    celery_app as app,
    get_celery_app,
    get_task_info,
    BaseTask,
    debug_task
)

from enterprise_kb.core.config import settings
from enterprise_kb.utils.logging import get_logger, configure_logging

# 发出弃用警告
warnings.warn(
    "enterprise_kb.core.celery_app已弃用，请使用enterprise_kb.core.unified_celery",
    DeprecationWarning,
    stacklevel=2
)

# 创建日志目录
os.makedirs(settings.LOGS_DIR, exist_ok=True)

# 获取日志记录器
logger = get_logger(__name__)

# 记录迁移提示
logger.warning("此模块已弃用，请使用enterprise_kb.core.unified_celery")

# 启动Celery worker的新命令:
# celery -A enterprise_kb.core.unified_celery worker -Q default,document_processing,document_splitting,document_segment,document_merging,index,priority -l info