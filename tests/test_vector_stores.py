#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
向量数据库测试脚本
用于测试Milvus和Elasticsearch向量数据库的基本功能
"""
import asyncio
import os
import random
import uuid
import logging
from typing import List, Dict, Any, Optional

# 设置环境变量
os.environ["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from enterprise_kb.storage.vector_store.factory import VectorStoreFactory
from enterprise_kb.storage.vector_store.base import VectorStoreBase
from enterprise_kb.services.vector_store_service import VectorStoreService
from enterprise_kb.core.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def test_vector_store(store_type: str, test_dimension: int = 128) -> None:
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


async def test_vector_store_service() -> None:
    """测试向量数据库服务"""
    logger.info("=== 开始测试向量数据库服务 ===")
    
    # 创建服务实例
    service = VectorStoreService()
    
    # 测试集合名称
    test_collection = f"test_service_collection_{uuid.uuid4().hex[:8]}"
    test_dimension = a = 128
    
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


async def main() -> None:
    """主函数"""
    logger.info("开始向量数据库测试")
    
    # 获取支持的向量数据库类型
    supported_types = VectorStoreFactory.list_supported_types()
    logger.info(f"支持的向量数据库类型: {supported_types}")
    
    # 测试Milvus
    try:
        await test_vector_store("milvus")
    except Exception as e:
        logger.error(f"Milvus测试失败: {str(e)}")
    
    # 测试Elasticsearch
    try:
        # 注意：运行前请确保已经在环境变量或settings中配置了Elasticsearch连接信息
        await test_vector_store("elasticsearch")
    except Exception as e:
        logger.error(f"Elasticsearch测试失败: {str(e)}")
    
    # 测试服务层
    try:
        await test_vector_store_service()
    except Exception as e:
        logger.error(f"向量数据库服务测试失败: {str(e)}")
    
    logger.info("向量数据库测试完成")


if __name__ == "__main__":
    asyncio.run(main()) 