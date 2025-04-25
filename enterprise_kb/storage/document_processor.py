"""文档处理器模块"""
import os
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, BinaryIO
from pathlib import Path

from llama_index.core import Document, Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter
from llama_index.readers.file import PyMuPDFReader, DocxReader, UnstructuredReader
from llama_index.embeddings.openai import OpenAIEmbedding

from enterprise_kb.core.config.settings import settings
from enterprise_kb.storage.vector_store import get_storage_context
from enterprise_kb.utils.milvus_client import get_milvus_client

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """文档处理器，用于加载、处理和索引文档"""
    
    def __init__(self):
        """初始化文档处理器"""
        # 设置LlamaIndex全局配置
        Settings.embed_model = OpenAIEmbedding()
        Settings.chunk_size = settings.LLAMA_INDEX_CHUNK_SIZE
        Settings.chunk_overlap = settings.LLAMA_INDEX_CHUNK_OVERLAP
        
        # 创建文档存储目录
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
        
        # 初始化Milvus客户端
        self.vector_store_client = get_milvus_client()
        
        # 初始化LlamaIndex存储上下文
        self.storage_context = get_storage_context()
        
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
        self.ingestion_pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(
                    chunk_size=settings.LLAMA_INDEX_CHUNK_SIZE,
                    chunk_overlap=settings.LLAMA_INDEX_CHUNK_OVERLAP
                )
            ],
            vector_store=self.storage_context.vector_store
        )
    
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
    
    def process_document(
        self, 
        file_path: str, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """处理文档并索引到向量存储"""
        try:
            # 准备元数据
            if metadata is None:
                metadata = {}
                
            # 添加基本元数据
            file_name = os.path.basename(file_path)
            doc_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            base_metadata = {
                "doc_id": doc_id,
                "file_name": file_name,
                "file_path": file_path,
                "file_type": os.path.splitext(file_path)[1].lower(),
                "upload_time": now,
                "process_time": now
            }
            
            # 合并元数据
            metadata = {**base_metadata, **metadata}
            
            # 加载文档
            reader = self.get_reader_for_file(file_path)
            documents = reader.load(file_path)
            
            # 添加元数据到文档
            for doc in documents:
                doc.metadata.update(metadata)
                
            # 处理文档并索引
            nodes = self.ingestion_pipeline.run(documents=documents)
            
            # 返回处理结果
            result = {
                "doc_id": doc_id,
                "file_name": file_name,
                "metadata": metadata,
                "status": "success",
                "node_count": len(nodes),
                "text_chars": sum(len(node.get_content()) for node in nodes)
            }
            
            logger.info(f"成功处理文档: {file_name}, ID: {doc_id}")
            return result
            
        except Exception as e:
            logger.error(f"处理文档失败: {str(e)}")
            raise
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档及其向量数据"""
        try:
            # 删除向量数据
            self.vector_store_client.delete(f"doc_id == '{doc_id}'")
            
            # 可以在这里添加删除原始文件的逻辑
            logger.info(f"成功删除文档 ID: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            return False

# 创建单例实例
_document_processor = None

def get_document_processor() -> DocumentProcessor:
    """获取文档处理器单例"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor 