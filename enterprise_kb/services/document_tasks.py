from typing import List, Dict, Any, Optional, Union
import logging
from pathlib import Path

from enterprise_kb.core.celery_app import celery_app
from enterprise_kb.core.config import settings
from enterprise_kb.db.repositories.document import DocumentRepository
from enterprise_kb.db.repositories.knowledge_base import KnowledgeBaseRepository
from enterprise_kb.services.document_processor import DocumentProcessor
from enterprise_kb.services.index_service import IndexService
from enterprise_kb.utils.timing import timeit

logger = logging.getLogger(__name__)

@celery_app.task(name="process-document", bind=True)
def process_document(
    self,
    document_id: int,
    file_path: str,
    kb_id: int,
    metadata: Optional[Dict[str, Any]] = None
):
    """
    处理单个文档并将其添加到知识库索引中
    
    Args:
        document_id: 文档ID
        file_path: 文档文件路径
        kb_id: 知识库ID
        metadata: 文档元数据
    
    Returns:
        处理结果
    """
    logger.info(f"开始处理文档，ID: {document_id}, 文件: {file_path}")
    
    # 更新任务状态
    self.update_state(
        state="PROCESSING",
        meta={"current": 0, "total": 100, "status": "正在处理文档"}
    )
    
    try:
        document_processor = DocumentProcessor()
        index_service = IndexService()
        document_repo = DocumentRepository()
        kb_repo = KnowledgeBaseRepository()
        
        # 获取知识库信息
        kb = kb_repo.get(kb_id)
        if not kb:
            raise ValueError(f"找不到ID为{kb_id}的知识库")
        
        # 检查文件是否存在
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            raise FileNotFoundError(f"找不到文件: {file_path}")
        
        # 更新状态
        self.update_state(
            state="PROCESSING",
            meta={"current": 20, "total": 100, "status": "正在解析文档"}
        )
        
        # 处理文档
        chunks = document_processor.process_document(
            file_path=file_path,
            document_id=document_id,
            metadata=metadata or {}
        )
        
        # 更新状态
        self.update_state(
            state="PROCESSING",
            meta={"current": 60, "total": 100, "status": "正在添加到索引"}
        )
        
        # 将文档添加到索引
        index_result = index_service.add_documents_to_index(
            kb_id=kb_id,
            document_id=document_id,
            chunks=chunks
        )
        
        # 更新文档状态为已处理
        document_repo.update(
            id=document_id,
            obj_in={"status": "processed", "chunk_count": len(chunks)}
        )
        
        # 更新状态
        self.update_state(
            state="PROCESSING", 
            meta={"current": 100, "total": 100, "status": "文档处理完成"}
        )
        
        logger.info(f"文档处理完成，ID: {document_id}, 生成的块数: {len(chunks)}")
        return {
            "success": True,
            "document_id": document_id,
            "chunk_count": len(chunks),
            "index_result": index_result
        }
        
    except Exception as e:
        logger.error(f"处理文档 {document_id} 时出错: {str(e)}", exc_info=True)
        
        # 更新文档状态为处理失败
        try:
            document_repo = DocumentRepository()
            document_repo.update(
                id=document_id,
                obj_in={"status": "failed", "error_message": str(e)}
            )
        except Exception as update_error:
            logger.error(f"更新文档状态失败: {str(update_error)}")
        
        # 重新抛出异常，让Celery知道任务失败了
        raise

@celery_app.task(name="batch-process-documents", bind=True)
def batch_process_documents(
    self,
    document_ids: List[int],
    kb_id: int
):
    """
    批量处理多个文档
    
    Args:
        document_ids: 文档ID列表
        kb_id: 知识库ID
    
    Returns:
        处理结果
    """
    logger.info(f"开始批量处理文档，文档数: {len(document_ids)}, 知识库ID: {kb_id}")
    
    document_repo = DocumentRepository()
    total_documents = len(document_ids)
    processed_count = 0
    success_count = 0
    failed_count = 0
    results = []
    
    # 更新任务状态
    self.update_state(
        state="PROCESSING",
        meta={
            "current": processed_count,
            "total": total_documents,
            "status": f"已处理: {processed_count}/{total_documents}"
        }
    )
    
    for idx, doc_id in enumerate(document_ids):
        try:
            # 获取文档信息
            document = document_repo.get(doc_id)
            if not document:
                logger.warning(f"找不到ID为{doc_id}的文档，跳过处理")
                failed_count += 1
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": "文档不存在"
                })
                continue
                
            # 启动子任务处理单个文档
            subtask = process_document.delay(
                document_id=doc_id,
                file_path=document.file_path,
                kb_id=kb_id,
                metadata=document.metadata
            )
            
            # 保存任务ID到文档记录
            document_repo.update(
                id=doc_id,
                obj_in={"task_id": subtask.id, "status": "processing"}
            )
            
            # 记录结果
            success_count += 1
            results.append({
                "document_id": doc_id,
                "success": True,
                "task_id": subtask.id
            })
            
        except Exception as e:
            logger.error(f"为文档 {doc_id} 创建处理任务时出错: {str(e)}")
            failed_count += 1
            results.append({
                "document_id": doc_id,
                "success": False,
                "error": str(e)
            })
            
            # 更新文档状态为处理失败
            try:
                document_repo.update(
                    id=doc_id,
                    obj_in={"status": "failed", "error_message": str(e)}
                )
            except Exception as update_error:
                logger.error(f"更新文档状态失败: {str(update_error)}")
        
        # 更新处理进度
        processed_count += 1
        self.update_state(
            state="PROCESSING",
            meta={
                "current": processed_count,
                "total": total_documents,
                "status": f"已处理: {processed_count}/{total_documents}"
            }
        )
    
    logger.info(f"批量处理任务完成，总数: {total_documents}, 成功: {success_count}, 失败: {failed_count}")
    
    return {
        "total_documents": total_documents,
        "success_count": success_count,
        "failed_count": failed_count,
        "results": results
    }

