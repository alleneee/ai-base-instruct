"""文档处理模块，用于处理和索引文档"""
import os
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from llama_index.core import Document, Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.readers.file import PyMuPDFReader, DocxReader, UnstructuredReader
from llama_index.embeddings.openai import OpenAIEmbedding

from enterprise_kb.core.config.settings import settings
from enterprise_kb.storage.vector_store_manager import get_vector_store_manager

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """文档处理器，用于加载、处理和索引文档"""
    
    def __init__(self, default_datasource: str = "primary"):
        """初始化文档处理器
        
        Args:
            default_datasource: 默认数据源名称
        """
        # 设置LlamaIndex全局配置
        Settings.embed_model = OpenAIEmbedding()
        Settings.chunk_size = settings.LLAMA_INDEX_CHUNK_SIZE
        Settings.chunk_overlap = settings.LLAMA_INDEX_CHUNK_OVERLAP
        
        # 创建文档存储目录
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
        
        # 获取向量存储管理器
        self.vector_store_manager = get_vector_store_manager()
        self.default_datasource = default_datasource
        
        # 创建文档加载器映射
        self.file_readers = {
            ".pdf": PyMuPDFReader(),
            ".docx": DocxReader(),
            ".doc": UnstructuredReader(),
            ".txt": UnstructuredReader(),
            ".md": UnstructuredReader(),
            ".ppt": UnstructuredReader(),
            ".pptx": UnstructuredReader(),
        }
        
        # 创建摘要管道
        self.ingestion_pipeline = None
    
    def get_reader_for_file(self, file_path: str):
        """根据文件扩展名获取合适的文档读取器"""
        file_ext = os.path.splitext(file_path)[1].lower()
        reader = self.file_readers.get(file_ext)
        
        if not reader:
            raise ValueError(f"不支持的文件类型: {file_ext}")
            
        return reader
    
    def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """保存上传的文件并返回唯一文件ID"""
        # 生成唯一ID
        file_id = str(uuid.uuid4())
        
        # 确保文件名唯一
        file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{filename}")
        
        # 写入文件
        with open(file_path, "wb") as f:
            f.write(file_content)
            
        logger.info(f"保存上传的文件: {file_path}")
        return file_path
    
    async def process_document(
        self, 
        file_path: str, 
        metadata: Optional[Dict[str, Any]] = None,
        datasource_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """处理文档并索引到向量存储
        
        Args:
            file_path: 文件路径
            metadata: 文档元数据
            datasource_name: 数据源名称，如果为None则使用默认数据源
            
        Returns:
            处理结果
            
        Raises:
            ValueError: 处理失败
        """
        try:
            # 使用默认数据源（如果未指定）
            if datasource_name is None:
                datasource_name = self.default_datasource
                
            # 检查数据源是否存在
            data_sources = await self.vector_store_manager.list_data_sources()
            datasource_exists = any(ds.name == datasource_name for ds in data_sources)
            
            if not datasource_exists:
                raise ValueError(f"数据源 '{datasource_name}' 不存在")
                
            # 准备元数据
            if metadata is None:
                metadata = {}
                
            # 添加基本元数据
            file_name = os.path.basename(file_path)
            doc_id = metadata.get("doc_id", str(uuid.uuid4()))
            now = datetime.now().isoformat()
            
            base_metadata = {
                "doc_id": doc_id,
                "file_name": file_name,
                "file_path": file_path,
                "file_type": os.path.splitext(file_path)[1].lower(),
                "upload_time": now,
                "process_time": now,
                "datasource": datasource_name
            }
            
            # 合并元数据
            metadata = {**base_metadata, **metadata}
            
            # 加载文档
            reader = self.get_reader_for_file(file_path)
            documents = reader.load(file_path)
            
            # 添加元数据到文档
            for doc in documents:
                doc.metadata.update(metadata)
            
            # 创建节点解析器
            node_parser = SentenceSplitter(
                chunk_size=settings.LLAMA_INDEX_CHUNK_SIZE,
                chunk_overlap=settings.LLAMA_INDEX_CHUNK_OVERLAP
            )
            
            # 解析文档为节点
            nodes = node_parser.get_nodes_from_documents(documents)
            
            # 向数据源添加节点
            node_ids = await self.vector_store_manager.add_nodes(nodes, datasource_name)
            
            # 返回处理结果
            result = {
                "doc_id": doc_id,
                "file_name": file_name,
                "metadata": metadata,
                "status": "success",
                "node_count": len(nodes),
                "text_chars": sum(len(node.text) for node in nodes),
                "datasource": datasource_name
            }
            
            logger.info(f"成功处理文档: {file_name}, ID: {doc_id}, 数据源: {datasource_name}")
            return result
            
        except Exception as e:
            logger.error(f"处理文档失败: {str(e)}")
            raise
    
    async def delete_document(self, doc_id: str, datasource_name: Optional[str] = None) -> bool:
        """删除文档及其向量数据
        
        Args:
            doc_id: 文档ID
            datasource_name: 数据源名称，如果为None则从所有数据源删除
            
        Returns:
            是否成功删除
        """
        try:
            # 从向量存储删除
            return await self.vector_store_manager.delete_nodes(doc_id, datasource_name)
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            return False

# 创建单例实例
_document_processor = None

async def get_document_processor() -> DocumentProcessor:
    """获取文档处理器单例"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
        
        # 确保至少有一个默认数据源（Milvus）
        try:
            vector_store_manager = get_vector_store_manager()
            data_sources = await vector_store_manager.list_data_sources()
            
            if not any(ds.name == "primary" for ds in data_sources):
                # 创建默认Milvus数据源
                await vector_store_manager.add_data_source(
                    source_type="milvus",
                    name="primary",
                    config={
                        "description": "默认向量存储",
                        "host": settings.MILVUS_HOST,
                        "port": settings.MILVUS_PORT,
                        "collection_name": settings.MILVUS_COLLECTION,
                        "dimension": settings.MILVUS_DIMENSION
                    }
                )
                logger.info("创建默认Milvus数据源: primary")
        except Exception as e:
            logger.error(f"创建默认数据源失败: {str(e)}")
    
    return _document_processor 