import os
import json
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, BinaryIO
from uuid import uuid4

from enterprise_kb.core.config.settings import settings
from enterprise_kb.models.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse, 
    DocumentStatus, DocumentMetadata, DocumentList
)
from enterprise_kb.core.document_processor import get_document_processor
from enterprise_kb.db.repositories.document_repository import DocumentRepository
from enterprise_kb.tasks.document_tasks import process_document_task

logger = logging.getLogger(__name__)

# 文档元数据存储路径
METADATA_DIR = os.path.join("data", "metadata")
os.makedirs(METADATA_DIR, exist_ok=True)

class DocumentService:
    """文档服务，管理文档元数据和处理文档"""
    
    def __init__(self, document_repository: DocumentRepository):
        """
        初始化文档服务
        
        Args:
            document_repository: 文档仓库
        """
        self.doc_repo = document_repository
        self.processor = None
        
    def _get_processor(self):
        """获取文档处理器实例"""
        if self.processor is None:
            self.processor = get_document_processor()
        return self.processor
        
    def _get_metadata_path(self, doc_id: str) -> str:
        """获取文档元数据文件路径"""
        return os.path.join(METADATA_DIR, f"{doc_id}.json")
    
    def _save_metadata(self, doc_id: str, metadata: Dict[str, Any]) -> None:
        """保存文档元数据到文件"""
        metadata_path = self._get_metadata_path(doc_id)
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, default=str)
    
    def _load_metadata(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """从文件加载文档元数据"""
        metadata_path = self._get_metadata_path(doc_id)
        if not os.path.exists(metadata_path):
            return None
            
        with open(metadata_path, "r", encoding="utf-8") as f:
            return json.load(f)
    
    def _to_document_response(self, document: Dict[str, Any]) -> DocumentResponse:
        """
        将文档数据转换为响应对象
        
        Args:
            document: 文档数据
            
        Returns:
            文档响应对象
        """
        doc_metadata = DocumentMetadata(**document.get("metadata", {}))
        
        return DocumentResponse(
            doc_id=document.get("doc_id") or document.get("id"),
            file_name=document.get("file_name"),
            title=document.get("title"),
            description=document.get("description"),
            file_type=document.get("file_type"),
            status=document.get("status", DocumentStatus.COMPLETED),
            created_at=document.get("created_at"),
            updated_at=document.get("updated_at"),
            metadata=doc_metadata,
            node_count=document.get("node_count"),
            size_bytes=document.get("size_bytes"),
            datasource=document.get("datasource", "primary")
        )
    
    async def create_document(
        self, 
        file: BinaryIO,
        filename: str,
        document_data: DocumentCreate,
        datasource: Optional[str] = None,
        custom_processors: Optional[List[str]] = None
    ) -> DocumentResponse:
        """
        创建新文档
        
        Args:
            file: 上传的文件对象
            filename: 文件名
            document_data: 文档元数据
            datasource: 数据源名称，默认使用配置的默认数据源
            custom_processors: 自定义处理器列表
            
        Returns:
            创建的文档响应
        """
        try:
            # 获取处理器
            processor = self._get_processor()
            
            # 读取文件内容
            file_content = file.read()
            file_size = len(file_content)
            
            # 生成文档ID
            doc_id = str(uuid4())
            now = datetime.now()
            
            # 保存文件
            file_path = processor.save_uploaded_file(file_content, filename)
            
            # 获取文件类型
            file_type = os.path.splitext(filename)[1].lower().lstrip(".")
            
            # 创建文档记录
            document = {
                "id": doc_id,
                "file_name": filename,
                "file_path": file_path,
                "file_type": file_type,
                "title": document_data.title or os.path.splitext(filename)[0],
                "description": document_data.description,
                "status": DocumentStatus.PENDING,
                "size_bytes": file_size,
                "metadata": document_data.metadata.dict() if document_data.metadata else {},
                "datasource": datasource or settings.DEFAULT_DATASOURCE,
                "created_at": now,
                "updated_at": now
            }
            
            # 保存到数据库
            doc_id = await self.doc_repo.create(document)
            
            # 启动异步处理任务
            process_document_task.delay(
                doc_id=doc_id,
                file_path=file_path,
                metadata={
                    "doc_id": doc_id,
                    "title": document["title"],
                    "description": document.get("description"),
                    **(document["metadata"] or {})
                },
                datasource_name=datasource,
                custom_processors=custom_processors
            )
            
            # 返回文档响应
            return self._to_document_response(document)
            
        except Exception as e:
            logger.error(f"创建文档失败: {str(e)}")
            raise
    
    async def get_document(self, doc_id: str) -> Optional[DocumentResponse]:
        """
        获取文档信息
        
        Args:
            doc_id: 文档ID
            
        Returns:
            文档响应，如果不存在则返回None
        """
        document = await self.doc_repo.get(doc_id)
        if not document:
            return None
            
        return self._to_document_response(document)
    
    async def update_document(
        self, 
        doc_id: str, 
        update_data: DocumentUpdate
    ) -> Optional[DocumentResponse]:
        """
        更新文档信息
        
        Args:
            doc_id: 文档ID
            update_data: 更新数据
            
        Returns:
            更新后的文档响应，如果不存在则返回None
        """
        # 检查文档是否存在
        document = await self.doc_repo.get(doc_id)
        if not document:
            return None
            
        # 准备更新数据
        update_dict = {}
        if update_data.title is not None:
            update_dict["title"] = update_data.title
            
        if update_data.description is not None:
            update_dict["description"] = update_data.description
            
        if update_data.metadata is not None:
            update_dict["metadata"] = update_data.metadata.dict()
            
        # 执行更新
        if update_dict:
            update_dict["updated_at"] = datetime.now()
            await self.doc_repo.update(doc_id, update_dict)
            
        # 获取更新后的文档
        updated_document = await self.doc_repo.get(doc_id)
        return self._to_document_response(updated_document)
    
    async def delete_document(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            删除是否成功
        """
        # 获取文档信息
        document = await self.doc_repo.get(doc_id)
        if not document:
            return False
            
        # 获取处理器
        processor = self._get_processor()
        
        # 删除向量数据
        try:
            processor.delete_document(doc_id)
        except Exception as e:
            logger.error(f"删除向量数据失败: {str(e)}")
        
        # 删除文件
        try:
            file_path = document.get("file_path")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
        
        # 删除文档记录
        try:
            await self.doc_repo.delete(doc_id)
        except Exception as e:
            logger.error(f"删除文档记录失败: {str(e)}")
            return False
            
        return True
    
    async def list_documents(
        self, 
        skip: int = 0, 
        limit: int = 100,
        status: Optional[DocumentStatus] = None,
        datasource: Optional[str] = None
    ) -> DocumentList:
        """
        获取文档列表
        
        Args:
            skip: 跳过数量
            limit: 限制数量
            status: 文档状态过滤
            datasource: 数据源过滤
            
        Returns:
            文档列表响应
        """
        # 构建过滤条件
        filters = {}
        if status:
            filters["status"] = status
        if datasource:
            filters["datasource"] = datasource
            
        # 查询数据库
        documents, total = await self.doc_repo.get_many(
            skip=skip,
            limit=limit,
            filters=filters
        )
        
        # 转换为响应对象
        document_responses = [self._to_document_response(doc) for doc in documents]
        
        return DocumentList(
            total=total,
            documents=document_responses
        ) 