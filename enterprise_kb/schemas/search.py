"""搜索相关模式"""
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, ConfigDict
from enum import Enum

class SearchMode(str, Enum):
    """搜索模式"""
    VECTOR = "vector"    # 向量搜索
    KEYWORD = "keyword"  # 关键词搜索
    HYBRID = "hybrid"    # 混合搜索（默认）

class SearchRequest(BaseModel):
    """搜索请求模型"""
    
    query: str = Field(..., description="查询文本")
    top_k: Optional[int] = Field(5, description="返回的最大结果数", ge=1, le=20)
    min_score: Optional[float] = Field(0.7, description="最小相似度分数", ge=0, le=1)
    filters: Optional[Dict[str, Any]] = Field(None, description="过滤条件")
    datasources: Optional[List[str]] = Field(None, description="要查询的数据源列表，为空则查询所有数据源")
    search_mode: Optional[SearchMode] = Field(SearchMode.HYBRID, description="搜索模式，可选向量搜索、关键词搜索或混合搜索")
    

class SearchResult(BaseModel):
    """搜索结果项"""
    
    text: str = Field(..., description="文本内容")
    score: float = Field(..., description="相似度分数")
    doc_id: str = Field(..., description="文档ID")
    file_name: Optional[str] = Field(None, description="文件名")
    datasource: str = Field("未知", description="数据源名称")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    search_source: str = Field("hybrid", description="搜索来源：vector、keyword或hybrid")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "text": "这是一段匹配的文本内容...",
                "score": 0.92,
                "doc_id": "d8f7e6c5-b4a3-1234-5678-9012d3e4f5a6",
                "file_name": "企业介绍.pdf",
                "datasource": "primary",
                "search_source": "hybrid",
                "metadata": {
                    "page": 1,
                    "file_type": "pdf",
                    "author": "企业知识库"
                }
            }
        }
    )
    

class SearchResponse(BaseModel):
    """搜索响应模型"""
    
    query: str = Field(..., description="原始查询文本")
    results: List[SearchResult] = Field(default_factory=list, description="搜索结果列表")
    total: int = Field(..., description="结果总数")
    search_mode: SearchMode = Field(SearchMode.HYBRID, description="使用的搜索模式")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "query": "企业的主要产品",
                "results": [
                    {
                        "text": "我们公司的主要产品包括...",
                        "score": 0.92,
                        "doc_id": "d8f7e6c5-b4a3-1234-5678-9012d3e4f5a6",
                        "file_name": "企业介绍.pdf",
                        "datasource": "primary",
                        "search_source": "hybrid",
                        "metadata": {
                            "page": 1,
                            "file_type": "pdf"
                        }
                    }
                ],
                "total": 1,
                "search_mode": "hybrid"
            }
        }
    ) 