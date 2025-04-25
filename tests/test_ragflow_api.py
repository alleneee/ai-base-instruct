"""测试RAGFlow API集成"""
import os
import json
import aiohttp
import pytest
import asyncio
from typing import Dict, Any

# 测试配置
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/v1")

@pytest.fixture
async def http_client():
    """创建HTTP客户端会话"""
    async with aiohttp.ClientSession() as session:
        yield session

async def upload_test_document(client: aiohttp.ClientSession, filename: str = "test.txt"):
    """上传测试文档"""
    # 创建测试文件内容
    content = "这是一个测试文档，用于验证RAGFlow API集成功能。"
    
    # 准备表单数据
    form = aiohttp.FormData()
    form.add_field('file', content.encode('utf-8'), filename=filename)
    form.add_field('title', '测试文档')
    form.add_field('description', '用于API测试的文档')
    form.add_field('datasource', 'primary')
    form.add_field('metadata', json.dumps({'test_key': 'test_value'}))
    
    # 上传文档
    response = await client.post(f"{API_BASE_URL}/documents/", data=form)
    return await response.json()

@pytest.mark.asyncio
async def test_ragflow_retrieve_endpoint(http_client):
    """测试RAGFlow检索接口"""
    # 上传测试文档
    doc_result = await upload_test_document(http_client)
    assert 'doc_id' in doc_result
    doc_id = doc_result['doc_id']
    
    try:
        # 等待索引完成
        await asyncio.sleep(2)
        
        # 测试RAGFlow检索接口
        query_data = {
            "query": "测试文档",
            "top_k": 3,
            "datasources": ["primary"]
        }
        
        response = await http_client.post(
            f"{API_BASE_URL}/ragflow/retrieve",
            json=query_data
        )
        
        assert response.status == 200
        result = await response.json()
        
        # 验证响应结构
        assert "contexts" in result
        assert "query" in result
        assert result["query"] == query_data["query"]
        
        # 至少应该找到一个结果（我们上传的文档）
        if len(result["contexts"]) > 0:
            context = result["contexts"][0]
            assert "content" in context
            assert "metadata" in context
            assert "score" in context["metadata"]
        
    finally:
        # 清理：删除测试文档
        await http_client.delete(f"{API_BASE_URL}/documents/{doc_id}")

@pytest.mark.asyncio
async def test_search_endpoint(http_client):
    """测试普通搜索接口"""
    # 上传测试文档
    doc_result = await upload_test_document(http_client)
    assert 'doc_id' in doc_result
    doc_id = doc_result['doc_id']
    
    try:
        # 等待索引完成
        await asyncio.sleep(2)
        
        # 测试搜索接口
        query_data = {
            "query": "测试文档",
            "search_type": "hybrid",
            "top_k": 3,
            "datasources": ["primary"],
            "rerank": True
        }
        
        response = await http_client.post(
            f"{API_BASE_URL}/retrieval/search",
            json=query_data
        )
        
        assert response.status == 200
        result = await response.json()
        
        # 验证响应结构
        assert "results" in result
        assert "total" in result
        assert "query" in result
        assert "search_type" in result
        
        # 至少应该找到一个结果（我们上传的文档）
        if result["total"] > 0:
            item = result["results"][0]
            assert "text" in item
            assert "metadata" in item
            assert "score" in item
            assert "node_id" in item
        
    finally:
        # 清理：删除测试文档
        await http_client.delete(f"{API_BASE_URL}/documents/{doc_id}")

@pytest.mark.asyncio
async def test_datasource_endpoints(http_client):
    """测试数据源管理接口"""
    # 获取可用数据源类型
    response = await http_client.get(f"{API_BASE_URL}/datasources/types")
    assert response.status == 200
    types = await response.json()
    assert isinstance(types, dict)
    
    # 获取数据源列表
    response = await http_client.get(f"{API_BASE_URL}/datasources/")
    assert response.status == 200
    sources = await response.json()
    assert isinstance(sources, list)

@pytest.mark.asyncio
async def test_documents_list_endpoint(http_client):
    """测试文档列表接口"""
    response = await http_client.get(f"{API_BASE_URL}/documents/")
    assert response.status == 200
    result = await response.json()
    assert "total" in result
    assert "documents" in result
    assert isinstance(result["documents"], list) 