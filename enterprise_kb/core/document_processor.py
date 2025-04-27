"""文档处理器模块"""
import os
import logging
from typing import Dict, Any, Optional, List
from uuid import uuid4

from enterprise_kb.core.config.settings import settings
from enterprise_kb.core.document_pipeline.base import PipelineFactory

logger = logging.getLogger(__name__)

class DocumentProcessor:
    """文档处理器，处理上传的文档并索引"""
    
    def __init__(self):
        """初始化文档处理器"""
        self.upload_dir = settings.UPLOAD_DIR
        os.makedirs(self.upload_dir, exist_ok=True)
        
    def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """
        保存上传的文件
        
        Args:
            file_content: 文件内容
            filename: 文件名
            
        Returns:
            保存后的文件路径
        """
        file_id = str(uuid4())
        file_ext = os.path.splitext(filename)[1].lower()
        safe_filename = f"{file_id}{file_ext}"
        file_path = os.path.join(self.upload_dir, safe_filename)
        
        with open(file_path, "wb") as f:
            f.write(file_content)
            
        return file_path
        
    def process_document(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        datasource_name: Optional[str] = None,
        custom_processors: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        处理文档
        
        Args:
            file_path: 文件路径
            metadata: 文档元数据
            datasource_name: 数据源名称
            custom_processors: 自定义处理器列表
            
        Returns:
            处理结果
        """
        try:
            file_type = os.path.splitext(file_path)[1].lower().lstrip(".")
            
            # 创建处理上下文
            context = {
                "file_path": file_path,
                "file_type": file_type,
                "metadata": metadata,
                "datasource_name": datasource_name or settings.DEFAULT_DATASOURCE
            }
            
            # 创建并执行处理管道
            pipeline = PipelineFactory.create_pipeline(file_type, custom_processors)
            result_context = pipeline.process(context)
            
            # 返回处理结果
            return {
                "doc_id": metadata.get("doc_id"),
                "node_count": result_context.get("node_count", 0),
                "datasource": result_context.get("datasource_name", datasource_name or settings.DEFAULT_DATASOURCE),
                "chunks": len(result_context.get("chunks", [])),
                "status": "completed"
            }
            
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            raise
        
    def delete_document(self, doc_id: str) -> bool:
        """
        删除文档
        
        Args:
            doc_id: 文档ID
            
        Returns:
            是否成功删除
        """
        # 这里应该实现删除向量数据的逻辑
        # 简化示例，实际应连接到向量数据库
        try:
            logger.info(f"删除文档: {doc_id}")
            # 模拟删除操作
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            raise

# 单例处理器实例
_processor_instance = None

def get_document_processor() -> DocumentProcessor:
    """
    获取文档处理器实例
    
    Returns:
        文档处理器实例
    """
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = DocumentProcessor()
    return _processor_instance