"""
文档处理异步任务模块
"""
import os
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
import uuid
import traceback

from celery.utils.log import get_task_logger

from enterprise_kb.core.unified_celery import celery_app as app
from enterprise_kb.core.config.settings import settings
from enterprise_kb.services.document.processors import (
    PDFProcessor,
    DocxProcessor,
    TextProcessor,
    MarkdownProcessor,
    CSVProcessor,
    ExcelProcessor,
    PowerPointProcessor,
)
from enterprise_kb.services.index.service import IndexService
from enterprise_kb.utils.exceptions import ProcessingError
from enterprise_kb.db.models.document import Document, DocumentStatus
from enterprise_kb.db.repositories.document import DocumentRepository
from enterprise_kb.services.document.processor import DocumentProcessor
from enterprise_kb.db.repositories.collection import CollectionRepository
from enterprise_kb.services.index.tasks import reindex_collection, index_document
from enterprise_kb.utils.logging import get_logger

# 获取任务日志器
logger = get_task_logger(__name__)
service_logger = get_logger(__name__)

# 处理器映射
PROCESSOR_MAP = {
    ".pdf": PDFProcessor,
    ".docx": DocxProcessor,
    ".doc": DocxProcessor,
    ".txt": TextProcessor,
    ".md": MarkdownProcessor,
    ".csv": CSVProcessor,
    ".xlsx": ExcelProcessor,
    ".xls": ExcelProcessor,
    ".ppt": PowerPointProcessor,
    ".pptx": PowerPointProcessor,
}


