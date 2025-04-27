"""并行文档处理模块，用于大型文档的高效处理"""
import os
import logging
import asyncio
import concurrent.futures
from typing import Dict, List, Optional, Any, Callable, Tuple, Union
from functools import partial

from llama_index.core import Document
from llama_index.core.schema import BaseNode

from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

class ParallelProcessor:
    """并行文档处理器，用于大型文档的高效处理"""
    
    def __init__(self, max_workers: Optional[int] = None):
        """初始化并行处理器
        
        Args:
            max_workers: 最大工作线程数，如果为None则使用CPU核心数
        """
        self.max_workers = max_workers or min(32, os.cpu_count() * 2)
        logger.info(f"初始化并行处理器，最大工作线程数: {self.max_workers}")
    
    async def process_document_in_chunks(
        self,
        document: Document,
        chunk_size: int = 100000,  # 每个块的字符数
        processor_func: Callable[[str, Dict[str, Any]], List[BaseNode]],
        metadata: Optional[Dict[str, Any]] = None,
        preserve_order: bool = True
    ) -> List[BaseNode]:
        """并行处理大型文档
        
        将文档分割成多个块，并行处理，然后合并结果
        
        Args:
            document: 要处理的文档
            chunk_size: 每个块的字符数
            processor_func: 处理函数，接收文本和元数据，返回节点列表
            metadata: 文档元数据
            preserve_order: 是否保持原始顺序
            
        Returns:
            处理后的节点列表
        """
        if metadata is None:
            metadata = {}
        
        # 合并文档元数据
        if document.metadata:
            metadata = {**document.metadata, **metadata}
        
        text = document.text
        text_length = len(text)
        
        # 如果文档较小，直接处理
        if text_length <= chunk_size:
            return processor_func(text, metadata)
        
        # 分割文档为多个块
        chunks = []
        for i in range(0, text_length, chunk_size):
            end = min(i + chunk_size, text_length)
            # 尝试在句子边界分割
            if end < text_length:
                # 向后查找最近的句子结束符
                for j in range(min(end + 200, text_length) - 1, end - 1, -1):
                    if j < text_length and text[j] in ['.', '!', '?', '\n']:
                        end = j + 1
                        break
            
            chunk_text = text[i:end]
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = len(chunks)
            chunk_metadata["is_partial"] = True
            chunks.append((chunk_text, chunk_metadata))
        
        logger.info(f"将文档分割为 {len(chunks)} 个块进行并行处理")
        
        # 使用线程池并行处理
        all_nodes = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 创建处理任务
            futures = []
            for chunk_text, chunk_metadata in chunks:
                future = executor.submit(processor_func, chunk_text, chunk_metadata)
                futures.append(future)
            
            # 收集结果
            for i, future in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    chunk_nodes = future.result()
                    logger.debug(f"完成块 {i+1}/{len(chunks)} 的处理，生成 {len(chunk_nodes)} 个节点")
                    all_nodes.extend(chunk_nodes)
                except Exception as e:
                    logger.error(f"处理块 {i+1} 时出错: {str(e)}")
        
        # 如果需要保持原始顺序
        if preserve_order and all_nodes:
            # 按照块索引和节点在块内的位置排序
            all_nodes.sort(key=lambda node: (
                node.metadata.get("chunk_index", 0) if node.metadata else 0,
                node.metadata.get("node_position", 0) if node.metadata else 0
            ))
            
            # 清理临时元数据
            for node in all_nodes:
                if node.metadata:
                    node.metadata.pop("chunk_index", None)
                    node.metadata.pop("node_position", None)
                    node.metadata.pop("is_partial", None)
        
        logger.info(f"并行处理完成，总共生成 {len(all_nodes)} 个节点")
        return all_nodes
    
    async def process_multiple_documents(
        self,
        documents: List[Document],
        processor_func: Callable[[Document], List[BaseNode]],
        max_concurrent: Optional[int] = None
    ) -> List[BaseNode]:
        """并行处理多个文档
        
        Args:
            documents: 要处理的文档列表
            processor_func: 处理函数，接收文档，返回节点列表
            max_concurrent: 最大并发处理数，如果为None则使用max_workers
            
        Returns:
            处理后的节点列表
        """
        if not documents:
            return []
        
        max_concurrent = max_concurrent or self.max_workers
        
        logger.info(f"开始并行处理 {len(documents)} 个文档，最大并发数: {max_concurrent}")
        
        # 创建信号量限制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(doc: Document) -> List[BaseNode]:
            async with semaphore:
                # 使用线程池执行CPU密集型任务
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(None, processor_func, doc)
        
        # 创建任务
        tasks = [process_with_semaphore(doc) for doc in documents]
        
        # 等待所有任务完成
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 处理结果
        all_nodes = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"处理文档 {i+1} 时出错: {str(result)}")
            else:
                all_nodes.extend(result)
        
        logger.info(f"并行处理完成，总共生成 {len(all_nodes)} 个节点")
        return all_nodes

# 创建单例实例
_parallel_processor = None

def get_parallel_processor() -> ParallelProcessor:
    """获取并行处理器单例"""
    global _parallel_processor
    if _parallel_processor is None:
        _parallel_processor = ParallelProcessor(
            max_workers=settings.MAX_CONCURRENT_TASKS
        )
    return _parallel_processor
