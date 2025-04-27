"""
文档处理和索引更新的Celery任务

本模块包含用于异步处理文档和更新向量索引的Celery任务。
"""
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
import os

from enterprise_kb.core.unified_celery import celery_app
from enterprise_kb.core.config.settings import settings
from enterprise_kb.services.document_processor import DocumentProcessor
from enterprise_kb.services.vector_store import VectorStoreService
from enterprise_kb.services.ingestion_service import IngestionService
from enterprise_kb.db.repositories.document_repository import DocumentRepository
from enterprise_kb.db.repositories.index_repository import IndexRepository

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, name="process_document")
def process_document(self, file_path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    处理单个文档的Celery任务
    
    Args:
        file_path: 待处理文档的文件路径
        metadata: 文档的元数据信息
        
    Returns:
        Dict[str, Any]: 处理结果
    """
    try:
        logger.info(f"开始处理文档: {file_path}")
        
        # 创建服务实例
        doc_processor = DocumentProcessor()
        
        # 处理文档
        processed_result = doc_processor.process_file(file_path, metadata)
        
        logger.info(f"文档处理成功: {file_path}")
        return {
            "status": "success",
            "file_path": file_path,
            "processed_at": datetime.now().isoformat(),
            "chunks_count": processed_result.get("chunks_count", 0),
            "metadata": processed_result.get("metadata", {})
        }
    except Exception as e:
        logger.error(f"处理文档失败: {file_path}, 错误: {str(e)}")
        # 将异常信息保存到任务结果中
        self.update_state(
            state="FAILURE",
            meta={
                "status": "error",
                "file_path": file_path,
                "error": str(e),
                "traceback": str(e.__traceback__)
            }
        )
        raise

@celery_app.task(bind=True, name="batch_process_documents")
def batch_process_documents(self, file_paths: List[str], common_metadata: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    批量处理多个文档的Celery任务
    
    Args:
        file_paths: 待处理文档的文件路径列表
        common_metadata: 所有文档共享的元数据信息
        
    Returns:
        List[Dict[str, Any]]: 处理结果列表
    """
    logger.info(f"开始批量处理 {len(file_paths)} 个文档")
    
    results = []
    for idx, file_path in enumerate(file_paths):
        # 更新任务进度
        self.update_state(
            state="PROGRESS",
            meta={
                "current": idx,
                "total": len(file_paths),
                "status": f"处理中 {idx}/{len(file_paths)}"
            }
        )
        
        # 为每个文档创建元数据副本，避免修改原始元数据
        file_metadata = common_metadata.copy() if common_metadata else {}
        file_metadata.update({"batch_id": self.request.id, "index_in_batch": idx})
        
        try:
            # 处理单个文档
            result = process_document.delay(file_path, file_metadata)
            results.append({"task_id": result.id, "file_path": file_path})
        except Exception as e:
            logger.error(f"提交文档处理任务失败: {file_path}, 错误: {str(e)}")
            results.append({"file_path": file_path, "status": "error", "error": str(e)})
    
    logger.info(f"批量文档处理任务已提交，共 {len(file_paths)} 个文档")
    return results

@celery_app.task(bind=True, name="rebuild_index")
def rebuild_index(self) -> Dict[str, Any]:
    """
    重建向量索引的Celery任务
    
    Returns:
        Dict[str, Any]: 重建结果
    """
    try:
        logger.info("开始重建向量索引")
        
        # 创建向量存储服务实例
        vector_store = VectorStoreService()
        
        # 重建索引
        result = vector_store.rebuild_index()
        
        logger.info("向量索引重建成功")
        return {
            "status": "success",
            "completed_at": datetime.now().isoformat(),
            "index_info": result
        }
    except Exception as e:
        logger.error(f"重建向量索引失败，错误: {str(e)}")
        self.update_state(
            state="FAILURE",
            meta={
                "status": "error",
                "error": str(e)
            }
        )
        raise

@celery_app.task(name="scheduled_index_optimize")
def scheduled_index_optimize() -> Dict[str, Any]:
    """
    定时优化向量索引的Celery任务
    
    Returns:
        Dict[str, Any]: 优化结果
    """
    try:
        logger.info("开始定时优化向量索引")
        
        # 创建向量存储服务实例
        vector_store = VectorStoreService()
        
        # 执行索引优化
        result = vector_store.optimize_index()
        
        logger.info("向量索引优化成功")
        return {
            "status": "success",
            "optimized_at": datetime.now().isoformat(),
            "optimization_details": result
        }
    except Exception as e:
        logger.error(f"优化向量索引失败，错误: {str(e)}")
        return {
            "status": "error",
            "error": str(e)
        }

@celery_app.task(name="update_vector_index")
def update_vector_index(index_id: Optional[str] = None) -> Dict[str, Any]:
    """
    更新向量索引的Celery任务
    
    Args:
        index_id: 可选的索引ID，如果未提供则更新所有索引
        
    Returns:
        包含更新结果的字典
    """
    try:
        logger.info(f"开始更新向量索引 {index_id if index_id else 'all'}")
        
        vector_store = VectorStore()
        index_repo = IndexRepository()
        
        if index_id:
            # 更新指定索引
            index = index_repo.get(index_id)
            if not index:
                return {
                    "success": False,
                    "message": f"索引 {index_id} 不存在"
                }
            
            result = vector_store.update_index(index_id)
            return {
                "success": True,
                "index_id": index_id,
                "updated_at": datetime.now().isoformat(),
                "documents_count": result.get("documents_count", 0),
                "message": f"索引 {index_id} 更新成功"
            }
        else:
            # 更新所有索引
            indexes = index_repo.list()
            results = []
            
            for index in indexes:
                result = vector_store.update_index(index.id)
                results.append({
                    "index_id": index.id, 
                    "documents_count": result.get("documents_count", 0)
                })
            
            return {
                "success": True,
                "updated_at": datetime.now().isoformat(),
                "indexes_count": len(results),
                "indexes": results,
                "message": "所有索引更新成功"
            }
    except Exception as e:
        logger.error(f"更新向量索引失败: {str(e)}")
        return {
            "success": False,
            "message": f"更新失败: {str(e)}"
        } 