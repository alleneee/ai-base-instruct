"""
Milvus向量数据库集成测试

本测试文件整合了根目录下test_milvus.py中的测试内容，
提供了对MilvusClient和MilvusDataSource的完整测试套件。

主要测试内容：
1. MilvusClient的基本CRUD操作
2. MilvusDataSource的文档管理功能
3. Milvus的混合搜索能力
"""
import asyncio
import os
import pytest
import random
import logging
from typing import List, Dict, Any

from dotenv import load_dotenv
# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv(verbose=True)

# 导入Milvus相关模块
from enterprise_kb.utils.milvus_client import MilvusClient, get_milvus_client
from enterprise_kb.storage.datasource.milvus import MilvusDataSource, MilvusDataSourceConfig
from llama_index.core.schema import TextNode

# 生成随机向量的辅助函数
def generate_random_vector(dim: int = 1536) -> List[float]:
    return [random.uniform(-1.0, 1.0) for _ in range(dim)]

# 生成测试数据
def generate_test_data(count: int = 5) -> List[Dict[str, Any]]:
    data = []
    for i in range(count):
        data.append({
            "doc_id": f"doc_{i}",
            "chunk_id": f"chunk_{i}",
            "text": f"This is test document {i} with some content for testing purposes.",
            "vector": generate_random_vector(),
            "metadata": {"type": "test", "source": "generated", "category": f"category_{i % 3}"}
        })
    return data

# 配置是否跳过测试的条件
milvus_available = os.getenv("MILVUS_HOST") and os.getenv("MILVUS_PORT")

@pytest.mark.skipif(not milvus_available, reason="Milvus环境变量未设置")
def test_milvus_client():
    """测试MilvusClient的基本功能"""
    logger.info("=== 测试 MilvusClient ===")
    client = MilvusClient()
    
    # 创建集合
    logger.info("创建测试集合...")
    client.create_collection(force_recreate=True)
    
    # 生成测试数据
    test_data = generate_test_data(10)
    
    # 批量插入数据
    logger.info("批量插入测试数据...")
    client.batch_insert(test_data)
    
    # 查询数据
    logger.info("搜索向量...")
    results = client.search(
        vector=generate_random_vector(),
        top_k=3
    )
    assert len(results) <= 3, "搜索结果数量应小于等于3"
    if results:
        logger.info(f"第一条结果: ID={results[0]['doc_id']}, 文本={results[0]['text'][:30]}..., 相似度={results[0]['distance']}")
    
    # 获取状态
    stats = client.get_collection_stats()
    logger.info(f"集合统计: {stats}")
    assert 'row_count' in stats, "统计信息应包含row_count"
    
    # 删除一个文档
    if test_data:
        doc_id = test_data[0]["doc_id"]
        logger.info(f"删除文档: {doc_id}")
        deleted = client.delete_by_doc_id(doc_id)
        assert deleted > 0, "应成功删除至少一条记录"
    
    # 清理集合
    logger.info("清空集合...")
    # 获取所有文档ID
    all_doc_ids = [item["doc_id"] for item in test_data[1:]]
    deleted = client.batch_delete_by_doc_ids(all_doc_ids)
    logger.info(f"已删除 {deleted} 条记录")
    assert deleted > 0, "应成功删除多条记录"
    
    # 关闭连接
    client.close()
    logger.info("测试完成!")

