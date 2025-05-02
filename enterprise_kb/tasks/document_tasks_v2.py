"""改进的文档处理任务模块"""
import logging
import json
import os
import time
from typing import Dict, Any, Optional, List, Union

from enterprise_kb.core.unified_celery import celery_app
from enterprise_kb.core.celery.task_manager import tracked_task, get_task_manager
from enterprise_kb.storage.document_processor import get_document_processor
from enterprise_kb.core.parallel_processor import get_parallel_processor
from enterprise_kb.core.semantic_chunking import create_chunker
from enterprise_kb.core.incremental_processor import get_incremental_processor
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

@tracked_task(
    name="enterprise_kb.tasks.document_tasks_v2.process_document",
    retry_backoff=True,
    max_retries=3,
    rate_limit="10/m"
)
def process_document_task(
    self,
    file_path: str,
    metadata: Dict[str, Any],
    datasource_name: Optional[str] = "primary",
    use_parallel: Optional[bool] = None,
    use_semantic_chunking: Optional[bool] = None,
    use_incremental: Optional[bool] = None,
    chunking_type: Optional[str] = None
) -> Dict[str, Any]:
    """
    处理单个文档的Celery任务
    
    Args:
        file_path: 文件路径
        metadata: 文档元数据
        datasource_name: 数据源名称
        use_parallel: 是否使用并行处理
        use_semantic_chunking: 是否使用语义分块
        use_incremental: 是否使用增量更新
        chunking_type: 分块类型
        
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
        
        # 处理文档
        result = document_processor.process_document(
            file_path=file_path,
            metadata=metadata,
            datasource_name=datasource_name,
            use_parallel=use_parallel,
            use_semantic_chunking=use_semantic_chunking,
            use_incremental=use_incremental,
            chunking_type=chunking_type
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

@tracked_task(
    name="enterprise_kb.tasks.document_tasks_v2.batch_process",
    soft_time_limit=3600 * 2,  # 2小时时间限制
    time_limit=3600 * 2 + 300,  # 额外5分钟用于清理
)
def batch_process_documents_task(
    self,
    file_paths: List[str],
    shared_metadata: Dict[str, Any],
    datasource_name: Optional[str] = "primary",
    use_parallel: Optional[bool] = None,
    use_semantic_chunking: Optional[bool] = None,
    use_incremental: Optional[bool] = None,
    chunking_type: Optional[str] = None,
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """
    批量处理文档的任务
    
    Args:
        file_paths: 文件路径列表
        shared_metadata: 共享元数据
        datasource_name: 数据源名称
        use_parallel: 是否使用并行处理
        use_semantic_chunking: 是否使用语义分块
        use_incremental: 是否使用增量更新
        chunking_type: 分块类型
        max_concurrent: 最大并发处理数
        
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
    
    # 获取任务管理器
    task_manager = get_task_manager()
    
    # 创建子任务
    subtasks = []
    for i, file_path in enumerate(file_paths):
        # 为每个文件创建元数据副本
        file_metadata = {
            **shared_metadata, 
            "file_name": os.path.basename(file_path),
            "batch_id": self.request.id,
            "file_index": i
        }
        
        # 创建子任务
        subtask = process_document_task.s(
            file_path=file_path,
            metadata=file_metadata,
            datasource_name=datasource_name,
            use_parallel=use_parallel,
            use_semantic_chunking=use_semantic_chunking,
            use_incremental=use_incremental,
            chunking_type=chunking_type
        )
        subtasks.append(subtask)
    
    # 创建任务组
    from celery import group
    task_group = group(subtasks)
    group_result = task_group.apply_async()
    
    # 保存任务组ID
    group_id = group_result.id
    
    # 更新任务状态
    self.update_state(state="PROCESSING", meta={
        "total_files": len(file_paths),
        "processed_files": 0,
        "progress": 0,
        "group_id": group_id
    })
    
    # 等待任务组完成
    completed = 0
    total = len(subtasks)
    
    while not group_result.ready():
        # 获取已完成的任务数
        completed_tasks = [r for r in group_result.results if r.ready()]
        completed = len(completed_tasks)
        
        # 更新进度
        progress = int(completed / total * 100)
        self.update_state(state="PROCESSING", meta={
            "total_files": total,
            "processed_files": completed,
            "progress": progress,
            "group_id": group_id
        })
        
        # 等待一段时间
        time.sleep(2)
    
    # 获取所有结果
    results = []
    for i, result in enumerate(group_result.results):
        try:
            task_result = result.get()
            results.append({
                "status": "success",
                "file_path": file_paths[i],
                "result": task_result
            })
        except Exception as e:
            logger.exception(f"处理文件 {file_paths[i]} 失败: {str(e)}")
            results.append({
                "status": "error",
                "file_path": file_paths[i],
                "error": str(e)
            })
    
    # 汇总处理结果
    success_count = sum(1 for r in results if r["status"] == "success")
    error_count = sum(1 for r in results if r["status"] == "error")
    
    logger.info(f"批量处理完成: 成功 {success_count}, 失败 {error_count}")
    
    return {
        "total": len(file_paths),
        "successful": success_count,
        "failed": error_count,
        "results": results,
        "group_id": group_id
    }

