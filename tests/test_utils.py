"""
测试工具模块
提供测试所需的辅助工具和Mock对象
"""
import os
import sys
from unittest.mock import patch
from typing import Any, Dict

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 定义测试设置
class TestSettings:
    """用于测试的模拟设置对象"""
    MYSQL_URL = "mysql+pymysql://test:test@localhost:3306/test_db"
    DEBUG = True
    MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB
    MAX_CHUNK_SIZE = 1000
    
    # 向量数据库相关设置
    VECTOR_STORE_TYPE = "mock"
    ELASTICSEARCH_URL = "http://localhost:9200"
    ELASTICSEARCH_USERNAME = ""
    ELASTICSEARCH_PASSWORD = ""
    ELASTICSEARCH_API_KEY = ""
    
    BACKEND_CORS_ORIGINS = ["http://localhost:8000"]
    
    @property
    def ALLOWED_HOSTS(self):
        return ["*"]

# 创建用于修补模块的装饰器
def patch_settings(func):
    """装饰器：使用测试设置替换实际设置"""
    test_settings = TestSettings()
    return patch('enterprise_kb.core.config.settings.settings', test_settings)(func)
