"""索引服务相关的Celery任务"""
import time
from typing import Dict, List, Any, Optional
import traceback

from celery.utils.log import get_task_logger

from enterprise_kb.core.unified_celery import celery_app as app
from enterprise_kb.utils.logging import get_logger
from enterprise_kb.services.index.manager import IndexManager
from enterprise_kb.db.repositories.document import DocumentRepository
from enterprise_kb.db.repositories.collection import CollectionRepository
from enterprise_kb.db.models.document import DocumentStatus
from enterprise_kb.services.index.service import IndexService

# 获取任务日志器
logger = get_task_logger(__name__)
service_logger = get_logger(__name__)


@celery_app.task(
    name="index.index_document",
    queue="indexing",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
)
def index_document(
    self,
    document_id: str,
    collection_id: str,
    force_update: bool = False,
) -> Dict[str, Any]:
    """
    索引单个文档
    
    Args:
        document_id: 文档ID
        collection_id: 集合ID
        force_update: 是否强制更新索引，即使文档已经被索引
        
    Returns:
        包含操作结果的字典
    """
    logger.info(f"开始索引文档: document_id={document_id}, collection_id={collection_id}")
    
    document_repo = DocumentRepository()
    
    try:
        # 获取文档
        document = document_repo.get_by_id(document_id)
        if not document:
            error_msg = f"文档不存在: document_id={document_id}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
        
        # 检查文档状态
        if document.status != DocumentStatus.PROCESSED and not force_update:
            error_msg = f"文档状态不适合索引: document_id={document_id}, status={document.status}"
            logger.warning(error_msg)
            return {"success": False, "message": error_msg}
        
        # 更新文档状态为索引中
        document_repo.update(document_id, {"status": DocumentStatus.INDEXING})
        
        # 执行索引操作
        index_service = IndexService()
        index_result = index_service.index_document(document, collection_id)
        
        # 更新文档状态为已索引
        document_repo.update(document_id, {"status": DocumentStatus.INDEXED})
        
        logger.info(f"文档索引成功: document_id={document_id}")
        return {
            "success": True,
            "message": "文档索引成功",
            "document_id": document_id,
            "index_result": index_result
        }
        
    except Exception as e:
        logger.error(f"文档索引失败: document_id={document_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        
        # 更新文档状态为索引失败
        document_repo.update(document_id, {"status": DocumentStatus.INDEX_FAILED})
        
        # 记录异常并重试
        self.retry(exc=e)
        
        return {
            "success": False,
            "message": f"文档索引失败: {str(e)}",
            "document_id": document_id
        }


@celery_app.task(
    name="index.reindex_collection",
    queue="indexing",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def reindex_collection(
    self,
    collection_id: str,
    force_update: bool = False,
) -> Dict[str, Any]:
    """
    重新索引集合中的所有已处理文档
    
    Args:
        collection_id: 集合ID
        force_update: 是否强制更新索引，即使文档已经被索引
        
    Returns:
        包含操作结果的字典
    """
    logger.info(f"开始重新索引集合: collection_id={collection_id}")
    
    document_repo = DocumentRepository()
    collection_repo = CollectionRepository()
    
    try:
        # 检查集合是否存在
        collection = collection_repo.get_by_id(collection_id)
        if not collection:
            error_msg = f"集合不存在: collection_id={collection_id}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
        
        # 获取集合中已处理的文档
        documents = document_repo.get_by_collection_id(
            collection_id,
            status=DocumentStatus.PROCESSED if not force_update else None
        )
        
        if not documents:
            logger.warning(f"集合中没有可索引的文档: collection_id={collection_id}")
            return {
                "success": True,
                "message": "集合中没有可索引的文档",
                "count": 0
            }
        
        logger.info(f"找到 {len(documents)} 个文档需要索引: collection_id={collection_id}")
        
        # 对每个文档创建索引任务
        for document in documents:
            index_document.delay(document.id, collection_id, force_update)
        
        return {
            "success": True,
            "message": f"已提交 {len(documents)} 个文档的索引任务",
            "count": len(documents)
        }
        
    except Exception as e:
        logger.error(f"重新索引集合失败: collection_id={collection_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        
        # 记录异常并重试
        self.retry(exc=e)
        
        return {
            "success": False,
            "message": f"重新索引集合失败: {str(e)}",
            "collection_id": collection_id
        }


@celery_app.task(
    name="index.batch_index_documents",
    queue="indexing",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def batch_index_documents(
    self,
    document_ids: List[str],
    collection_id: str,
    force_update: bool = False,
) -> Dict[str, Any]:
    """
    批量索引多个文档
    
    Args:
        document_ids: 文档ID列表
        collection_id: 集合ID
        force_update: 是否强制更新索引，即使文档已经被索引
        
    Returns:
        包含操作结果的字典
    """
    logger.info(f"开始批量索引文档: collection_id={collection_id}, document_count={len(document_ids)}")
    
    document_repo = DocumentRepository()
    collection_repo = CollectionRepository()
    
    try:
        # 检查集合是否存在
        collection = collection_repo.get_by_id(collection_id)
        if not collection:
            error_msg = f"集合不存在: collection_id={collection_id}"
            logger.error(error_msg)
            return {"success": False, "message": error_msg}
        
        successful_count = 0
        failed_count = 0
        skipped_count = 0
        
        # 对每个文档创建索引任务
        for doc_id in document_ids:
            # 检查文档状态
            document = document_repo.get_by_id(doc_id)
            
            if not document:
                logger.warning(f"文档不存在: document_id={doc_id}")
                skipped_count += 1
                continue
                
            if document.status != DocumentStatus.PROCESSED and not force_update:
                logger.info(f"跳过文档索引 (状态不适合): document_id={doc_id}, status={document.status}")
                skipped_count += 1
                continue
            
            try:
                # 创建索引任务
                index_document.delay(doc_id, collection_id, force_update)
                successful_count += 1
            except Exception as e:
                logger.error(f"提交索引任务失败: document_id={doc_id}, error={str(e)}")
                failed_count += 1
        
        logger.info(
            f"批量索引任务提交完成: 成功={successful_count}, "
            f"失败={failed_count}, 跳过={skipped_count}"
        )
        
        return {
            "success": True,
            "message": "批量索引任务已提交",
            "stats": {
                "total": len(document_ids),
                "successful": successful_count,
                "failed": failed_count,
                "skipped": skipped_count
            }
        }
        
    except Exception as e:
        logger.error(f"批量索引文档失败: collection_id={collection_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        
        # 记录异常并重试
        self.retry(exc=e)
        
        return {
            "success": False,
            "message": f"批量索引文档失败: {str(e)}",
            "collection_id": collection_id
        }


@celery_app.task(
    name="index.delete_document_from_index",
    queue="indexing",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def delete_document_from_index(
    self,
    document_id: str,
    collection_id: str,
) -> Dict[str, Any]:
    """
    从索引中删除文档
    
    Args:
        document_id: 文档ID
        collection_id: 集合ID
        
    Returns:
        包含操作结果的字典
    """
    logger.info(f"开始从索引中删除文档: document_id={document_id}, collection_id={collection_id}")
    
    document_repo = DocumentRepository()
    
    try:
        # 获取文档
        document = document_repo.get_by_id(document_id)
        if not document:
            logger.warning(f"文档不存在，无需从索引中删除: document_id={document_id}")
            return {
                "success": True,
                "message": "文档不存在，无需从索引中删除",
                "document_id": document_id
            }
        
        # 执行从索引中删除文档
        index_service = IndexService()
        index_service.delete_document_from_index(document_id, collection_id)
        
        # 更新文档状态
        document_repo.update(document_id, {"status": DocumentStatus.PROCESSED})
        
        logger.info(f"文档已从索引中删除: document_id={document_id}")
        return {
            "success": True,
            "message": "文档已从索引中删除",
            "document_id": document_id
        }
        
    except Exception as e:
        logger.error(f"从索引中删除文档失败: document_id={document_id}, error={str(e)}")
        logger.error(traceback.format_exc())
        
        # 记录异常并重试
        self.retry(exc=e)
        
        return {
            "success": False,
            "message": f"从索引中删除文档失败: {str(e)}",
            "document_id": document_id
        } 