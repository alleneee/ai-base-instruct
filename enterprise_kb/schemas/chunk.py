from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field


class ChunkCreate(BaseModel):
    """创建块请求模型"""
    content: str = Field(..., description="块内容")
    important_keywords: Optional[List[str]] = Field([], description="重要关键词")
    questions: Optional[List[str]] = Field([], description="问题列表，如果有，嵌入的块将基于这些内容")


class ChunkUpdate(BaseModel):
    """更新块请求模型"""
    content: Optional[str] = Field(None, description="块内容")
    important_keywords: Optional[List[str]] = Field(None, description="重要关键词")
    available: Optional[bool] = Field(None, description="可用性状态")


class ChunkDeleteRequest(BaseModel):
    """删除块请求模型"""
    chunk_ids: List[str] = Field(..., description="要删除的块ID列表")


class ChunkData(BaseModel):
    """块数据模型"""
    id: str = Field(..., description="块ID")
    content: str = Field(..., description="块内容")
    document_id: str = Field(..., description="文档ID")
    dataset_id: str = Field(..., description="数据集ID")
    important_keywords: List[str] = Field([], description="重要关键词")
    questions: List[str] = Field([], description="问题列表")
    create_time: str = Field(..., description="创建时间")
    create_timestamp: float = Field(..., description="创建时间戳")


class ChunkResponse(BaseModel):
    """块响应模型"""
    code: int = Field(0, description="状态码")
    data: Dict[str, ChunkData] = Field(..., description="块数据")


class ChunkDetail(BaseModel):
    """块详细信息模型"""
    id: str = Field(..., description="块ID")
    content: str = Field(..., description="块内容")
    docnm_kwd: str = Field(..., description="文档名称关键词")
    document_id: str = Field(..., description="文档ID")
    image_id: str = Field("", description="图片ID")
    important_keywords: str = Field("", description="重要关键词，逗号分隔")
    positions: List[str] = Field([], description="位置")
    available: bool = Field(True, description="是否可用")


class DocumentWithChunks(BaseModel):
    """带有块的文档模型"""
    chunk_count: int = Field(..., description="块数量")
    chunk_method: str = Field(..., description="分块方法")
    create_date: str = Field(..., description="创建日期")
    create_time: int = Field(..., description="创建时间戳")
    created_by: str = Field(..., description="创建者ID")
    dataset_id: str = Field(..., description="数据集ID")
    id: str = Field(..., description="文档ID")
    location: str = Field(..., description="位置")
    name: str = Field(..., description="文档名称")
    parser_config: Dict[str, Any] = Field(..., description="解析器配置")
    process_begin_at: Optional[str] = Field(None, description="处理开始时间")
    process_duation: float = Field(0.0, description="处理持续时间")
    progress: float = Field(0.0, description="进度")
    progress_msg: str = Field("", description="进度消息")
    run: str = Field(..., description="运行状态")
    size: int = Field(..., description="大小")
    source_type: str = Field(..., description="源类型")
    status: str = Field(..., description="状态")
    thumbnail: Optional[str] = Field(None, description="缩略图")
    token_count: int = Field(..., description="令牌数量")
    type: str = Field(..., description="类型")
    update_date: str = Field(..., description="更新日期")
    update_time: int = Field(..., description="更新时间戳")


class ChunkListData(BaseModel):
    """块列表数据模型"""
    chunks: List[ChunkDetail] = Field(..., description="块列表")
    doc: DocumentWithChunks = Field(..., description="文档信息")
    total: int = Field(..., description="总数")


class ChunkListResponse(BaseModel):
    """块列表响应模型"""
    code: int = Field(0, description="状态码")
    data: ChunkListData = Field(..., description="块列表数据") 