@pytest.mark.asyncio
@pytest.mark.skipif(not milvus_available, reason="Milvus环境变量未设置")
async def test_milvus_datasource():
    """测试MilvusDataSource的基本功能"""
    logger.info("=== 测试 MilvusDataSource ===")
    
    # 创建测试数据源配置
    config = MilvusDataSourceConfig(
        name="test_datasource",
        description="测试Milvus数据源",
        uri=f"http://{os.getenv('MILVUS_HOST', 'localhost')}:{os.getenv('MILVUS_PORT', '19530')}",
        collection_name=os.getenv("MILVUS_COLLECTION", "test_collection"),
        dimension=int(os.getenv("MILVUS_DIMENSION", "1536"))
    )
    
    datasource = MilvusDataSource(config)
    
    # 连接
    logger.info("连接到Milvus数据源...")
    await datasource.connect()
    
    # 创建测试节点
    nodes = []
    for i in range(5):
        node = TextNode(
            text=f"This is a test node {i}",
            id_=f"node_{i}",
            metadata={"doc_id": f"test_doc_{i}", "category": f"category_{i % 2}"},
            embedding=generate_random_vector()
        )
        nodes.append(node)
    
    # 添加文档
    logger.info("添加文档节点...")
    node_ids = await datasource.add_documents(nodes)
    logger.info(f"添加了 {len(node_ids)} 个节点")
    assert len(node_ids) == 5, "应成功添加5个节点"
    
    # 搜索文档
    logger.info("搜索文档...")
    results = await datasource.search_documents(
        query_vector=generate_random_vector(),
        top_k=3
    )
    logger.info(f"搜索结果: {len(results)} 条")
    assert len(results) <= 3, "搜索结果数量应小于等于3"
    
    if results:
        logger.info(f"第一条结果: ID={results[0].node.metadata.get('doc_id')}, 文本={results[0].node.text[:30]}...")
    
    # 更新文档
    if nodes:
        doc_id = f"test_doc_0"
        logger.info(f"更新文档: {doc_id}")
        new_node = TextNode(
            text="This is an updated node content",
            id_="updated_node",
            metadata={"doc_id": doc_id, "updated": True},
            embedding=generate_random_vector()
        )
        success = await datasource.update_document(doc_id, new_node)
        logger.info(f"更新结果: {'成功' if success else '失败'}")
        assert success is True, "文档更新应成功"
    
    # 删除文档
    if nodes:
        doc_id = f"test_doc_1"
        logger.info(f"删除文档: {doc_id}")
        success = await datasource.delete_document(doc_id)
        logger.info(f"删除结果: {'成功' if success else '失败'}")
        assert success is True, "文档删除应成功"
    
    # 批量删除
    doc_ids = [f"test_doc_{i}" for i in range(2, 5)]
    logger.info(f"批量删除文档: {doc_ids}")
    results = await datasource.batch_delete_documents(doc_ids)
    logger.info(f"批量删除结果: {results}")
    assert all(results.values()), "所有文档应成功删除"
    
    # 清空集合
    logger.info("清空集合...")
    success = await datasource.clear_collection()
    logger.info(f"清空结果: {'成功' if success else '失败'}")
    assert success is True, "集合清空应成功"
    
    # 断开连接
    await datasource.disconnect()
    logger.info("测试完成!")

@pytest.mark.asyncio
@pytest.mark.skipif(not milvus_available, reason="Milvus环境变量未设置")
async def test_milvus_hybrid_search():
    """测试MilvusDataSource的混合搜索功能"""
    logger.info("=== 测试 Milvus 混合搜索 ===")
    
    # 创建测试数据源配置
    config = MilvusDataSourceConfig(
        name="test_hybrid_search",
        description="测试Milvus混合搜索",
        uri=f"http://{os.getenv('MILVUS_HOST', 'localhost')}:{os.getenv('MILVUS_PORT', '19530')}",
        collection_name=f"test_hybrid_{random.randint(1000, 9999)}",
        dimension=int(os.getenv("MILVUS_DIMENSION", "1536"))
    )
    
    datasource = MilvusDataSource(config)
    
    # 连接
    logger.info("连接到Milvus数据源...")
    try:
        await datasource.connect()
        
        # 创建测试节点 - 使用特定文本便于后续测试
        nodes = []
        texts = [
            "人工智能在医疗领域的应用",
            "机器学习模型评估方法",
            "深度学习在图像识别中的突破",
            "自然语言处理技术进展",
            "强化学习在自动驾驶中的应用"
        ]
        
        for i, text in enumerate(texts):
            node = TextNode(
                text=text,
                id_=f"hybrid_node_{i}",
                metadata={"doc_id": f"hybrid_doc_{i}", "category": "AI技术"},
                embedding=generate_random_vector()
            )
            nodes.append(node)
        
        # 添加文档
        logger.info("添加文档节点...")
        node_ids = await datasource.add_documents(nodes)
        assert len(node_ids) == len(texts), f"应成功添加{len(texts)}个节点"
        
        # 执行混合搜索
        logger.info("执行混合搜索...")
        query_text = "医疗行业中的人工智能"
        query_vector = generate_random_vector()
        
        results = await datasource.hybrid_search(
            query_text=query_text,
            query_vector=query_vector,
            top_k=3
        )
        
        logger.info(f"混合搜索结果: {len(results)} 条")
        assert len(results) <= 3, "混合搜索结果数量应小于等于3"
        
        if results:
            for i, result in enumerate(results):
                logger.info(f"结果 {i+1}: 文本={result.node.text}, 分数={result.score}")
    
    finally:
        # 清理资源
        if datasource._connected:
            logger.info("清理测试集合...")
            await datasource.clear_collection()
            await datasource.disconnect()
        
        logger.info("混合搜索测试完成!") 