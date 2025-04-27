"""文档分段处理任务模块，使用Celery优化文档的分段处理"""
import logging
import os
import time
import uuid
from typing import Dict, List, Any, Optional, Tuple, Union
from datetime import datetime

from celery import chord, group, chain
from celery.result import GroupResult

from enterprise_kb.core.unified_celery import celery_app
from enterprise_kb.core.celery.task_manager import tracked_task, get_task_manager
from enterprise_kb.storage.document_processor import get_document_processor
from enterprise_kb.core.parallel_processor import get_parallel_processor
from enterprise_kb.core.semantic_chunking import create_chunker
from enterprise_kb.core.incremental_processor import get_incremental_processor
from enterprise_kb.storage.vector_store_manager import get_vector_store_manager
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

@tracked_task(
    name="enterprise_kb.tasks.document_segment_tasks.split_document",
    soft_time_limit=600,  # 10分钟
    time_limit=720,       # 12分钟
)
def split_document_task(
    self,
    file_path: str,
    metadata: Dict[str, Any],
    chunking_type: str = "hierarchical",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    max_segments: Optional[int] = None
) -> Dict[str, Any]:
    """
    将文档分割成多个段落的任务
    
    Args:
        file_path: 文件路径
        metadata: 文档元数据
        chunking_type: 分块类型
        chunk_size: 块大小
        chunk_overlap: 块重叠
        max_segments: 最大段落数，如果为None则不限制
        
    Returns:
        分割结果，包含段落列表和元数据
    """
    logger.info(f"开始分割文档: {file_path}")
    
    # 更新任务状态
    self.update_state(state="PROCESSING", meta={
        "file_path": file_path,
        "progress": 0,
        "stage": "splitting"
    })
    
    try:
        # 获取文档处理器
        document_processor = get_document_processor()
        
        # 加载文档
        reader = document_processor.get_reader_for_file(file_path)
        documents = reader.load(file_path)
        
        if not documents:
            raise ValueError(f"无法加载文档: {file_path}")
        
        # 添加元数据到文档
        for doc in documents:
            doc.metadata.update(metadata)
        
        # 创建分块器
        chunker = create_chunker(
            chunking_type=chunking_type,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            respect_markdown=settings.SEMANTIC_RESPECT_MARKDOWN
        )
        
        # 分割文档
        segments = []
        for doc in documents:
            # 解析文档为节点
            nodes = chunker.get_nodes_from_documents([doc])
            
            # 将节点转换为段落
            for i, node in enumerate(nodes):
                # 创建段落元数据
                segment_metadata = node.metadata.copy() if node.metadata else {}
                segment_metadata.update({
                    "segment_id": f"{metadata.get('doc_id', '')}_segment_{i}",
                    "segment_index": i,
                    "total_segments": len(nodes),
                    "parent_doc_id": metadata.get("doc_id", ""),
                    "original_file_path": file_path
                })
                
                # 添加段落
                segments.append({
                    "text": node.text,
                    "metadata": segment_metadata
                })
        
        # 如果设置了最大段落数，则限制段落数量
        if max_segments and len(segments) > max_segments:
            segments = segments[:max_segments]
        
        # 更新任务状态
        self.update_state(state="SUCCESS", meta={
            "file_path": file_path,
            "progress": 100,
            "stage": "split_complete",
            "segment_count": len(segments)
        })
        
        # 返回分割结果
        return {
            "doc_id": metadata.get("doc_id", ""),
            "file_path": file_path,
            "segment_count": len(segments),
            "segments": segments,
            "metadata": metadata
        }
    
    except Exception as e:
        logger.exception(f"分割文档失败: {str(e)}")
        # 更新任务状态
        self.update_state(state="FAILURE", meta={
            "file_path": file_path,
            "error": str(e)
        })
        raise

