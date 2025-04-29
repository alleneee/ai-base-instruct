"""文档数据库模型模块"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import String, DateTime, JSON, Integer, ForeignKey, Table, Column
from sqlalchemy.orm import relationship, Mapped, mapped_column

from enterprise_kb.db.base import Base
from enterprise_kb.schemas.documents import DocumentStatus


# 文档模型
class DocumentModel(Base):
    """文档数据库模型"""
    __tablename__ = "documents"
    
    # 基本信息
    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # 处理状态
    status: Mapped[str] = mapped_column(
        String(20), 
        nullable=False, 
        default=DocumentStatus.PENDING.value
    )
    error: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # 统计信息
    size_bytes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    node_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # 时间戳
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=datetime.utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=datetime.utcnow, 
        onupdate=datetime.utcnow
    )
    
    # 元数据
    doc_metadata: Mapped[Dict[str, Any]] = mapped_column(
        JSON, 
        nullable=False, 
        default=dict
    )
    
    # 关系
    tags = relationship("DocumentTag", secondary="document_tag_link", back_populates="documents")


# 文档标签
class DocumentTag(Base):
    """文档标签模型"""
    __tablename__ = "document_tags"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # 关系
    documents = relationship("DocumentModel", secondary="document_tag_link", back_populates="tags")


# 文档标签关联表
document_tag_link = Table(
    "document_tag_link",
    Base.metadata,
    Column("document_id", String(50), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", Integer, ForeignKey("document_tags.id", ondelete="CASCADE"), primary_key=True),
) 