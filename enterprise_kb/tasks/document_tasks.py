"""文档处理任务模块"""
import logging
import json
import os
from typing import Dict, Any, Optional, List, Union

from enterprise_kb.core.celery.app import celery_app
from enterprise_kb.storage.document_processor import get_document_processor

logger = logging.getLogger(__name__)

@celery_app.task(
    bind=True, 
    name="enterprise_kb.tasks.document_tasks.process_document",
    retry_backoff=True,
    max_retries=3,
    rate_limit="10/m"
)
def process_document_task(
    self,
    file_path: str,
    metadata: Dict[str, Any],
    convert_to_md: Optional[bool] = None,
    strategy: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    处理单个文档的Celery任务
    
    Args:
        file_path: 文件路径
        metadata: 文档元数据
        convert_to_md: 是否转换为Markdown
        strategy: 处理策略
        
    Returns:
        处理结果
    """
    logger.info(f"开始处理文档: {file_path}")
    
    # 更新任务状态为进行中
    self.update_state(state="PROCESSING", meta={
        "file_path": file_path,
        "progress": 0
    })
    
    try:
        # 获取文档处理器
        document_processor = get_document_processor()
        
        # 如果没有提供处理策略且需要自动分析
        if not strategy and metadata.get("auto_analyze", True):
            try:
                # 分析文档并确定处理策略
                strategy = document_processor.determine_processing_strategy(file_path)
                logger.info(f"自动确定文档处理策略: {strategy}")
            except Exception as e:
                logger.warning(f"文档分析失败，使用默认处理方式: {e}")
        
        # 处理文档
        result = document_processor.process_document(
            file_path=file_path,
            metadata=metadata,
            convert_to_md=convert_to_md,
            strategy=strategy
        )
        
        # 更新任务状态为已完成
        self.update_state(state="SUCCESS", meta={
            "file_path": file_path,
            "progress": 100,
            "doc_id": result.get("doc_id")
        })
        
        return result
    
    except Exception as e:
        logger.exception(f"处理文档失败: {str(e)}")
        # 更新任务状态为失败
        self.update_state(state="FAILURE", meta={
            "file_path": file_path,
            "error": str(e)
        })
        raise

@celery_app.task(
    bind=True, 
    name="enterprise_kb.tasks.document_tasks.batch_process",
    soft_time_limit=3600 * 2,  # 2小时时间限制
    time_limit=3600 * 2 + 300,  # 额外5分钟用于清理
)
def batch_process_documents_task(
    self,
    file_paths: List[str],
    shared_metadata: Dict[str, Any],
    auto_process: bool = True,
    convert_to_md: Optional[bool] = None
) -> Dict[str, Any]:
    """
    批量处理文档的任务
    
    Args:
        file_paths: 文件路径列表
        shared_metadata: 共享元数据
        auto_process: 是否自动分析处理
        convert_to_md: 是否转换为Markdown
        
    Returns:
        处理结果
    """
    logger.info(f"开始批量处理 {len(file_paths)} 个文档")
    
    # 更新任务状态
    self.update_state(state="PROCESSING", meta={
        "total_files": len(file_paths),
        "processed_files": 0,
        "progress": 0
    })
    
    results = []
    document_processor = get_document_processor()
    
    for i, file_path in enumerate(file_paths):
        try:
            # 为每个文件创建元数据副本
            file_metadata = {
                **shared_metadata, 
                "file_name": os.path.basename(file_path),
                "batch_id": self.request.id,
                "file_index": i
            }
            
            # 自动分析文档（如果需要）
            strategy = None
            if auto_process:
                try:
                    strategy = document_processor.determine_processing_strategy(file_path)
                except Exception as e:
                    logger.warning(f"文档分析失败，使用默认处理方式: {e}")
            
            # 处理文档
            result = document_processor.process_document(
                file_path=file_path,
                metadata=file_metadata,
                convert_to_md=convert_to_md,
                strategy=strategy
            )
            
            results.append({
                "status": "success",
                "file_path": file_path,
                "result": result
            })
            
        except Exception as e:
            logger.exception(f"处理文件 {file_path} 失败: {str(e)}")
            results.append({
                "status": "error",
                "file_path": file_path,
                "error": str(e)
            })
        
        # 更新进度
        progress = int((i + 1) / len(file_paths) * 100)
        self.update_state(state="PROCESSING", meta={
            "total_files": len(file_paths),
            "processed_files": i + 1,
            "progress": progress
        })
    
    # 汇总处理结果
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    
    logger.info(f"批量处理完成: 成功 {success_count}, 失败 {error_count}")
    
    return {
        "total": len(file_paths),
        "successful": success_count,
        "failed": error_count,
        "results": results
    }

@celery_app.task(
    bind=True,
    name="enterprise_kb.tasks.document_tasks.cleanup_temp_files",
    retry_backoff=True
)
def cleanup_task(self, file_paths: List[str], keep_original: bool = False) -> Dict[str, Any]:
    """
    清理临时文件任务
    
    Args:
        file_paths: 需要清理的文件路径列表
        keep_original: 是否保留原始文件
        
    Returns:
        清理结果
    """
    logger.info(f"开始清理临时文件: {len(file_paths)} 个文件")
    results = {"deleted": 0, "failed": 0, "skipped": 0}
    
    for file_path in file_paths:
        try:
            # 如果是原始文件且需要保留，则跳过
            if keep_original and "/uploads/" in file_path:
                results["skipped"] += 1
                continue
                
            # 检查文件是否存在
            if os.path.exists(file_path):
                os.remove(file_path)
                results["deleted"] += 1
                logger.debug(f"已删除文件: {file_path}")
            else:
                results["skipped"] += 1
        except Exception as e:
            logger.error(f"删除文件失败 {file_path}: {str(e)}")
            results["failed"] += 1
    
    logger.info(f"清理完成: 删除 {results['deleted']}, 失败 {results['failed']}, 跳过 {results['skipped']}")
    return results 