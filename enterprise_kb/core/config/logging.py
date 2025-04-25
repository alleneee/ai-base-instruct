"""日志配置模块"""
import logging
import sys
from typing import Any, Dict

from enterprise_kb.core.config.settings import settings

def configure_logging() -> None:
    """配置应用日志"""
    log_format = settings.LOG_FORMAT
    log_level = getattr(logging, settings.LOG_LEVEL)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    
    # 可选：配置特定模块的日志级别
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    logging.info(f"日志配置完成: 级别={settings.LOG_LEVEL}")


def get_logger(name: str) -> logging.Logger:
    """获取指定名称的日志记录器"""
    return logging.getLogger(name) 