@tracked_task(
    name="enterprise_kb.tasks.document_segment_tasks.process_segment",
    soft_time_limit=300,  # 5分钟
    time_limit=360,       # 6分钟
)
def process_segment_task(
    self,
    segment: Dict[str, Any],
    datasource_name: str = "primary"
) -> Dict[str, Any]:
    """
    处理单个文档段落的任务
    
    Args:
        segment: 段落信息，包含文本和元数据
        datasource_name: 数据源名称
        
    Returns:
        处理结果
    """
    segment_id = segment["metadata"].get("segment_id", "unknown")
    logger.info(f"开始处理段落: {segment_id}")
    
    # 更新任务状态
    self.update_state(state="PROCESSING", meta={
        "segment_id": segment_id,
        "progress": 0,
        "stage": "processing"
    })
    
    try:
        # 获取文本和元数据
        text = segment["text"]
        metadata = segment["metadata"]
        
        # 更新任务状态
        self.update_state(state="PROCESSING", meta={
            "segment_id": segment_id,
            "progress": 50,
            "stage": "embedding"
        })
        
        # 创建向量存储管理器
        vector_store_manager = get_vector_store_manager()
        
        # 创建文档节点
        from llama_index.core import Document
        from llama_index.core.schema import TextNode
        
        # 创建节点
        node = TextNode(
            text=text,
            metadata=metadata,
            id_=metadata.get("segment_id")
        )
        
        # 添加节点到向量存储
        node_ids = vector_store_manager.add_nodes([node], datasource_name)
        
        # 更新任务状态
        self.update_state(state="SUCCESS", meta={
            "segment_id": segment_id,
            "progress": 100,
            "stage": "complete",
            "node_ids": node_ids
        })
        
        # 返回处理结果
        return {
            "segment_id": segment_id,
            "node_ids": node_ids,
            "metadata": metadata,
            "status": "success"
        }
    
    except Exception as e:
        logger.exception(f"处理段落失败: {str(e)}")
        # 更新任务状态
        self.update_state(state="FAILURE", meta={
            "segment_id": segment_id,
            "error": str(e)
        })
        raise

