"""检索API路由"""
from fastapi import APIRouter, HTTPException, Body
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from enterprise_kb.core.hybrid_retrieval import get_hybrid_retrieval_engine, SearchType
from enterprise_kb.core.retrieval_engine import get_retrieval_engine, SearchMode
from enterprise_kb.core.config.settings import settings

router = APIRouter(prefix="/api/v1/retrieval", tags=["检索服务"])

class QueryRequest(BaseModel):
    """查询请求模型"""
    query: str = Field(..., description="查询文本")
    search_type: str = Field("hybrid", description="搜索类型: vector, keyword, hybrid")
    top_k: int = Field(5, ge=1, le=100, description="返回结果数量")
    datasources: Optional[List[str]] = Field(None, description="指定数据源，为空则搜索所有数据源")
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件，如 {'file_type': 'pdf'}")
    rerank: bool = Field(True, description="是否对结果重新排序")
    use_query_rewriting: Optional[bool] = Field(None, description="是否使用查询重写，如果为None则使用系统默认设置")
    domain: Optional[str] = Field(None, description="查询领域，用于查询重写")

class SearchResultItem(BaseModel):
    """搜索结果项模型"""
    text: str = Field(..., description="文本内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    score: float = Field(..., description="相似度分数")
    node_id: str = Field(..., description="节点ID")

class SearchResponse(BaseModel):
    """搜索响应模型"""
    results: List[SearchResultItem] = Field(default_factory=list, description="搜索结果")
    total: int = Field(..., description="结果总数")
    query: str = Field(..., description="查询文本")
    search_type: str = Field(..., description="搜索类型")
    used_query_rewriting: bool = Field(False, description="是否使用了查询重写")
    query_variants: Optional[List[str]] = Field(None, description="查询变体列表，如果使用了查询重写")

@router.post("/search", response_model=SearchResponse)
async def search_documents(request: QueryRequest):
    """
    检索文档

    Args:
        request: 包含查询文本和检索参数的请求

    Returns:
        检索结果
    """
    try:
        # 获取检索引擎
        retrieval_engine = await get_retrieval_engine()

        # 确定搜索类型
        search_mode_map = {
            "vector": SearchMode.VECTOR,
            "keyword": SearchMode.KEYWORD,
            "hybrid": SearchMode.HYBRID
        }
        search_mode = search_mode_map.get(request.search_type.lower(), SearchMode.HYBRID)

        # 执行检索
        results = await retrieval_engine.retrieve(
            query=request.query,
            search_mode=search_mode,
            top_k=request.top_k,
            filters=request.filters,
            datasource_names=request.datasources,
            use_query_rewriting=request.use_query_rewriting,
            domain=request.domain
        )

        # 处理结果
        search_results = []
        for result in results:
            # 确保分数是浮点数
            score = float(result.score) if hasattr(result, "score") else 0.0

            # 创建结果项
            search_results.append(SearchResultItem(
                text=result.node.text,
                metadata=result.node.metadata or {},
                score=score,
                node_id=result.node.node_id
            ))

        # 检查是否使用了查询重写
        used_query_rewriting = False
        query_variants = None

        # 从结果中提取查询变体信息
        if search_results:
            # 检查第一个结果的元数据中是否有查询变体信息
            for result in search_results:
                if "query_variant" in result.metadata:
                    used_query_rewriting = True
                    break

            # 如果使用了查询重写，收集所有变体
            if used_query_rewriting:
                variants_set = {request.query}  # 包含原始查询
                for result in search_results:
                    if "query_variant" in result.metadata:
                        variants_set.add(result.metadata["query_variant"])
                query_variants = list(variants_set)

        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query=request.query,
            search_type=request.search_type,
            used_query_rewriting=used_query_rewriting,
            query_variants=query_variants
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}")

class SimilarDocumentsRequest(BaseModel):
    """相似文档请求模型"""
    doc_id: str = Field(..., description="文档ID")
    top_k: int = Field(5, ge=1, le=100, description="返回结果数量")
    datasources: Optional[List[str]] = Field(None, description="指定数据源，为空则搜索所有数据源")
    exclude_self: bool = Field(True, description="是否排除自身")

@router.post("/similar", response_model=SearchResponse)
async def find_similar_documents(request: SimilarDocumentsRequest):
    """
    查找相似文档

    Args:
        request: 包含文档ID和查询参数的请求

    Returns:
        相似文档列表
    """
    try:
        # 获取检索引擎
        retrieval_engine = await get_hybrid_retrieval_engine()

        # 首先获取所有数据源中的节点
        nodes = await retrieval_engine._get_nodes_from_datasources(
            datasource_name=request.datasources[0] if request.datasources else None
        )

        # 查找目标文档
        target_node = None
        for node in nodes:
            if node.metadata and node.metadata.get("doc_id") == request.doc_id:
                target_node = node
                break

        if not target_node:
            raise HTTPException(status_code=404, detail="文档不存在")

        # 使用当前文档内容作为查询
        results = await retrieval_engine.retrieve(
            query=target_node.text[:1000],  # 使用前1000个字符作为查询，避免查询太长
            search_type=SearchType.VECTOR,
            top_k=request.top_k + (1 if request.exclude_self else 0),  # 多取一个结果，用于排除自身
            datasource_names=request.datasources
        )

        # 处理结果
        search_results = []
        for result in results:
            # 排除自身
            if request.exclude_self and result.node.node_id == target_node.node_id:
                continue

            # 确保分数是浮点数
            score = float(result.score) if hasattr(result, "score") else 0.0

            # 创建结果项
            search_results.append(SearchResultItem(
                text=result.node.text,
                metadata=result.node.metadata or {},
                score=score,
                node_id=result.node.node_id
            ))

            if len(search_results) >= request.top_k:
                break

        return SearchResponse(
            results=search_results,
            total=len(search_results),
            query=f"Similar to document {request.doc_id}",
            search_type="vector",
            used_query_rewriting=False,
            query_variants=None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"查找相似文档失败: {str(e)}")