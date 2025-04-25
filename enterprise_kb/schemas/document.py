from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field


class DocumentUpdate(BaseModel):
    """更新文档请求模型"""
    name: Optional[str] = Field(None, description="文档名称")
    meta_fields: Optional[Dict[str, Any]] = Field(None, description="元字段")
    chunk_method: Optional[str] = Field(None, description="分块方法")
    parser_config: Optional[Dict[str, Any]] = Field(None, description="解析器配置")


class DocumentDeleteRequest(BaseModel):
    """删除文档请求模型"""
    ids: List[str] = Field(..., description="要删除的文档ID列表")


class DocumentParseRequest(BaseModel):
    """解析文档请求模型"""
    document_ids: List[str] = Field(..., description="要解析的文档ID列表")


class Document(BaseModel):
    """文档模型"""
    id: str = Field(..., description="文档ID")
    name: str = Field(..., description="文档名称")
    location: str = Field(..., description="位置")
    size: int = Field(..., description="大小")
    type: str = Field(..., description="类型")
    thumbnail: Optional[str] = Field(None, description="缩略图")
    run: str = Field(..., description="运行状态")
    chunk_method: str = Field(..., description="分块方法")
    parser_config: Dict[str, Any] = Field(..., description="解析器配置")
    dataset_id: str = Field(..., description="数据集ID")
    created_by: str = Field(..., description="创建者ID")
    
    # 以下是文档处理相关字段，仅在返回已处理文档时包含
    chunk_count: Optional[int] = Field(None, description="块数量")
    token_count: Optional[int] = Field(None, description="令牌数量")
    process_begin_at: Optional[datetime] = Field(None, description="处理开始时间")
    process_duation: Optional[float] = Field(None, description="处理持续时间")
    progress: Optional[float] = Field(None, description="进度")
    progress_msg: Optional[str] = Field(None, description="进度消息")
    source_type: Optional[str] = Field(None, description="源类型")
    status: Optional[str] = Field(None, description="状态")
    create_date: Optional[datetime] = Field(None, description="创建日期")
    update_date: Optional[datetime] = Field(None, description="更新日期")
    create_time: Optional[int] = Field(None, description="创建时间戳")
    update_time: Optional[int] = Field(None, description="更新时间戳")


class DocumentUploadResponse(BaseModel):
    """文档上传响应模型"""
    code: int = Field(0, description="状态码")
    data: List[Document] = Field(..., description="上传的文档列表")


class DocumentListData(BaseModel):
    """文档列表数据模型"""
    docs: List[Document] = Field(..., description="文档列表")
    total: int = Field(..., description="总数")


class DocumentListResponse(BaseModel):
    """文档列表响应模型"""
    code: int = Field(0, description="状态码")
    data: DocumentListData = Field(..., description="文档列表数据") 