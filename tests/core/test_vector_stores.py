import pytest
import asyncio
import os
import random
import uuid
import logging
from typing import List, Dict, Any, Optional

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 导入前手动加载环境变量
from dotenv import load_dotenv
logger.info("Loading .env file")
load_dotenv(verbose=True)

from enterprise_kb.storage.vector_store.factory import VectorStoreFactory
from enterprise_kb.storage.vector_store.base import VectorStoreBase
from enterprise_kb.services.vector_store_service import VectorStoreService
from enterprise_kb.core.config.settings import settings
from enterprise_kb.utils.milvus_client import MilvusClient
from enterprise_kb.storage.vector_store.es_client import ElasticsearchClient

# 检查环境变量和系统配置
vector_store_type = os.getenv('VECTOR_STORE_TYPE', 'milvus')
logger.info(f"VECTOR_STORE_TYPE = {vector_store_type}")

# 测试条件：环境是否配置好向量数据库
vector_db_configured = bool(vector_store_type)
logger.info(f"vector_db_configured = {vector_db_configured}")

# 生成测试集合名
TEST_COLLECTION_NAME = f"test_collection_{uuid.uuid4().hex[:8]}"
TEST_DATA_SIZE = 100
VECTOR_DIM = 1536  # OpenAI维度

# 辅助函数
def generate_test_data(size: int, dim: int) -> List[Dict[str, Any]]:
    """生成测试数据"""
    data = []
    for i in range(size):
        data.append({
            "id": str(i),
            "doc_id": f"doc_{i}",
            "vector": [random.random() for _ in range(dim)],
            "metadata": {"source": "test", "page": i % 10}
        })
    return data

@pytest.mark.asyncio
@pytest.mark.skipif(not vector_db_configured, reason="向量数据库未配置")
async def test_milvus_basic_operations():
    """测试Milvus向量数据库的基本操作"""
    if vector_store_type != 'milvus':
        pytest.skip("跳过Milvus测试，当前向量存储类型不是Milvus")
        
    logger.info("开始Milvus基本操作测试")
    client = MilvusClient()
    
    # 创建集合
    await client.create_collection(TEST_COLLECTION_NAME, VECTOR_DIM)
    assert await client.has_collection(TEST_COLLECTION_NAME)
    
    # 生成测试数据并插入
    test_data = generate_test_data(TEST_DATA_SIZE, VECTOR_DIM)
    await client.insert(TEST_COLLECTION_NAME, test_data)
    
    # 获取集合统计信息
    count = await client.count(TEST_COLLECTION_NAME)
    assert count == TEST_DATA_SIZE
    
    # 搜索测试
    query_vector = [random.random() for _ in range(VECTOR_DIM)]
    results = await client.search(
        TEST_COLLECTION_NAME, 
        query_vector, 
        limit=5,
        expr='metadata.source == "test"'
    )
    assert len(results) <= 5
    
    # 清理
    await client.drop_collection(TEST_COLLECTION_NAME)
    assert not await client.has_collection(TEST_COLLECTION_NAME)
    logger.info("Milvus基本操作测试完成")

@pytest.mark.asyncio
@pytest.mark.skipif(not vector_db_configured, reason="向量数据库未配置")
async def test_elasticsearch_basic_operations():
    """测试Elasticsearch向量数据库的基本操作"""
    if vector_store_type != 'elasticsearch':
        pytest.skip("跳过Elasticsearch测试，当前向量存储类型不是Elasticsearch")
        
    logger.info("开始Elasticsearch基本操作测试")
    client = ElasticsearchClient()
    
    # 创建索引
    await client.create_collection(TEST_COLLECTION_NAME, VECTOR_DIM)
    assert await client.has_collection(TEST_COLLECTION_NAME)
    
    # 生成测试数据并插入
    test_data = generate_test_data(TEST_DATA_SIZE, VECTOR_DIM)
    await client.insert(TEST_COLLECTION_NAME, test_data)
    
    # 获取索引统计信息（需要刷新索引）
    await client.refresh(TEST_COLLECTION_NAME)
    count = await client.count(TEST_COLLECTION_NAME)
    assert count == TEST_DATA_SIZE
    
    # 搜索测试
    query_vector = [random.random() for _ in range(VECTOR_DIM)]
    results = await client.search(
        TEST_COLLECTION_NAME, 
        query_vector, 
        limit=5,
        filter_={"term": {"metadata.source": "test"}}
    )
    assert len(results) <= 5
    
    # 清理
    await client.drop_collection(TEST_COLLECTION_NAME)
    assert not await client.has_collection(TEST_COLLECTION_NAME)
    logger.info("Elasticsearch基本操作测试完成")