@tracked_task(
    name="enterprise_kb.tasks.document_segment_tasks.merge_results",
    soft_time_limit=300,  # 5分钟
    time_limit=360,       # 6分钟
)
def merge_results_task(
    self,
    results: List[Dict[str, Any]],
    doc_id: str,
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    合并所有段落处理结果的任务
    
    Args:
        results: 段落处理结果列表
        doc_id: 文档ID
        metadata: 文档元数据
        
    Returns:
        合并结果
    """
    logger.info(f"开始合并文档处理结果: {doc_id}")
    
    # 更新任务状态
    self.update_state(state="PROCESSING", meta={
        "doc_id": doc_id,
        "progress": 0,
        "stage": "merging"
    })
    
    try:
        # 统计成功和失败的段落
        success_count = sum(1 for r in results if r.get("status") == "success")
        failed_count = len(results) - success_count
        
        # 收集所有节点ID
        node_ids = []
        for result in results:
            if result.get("status") == "success" and "node_ids" in result:
                node_ids.extend(result["node_ids"])
        
        # 更新任务状态
        self.update_state(state="SUCCESS", meta={
            "doc_id": doc_id,
            "progress": 100,
            "stage": "complete",
            "success_count": success_count,
            "failed_count": failed_count,
            "node_count": len(node_ids)
        })
        
        # 返回合并结果
        return {
            "doc_id": doc_id,
            "status": "success" if failed_count == 0 else "partial_success",
            "segment_count": len(results),
            "success_count": success_count,
            "failed_count": failed_count,
            "node_ids": node_ids,
            "metadata": metadata
        }
    
    except Exception as e:
        logger.exception(f"合并结果失败: {str(e)}")
        # 更新任务状态
        self.update_state(state="FAILURE", meta={
            "doc_id": doc_id,
            "error": str(e)
        })
        raise

@tracked_task(
    name="enterprise_kb.tasks.document_segment_tasks.process_document_segmented",
    soft_time_limit=3600,  # 1小时
    time_limit=3900,       # 1小时5分钟
)
def process_document_segmented_task(
    self,
    file_path: str,
    metadata: Dict[str, Any],
    datasource_name: str = "primary",
    chunking_type: str = "hierarchical",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    max_segments: Optional[int] = None,
    max_concurrent: int = 10
) -> Dict[str, Any]:
    """
    使用分段处理方式处理文档的任务
    
    Args:
        file_path: 文件路径
        metadata: 文档元数据
        datasource_name: 数据源名称
        chunking_type: 分块类型
        chunk_size: 块大小
        chunk_overlap: 块重叠
        max_segments: 最大段落数，如果为None则不限制
        max_concurrent: 最大并发处理数
        
    Returns:
        处理结果
    """
    logger.info(f"开始分段处理文档: {file_path}")
    
    # 更新任务状态
    self.update_state(state="PROCESSING", meta={
        "file_path": file_path,
        "progress": 0,
        "stage": "starting"
    })
    
    try:
        # 确保文档ID存在
        if "doc_id" not in metadata:
            metadata["doc_id"] = str(uuid.uuid4())
        
        doc_id = metadata["doc_id"]
        
        # 第一步：分割文档
        split_task = split_document_task.s(
            file_path=file_path,
            metadata=metadata,
            chunking_type=chunking_type,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            max_segments=max_segments
        )
        
        # 第二步：处理每个段落（使用回调）
        def process_segments_callback(split_result):
            """分割完成后的回调函数"""
            segments = split_result["segments"]
            
            # 创建段落处理任务
            segment_tasks = []
            for segment in segments:
                task = process_segment_task.s(
                    segment=segment,
                    datasource_name=datasource_name
                )
                segment_tasks.append(task)
            
            # 创建任务组
            segment_group = group(segment_tasks)
            
            # 第三步：合并结果
            merge_task = merge_results_task.s(
                doc_id=doc_id,
                metadata=metadata
            )
            
            # 创建和弦（任务组 + 回调）
            segment_chord = chord(
                header=segment_group,
                body=merge_task
            )
            
            # 执行和弦
            return segment_chord()
        
        # 执行分割任务并设置回调
        split_async_result = split_task.apply_async()
        
        # 等待分割任务完成
        split_result = split_async_result.get()
        
        # 执行回调
        chord_result = process_segments_callback(split_result)
        
        # 等待和弦完成
        final_result = chord_result.get()
        
        # 更新任务状态
        self.update_state(state="SUCCESS", meta={
            "file_path": file_path,
            "doc_id": doc_id,
            "progress": 100,
            "stage": "complete",
            "segment_count": final_result["segment_count"],
            "success_count": final_result["success_count"],
            "failed_count": final_result["failed_count"],
            "node_count": len(final_result["node_ids"])
        })
        
        # 返回最终结果
        return {
            "doc_id": doc_id,
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "status": final_result["status"],
            "segment_count": final_result["segment_count"],
            "success_count": final_result["success_count"],
            "failed_count": final_result["failed_count"],
            "node_count": len(final_result["node_ids"]),
            "metadata": metadata,
            "processing_time": time.time() - self.request.started_at.timestamp() if hasattr(self.request, "started_at") else None
        }
    
    except Exception as e:
        logger.exception(f"分段处理文档失败: {str(e)}")
        # 更新任务状态
        self.update_state(state="FAILURE", meta={
            "file_path": file_path,
            "error": str(e)
        })
        raise

@tracked_task(
    name="enterprise_kb.tasks.document_segment_tasks.batch_process_segmented",
    soft_time_limit=7200,  # 2小时
    time_limit=7500,       # 2小时5分钟
)
def batch_process_segmented_task(
    self,
    file_paths: List[str],
    shared_metadata: Dict[str, Any],
    datasource_name: str = "primary",
    chunking_type: str = "hierarchical",
    chunk_size: int = 500,
    chunk_overlap: int = 50,
    max_segments: Optional[int] = None,
    max_concurrent: int = 5
) -> Dict[str, Any]:
    """
    批量分段处理文档的任务
    
    Args:
        file_paths: 文件路径列表
        shared_metadata: 共享元数据
        datasource_name: 数据源名称
        chunking_type: 分块类型
        chunk_size: 块大小
        chunk_overlap: 块重叠
        max_segments: 最大段落数，如果为None则不限制
        max_concurrent: 最大并发处理数
        
    Returns:
        处理结果
    """
    logger.info(f"开始批量分段处理 {len(file_paths)} 个文档")
    
    # 更新任务状态
    self.update_state(state="PROCESSING", meta={
        "total_files": len(file_paths),
        "processed_files": 0,
        "progress": 0
    })
    
    try:
        # 创建文档处理任务
        document_tasks = []
        for i, file_path in enumerate(file_paths):
            # 为每个文件创建元数据副本
            file_metadata = {
                **shared_metadata, 
                "file_name": os.path.basename(file_path),
                "batch_id": self.request.id,
                "file_index": i,
                "doc_id": f"{shared_metadata.get('batch_id', str(uuid.uuid4()))}_{i}"
            }
            
            # 创建文档处理任务
            task = process_document_segmented_task.s(
                file_path=file_path,
                metadata=file_metadata,
                datasource_name=datasource_name,
                chunking_type=chunking_type,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                max_segments=max_segments,
                max_concurrent=max_concurrent
            )
            document_tasks.append(task)
        
        # 创建任务组
        document_group = group(document_tasks)
        group_result = document_group.apply_async()
        
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
        total = len(document_tasks)
        
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
        
        # 计算总段落数和总节点数
        total_segments = sum(r["result"].get("segment_count", 0) for r in results if r["status"] == "success")
        total_nodes = sum(r["result"].get("node_count", 0) for r in results if r["status"] == "success")
        
        logger.info(f"批量分段处理完成: 成功 {success_count}, 失败 {error_count}, 总段落数 {total_segments}, 总节点数 {total_nodes}")
        
        # 返回最终结果
        return {
            "batch_id": shared_metadata.get("batch_id", str(uuid.uuid4())),
            "total": len(file_paths),
            "successful": success_count,
            "failed": error_count,
            "total_segments": total_segments,
            "total_nodes": total_nodes,
            "results": results,
            "group_id": group_id,
            "processing_time": time.time() - self.request.started_at.timestamp() if hasattr(self.request, "started_at") else None
        }
    
    except Exception as e:
        logger.exception(f"批量分段处理失败: {str(e)}")
        # 更新任务状态
        self.update_state(state="FAILURE", meta={
            "error": str(e)
        })
        raise