@celery_app.task(
    name="document.process_document",
    queue="processing",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def process_document(
    self,
    document_id: str,
    auto_index: bool = True,
    processing_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    处理单个文档
    
    Args:
        document_id: 文档ID
        auto_index: 处理完成后是否自动索引
        processing_options: 处理选项
        
    Returns:
        包含操作结果的字典
    """
    logger.info(f"开始处理文档: document_id={document_id}, auto_index={auto_index}")
    
    document_repo = DocumentRepository()
    
    try:
        # 获取文档
        document = document_repo.get_by_id(document_id)
        if not document:
            error_msg = f"文档不存在: document_id={document_id}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
        
        # 检查文档状态
        if document.status == DocumentStatus.PROCESSED:
            logger.info(f"文档已处理完成，无需再次处理: document_id={document_id}")
            return {"success": True, "message": "文档已处理完成", "document_id": document_id}
        
        # 更新文档状态为处理中
        document_repo.update(document_id, {"status": DocumentStatus.PROCESSING})
        
        # 初始化文档处理器
        processor = DocumentProcessor()
        
        # 处理文档
        processing_result = processor.process_document(
            document=document,
            options=processing_options or {}
        )
        
        # 更新文档状态为已处理
        document_repo.update(
            document_id, 
            {
                "status": DocumentStatus.PROCESSED,
                "metadata": {
                    **document.metadata,
                    "processing_stats": processing_result.get("stats", {})
                }
            }
        )
        
        logger.info(f"文档处理成功: document_id={document_id}")
        
        # 如果需要自动索引，启动索引任务
        if auto_index:
            logger.info(f"启动文档索引任务: document_id={document_id}")
            index_document.delay(document_id, document.collection_id)
        
        return {
            "success": True,
            "message": "文档处理成功",
            "document_id": document_id,
            "processing_result": processing_result,
            "auto_index": auto_index
        }
        
    except Exception as e:
        logger.error(f"文档处理失败: document_id={document_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        
        # 更新文档状态为处理失败
        document_repo.update(
            document_id, 
            {
                "status": DocumentStatus.PROCESSING_FAILED,
                "metadata": {
                    **document.metadata if document else {},
                    "processing_error": str(e)
                }
            }
        )
        
        # 记录异常并重试
        self.retry(exc=e)
        
        return {
            "success": False,
            "message": f"文档处理失败: {str(e)}",
            "document_id": document_id
        }


@celery_app.task(
    name="document.process_collection",
    queue="documents",
)
def process_collection(
    self,
    collection_id: str,
    reindex: bool = True,
) -> Dict[str, Any]:
    """
    处理一个集合中的所有未处理文档
    
    Args:
        collection_id: 集合ID
        reindex: 处理完成后是否重新索引集合
    
    Returns:
        处理结果
    """
    logger.info(f"开始处理集合中的文档: {collection_id}")
    
    # 获取集合存储库和文档存储库
    collection_repo = CollectionRepository()
    doc_repo = DocumentRepository()
    
    # 检查集合是否存在
    collection = collection_repo.get_collection(collection_id)
    if not collection:
        logger.error(f"集合不存在: {collection_id}")
        return {"success": False, "error": f"集合不存在: {collection_id}"}
    
    # 获取所有待处理文档
    pending_docs = doc_repo.get_documents_by_status(
        collection_id=collection_id,
        status="pending"
    )
    
    if not pending_docs:
        logger.info(f"集合 {collection_id} 中没有待处理文档")
        return {"success": True, "processed_count": 0}
    
    # 为每个文档创建处理任务
    task_ids = []
    for doc in pending_docs:
        task = process_document.delay(
            document_id=doc.id,
            collection_id=collection_id,
            file_path=doc.file_path,
            metadata=doc.metadata
        )
        task_ids.append(task.id)
        
    # 如果需要重新索引，将在所有文档处理完成后触发
    if reindex and task_ids:
        logger.info(f"将在文档处理完成后重新索引集合: {collection_id}")
        # 使用chord组合，但由于Celery的chord在某些broker中可能不可靠
        # 所以这里通过设置countdown来延迟执行索引任务
        reindex_collection.apply_async(
            args=[collection_id],
            countdown=300,  # 5分钟后执行，假设文档处理会在此时间内完成
        )
    
    return {
        "success": True,
        "collection_id": collection_id,
        "processed_count": len(pending_docs),
        "task_ids": task_ids
    }


@celery_app.task(
    name="document.batch_process_documents",
    queue="processing",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def batch_process_documents(
    self,
    document_ids: List[str],
    auto_index: bool = True,
    processing_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    批量处理多个文档
    
    Args:
        document_ids: 文档ID列表
        auto_index: 处理完成后是否自动索引
        processing_options: 处理选项
        
    Returns:
        包含操作结果的字典
    """
    logger.info(f"开始批量处理文档: document_count={len(document_ids)}")
    
    document_repo = DocumentRepository()
    
    try:
        successful_count = 0
        failed_count = 0
        skipped_count = 0
        
        # 对每个文档创建处理任务
        for doc_id in document_ids:
            # 检查文档状态
            document = document_repo.get_by_id(doc_id)
            
            if not document:
                logger.warning(f"文档不存在: document_id={doc_id}")
                skipped_count += 1
                continue
                
            if document.status == DocumentStatus.PROCESSED:
                logger.info(f"文档已处理完成，跳过: document_id={doc_id}")
                skipped_count += 1
                continue
            
            try:
                # 创建处理任务
                process_document.delay(doc_id, auto_index, processing_options)
                successful_count += 1
            except Exception as e:
                logger.error(f"提交处理任务失败: document_id={doc_id}, error={str(e)}")
                failed_count += 1
        
        logger.info(
            f"批量处理任务提交完成: 成功={successful_count}, "
            f"失败={failed_count}, 跳过={skipped_count}"
        )
        
        return {
            "success": True,
            "message": "批量处理任务已提交",
            "stats": {
                "total": len(document_ids),
                "successful": successful_count,
                "failed": failed_count,
                "skipped": skipped_count
            }
        }
        
    except Exception as e:
        logger.error(f"批量处理文档失败: error={str(e)}")
        logger.error(traceback.format_exc())
        
        # 记录异常并重试
        self.retry(exc=e)
        
        return {
            "success": False,
            "message": f"批量处理文档失败: {str(e)}"
        }


@celery_app.task(
    bind=True,
    name="document.delete_document",
    queue="documents",
)
def delete_document(
    self, 
    document_id: str,
    delete_file: bool = False
) -> Dict[str, Any]:
    """
    删除文档及其相关数据
    
    Args:
        document_id: 文档ID
        delete_file: 是否同时删除文件
    
    Returns:
        删除结果
    """
    logger.info(f"开始删除文档: {document_id}")
    
    try:
        doc_repo = DocumentRepository()
        # 获取文档信息(用于之后可能的文件删除)
        document = doc_repo.get_document(document_id)
        
        if not document:
            logger.warning(f"要删除的文档不存在: {document_id}")
            return {"success": False, "error": "文档不存在"}
        
        # 删除文档数据
        doc_repo.delete_document(document_id)
        
        # 如果需要，删除文件
        if delete_file and document.file_path:
            if os.path.exists(document.file_path):
                os.remove(document.file_path)
                logger.info(f"已删除文档文件: {document.file_path}")
        
        return {
            "success": True,
            "document_id": document_id,
            "file_deleted": delete_file and document.file_path is not None
        }
    except Exception as e:
        logger.error(f"删除文档 {document_id} 失败: {str(e)}", exc_info=True)
        return {"success": False, "error": str(e)}


@celery_app.task(name="enterprise_kb.services.document.tasks.add_to_index")
def add_to_index(document_id: int) -> Dict[str, Any]:
    """
    将处理后的文档添加到索引
    
    Args:
        document_id: 文档ID
    
    Returns:
        索引结果信息
    """
    logger.info(f"开始为文档 {document_id} 创建索引")
    
    # 获取文档信息
    repo = DocumentRepository()
    document = repo.get_document_by_id_sync(document_id)
    
    if not document:
        error_msg = f"找不到ID为 {document_id} 的文档"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
    
    try:
        # 更新文档状态为索引中
        repo.update_document_status_sync(document_id, DocumentStatus.INDEXING)
        
        # 检查处理后的路径是否存在
        if not document.processed_path or not os.path.exists(document.processed_path):
            raise ProcessingError(f"处理后的文档不存在: {document.processed_path}")
        
        # 从处理后的文件中读取内容
        with open(document.processed_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # 创建索引服务实例
        index_service = IndexService()
        
        # 添加到索引
        index_result = index_service.add_document_to_index(
            document_id=document_id,
            content=content,
            metadata=document.metadata
        )
        
        # 更新文档状态为已索引
        repo.update_document_status_sync(
            document_id=document_id,
            status=DocumentStatus.INDEXED
        )
        
        logger.info(f"文档 {document_id} 索引成功")
        return {
            "success": True,
            "document_id": document_id,
            "index_result": index_result
        }
        
    except Exception as e:
        error_msg = f"为文档 {document_id} 创建索引时出错: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # 更新文档状态为索引失败
        repo.update_document_status_sync(
            document_id=document_id,
            status=DocumentStatus.INDEX_FAILED,
            error_message=str(e)
        )
        
        return {"success": False, "error": error_msg}


@celery_app.task(name="enterprise_kb.services.document.tasks.bulk_process_documents")
def bulk_process_documents(document_ids: List[int]) -> Dict[str, Any]:
    """
    批量处理多个文档
    
    Args:
        document_ids: 要处理的文档ID列表
    
    Returns:
        批处理结果信息
    """
    logger.info(f"开始批量处理 {len(document_ids)} 个文档")
    results = []
    
    for doc_id in document_ids:
        # 为每个文档创建一个异步任务
        task = process_document.delay(doc_id)
        results.append({"document_id": doc_id, "task_id": task.id})
    
    return {
        "success": True,
        "total": len(document_ids),
        "tasks": results
    }


@celery_app.task(name="enterprise_kb.services.document.tasks.scheduled_index_optimize")
def scheduled_index_optimize() -> Dict[str, Any]:
    """
    定时优化索引任务
    
    Returns:
        优化结果信息
    """
    logger.info("开始执行定时索引优化任务")
    
    try:
        # 创建索引服务实例
        index_service = IndexService()
        
        # 执行索引优化
        result = index_service.optimize_index()
        
        logger.info("索引优化成功完成")
        return {
            "success": True,
            "result": result
        }
        
    except Exception as e:
        error_msg = f"索引优化失败: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {
            "success": False,
            "error": error_msg
        }


def save_processed_document(
    document_id: int,
    file_name: str,
    content: str,
    metadata: Dict[str, Any]
) -> Path:
    """
    保存处理后的文档内容到文件

    Args:
        document_id: 文档ID
        file_name: 原始文件名
        content: 处理后的文本内容
        metadata: 文档元数据

    Returns:
        处理后文件的路径
    """
    # 创建处理后的目录
    doc_dir = Path(settings.PROCESSED_DIR) / f"doc_{document_id}"
    doc_dir.mkdir(exist_ok=True)
    
    # 保存处理后的内容到文本文件
    processed_path = doc_dir / f"{Path(file_name).stem}.txt"
    with open(processed_path, "w", encoding="utf-8") as f:
        f.write(content)
    
    # 保存元数据
    metadata_path = doc_dir / "metadata.json"
    import json
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    
    return processed_path


@celery_app.task(
    name="document.purge_document",
    queue="processing",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def purge_document(
    self,
    document_id: str,
    delete_file: bool = True,
) -> Dict[str, Any]:
    """
    清除文档（从索引和存储中）
    
    Args:
        document_id: 文档ID
        delete_file: 是否删除文件
        
    Returns:
        包含操作结果的字典
    """
    logger.info(f"开始清除文档: document_id={document_id}, delete_file={delete_file}")
    
    document_repo = DocumentRepository()
    
    try:
        # 获取文档
        document = document_repo.get_by_id(document_id)
        if not document:
            logger.warning(f"文档不存在，无需清除: document_id={document_id}")
            return {
                "success": True,
                "message": "文档不存在，无需清除",
                "document_id": document_id
            }
        
        # 如果文档已索引，则从索引中删除
        if document.status == DocumentStatus.INDEXED:
            from enterprise_kb.services.index.tasks import delete_document_from_index
            delete_document_from_index.delay(document_id, document.collection_id)
        
        # 如果需要删除文件
        if delete_file and document.file_path:
            file_path = Path(document.file_path)
            if file_path.exists():
                file_path.unlink()
                logger.info(f"已删除文档文件: {document.file_path}")
        
        # 从数据库中删除文档
        document_repo.delete(document_id)
        
        logger.info(f"文档已清除: document_id={document_id}")
        return {
            "success": True,
            "message": "文档已清除",
            "document_id": document_id
        }
        
    except Exception as e:
        logger.error(f"清除文档失败: document_id={document_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        
        # 记录异常并重试
        self.retry(exc=e)
        
        return {
            "success": False,
            "message": f"清除文档失败: {str(e)}",
            "document_id": document_id
        } 