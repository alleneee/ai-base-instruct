"""文档模式(Schema)模块"""
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, validator, ConfigDict


class FileType(str, Enum):
    """支持的文件类型"""
    PDF = "pdf"
    DOCX = "docx"
    DOC = "doc"
    TXT = "txt"
    MD = "md"
    PPT = "ppt"
    PPTX = "pptx"
    CSV = "csv"
    XLSX = "xlsx"
    XLS = "xls"


class DocumentStatus(str, Enum):
    """文档处理状态"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentMetadata(BaseModel):
    """文档元数据"""
    title: Optional[str] = None
    author: Optional[str] = None
    source: Optional[str] = None
    created_at: Optional[datetime] = None
    tags: List[str] = Field(default_factory=list)
    custom_metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentCreate(BaseModel):
    """文档创建请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[DocumentMetadata] = Field(default_factory=DocumentMetadata)
    
    @validator('title')
    def title_not_empty(cls, v):
        if v is not None and len(v.strip()) == 0:
            raise ValueError('标题不能为空')
        return v


class DocumentResponse(BaseModel):
    """文档响应"""
    doc_id: str
    file_name: str
    title: Optional[str] = None
    description: Optional[str] = None
    file_type: str
    status: DocumentStatus
    created_at: datetime
    updated_at: datetime
    metadata: DocumentMetadata = Field(default_factory=DocumentMetadata)
    node_count: Optional[int] = None
    size_bytes: Optional[int] = None
    
    model_config = ConfigDict(from_attributes=True)


class DocumentList(BaseModel):
    """文档列表响应"""
    total: int
    documents: List[DocumentResponse]


class DocumentUpdate(BaseModel):
    """文档更新请求"""
    title: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[DocumentMetadata] = None


class DocumentTag(BaseModel):
    """文档标签"""
    id: Optional[int] = None
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True) 