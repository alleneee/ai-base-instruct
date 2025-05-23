"""
向量数据库API
提供对Milvus向量数据库的操作接口，包括增删改查功能
"""
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, status
from pydantic import BaseModel, Field, conlist

from enterprise_kb.storage.datasource.milvus import MilvusDataSource, MilvusDataSourceConfig
from enterprise_kb.utils.milvus_client import get_milvus_client
from enterprise_kb.core.config.settings import settings
from enterprise_kb.storage.pool.milvus_pool import (
    get_milvus_pool, get_milvus_batch_inserter, 
    get_milvus_batch_deleter, get_milvus_batch_updater
)

router = APIRouter()

# 模型定义
class VectorData(BaseModel):
    """向量数据模型"""
    doc_id: str = Field(..., description="文档ID")
    chunk_id: Optional[str] = Field(None, description="文档块ID")
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
    search_params: Optional[Dict[str, Any]] = Field(None, description="搜索参数")

class HybridSearchQuery(BaseModel):
    """混合搜索查询模型"""
    text: str = Field(..., description="查询文本")
    vector: List[float] = Field(..., description="查询向量")
    top_k: int = Field(5, description="返回结果数量", gt=0, le=100)
    text_weight: float = Field(0.5, description="文本权重", ge=0.0, le=1.0)
    vector_weight: float = Field(0.5, description="向量权重", ge=0.0, le=1.0)
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
    row_count: int = Field(..., description="记录数量")
    fields: List[str] = Field(..., description="字段列表")
    exists: bool = Field(..., description="集合是否存在")
    index: Optional[Dict[str, Any]] = Field(None, description="索引信息")

# 依赖项
async def get_milvus_datasource() -> MilvusDataSource:
    """获取Milvus数据源，使用连接池管理连接"""
    config = MilvusDataSourceConfig(
        name="milvus",
        description="Milvus向量数据库",
        uri=settings.MILVUS_URI,
        collection_name=settings.MILVUS_COLLECTION,
        dimension=settings.MILVUS_DIMENSION
    )
    datasource = MilvusDataSource(config)
    await datasource.connect()
    try:
        yield datasource
    finally:
        await datasource.disconnect()  # 现在会将连接归还到连接池而不是关闭

async def get_connection_pool_stats():
    """获取连接池统计信息"""
    pool = get_milvus_pool()
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
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """获取向量集合统计信息"""
    try:
        stats = await datasource.get_collection_stats()
        if "error" in stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"获取集合统计信息失败: {stats.get('error')}"
            )
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取统计信息时出错: {str(e)}"
        )

@router.post("/add", response_model=StatusResponse)
async def add_vector(
    data: VectorData,
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """添加单个向量数据"""
    try:
        from llama_index.core.schema import TextNode
        
        # 验证向量维度
        if len(data.vector) != settings.MILVUS_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"向量维度不匹配，需要 {settings.MILVUS_DIMENSION} 维，提供了 {len(data.vector)} 维"
            )
        
        # 创建节点
        node = TextNode(
            text=data.text,
            id_=data.chunk_id or data.doc_id,
            embedding=data.vector,
            metadata={"doc_id": data.doc_id, **data.metadata}
        )
        
        # 添加到Milvus
        node_ids = await datasource.add_documents([node])
        
        return {
            "success": True,
            "message": f"成功添加向量数据: {data.doc_id}",
            "details": {"node_ids": node_ids}
        }
    except HTTPException:
        raise
async def batch_add_vectors(
    data: VectorDataBatch,
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
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
            if len(item.vector) != settings.MILVUS_DIMENSION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"向量维度不匹配，需要 {settings.MILVUS_DIMENSION} 维，提供了 {len(item.vector)} 维"
                )
        
        # 转换为BaseNode对象
        nodes = []
        for item in data.vectors:
            node = TextNode(
                id_=item.doc_id,
                text=item.text,
                metadata={
                    **item.metadata,
                    "chunk_id": item.chunk_id
                },
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
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """更新向量数据（使用批处理器优化）"""
    try:
        # 验证输入向量维度
        if len(data.new_data.vector) != settings.MILVUS_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"向量维度不匹配，需要 {settings.MILVUS_DIMENSION} 维，提供了 {len(data.new_data.vector)} 维"
            )
            
        # 转换为BaseNode对象
        node = TextNode(
            id_=data.new_data.doc_id,
            text=data.new_data.text,
            metadata={
                **data.new_data.metadata,
                "chunk_id": data.new_data.chunk_id
            },
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

@router.post("/vectors/batch_delete", response_model=Dict[str, bool])
async def batch_delete_vectors(
    doc_ids: List[str] = Body(..., description="要删除的文档ID列表"),
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
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

@router.post("/pool/config", response_model=StatusResponse)
async def configure_connection_pool(
    config: PoolConfig
) -> Dict[str, Any]:
    """配置连接池参数"""
    try:
        pool = get_milvus_pool()
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
        insert_results = await get_milvus_batch_inserter().async_flush()
        delete_results = await get_milvus_batch_deleter().async_flush()
        update_results = await get_milvus_batch_updater().async_flush()
        
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
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """检查Milvus向量数据库健康状态"""
    try:
        is_healthy = await datasource.health_check()
        
        if is_healthy:
            stats = await datasource.get_collection_stats()
            return {
                "success": True,
                "message": "Milvus向量数据库连接正常",
                "details": stats
            }
        else:
            return {
                "success": False,
                "message": "Milvus向量数据库连接异常"
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"健康检查失败: {str(e)}",
            "details": {"error": str(e)}
        } 