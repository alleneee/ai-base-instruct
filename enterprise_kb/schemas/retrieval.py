from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class DocumentAggregation(BaseModel):
    """文档聚合模型"""
    doc_id: str = Field(..., description="文档ID")
    doc_name: str = Field(..., description="文档名称")
    count: int = Field(..., description="块数量")


class RetrievedChunk(BaseModel):
    """检索到的块模型"""
    id: str = Field(..., description="块ID")
    content: str = Field(..., description="块内容")
    content_ltks: Optional[str] = Field(None, description="块内容本地化")
    document_id: str = Field(..., description="文档ID")
    document_keyword: str = Field(..., description="文档关键词")
    highlight: Optional[str] = Field(None, description="高亮内容")
    image_id: str = Field("", description="图片ID")
    important_keywords: List[str] = Field([], description="重要关键词")
    kb_id: str = Field(..., description="知识库ID")
    positions: List[str] = Field([], description="位置")
    similarity: float = Field(..., description="相似度")
    term_similarity: float = Field(..., description="术语相似度")
    vector_similarity: float = Field(..., description="向量相似度")


class RetrievalData(BaseModel):
    """检索数据模型"""
    chunks: List[RetrievedChunk] = Field(..., description="检索到的块列表")
    doc_aggs: List[DocumentAggregation] = Field(..., description="文档聚合")
    total: int = Field(..., description="总数")


class RetrievalResponse(BaseModel):
    """检索响应模型"""
    code: int = Field(0, description="状态码")
    data: RetrievalData = Field(..., description="检索数据")


class RetrievalRequest(BaseModel):
    """检索请求模型"""
    question: str = Field(..., description="问题")
    dataset_ids: Optional[List[str]] = Field(None, description="数据集ID列表")
    document_ids: Optional[List[str]] = Field(None, description="文档ID列表")
    page: Optional[int] = Field(1, description="页码")
    page_size: Optional[int] = Field(30, description="每页大小")
    similarity_threshold: Optional[float] = Field(0.2, description="相似度阈值")
    vector_similarity_weight: Optional[float] = Field(0.3, description="向量相似度权重")
    top_k: Optional[int] = Field(1024, description="参与向量余弦计算的块数量")
    rerank_id: Optional[str] = Field(None, description="重排序模型ID")
    keyword: Optional[bool] = Field(False, description="是否启用基于关键词的匹配")
    highlight: Optional[bool] = Field(False, description="是否在结果中高亮匹配项") 