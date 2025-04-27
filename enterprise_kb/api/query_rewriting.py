"""查询重写API路由"""
from fastapi import APIRouter, HTTPException, Body, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

from enterprise_kb.core.query_rewriting import get_query_rewriter
from enterprise_kb.core.config.settings import settings

router = APIRouter(prefix="/api/v1/query-rewriting", tags=["查询重写"])

class QueryRewriteRequest(BaseModel):
    """查询重写请求模型"""
    query: str = Field(..., description="原始查询文本")
    num_variants: int = Field(3, ge=1, le=10, description="生成的变体数量")
    domain: Optional[str] = Field(None, description="查询领域，如'法律'、'医疗'等")
    language: str = Field("zh", description="查询语言，默认为中文")

class QueryRewriteResponse(BaseModel):
    """查询重写响应模型"""
    original_query: str = Field(..., description="原始查询")
    variants: List[str] = Field(..., description="重写后的查询变体")
    total: int = Field(..., description="变体总数")

@router.post("", response_model=QueryRewriteResponse)
async def rewrite_query(request: QueryRewriteRequest = Body(...)):
    """
    重写查询以提高检索质量
    
    将原始查询重写为多个变体，以提高检索的召回率
    """
    try:
        # 检查查询重写是否启用
        if not settings.QUERY_REWRITE_ENABLED:
            raise HTTPException(
                status_code=400,
                detail="查询重写功能已禁用"
            )
            
        # 获取查询重写器
        query_rewriter = get_query_rewriter()
        
        # 重写查询
        variants = await query_rewriter.rewrite_query(
            original_query=request.query,
            num_variants=request.num_variants,
            domain=request.domain,
            language=request.language
        )
        
        # 构建响应
        return QueryRewriteResponse(
            original_query=request.query,
            variants=variants,
            total=len(variants)
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"查询重写失败: {str(e)}"
        )

@router.get("/status")
async def get_rewrite_status():
    """
    获取查询重写功能状态
    
    返回查询重写功能的当前配置状态
    """
    return {
        "enabled": settings.QUERY_REWRITE_ENABLED,
        "model": settings.QUERY_REWRITE_MODEL,
        "default_variants": settings.QUERY_REWRITE_VARIANTS
    }
