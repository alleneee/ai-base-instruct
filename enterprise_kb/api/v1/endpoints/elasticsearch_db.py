"""
Elasticsearch向量数据库API
提供对Elasticsearch向量数据库的操作接口，包括增删改查功能
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from pydantic import BaseModel, Field, conlist

from enterprise_kb.storage.datasource.elasticsearch import ElasticsearchDataSource, ElasticsearchDataSourceConfig
from enterprise_kb.storage.pool.elasticsearch_pool import (
    get_elasticsearch_pool, get_elasticsearch_batch_inserter, 
    get_elasticsearch_batch_deleter, get_elasticsearch_batch_updater
)
from enterprise_kb.core.config.settings import settings

router = APIRouter()

# 模型定义
class VectorData(BaseModel):
    """向量数据模型"""
    doc_id: str = Field(..., description="文档ID")
    text: str = Field(..., description="文本内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    vector: List[float] = Field(..., description="向量数据")

class VectorDataBatch(BaseModel):
    """批量向量数据模型"""
    vectors: List[VectorData] = Field(..., description="向量数据列表")

class SearchQuery(BaseModel):
    """向量搜索查询模型"""
    vector: List[float] = Field(..., description="查询向量")
    top_k: int = Field(5, description="返回结果数量", gt=0, le=100)
    filter_expr: Optional[str] = Field(None, description="过滤表达式")

class VectorUpdateData(BaseModel):
    """向量更新数据模型"""
    doc_id: str = Field(..., description="要更新的文档ID")
    new_data: VectorData = Field(..., description="新的向量数据")

class VectorSearchResponse(BaseModel):
    """向量搜索结果响应模型"""
    results: List[Dict[str, Any]] = Field(..., description="搜索结果列表")
    total: int = Field(..., description="结果总数")

class StatusResponse(BaseModel):
    """操作状态响应模型"""
    success: bool = Field(..., description="操作是否成功")
    message: str = Field(..., description="操作消息")
    details: Optional[Dict[str, Any]] = Field(None, description="详细信息")

class CollectionStats(BaseModel):
    """集合统计信息响应模型"""
    name: str = Field(..., description="集合名称")
    documents_count: int = Field(..., description="文档数量")
    exists: bool = Field(..., description="集合是否存在")

class PoolConfig(BaseModel):
    """连接池配置"""
    max_connections: int = Field(10, description="最大连接数")
    min_connections: int = Field(2, description="最小连接数")
    max_idle_time: int = Field(60, description="最大空闲时间（秒）")
    reconnect_timeout: int = Field(5, description="重连超时（秒）")
    max_retries: int = Field(3, description="最大重试次数")


# 依赖项
async def get_elasticsearch_datasource() -> ElasticsearchDataSource:
    """获取Elasticsearch数据源，使用连接池管理连接"""
    config = ElasticsearchDataSourceConfig(
        name="elasticsearch",
        description="Elasticsearch向量数据库",
        hosts=[settings.ELASTICSEARCH_URL],
        collection_name=settings.ELASTICSEARCH_COLLECTION,
        dimension=settings.ELASTICSEARCH_DIMENSION
    )
    datasource = ElasticsearchDataSource(config)
    await datasource.connect()
    try:
        yield datasource
    finally:
        await datasource.disconnect()  # 现在会将连接归还到连接池而不是关闭

async def get_connection_pool_stats():
    """获取连接池统计信息"""
    pool = get_elasticsearch_pool()
    return pool.stats()


# API端点
@router.get("/pool/stats", response_model=Dict[str, Any])
async def get_pool_statistics() -> Dict[str, Any]:
    """获取连接池统计信息"""
    try:
        stats = await get_connection_pool_stats()
        return {
            "success": True,
            "message": "成功获取连接池统计信息",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取连接池统计信息失败: {str(e)}"
        )

@router.get("/stats", response_model=CollectionStats)
async def get_collection_statistics(
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> Dict[str, Any]:
    """获取向量集合统计信息"""
    try:
        # 获取集合信息
        info = await datasource.get_info()
        
        # 检查集合是否存在
        exists = await datasource.vector_store.has_collection(datasource.config.collection_name)
        
        # 获取文档数量
        count = await datasource.count_documents()
        
        return {
            "name": datasource.config.collection_name,
            "documents_count": count,
            "exists": exists
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取集合统计信息失败: {str(e)}"
        )

@router.post("/vectors", response_model=StatusResponse)
async def add_vector(
    data: VectorData,
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> Dict[str, Any]:
    """添加向量数据"""
    try:
        # 验证向量维度
        if len(data.vector) != settings.ELASTICSEARCH_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"向量维度不匹配，需要 {settings.ELASTICSEARCH_DIMENSION} 维，提供了 {len(data.vector)} 维"
            )
        
        # 转换为BaseNode对象
        from llama_index.core.schema import TextNode
        node = TextNode(
            id_=data.doc_id,
            text=data.text,
            metadata=data.metadata,
            embedding=data.vector
        )
        
        # 添加文档
        doc_ids = await datasource.add_documents([node])
        
        if doc_ids:
            return {
                "success": True,
                "message": f"成功添加向量数据: {data.doc_id}"
            }
        else:
            return {
                "success": False,
                "message": f"添加向量数据失败: {data.doc_id}"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加向量数据失败: {str(e)}"
        )

@router.post("/vectors/batch", response_model=List[str])
async def batch_add_vectors(
    data: VectorDataBatch,
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> List[str]:
    """批量添加向量数据（使用批处理器优化）"""
    try:
        # 验证输入
        if not data.vectors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="向量数据列表为空"
            )
            
        # 验证向量维度
        for item in data.vectors:
            if len(item.vector) != settings.ELASTICSEARCH_DIMENSION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"向量维度不匹配，需要 {settings.ELASTICSEARCH_DIMENSION} 维，提供了 {len(item.vector)} 维"
                )
        
        # 转换为BaseNode对象
        from llama_index.core.schema import TextNode
        nodes = []
        for item in data.vectors:
            node = TextNode(
                id_=item.doc_id,
                text=item.text,
                metadata=item.metadata,
                embedding=item.vector
            )
            nodes.append(node)
            
        # 利用优化的批量添加方法添加文档
        doc_ids = await datasource.batch_add_documents(nodes)
        return doc_ids
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量添加向量数据失败: {str(e)}"
        )

@router.post("/vectors/update", response_model=StatusResponse)
async def update_vector(
    data: VectorUpdateData,
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> Dict[str, Any]:
    """更新向量数据（使用批处理器优化）"""
    try:
        # 验证输入向量维度
        if len(data.new_data.vector) != settings.ELASTICSEARCH_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"向量维度不匹配，需要 {settings.ELASTICSEARCH_DIMENSION} 维，提供了 {len(data.new_data.vector)} 维"
            )
            
        # 转换为BaseNode对象
        from llama_index.core.schema import TextNode
        node = TextNode(
            id_=data.new_data.doc_id,
            text=data.new_data.text,
            metadata=data.new_data.metadata,
            embedding=data.new_data.vector
        )
        
        # 使用优化的更新方法
        success = await datasource.update_document(data.doc_id, node)
        
        if success:
            return {
                "success": True,
                "message": f"成功更新文档 {data.doc_id}"
            }
        else:
            return {
                "success": False,
                "message": f"未找到文档 {data.doc_id} 或更新失败"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新向量数据失败: {str(e)}"
        )

@router.delete("/vectors/{doc_id}", response_model=StatusResponse)
async def delete_vector(
    doc_id: str,
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> Dict[str, Any]:
    """删除向量数据"""
    try:
        success = await datasource.delete_document(doc_id)
        
        if success:
            return {
                "success": True,
                "message": f"成功删除文档 {doc_id}"
            }
        else:
            return {
                "success": False,
                "message": f"未找到文档 {doc_id} 或删除失败"
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除向量数据失败: {str(e)}"
        )

@router.post("/vectors/batch_delete", response_model=Dict[str, bool])
async def batch_delete_vectors(
    doc_ids: List[str] = Body(..., description="要删除的文档ID列表"),
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> Dict[str, bool]:
    """批量删除向量数据（使用批处理器优化）"""
    try:
        # 验证输入
        if not doc_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文档ID列表为空"
            )
            
        # 使用优化的批量删除方法
        results = await datasource.batch_delete_documents(doc_ids)
        return results
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除向量数据失败: {str(e)}"
        )

@router.post("/search", response_model=VectorSearchResponse)
async def search_vectors(
    query: SearchQuery,
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> Dict[str, Any]:
    """搜索向量数据"""
    try:
        # 验证向量维度
        if len(query.vector) != settings.ELASTICSEARCH_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"查询向量维度不匹配，需要 {settings.ELASTICSEARCH_DIMENSION} 维，提供了 {len(query.vector)} 维"
            )
            
        # 验证top_k参数
        top_k = min(query.top_k, 100)  # 限制最大为100
        
        # 执行搜索
        nodes = await datasource.search_documents(
            query_vector=query.vector,
            top_k=top_k,
            filter_expr=query.filter_expr
        )
        
        # 处理结果
        results = []
        for node in nodes:
            # 获取节点原始数据
            node_data = node.node
            
            # 整理结果
            result = {
                "id": node_data.id_,
                "text": node_data.text,
                "metadata": node_data.metadata or {},
                "score": node.score
            }
            results.append(result)
            
        return {
            "results": results,
            "total": len(results)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"搜索向量数据失败: {str(e)}"
        )

@router.post("/clear", response_model=StatusResponse)
async def clear_collection(
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> Dict[str, Any]:
    """清空集合"""
    try:
        success = await datasource.clear_collection()
        
        # 如果成功清空，同时重置批处理器以避免处理旧数据
        if success:
            # 强制刷新所有批处理器
            await get_elasticsearch_batch_inserter().async_flush()
            await get_elasticsearch_batch_deleter().async_flush()
            await get_elasticsearch_batch_updater().async_flush()
            
            return {
                "success": True,
                "message": "成功清空向量集合"
            }
        else:
            return {
                "success": False,
                "message": "清空向量集合失败"
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"清空向量集合失败: {str(e)}"
        )

@router.post("/pool/config", response_model=StatusResponse)
async def configure_connection_pool(
    config: PoolConfig
) -> Dict[str, Any]:
    """配置连接池参数"""
    try:
        pool = get_elasticsearch_pool()
        pool.config.update(
            max_connections=config.max_connections,
            min_connections=config.min_connections,
            max_idle_time=config.max_idle_time,
            connection_timeout=config.reconnect_timeout,
            max_retries=config.max_retries
        )
        
        return {
            "success": True,
            "message": "成功更新连接池配置",
            "details": {
                "max_connections": pool.config.max_connections,
                "min_connections": pool.config.min_connections,
                "current_active": pool.health_check()["active_connections"]
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"配置连接池失败: {str(e)}"
        )

@router.post("/batch/flush", response_model=StatusResponse)
async def flush_batch_processors() -> Dict[str, Any]:
    """强制刷新所有批处理器队列"""
    try:
        # 获取批处理器并刷新
        insert_results = await get_elasticsearch_batch_inserter().async_flush()
        delete_results = await get_elasticsearch_batch_deleter().async_flush()
        update_results = await get_elasticsearch_batch_updater().async_flush()
        
        return {
            "success": True,
            "message": "成功刷新所有批处理器队列",
            "details": {
                "insert_count": len(insert_results) if insert_results else 0,
                "delete_count": len(delete_results) if delete_results else 0,
                "update_count": len(update_results) if update_results else 0
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"刷新批处理器队列失败: {str(e)}"
        )

@router.get("/health", response_model=StatusResponse)
async def check_health(
    datasource: ElasticsearchDataSource = Depends(get_elasticsearch_datasource)
) -> Dict[str, Any]:
    """检查Elasticsearch向量数据库健康状态"""
    try:
        is_healthy = await datasource.health_check()
        
        if is_healthy:
            info = await datasource.get_info()
            return {
                "success": True,
                "message": "Elasticsearch向量数据库连接正常",
                "details": info
            }
        else:
            return {
                "success": False,
                "message": "Elasticsearch向量数据库连接异常"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"健康检查失败: {str(e)}",
            "details": {"error": str(e)}
        }
