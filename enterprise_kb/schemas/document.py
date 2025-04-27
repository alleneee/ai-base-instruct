from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    """文档基础模型"""
    title: Optional[str] = Field(None, description="文档标题")
    description: Optional[str] = Field(None, description="文档描述")
    file_type: Optional[str] = Field(None, description="文件类型")
    

class DocumentCreate(DocumentBase):
    """文档创建模型"""
    tags: Optional[List[str]] = Field(default_factory=list, description="文档标签")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="元数据")
    source: Optional[str] = Field(None, description="文档来源")
    convert_to_markdown: bool = Field(True, description="是否转换为Markdown格式")
    

class DocumentResponse(DocumentBase):
    """文档响应模型"""
    id: str = Field(..., description="文档ID")
    file_name: str = Field(..., description="文件名")
    file_path: str = Field(..., description="文件路径")
    created_at: datetime = Field(..., description="创建时间")
    updated_at: Optional[datetime] = Field(None, description="更新时间")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    tags: List[str] = Field(default_factory=list, description="文档标签")
    node_count: Optional[int] = Field(None, description="节点数量")
    status: str = Field("active", description="文档状态")
    

class DocumentUpdate(BaseModel):
    """文档更新模型"""
    title: Optional[str] = Field(None, description="文档标题")
    description: Optional[str] = Field(None, description="文档描述")
    tags: Optional[List[str]] = Field(None, description="文档标签")
    metadata: Optional[Dict[str, Any]] = Field(None, description="元数据")
    status: Optional[str] = Field(None, description="文档状态")
    

class DocumentFilter(BaseModel):
    """文档筛选模型"""
    tags: Optional[List[str]] = Field(None, description="按标签筛选")
    file_type: Optional[str] = Field(None, description="按文件类型筛选")
    status: Optional[str] = Field(None, description="按状态筛选")
    created_after: Optional[datetime] = Field(None, description="创建时间晚于")
    created_before: Optional[datetime] = Field(None, description="创建时间早于")
    search_text: Optional[str] = Field(None, description="全文搜索")
    

class MarkdownDocument(BaseModel):
    """Markdown文档模型"""
    id: str = Field(..., description="文档ID")
    content: str = Field(..., description="Markdown内容")
    original_file_path: Optional[str] = Field(None, description="原始文件路径")
    original_file_type: Optional[str] = Field(None, description="原始文件类型")
    markdown_path: str = Field(..., description="Markdown文件路径")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="元数据")
    created_at: datetime = Field(..., description="创建时间")
    

class DocumentConversionRequest(BaseModel):
    """文档转换请求模型"""
    doc_id: str = Field(..., description="文档ID")
    convert_to_markdown: bool = Field(True, description="是否转换为Markdown格式")
    force_reconvert: bool = Field(False, description="强制重新转换")
    

class DocumentConversionResponse(BaseModel):
    """文档转换响应模型"""
    doc_id: str = Field(..., description="文档ID")
    status: str = Field(..., description="转换状态")
    markdown_path: Optional[str] = Field(None, description="Markdown文件路径")
    message: Optional[str] = Field(None, description="消息")


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