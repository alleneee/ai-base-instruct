#!/usr/bin/env python3
"""
Milvus功能测试脚本
用于验证Milvus数据源的基本功能，包括连接、增删改查等操作
"""
import os
import sys
import asyncio
import logging
from typing import List, Dict, Any
import random
import numpy as np

# 添加项目根目录到 PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from enterprise_kb.storage.datasource.milvus import MilvusDataSource, MilvusDataSourceConfig
from enterprise_kb.core.config.settings import settings
from enterprise_kb.utils.milvus_client import get_milvus_client
from llama_index.core.schema import TextNode

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 生成随机向量
def generate_random_vector(dim: int = 1536) -> List[float]:
    """生成随机向量，用于测试"""
    vector = np.random.randn(dim).tolist()
    # 归一化
    norm = np.linalg.norm(vector)
    return [x / norm for x in vector]

# 创建测试文档
def create_test_documents(count: int = 10) -> List[dict]:
    """创建测试文档数据"""
    documents = []
    for i in range(count):
        documents.append({
            "doc_id": f"test-doc-{i}",
            "chunk_id": f"test-chunk-{i}",
            "text": f"这是测试文档 {i} 的内容。包含一些关键词：测试、向量、数据库、Milvus。",
            "metadata": {
                "doc_id": f"test-doc-{i}",
                "source": "test",
                "category": random.choice(["文档", "技术文档", "操作手册", "说明书"]),
                "importance": random.randint(1, 5)
            },
            "vector": generate_random_vector(settings.MILVUS_DIMENSION)
        })
    return documents

async def run_test():
    """运行Milvus功能测试"""
    logger.info("开始Milvus功能测试...")
    
    # 检查 Milvus 环境变量
    logger.info(f"Milvus配置: URI={settings.MILVUS_URI}, Collection={settings.MILVUS_COLLECTION}, Dimension={settings.MILVUS_DIMENSION}")
    
    # 创建Milvus数据源配置
    config = MilvusDataSourceConfig(
        name="milvus-test",
        description="Milvus测试数据源",
        uri=settings.MILVUS_URI,
        collection_name=f"test_{settings.MILVUS_COLLECTION}",
        dimension=settings.MILVUS_DIMENSION
    )
    
    datasource = None
    try:
        # 创建数据源并连接
        datasource = MilvusDataSource(config)
        logger.info("尝试连接到Milvus服务器...")
        await datasource.connect()
        logger.info("成功连接到Milvus服务器")
        
        # 获取集合信息
        info = await datasource.get_collection_stats()
        logger.info(f"集合信息: {info}")
        
        # 清空集合（如果需要）
        await datasource.clear_collection()
        logger.info("已清空集合")
        
        # 添加测试文档
        test_docs = create_test_documents(10)
        logger.info(f"生成了 {len(test_docs)} 个测试文档")
        
        # 转换为TextNode
        nodes = []
        for doc in test_docs:
            node = TextNode(
                text=doc["text"],
                id_=doc["chunk_id"],
                embedding=doc["vector"],
                metadata=doc["metadata"]
            )
            nodes.append(node)
        
        # 批量添加
        node_ids = await datasource.batch_add_documents(nodes)
        logger.info(f"成功添加 {len(node_ids)} 个文档")
        
        # 搜索测试
        # 随机选择一个向量进行搜索
        search_vector = random.choice(test_docs)["vector"]
        search_results = await datasource.search_documents(
            query_vector=search_vector,
            top_k=5
        )
        logger.info(f"搜索返回 {len(search_results)} 个结果")
        for i, result in enumerate(search_results):
            # 修复：直接访问TextNode对象的属性
            logger.info(f"结果 {i+1}: ID={result.id_}, 分数={getattr(result, 'score', 'N/A')}")
            logger.info(f"  文本: {result.text[:50]}...")
        
        # 混合搜索测试
        hybrid_results = await datasource.hybrid_search(
            query_text="测试文档",
            query_vector=search_vector,
            top_k=5,
            text_weight=0.3,
            vector_weight=0.7
        )
        logger.info(f"混合搜索返回 {len(hybrid_results)} 个结果")
        for i, result in enumerate(hybrid_results):
            # 修复：直接访问TextNode对象的属性
            logger.info(f"结果 {i+1}: ID={result.id_}, 分数={getattr(result, 'score', 'N/A')}")
            logger.info(f"  文本: {result.text[:50]}...")
        
        # 删除一个文档
        doc_to_delete = test_docs[0]["doc_id"]
        delete_result = await datasource.delete_document(doc_to_delete)
        logger.info(f"删除文档 {doc_to_delete}: {'成功' if delete_result else '失败'}")
        
        # 批量删除
        docs_to_delete = [doc["doc_id"] for doc in test_docs[1:3]]
        batch_delete_results = await datasource.batch_delete_documents(docs_to_delete)
        logger.info(f"批量删除结果: {batch_delete_results}")
        
        # 更新文档
        doc_to_update = test_docs[3]["doc_id"]
        update_node = TextNode(
            text="这是更新后的文档内容",
            id_=test_docs[3]["chunk_id"],
            embedding=generate_random_vector(settings.MILVUS_DIMENSION),
            metadata={"doc_id": doc_to_update, "updated": True}
        )
        update_result = await datasource.update_document(doc_to_update, update_node)
        logger.info(f"更新文档 {doc_to_update}: {'成功' if update_result else '失败'}")
        
        # 运行健康检查
        health_status = await datasource.health_check()
        logger.info(f"健康检查: {'正常' if health_status else '异常'}")
        
        logger.info("功能测试完成")
    except ValueError as e:
        # 处理初始化或连接错误
        if "初始化Milvus数据源失败" in str(e) or "连接Milvus数据源失败" in str(e):
            logger.error("无法连接到Milvus服务器。请确保Milvus服务正在运行，并检查连接配置。")
            logger.error(f"错误详情: {str(e)}")
            logger.info("要运行Milvus服务，可以使用Docker:")
            logger.info("docker run -d --name milvus -p 19530:19530 -p 9091:9091 milvusdb/milvus:v2.3.2")
        else:
            logger.error(f"测试过程中发生值错误: {str(e)}")
    except Exception as e:
        logger.error(f"测试过程中发生错误: {str(e)}")
    finally:
        # 断开连接
        if datasource:
            try:
                await datasource.disconnect()
                logger.info("已断开Milvus连接")
            except Exception as e:
                logger.error(f"断开连接时发生错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(run_test()) 