@tracked_task(
    name="enterprise_kb.tasks.document_tasks_v2.process_large_document",
    soft_time_limit=3600 * 4,  # 4小时时间限制
    time_limit=3600 * 4 + 300,  # 额外5分钟用于清理
)
def process_large_document_task(
    self,
    file_path: str,
    metadata: Dict[str, Any],
    datasource_name: Optional[str] = "primary",
    chunk_size: int = 1000000,  # 1MB
    chunking_type: Optional[str] = "hierarchical"
) -> Dict[str, Any]:
    """
    处理大型文档的任务，将文档分割成多个块并行处理
    
    Args:
        file_path: 文件路径
        metadata: 文档元数据
        datasource_name: 数据源名称
        chunk_size: 块大小（字节）
        chunking_type: 分块类型
        
    Returns:
        处理结果
    """
    logger.info(f"开始处理大型文档: {file_path}")
    
    # 更新任务状态为进行中
    self.update_state(state="PROCESSING", meta={
        "file_path": file_path,
        "progress": 0
    })
    
    try:
        # 获取文档处理器
        document_processor = get_document_processor()
        
        # 获取并行处理器
        parallel_processor = get_parallel_processor()
        
        # 加载文档
        reader = document_processor.get_reader_for_file(file_path)
        documents = reader.load(file_path)
        
        if not documents:
            raise ValueError(f"无法加载文档: {file_path}")
        
        # 添加元数据到文档
        for doc in documents:
            doc.metadata.update(metadata)
        
        # 确定分块类型
        # 如果是Markdown文件并且配置了自动使用递归分割器，则切换到recursive_markdown
        file_extension = os.path.splitext(file_path)[1].lower()
        original_filename = metadata.get("original_filename", "")
        original_extension = os.path.splitext(original_filename)[1].lower()
        
        # 检查是否是Markdown文件
        is_markdown = (file_extension in [".md", ".markdown"] or 
                      original_extension in [".md", ".markdown"] or
                      metadata.get("file_type", "") in [".md", ".markdown"])
        
        # 如果是Markdown并且设置了自动使用递归分割器
        if is_markdown and settings.MARKDOWN_USE_RECURSIVE_SPLITTER:
            logger.info(f"检测到Markdown文件，使用递归分割器替代 {chunking_type}")
            chunking_type = "recursive_markdown"
        
        # 创建分块器
        chunker = create_chunker(
            chunking_type=chunking_type or "hierarchical",
            chunk_size=settings.LLAMA_INDEX_CHUNK_SIZE,
            chunk_overlap=settings.LLAMA_INDEX_CHUNK_OVERLAP,
            respect_markdown=settings.SEMANTIC_RESPECT_MARKDOWN
        )
        
        # 定义处理函数
        def process_text(text: str, text_metadata: Dict[str, Any]) -> List[Any]:
            """处理文本块，返回节点列表"""
            # 创建文档
            from llama_index.core import Document
            doc = Document(text=text, metadata=text_metadata)
            
            # 解析为节点
            return chunker.get_nodes_from_documents([doc])
        
        # 并行处理文档
        start_time = time.time()
        nodes = []
        
        for i, doc in enumerate(documents):
            # 更新进度
            progress = int(i / len(documents) * 50)  # 前50%进度用于处理文档
            self.update_state(state="PROCESSING", meta={
                "file_path": file_path,
                "progress": progress,
                "stage": "processing"
            })
            
            # 处理文档
            doc_nodes = parallel_processor.process_document_in_chunks(
                document=doc,
                chunk_size=chunk_size,
                processor_func=process_text,
                metadata=doc.metadata
            )
            nodes.extend(doc_nodes)
        
        # 更新进度
        self.update_state(state="PROCESSING", meta={
            "file_path": file_path,
            "progress": 50,
            "stage": "indexing",
            "node_count": len(nodes)
        })
        
        # 获取增量处理器
        incremental_processor = get_incremental_processor()
        
        # 提取文本块
        text_chunks = []
        for node in nodes:
            text_chunks.append(node.text)
        
        # 使用增量处理器
        result = incremental_processor.process_document_incrementally(
            doc_id=metadata.get("doc_id", ""),
            file_path=file_path,
            chunks=text_chunks,
            metadata=metadata,
            datasource_name=datasource_name,
            processor_func=process_text
        )
        
        # 计算处理时间
        processing_time = time.time() - start_time
        result["processing_time"] = processing_time
        
        # 更新任务状态为已完成
        self.update_state(state="SUCCESS", meta={
            "file_path": file_path,
            "progress": 100,
            "doc_id": result.get("doc_id"),
            "node_count": result.get("node_count"),
            "processing_time": processing_time
        })
        
        logger.info(f"大型文档处理完成: {file_path}, 节点数: {result.get('node_count')}, 耗时: {processing_time:.2f}秒")
        
        return result
    
    except Exception as e:
        logger.exception(f"处理大型文档失败: {str(e)}")
        # 更新任务状态为失败
        self.update_state(state="FAILURE", meta={
            "file_path": file_path,
            "error": str(e)
        })
        raise

@tracked_task(
    name="enterprise_kb.tasks.document_tasks_v2.cleanup_temp_files",
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
