"""
测试Milvus向量数据库的CRUD功能
"""
import asyncio
import os
import random
from typing import List, Dict, Any

# 设置环境变量
os.environ["MILVUS_HOST"] = "localhost"
os.environ["MILVUS_PORT"] = "19530"
os.environ["MILVUS_COLLECTION"] = "test_collection"
os.environ["MILVUS_DIMENSION"] = "1536"
os.environ["MILVUS_OVERWRITE"] = "true"

# 导入我们的Milvus模块
from enterprise_kb.storage.datasource.milvus import MilvusDataSource, MilvusDataSourceConfig
from enterprise_kb.utils.milvus_client import MilvusClient, get_milvus_client
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

# 初始化Milvus客户端测试
def test_milvus_client():
    print("\n=== 测试 MilvusClient ===")
    client = MilvusClient()
    
    # 创建集合
    print("创建测试集合...")
    client.create_collection(force_recreate=True)
    
    # 生成测试数据
    test_data = generate_test_data(10)
    
    # 批量插入数据
    print("批量插入测试数据...")
    client.batch_insert(test_data)
    
    # 查询数据
    print("搜索向量...")
    results = client.search(
        vector=generate_random_vector(),
        top_k=3
    )
    print(f"搜索结果: {len(results)} 条")
    if results:
        print(f"第一条结果: ID={results[0]['doc_id']}, 文本={results[0]['text'][:30]}..., 相似度={results[0]['distance']}")
    
    # 获取状态
    stats = client.get_collection_stats()
    print(f"集合统计: {stats}")
    
    # 删除一个文档
    if test_data:
        doc_id = test_data[0]["doc_id"]
        print(f"删除文档: {doc_id}")
        client.delete_by_doc_id(doc_id)
    
    # 清理集合
    print("清空集合...")
    # 获取所有文档ID
    all_doc_ids = [item["doc_id"] for item in test_data[1:]]
    deleted = client.batch_delete_by_doc_ids(all_doc_ids)
    print(f"已删除 {deleted} 条记录")
    
    # 关闭连接
    client.close()
    print("测试完成!")
    return True

# 测试MilvusDataSource
async def test_milvus_datasource():
    print("\n=== 测试 MilvusDataSource ===")
    config = MilvusDataSourceConfig(
        name="test_datasource",
        description="测试Milvus数据源",
        uri="http://localhost:19530",
        collection_name="test_collection",
        dimension=1536
    )
    
    datasource = MilvusDataSource(config)
    
    # 连接
    print("连接到Milvus数据源...")
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
    print("添加文档节点...")
    node_ids = await datasource.add_documents(nodes)
    print(f"添加了 {len(node_ids)} 个节点")
    
    # 搜索文档
    print("搜索文档...")
    results = await datasource.search_documents(
        query_vector=generate_random_vector(),
        top_k=3
    )
    print(f"搜索结果: {len(results)} 条")
    if results:
        print(f"第一条结果: ID={results[0].node.metadata.get('doc_id')}, 文本={results[0].node.text[:30]}...")
    
    # 更新文档
    if nodes:
        doc_id = f"test_doc_0"
        print(f"更新文档: {doc_id}")
        new_node = TextNode(
            text="This is an updated node content",
            id_="updated_node",
            metadata={"doc_id": doc_id, "updated": True},
            embedding=generate_random_vector()
        )
        success = await datasource.update_document(doc_id, new_node)
        print(f"更新结果: {'成功' if success else '失败'}")
    
    # 删除文档
    if nodes:
        doc_id = f"test_doc_1"
        print(f"删除文档: {doc_id}")
        success = await datasource.delete_document(doc_id)
        print(f"删除结果: {'成功' if success else '失败'}")
    
    # 批量删除
    doc_ids = [f"test_doc_{i}" for i in range(2, 5)]
    print(f"批量删除文档: {doc_ids}")
    results = await datasource.batch_delete_documents(doc_ids)
    print(f"批量删除结果: {results}")
    
    # 清空集合
    print("清空集合...")
    success = await datasource.clear_collection()
    print(f"清空结果: {'成功' if success else '失败'}")
    
    # 断开连接
    await datasource.disconnect()
    print("测试完成!")
    return True

# 主函数
async def main():
    print("开始测试Milvus向量数据库功能...")
    
    try:
        # 测试MilvusClient
        client_result = test_milvus_client()
        
        # 测试MilvusDataSource
        datasource_result = await test_milvus_datasource()
        
        if client_result and datasource_result:
            print("\n所有测试通过!")
        else:
            print("\n部分测试失败!")
            
    except Exception as e:
        print(f"测试过程中发生错误: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main()) 