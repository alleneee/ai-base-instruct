from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ParserConfig(BaseModel):
    """解析器配置模型"""
    chunk_token_num: Optional[int] = Field(128, description="块标记数量")
    delimiter: Optional[str] = Field("\\n", description="分隔符")
    html4excel: Optional[bool] = Field(False, description="是否将Excel文档转换为HTML格式")
    layout_recognize: Optional[bool] = Field(True, description="是否进行布局识别")
    task_page_size: Optional[int] = Field(12, description="每页任务数量，仅适用于PDF")
    raptor: Optional[Dict[str, Any]] = Field({"use_raptor": False}, description="Raptor特定设置")


class DatasetCreate(BaseModel):
    """创建数据集请求模型"""
    name: str = Field(..., description="数据集名称")
    avatar: Optional[str] = Field(None, description="头像（Base64编码）")
    description: Optional[str] = Field(None, description="数据集描述")
    embedding_model: Optional[str] = Field(None, description="嵌入模型名称")
    permission: Optional[str] = Field("me", description="权限设置，可选值：me, team")
    chunk_method: Optional[str] = Field("naive", description="分块方法")
    parser_config: Optional[ParserConfig] = Field(None, description="解析器配置")


class DatasetUpdate(BaseModel):
    """更新数据集请求模型"""
    name: Optional[str] = Field(None, description="数据集名称")
    embedding_model: Optional[str] = Field(None, description="嵌入模型名称")
    chunk_method: Optional[str] = Field(None, description="分块方法")


class DatasetDeleteRequest(BaseModel):
    """删除数据集请求模型"""
    ids: List[str] = Field(..., description="要删除的数据集ID列表")


class Dataset(BaseModel):
    """数据集模型"""
    id: str = Field(..., description="数据集ID")
    name: str = Field(..., description="数据集名称")
    avatar: Optional[str] = Field(None, description="头像")
    description: Optional[str] = Field(None, description="数据集描述")
    chunk_count: int = Field(0, description="块数量")
    chunk_method: str = Field(..., description="分块方法")
    document_count: int = Field(0, description="文档数量")
    embedding_model: str = Field(..., description="嵌入模型名称")
    language: str = Field("English", description="语言")
    parser_config: ParserConfig = Field(..., description="解析器配置")
    permission: str = Field(..., description="权限设置")
    similarity_threshold: float = Field(0.2, description="相似度阈值")
    status: str = Field("1", description="状态")
    token_num: int = Field(0, description="令牌数量")
    vector_similarity_weight: float = Field(0.3, description="向量相似度权重")
    created_by: str = Field(..., description="创建者ID")
    tenant_id: str = Field(..., description="租户ID")
    create_time: int = Field(..., description="创建时间戳")
    update_time: int = Field(..., description="更新时间戳")
    create_date: datetime = Field(..., description="创建日期")
    update_date: datetime = Field(..., description="更新日期")


class DatasetResponse(BaseModel):
    """数据集响应模型"""
    code: int = Field(0, description="状态码")
    data: Dataset = Field(..., description="数据集数据")


class DatasetListResponse(BaseModel):
    """数据集列表响应模型"""
    code: int = Field(0, description="状态码")
    data: List[Dataset] = Field(..., description="数据集列表") 