@celery_app.task(name="rebuild-index", bind=True)
def rebuild_index(self, kb_id: int):
    """
    重建知识库索引
    
    Args:
        kb_id: 知识库ID
    
    Returns:
        重建结果
    """
    logger.info(f"开始重建知识库索引，知识库ID: {kb_id}")
    
    try:
        document_repo = DocumentRepository()
        kb_repo = KnowledgeBaseRepository()
        index_service = IndexService()
        
        # 获取知识库信息
        kb = kb_repo.get(kb_id)
        if not kb:
            raise ValueError(f"找不到ID为{kb_id}的知识库")
        
        # 更新任务状态
        self.update_state(
            state="PROCESSING",
            meta={"current": 10, "total": 100, "status": "正在删除旧索引"}
        )
        
        # 删除旧索引
        index_service.delete_index(kb_id)
        
        # 创建新索引
        self.update_state(
            state="PROCESSING",
            meta={"current": 20, "total": 100, "status": "正在创建新索引"}
        )
        
        index_service.create_index(kb_id)
        
        # 获取该知识库下的所有已处理文档
        documents = document_repo.get_all_by_kb(
            kb_id=kb_id,
            status="processed"
        )
        
        total_documents = len(documents)
        if total_documents == 0:
            logger.info(f"知识库 {kb_id} 没有已处理文档，索引重建完成")
            return {
                "success": True,
                "kb_id": kb_id,
                "document_count": 0,
                "message": "索引已重建，但没有文档需要添加"
            }
        
        logger.info(f"开始重新添加 {total_documents} 个文档到索引")
        
        # 重新处理所有文档
        processed_count = 0
        for idx, document in enumerate(documents):
            try:
                # 更新进度
                progress = 20 + int(70 * idx / total_documents)
                self.update_state(
                    state="PROCESSING",
                    meta={
                        "current": processed_count,
                        "total": total_documents,
                        "status": f"正在重新索引文档 {processed_count+1}/{total_documents}"
                    }
                )
                
                # 为文档创建处理任务
                subtask = process_document.delay(
                    document_id=document.id,
                    file_path=document.file_path,
                    kb_id=kb_id,
                    metadata=document.metadata
                )
                
                # 更新文档状态
                document_repo.update(
                    id=document.id,
                    obj_in={"task_id": subtask.id, "status": "processing"}
                )
                
            except Exception as e:
                logger.error(f"为文档 {document.id} 创建重建索引任务时出错: {str(e)}")
            
            processed_count += 1
        
        # 完成
        self.update_state(
            state="PROCESSING",
            meta={"current": 100, "total": 100, "status": "索引重建完成"}
        )
        
        logger.info(f"知识库索引重建完成，知识库ID: {kb_id}，重新处理文档数: {processed_count}")
        
        return {
            "success": True,
            "kb_id": kb_id,
            "document_count": processed_count,
            "message": "索引重建任务已成功启动"
        }
        
    except Exception as e:
        logger.error(f"重建知识库 {kb_id} 索引时出错: {str(e)}", exc_info=True)
        raise

@celery_app.task(name="optimize_index")
@timeit
def optimize_index() -> Dict[str, Any]:
    """
    优化索引的周期性任务
    
    Returns:
        优化结果
    """
    try:
        logger.info("开始执行索引优化任务")
        document_service = DocumentService()
        result = document_service.optimize_index()
        logger.info("索引优化完成")
        return {
            "success": True,
            "message": "索引优化成功",
            "result": result
        }
    except Exception as e:
        logger.error(f"索引优化失败: {str(e)}", exc_info=True)
        return {
            "success": False,
            "message": f"索引优化失败: {str(e)}",
            "result": None
        } 