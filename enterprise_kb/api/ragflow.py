"""RAGFlow集成接口"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from enterprise_kb.core.hybrid_retrieval import get_hybrid_retrieval_engine, SearchType

router = APIRouter(prefix="/api/v1/ragflow", tags=["RAGFlow集成"])

class RAGQueryRequest(BaseModel):
    """RAG查询请求模型"""
    query: str
    top_k: int = 5
    datasources: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = None

class RAGContext(BaseModel):
    """RAG上下文响应模型"""
    content: str
    metadata: Dict[str, Any]

class RAGQueryResponse(BaseModel):
    """RAG查询响应模型"""
    contexts: List[RAGContext]
    query: str

@router.post("/retrieve", response_model=RAGQueryResponse)
async def retrieve_for_rag(request: RAGQueryRequest):
    """
    RAGFlow检索接口 - 返回符合RAGFlow输入格式的检索结果
    
    Args:
        request: 包含查询文本和检索参数的请求
        
    Returns:
        格式化为RAGFlow所需格式的检索结果
    """
    try:
        # 获取检索引擎
        retrieval_engine = await get_hybrid_retrieval_engine()
        
        # 执行混合检索
        results = await retrieval_engine.retrieve(
            query=request.query,
            search_type=SearchType.HYBRID,
            top_k=request.top_k,
            filters=request.filters,
            datasource_names=request.datasources
        )
        
        # 将结果格式化为RAGFlow需要的格式
        ragflow_contexts = []
        for result in results:
            # 处理元数据
            metadata = result.node.metadata.copy() if result.node.metadata else {}
            metadata["score"] = float(result.score) if hasattr(result, "score") else 0.0
            
            # 对于特殊字段进行处理
            source = metadata.get("source", "")
            if not source and "file_path" in metadata:
                source = metadata["file_path"]
            metadata["source"] = source
            
            # 创建上下文对象
            ragflow_contexts.append(RAGContext(
                content=result.node.text,
                metadata=metadata
            ))
        
        return RAGQueryResponse(
            contexts=ragflow_contexts,
            query=request.query
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"检索失败: {str(e)}") 