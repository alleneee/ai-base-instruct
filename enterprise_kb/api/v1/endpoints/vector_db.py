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
    """获取Milvus数据源"""
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
        await datasource.disconnect()

# API端点
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
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"添加向量数据失败: {str(e)}"
        )

@router.post("/batch_add", response_model=StatusResponse)
async def batch_add_vectors(
    data: VectorDataBatch,
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """批量添加向量数据"""
    try:
        from llama_index.core.schema import TextNode
        
        # 验证向量维度
        for i, item in enumerate(data.vectors):
            if len(item.vector) != settings.MILVUS_DIMENSION:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"第 {i+1} 个向量维度不匹配，需要 {settings.MILVUS_DIMENSION} 维，提供了 {len(item.vector)} 维"
                )
        
        # 创建节点列表
        nodes = []
        for item in data.vectors:
            node = TextNode(
                text=item.text,
                id_=item.chunk_id or item.doc_id,
                embedding=item.vector,
                metadata={"doc_id": item.doc_id, **item.metadata}
            )
            nodes.append(node)
        
        # 批量添加
        node_ids = await datasource.batch_add_documents(nodes)
        
        return {
            "success": True,
            "message": f"成功批量添加 {len(nodes)} 条向量数据",
            "details": {"count": len(nodes), "node_count": len(node_ids)}
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量添加向量数据失败: {str(e)}"
        )

@router.put("/update", response_model=StatusResponse)
async def update_vector(
    data: VectorUpdateData,
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """更新向量数据"""
    try:
        from llama_index.core.schema import TextNode
        
        # 验证向量维度
        if len(data.new_data.vector) != settings.MILVUS_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"向量维度不匹配，需要 {settings.MILVUS_DIMENSION} 维，提供了 {len(data.new_data.vector)} 维"
            )
        
        # 创建新节点
        new_node = TextNode(
            text=data.new_data.text,
            id_=data.new_data.chunk_id or data.new_data.doc_id,
            embedding=data.new_data.vector,
            metadata={"doc_id": data.new_data.doc_id, **data.new_data.metadata}
        )
        
        # 更新向量
        success = await datasource.update_document(data.doc_id, new_node)
        
        if success:
            return {
                "success": True,
                "message": f"成功更新向量数据: {data.doc_id}"
            }
        else:
            return {
                "success": False,
                "message": f"更新向量数据可能未成功: {data.doc_id}，未找到匹配记录"
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新向量数据失败: {str(e)}"
        )

@router.delete("/delete/{doc_id}", response_model=StatusResponse)
async def delete_vector(
    doc_id: str,
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """删除向量数据"""
    try:
        success = await datasource.delete_document(doc_id)
        
        if success:
            return {
                "success": True,
                "message": f"成功删除向量数据: {doc_id}"
            }
        else:
            return {
                "success": False,
                "message": f"未找到要删除的向量数据: {doc_id}"
            }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除向量数据失败: {str(e)}"
        )

@router.post("/batch_delete", response_model=StatusResponse)
async def batch_delete_vectors(
    doc_ids: List[str] = Body(..., description="要删除的文档ID列表"),
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """批量删除向量数据"""
    try:
        if not doc_ids:
            return {
                "success": False,
                "message": "提供的文档ID列表为空"
            }
            
        results = await datasource.batch_delete_documents(doc_ids)
        
        success_count = sum(1 for status in results.values() if status)
        
        return {
            "success": success_count > 0,
            "message": f"批量删除操作完成: 成功 {success_count}/{len(doc_ids)}",
            "details": {"results": results}
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除向量数据失败: {str(e)}"
        )

@router.post("/search", response_model=VectorSearchResponse)
async def search_vectors(
    query: SearchQuery,
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """搜索向量数据"""
    try:
        # 验证向量维度
        if len(query.vector) != settings.MILVUS_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"查询向量维度不匹配，需要 {settings.MILVUS_DIMENSION} 维，提供了 {len(query.vector)} 维"
            )
            
        # 验证top_k参数
        top_k = min(query.top_k, 100)  # 限制最大为100
        
        # 执行搜索
        nodes = await datasource.search_documents(
            query_vector=query.vector,
            top_k=top_k,
            filter_expr=query.filter_expr,
            search_params=query.search_params
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

@router.post("/hybrid_search", response_model=VectorSearchResponse)
async def hybrid_search_vectors(
    query: HybridSearchQuery,
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """混合搜索：同时使用文本和向量进行搜索"""
    try:
        # 验证向量维度
        if len(query.vector) != settings.MILVUS_DIMENSION:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"查询向量维度不匹配，需要 {settings.MILVUS_DIMENSION} 维，提供了 {len(query.vector)} 维"
            )
            
        # 验证权重参数
        if query.text_weight + query.vector_weight != 1.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"文本权重和向量权重之和必须为1，当前为 {query.text_weight + query.vector_weight}"
            )
            
        # 验证top_k参数
        top_k = min(query.top_k, 100)  # 限制最大为100
        
        # 执行混合搜索
        nodes = await datasource.hybrid_search(
            query_text=query.text,
            query_vector=query.vector,
            top_k=top_k,
            text_weight=query.text_weight,
            vector_weight=query.vector_weight,
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
            detail=f"混合搜索失败: {str(e)}"
        )

@router.post("/clear", response_model=StatusResponse)
async def clear_collection(
    datasource: MilvusDataSource = Depends(get_milvus_datasource)
) -> Dict[str, Any]:
    """清空集合"""
    try:
        success = await datasource.clear_collection()
        
        if success:
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