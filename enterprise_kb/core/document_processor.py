"""文档处理器模块"""
import os
import logging
from typing import Dict, Any, Optional, List
from uuid import uuid4
from pathlib import Path
import asyncio
from datetime import datetime

from enterprise_kb.core.config.settings import settings
from enterprise_kb.core.document_pipeline.base import PipelineFactory
from enterprise_kb.db.repositories.document_repository import DocumentRepository
from enterprise_kb.schemas.documents import DocumentStatus

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
        custom_processors: Optional[List[str]] = None,
        use_markitdown: bool = True,
        convert_to_markdown: bool = True,
        store_metadata: bool = False
    ) -> Dict[str, Any]:
        """
        处理文档

        Args:
            file_path: 文件路径
            metadata: 文档元数据
            datasource_name: 数据源名称
            custom_processors: 自定义处理器列表
            use_markitdown: 是否使用MarkItDown处理器
            convert_to_markdown: 是否将文档转换为Markdown
            store_metadata: 是否将元数据存储到MySQL数据库

        Returns:
            处理结果
        """
        try:
            # 获取文件类型
            file_type = os.path.splitext(file_path)[1].lower().lstrip(".")

            # 创建处理上下文
            context = {
                "file_path": file_path,
                "file_type": file_type,
                "metadata": metadata,
                "datasource_name": datasource_name or settings.DEFAULT_DATASOURCE,
                "convert_to_markdown": convert_to_markdown
            }

            # 创建并执行处理管道
            pipeline = PipelineFactory.create_pipeline(
                file_type,
                custom_processors,
                use_markitdown=use_markitdown
            )
            result_context = pipeline.process(context)

            # 如果生成了Markdown内容并且需要保存，将其保存到文件
            if convert_to_markdown and "markdown_content" in result_context:
                md_file_path = self._save_markdown_content(file_path, result_context["markdown_content"])
                result_context["markdown_file_path"] = md_file_path

            # 处理结果
            result = {
                "doc_id": metadata.get("doc_id"),
                "node_count": result_context.get("node_count", 0),
                "datasource": result_context.get("datasource_name", datasource_name or settings.DEFAULT_DATASOURCE),
                "chunks": result_context.get("chunks", []),
                "chunk_count": len(result_context.get("chunks", [])),
                "markdown_file_path": result_context.get("markdown_file_path"),
                "document_structure": result_context.get("document_structure"),
                "status": "completed"
            }

            # 如果需要存储元数据到MySQL
            if store_metadata:
                # 异步存储元数据
                self._store_metadata_to_db(
                    doc_id=metadata.get("doc_id"),
                    file_path=file_path,
                    file_type=file_type,
                    result_context=result_context,
                    metadata=metadata
                )

            return result

        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            raise

    def _save_markdown_content(self, original_file_path: str, markdown_content: str) -> str:
        """
        保存Markdown内容到文件

        Args:
            original_file_path: 原始文件路径
            markdown_content: Markdown内容

        Returns:
            保存的Markdown文件路径
        """
        # 生成Markdown文件路径
        original_filename = Path(original_file_path).stem
        md_filename = f"{original_filename}_converted.md"
        md_file_path = os.path.join(self.upload_dir, md_filename)

        # 保存Markdown内容
        with open(md_file_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)

        return md_file_path

    def _store_metadata_to_db(
        self,
        doc_id: str,
        file_path: str,
        file_type: str,
        result_context: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> None:
        """
        将文档元数据存储到MySQL数据库

        Args:
            doc_id: 文档ID
            file_path: 文件路径
            file_type: 文件类型
            result_context: 处理结果上下文
            metadata: 原始元数据
        """
        try:
            # 获取文件名
            file_name = os.path.basename(file_path)

            # 获取文件大小
            file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0

            # 准备数据库记录
            document_data = {
                "id": doc_id,
                "file_name": file_name,
                "file_path": file_path,
                "file_type": file_type,
                "title": metadata.get("title", file_name),
                "description": metadata.get("description"),
                "status": DocumentStatus.COMPLETED.value,
                "size_bytes": file_size,
                "node_count": result_context.get("node_count", 0),
                "metadata": metadata,
                "created_at": datetime.now(),
                "updated_at": datetime.now()
            }

            # 创建异步任务存储元数据
            asyncio.create_task(self._async_store_metadata(document_data))

            logger.info(f"已创建异步任务存储文档元数据: {doc_id}")

        except Exception as e:
            logger.error(f"准备存储元数据失败: {str(e)}")

    async def _async_store_metadata(self, document_data: Dict[str, Any]) -> None:
        """
        异步存储元数据到数据库

        Args:
            document_data: 文档数据
        """
        try:
            # 创建文档仓库
            doc_repo = DocumentRepository()

            # 检查文档是否已存在
            existing_doc = await doc_repo.get(document_data["id"])

            if existing_doc:
                # 更新现有文档
                await doc_repo.update(document_data["id"], document_data)
                logger.info(f"更新文档元数据成功: {document_data['id']}")
            else:
                # 创建新文档
                await doc_repo.create(document_data)
                logger.info(f"创建文档元数据成功: {document_data['id']}")

        except Exception as e:
            logger.error(f"存储元数据到数据库失败: {str(e)}")

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