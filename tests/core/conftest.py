import os
import pytest
import logging
from dotenv import load_dotenv

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 测试前加载环境变量
@pytest.fixture(scope="session", autouse=True)
def load_env():
    """自动加载环境变量"""
    logger.info("加载环境变量")
    load_dotenv(verbose=True)
    yield

# 检查向量数据库配置
@pytest.fixture(scope="session")
def vector_store_type():
    """获取向量存储类型"""
    store_type = os.getenv('VECTOR_STORE_TYPE', 'milvus')
    logger.info(f"向量存储类型: {store_type}")
    return store_type 