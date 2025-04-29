"""
向量数据库API路由
提供向量数据库管理和操作的REST API
"""
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Path
from pydantic import BaseModel, Field

from enterprise_kb.services.vector_store_service import VectorStoreService, get_vector_store_service
from enterprise_kb.storage.vector_store.factory import VectorStoreFactory
from enterprise_kb.core.config.settings import settings

router = APIRouter(prefix="/vector-store", tags=["向量数据库"])

# ----- 模型定义 -----

class CollectionCreate(BaseModel):
    """创建集合请求模型"""
    collection_name: str = Field(..., description="集合名称")
    dimension: int = Field(default=1536, description="向量维度")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="集合元数据")


class VectorData(BaseModel):
    """向量数据模型"""
    vector: List[float] = Field(..., description="向量数据")
    id: Optional[str] = Field(default=None, description="向量ID，如不提供则自动生成")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="向量元数据")


class VectorBatchInsert(BaseModel):
    """向量批量插入请求模型"""
    collection_name: str = Field(..., description="集合名称")
    vectors: List[VectorData] = Field(..., description="向量数据列表")


class SearchRequest(BaseModel):
    """向量搜索请求模型"""
    collection_name: str = Field(..., description="集合名称")
    query_vector: List[float] = Field(..., description="查询向量")
    limit: int = Field(default=10, description="返回结果数量限制")
    filter_expr: Optional[str] = Field(default=None, description="过滤表达式")


class DeleteRequest(BaseModel):
    """删除向量请求模型"""
    collection_name: str = Field(..., description="集合名称")
    ids: List[str] = Field(..., description="要删除的向量ID列表")


class VectorStoreInfo(BaseModel):
    """向量数据库信息模型"""
    current_type: str = Field(..., description="当前使用的向量数据库类型")
    supported_types: List[str] = Field(..., description="支持的向量数据库类型")


class CollectionInfo(BaseModel):
    """集合信息模型"""
    name: str = Field(..., description="集合名称")
    vector_count: int = Field(..., description="向量数量")


# ----- API路由 -----

@router.get("/info", response_model=VectorStoreInfo)
async def get_vector_store_info():
    """获取向量数据库信息"""
    return {
        "current_type": settings.VECTOR_STORE_TYPE,
        "supported_types": VectorStoreFactory.list_supported_types()
    }


@router.get("/collections", response_model=List[str])
async def list_collections(
    vector_store_service: VectorStoreService = Depends(get_vector_store_service)
):
    """列出所有集合"""
    return await vector_store_service.list_collections()


@router.post("/collections", status_code=201)
async def create_collection(
    collection: CollectionCreate,
    vector_store_service: VectorStoreService = Depends(get_vector_store_service)
):
    """创建新集合"""
    success = await vector_store_service.create_collection(
        collection_name=collection.collection_name,
        dimension=collection.dimension,
        metadata=collection.metadata
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="创建集合失败")
    
    return {"message": f"成功创建集合: {collection.collection_name}"}


@router.delete("/collections/{collection_name}")
async def drop_collection(
    collection_name: str = Path(..., description="集合名称"),
    vector_store_service: VectorStoreService = Depends(get_vector_store_service)
):
    """删除集合"""
    # 检查集合是否存在
    exists = await vector_store_service.has_collection(collection_name)
    if not exists:
        raise HTTPException(status_code=404, detail=f"集合不存在: {collection_name}")
    
    success = await vector_store_service.drop_collection(collection_name)
    
    if not success:
        raise HTTPException(status_code=500, detail="删除集合失败")
    
    return {"message": f"成功删除集合: {collection_name}"}


@router.get("/collections/{collection_name}", response_model=CollectionInfo)
async def get_collection_info(
    collection_name: str = Path(..., description="集合名称"),
    vector_store_service: VectorStoreService = Depends(get_vector_store_service)
):
    """获取集合信息"""
    # 检查集合是否存在
    exists = await vector_store_service.has_collection(collection_name)
    if not exists:
        raise HTTPException(status_code=404, detail=f"集合不存在: {collection_name}")
    
    # 获取向量数量
    vector_count = await vector_store_service.count(collection_name)
    
    return {
        "name": collection_name,
        "vector_count": vector_count
    }


@router.post("/vectors", status_code=201)
async def insert_vectors(
    request: VectorBatchInsert,
    vector_store_service: VectorStoreService = Depends(get_vector_store_service)
):
    """批量插入向量"""
    # 检查集合是否存在
    exists = await vector_store_service.has_collection(request.collection_name)
    if not exists:
        raise HTTPException(status_code=404, detail=f"集合不存在: {request.collection_name}")
    
    # 提取向量数据
    vectors = [item.vector for item in request.vectors]
    ids = [item.id for item in request.vectors if item.id is not None]
    metadata = [item.metadata or {} for item in request.vectors]
    
    # 如果提供了部分ID，但不是全部，则使用None表示自动生成
    if ids and len(ids) != len(vectors):
        ids = None
    
    # 插入向量
    result_ids = await vector_store_service.insert(
        collection_name=request.collection_name,
        vectors=vectors,
        ids=ids if ids else None,
        metadata=metadata
    )
    
    if not result_ids:
        raise HTTPException(status_code=500, detail="插入向量失败")
    
    return {"message": f"成功插入 {len(result_ids)} 条向量数据", "ids": result_ids}


@router.post("/search", status_code=200)
async def search_vectors(
    request: SearchRequest,
    vector_store_service: VectorStoreService = Depends(get_vector_store_service)
):
    """向量搜索"""
    # 检查集合是否存在
    exists = await vector_store_service.has_collection(request.collection_name)
    if not exists:
        raise HTTPException(status_code=404, detail=f"集合不存在: {request.collection_name}")
    
    # 执行搜索
    results = await vector_store_service.search(
        collection_name=request.collection_name,
        query_vector=request.query_vector,
        limit=request.limit,
        filter_expr=request.filter_expr
    )
    
    return {"results": results}


@router.delete("/vectors")
async def delete_vectors(
    request: DeleteRequest,
    vector_store_service: VectorStoreService = Depends(get_vector_store_service)
):
    """删除向量"""
    # 检查集合是否存在
    exists = await vector_store_service.has_collection(request.collection_name)
    if not exists:
        raise HTTPException(status_code=404, detail=f"集合不存在: {request.collection_name}")
    
    # 执行删除
    success = await vector_store_service.delete(
        collection_name=request.collection_name,
        ids=request.ids
    )
    
    if not success:
        raise HTTPException(status_code=500, detail="删除向量失败")
    
    return {"message": f"成功删除 {len(request.ids)} 条向量数据"} 