@pytest.mark.asyncio
@pytest.mark.skipif(not vector_db_configured, reason="向量数据库未配置")
async def test_vector_store_service_operations():
    """测试向量数据库服务层的操作"""
    await _test_vector_store_service()

async def _test_vector_store(store_type: str, test_dimension: int = 128) -> None:
    """
    测试向量数据库的基本功能
    
    Args:
        store_type: 向量数据库类型，如 'milvus' 或 'elasticsearch'
        test_dimension: 测试用向量维度
    """
    logger.info(f"=== 开始测试 {store_type} 向量数据库 ===")
    
    # 使用工厂创建向量数据库实例
    vector_store = VectorStoreFactory.get_vector_store(store_type=store_type)
    
    # 初始化连接
    await vector_store.initialize()
    
    # 测试集合名称
    test_collection = f"test_collection_{uuid.uuid4().hex[:8]}"
    
    try:
        # 1. 测试创建集合
        logger.info(f"创建集合: {test_collection}")
        success = await vector_store.create_collection(
            collection_name=test_collection,
            dimension=test_dimension,
            metadata={"description": "测试集合"}
        )
        assert success, "创建集合失败"
        
        # 2. 测试列出集合
        logger.info("列出所有集合:")
        collections = await vector_store.list_collections()
        logger.info(f"所有集合: {collections}")
        assert test_collection in collections, "新创建的集合未在列表中"
        
        # 3. 测试检查集合是否存在
        exists = await vector_store.has_collection(test_collection)
        assert exists, "集合应该存在"
        
        # 4. 测试插入向量
        logger.info(f"向集合 {test_collection} 插入向量")
        vectors = [[random.random() for _ in range(test_dimension)] for _ in range(10)]
        ids = [f"test_id_{i}" for i in range(10)]
        metadata = [{"text": f"测试文本 {i}", "source": "测试脚本"} for i in range(10)]
        
        result_ids = await vector_store.insert(
            collection_name=test_collection,
            vectors=vectors,
            ids=ids,
            metadata=metadata
        )
        assert len(result_ids) == 10, "应插入10个向量"
        logger.info(f"插入的ID: {result_ids}")
        
        # 5. 测试计数
        count = await vector_store.count(test_collection)
        assert count == 10, "集合中应有10个向量"
        logger.info(f"集合中的向量数量: {count}")
        
        # 6. 测试获取向量
        vectors_data = await vector_store.get(test_collection, ids[:3])
        assert len(vectors_data) == 3, "应获取3个向量"
        logger.info(f"获取的向量数量: {len(vectors_data)}")
        
        # 7. 测试搜索向量
        query_vector = vectors[0]  # 使用第一个向量作为查询向量
        results = await vector_store.search(
            collection_name=test_collection,
            query_vector=query_vector,
            limit=5
        )
        assert len(results) > 0, "搜索应返回结果"
        logger.info(f"搜索结果数量: {len(results)}")
        logger.info(f"第一个结果: {results[0]}")
        
        # 8. 测试删除向量
        deleted = await vector_store.delete(test_collection, ids[:2])
        assert deleted, "删除向量失败"
        
        # 9. 再次计数确认删除成功
        count_after_delete = await vector_store.count(test_collection)
        assert count_after_delete == 8, "删除后应剩余8个向量"
        logger.info(f"删除后的向量数量: {count_after_delete}")
        
    finally:
        # 10. 测试删除集合
        logger.info(f"删除集合: {test_collection}")
        success = await vector_store.drop_collection(test_collection)
        assert success, "删除集合失败"
        
        # 11. 关闭连接
        await vector_store.close()
    
    logger.info(f"=== {store_type} 向量数据库测试成功完成 ===\n")

