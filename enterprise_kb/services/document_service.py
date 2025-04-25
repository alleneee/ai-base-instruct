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

logger = logging.getLogger(__name__)

# 文档元数据存储路径
METADATA_DIR = os.path.join("data", "metadata")
os.makedirs(METADATA_DIR, exist_ok=True)

class DocumentService:
    """文档服务，管理文档元数据和处理文档"""
    
    def __init__(self):
        """初始化文档服务"""
        self.processor = None
        
    async def _get_processor(self):
        """获取文档处理器实例"""
        if self.processor is None:
            self.processor = await get_document_processor()
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
    
    def _to_document_response(self, metadata: Dict[str, Any]) -> DocumentResponse:
        """将元数据转换为文档响应对象"""
        doc_metadata = DocumentMetadata(**metadata.get("metadata", {}))
        
        return DocumentResponse(
            doc_id=metadata.get("doc_id"),
            file_name=metadata.get("file_name"),
            title=metadata.get("title"),
            description=metadata.get("description"),
            file_type=metadata.get("file_type"),
            status=metadata.get("status", DocumentStatus.COMPLETED),
            created_at=metadata.get("created_at"),
            updated_at=metadata.get("updated_at"),
            metadata=doc_metadata,
            node_count=metadata.get("node_count"),
            size_bytes=metadata.get("size_bytes"),
            datasource=metadata.get("datasource", "primary")
        )
    
    async def create_document(
        self, 
        file: BinaryIO,
        filename: str,
        document_data: DocumentCreate,
        datasource: Optional[str] = None
    ) -> DocumentResponse:
        """
        创建新文档
        
        Args:
            file: 上传的文件对象
            filename: 文件名
            document_data: 文档元数据
            datasource: 数据源名称，默认使用配置的默认数据源
            
        Returns:
            创建的文档响应
        """
        try:
            # 获取处理器
            processor = await self._get_processor()
            
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
            
            # 创建元数据对象
            metadata = {
                "doc_id": doc_id,
                "file_name": filename,
                "title": document_data.title or os.path.splitext(filename)[0],
                "description": document_data.description,
                "file_type": file_type,
                "file_path": file_path,
                "status": DocumentStatus.PROCESSING,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "metadata": document_data.metadata.dict() if document_data.metadata else {},
                "size_bytes": file_size,
                "datasource": datasource
            }
            
            # 保存元数据
            self._save_metadata(doc_id, metadata)
            
            # 异步处理文档（在实际项目中，这应该是一个后台任务）
            try:
                # 处理文档并索引
                process_result = await processor.process_document(
                    file_path=file_path,
                    metadata={
                        "doc_id": doc_id,
                        "title": metadata["title"],
                        "description": metadata.get("description"),
                        **metadata["metadata"]
                    },
                    datasource_name=datasource
                )
                
                # 更新元数据
                metadata["status"] = DocumentStatus.COMPLETED
                metadata["node_count"] = process_result["node_count"]
                metadata["datasource"] = process_result.get("datasource", "primary")
                metadata["updated_at"] = datetime.now().isoformat()
                self._save_metadata(doc_id, metadata)
                
            except Exception as e:
                # 处理失败
                logger.error(f"文档处理失败: {str(e)}")
                metadata["status"] = DocumentStatus.FAILED
                metadata["error"] = str(e)
                metadata["updated_at"] = datetime.now().isoformat()
                self._save_metadata(doc_id, metadata)
                raise
            
            return self._to_document_response(metadata)
            
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
        metadata = self._load_metadata(doc_id)
        if not metadata:
            return None
            
        return self._to_document_response(metadata)
    
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
        metadata = self._load_metadata(doc_id)
        if not metadata:
            return None
            
        # 更新元数据
        if update_data.title is not None:
            metadata["title"] = update_data.title
            
        if update_data.description is not None:
            metadata["description"] = update_data.description
            
        if update_data.metadata is not None:
            metadata["metadata"] = update_data.metadata.dict()
            
        metadata["updated_at"] = datetime.now().isoformat()
        
        # 保存更新后的元数据
        self._save_metadata(doc_id, metadata)
        
        return self._to_document_response(metadata)
    
    async def delete_document(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            删除是否成功
        """
        metadata = self._load_metadata(doc_id)
        if not metadata:
            return False
            
        # 获取处理器
        processor = await self._get_processor()
        
        # 删除向量数据
        try:
            await processor.delete_document(doc_id)
        except Exception as e:
            logger.error(f"删除向量数据失败: {str(e)}")
        
        # 删除文件
        try:
            file_path = metadata.get("file_path")
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.error(f"删除文件失败: {str(e)}")
        
        # 删除元数据
        try:
            metadata_path = self._get_metadata_path(doc_id)
            if os.path.exists(metadata_path):
                os.remove(metadata_path)
        except Exception as e:
            logger.error(f"删除元数据失败: {str(e)}")
            
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
        documents = []
        
        # 遍历元数据目录
        for filename in os.listdir(METADATA_DIR):
            if not filename.endswith(".json"):
                continue
                
            doc_id = filename.replace(".json", "")
            metadata = self._load_metadata(doc_id)
            
            if not metadata:
                continue
                
            # 应用状态过滤
            if status and metadata.get("status") != status:
                continue
                
            # 应用数据源过滤
            if datasource and metadata.get("datasource") != datasource:
                continue
                
            documents.append(self._to_document_response(metadata))
            
        # 排序、分页
        documents.sort(key=lambda x: x.updated_at, reverse=True)
        paginated_docs = documents[skip:skip+limit]
        
        return DocumentList(
            total=len(documents),
            documents=paginated_docs
        ) 