async def _test_vector_store_service() -> None:
    """测试向量数据库服务"""
    logger.info("=== 开始测试向量数据库服务 ===")
    
    # 创建服务实例
    service = VectorStoreService()
    
    # 测试集合名称
    test_collection = f"test_service_collection_{uuid.uuid4().hex[:8]}"
    test_dimension = 128
    
    try:
        # 1. 创建集合
        logger.info(f"创建集合: {test_collection}")
        success = await service.create_collection(
            collection_name=test_collection,
            dimension=test_dimension
        )
        assert success, "创建集合失败"
        
        # 2. 列出集合
        collections = await service.list_collections()
        logger.info(f"所有集合: {collections}")
        
        # 3. 插入向量
        vectors = [[random.random() for _ in range(test_dimension)] for _ in range(5)]
        metadata = [{"text": f"服务测试 {i}"} for i in range(5)]
        
        ids = await service.insert(
            collection_name=test_collection,
            vectors=vectors,
            metadata=metadata
        )
        logger.info(f"插入的向量ID: {ids}")
        
        # 4. 搜索向量
        results = await service.search(
            collection_name=test_collection,
            query_vector=vectors[0],
            limit=3
        )
        logger.info(f"搜索结果: {results}")
        
    finally:
        # 5. 删除集合
        await service.drop_collection(test_collection)
        
        # 6. 关闭连接
        await service.close()
    
    logger.info("=== 向量数据库服务测试成功完成 ===\n")

@pytest.mark.asyncio
async def test_vector_store_service():
    """测试向量存储服务层"""
    logger.info("开始向量存储服务测试")
    vector_store_type = os.getenv('VECTOR_STORE_TYPE', 'milvus')
    service = VectorStoreService(vector_store_type=vector_store_type)
    
    # 创建集合
    await service.create_collection(TEST_COLLECTION_NAME, VECTOR_DIM)
    assert await service.has_collection(TEST_COLLECTION_NAME)
    
    # 生成测试数据并插入
    test_data = generate_test_data(TEST_DATA_SIZE, VECTOR_DIM)
    await service.insert(TEST_COLLECTION_NAME, test_data)
    
    # 获取集合统计信息
    count = await service.count(TEST_COLLECTION_NAME)
    assert count == TEST_DATA_SIZE
    
    # 搜索测试
    query_vector = [random.random() for _ in range(VECTOR_DIM)]
    results = await service.search(
        TEST_COLLECTION_NAME, 
        query_vector, 
        limit=5,
        filter_expr='metadata.source == "test"' if vector_store_type == 'milvus' else \
                   {"term": {"metadata.source": "test"}}
    )
    assert len(results) <= 5
    
    # 清理
    await service.drop_collection(TEST_COLLECTION_NAME)
    assert not await service.has_collection(TEST_COLLECTION_NAME)
    logger.info("向量存储服务测试完成")

@pytest.mark.asyncio
async def test_vector_store_batch_operations():
    """测试向量存储批量操作"""
    logger.info("开始向量存储批量操作测试")
    vector_store_type = os.getenv('VECTOR_STORE_TYPE', 'milvus')
    service = VectorStoreService(vector_store_type=vector_store_type)
    
    # 创建集合
    await service.create_collection(TEST_COLLECTION_NAME, VECTOR_DIM)
    
    # 批量插入测试
    batches = 5
    batch_size = 20
    total_count = 0
    
    for i in range(batches):
        batch_data = generate_test_data(batch_size, VECTOR_DIM)
        await service.insert(TEST_COLLECTION_NAME, batch_data)
        total_count += batch_size
    
    # 验证总数
    count = await service.count(TEST_COLLECTION_NAME)
    assert count == total_count
    
    # 清理
    await service.drop_collection(TEST_COLLECTION_NAME)
    logger.info("向量存储批量操作测试完成") 