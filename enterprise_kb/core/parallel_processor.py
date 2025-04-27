"""并行文档处理模块，用于大型文档的高效处理

提供多种并行处理策略：
1. 线程池并行处理：适用于CPU密集型任务
2. 分布式任务处理：利用Celery进行分布式处理
3. 流式处理：适用于超大型文档，减少内存占用
"""
import os
import logging
import asyncio
import concurrent.futures
import re
import time
import tempfile
from typing import Dict, List, Optional, Any, Callable, Tuple, Union, Iterator
from functools import partial
from enum import Enum

from llama_index.core import Document
from llama_index.core.schema import BaseNode, TextNode

from enterprise_kb.core.config.settings import settings
from enterprise_kb.core.celery.app import celery_app

logger = logging.getLogger(__name__)

class ChunkingStrategy(Enum):
    """文档分块策略"""
    FIXED_SIZE = "fixed_size"       # 固定大小分块
    SENTENCE_BOUNDARY = "sentence"  # 句子边界分块
    PARAGRAPH_BOUNDARY = "paragraph"  # 段落边界分块
    SEMANTIC_BOUNDARY = "semantic"  # 语义边界分块

class ParallelProcessor:
    """并行文档处理器，用于大型文档的高效处理"""

    def __init__(
        self,
        max_workers: Optional[int] = None,
        chunk_strategy: ChunkingStrategy = ChunkingStrategy.SENTENCE_BOUNDARY,
        use_distributed: bool = False,
        memory_efficient: bool = False
    ):
        """初始化并行处理器

        Args:
            max_workers: 最大工作线程数，如果为None则使用CPU核心数
            chunk_strategy: 分块策略
            use_distributed: 是否使用分布式处理(Celery)
            memory_efficient: 是否使用内存高效模式(流式处理)
        """
        self.max_workers = max_workers or min(32, os.cpu_count() * 2)
        self.chunk_strategy = chunk_strategy
        self.use_distributed = use_distributed
        self.memory_efficient = memory_efficient

        # 句子边界正则表达式
        self.sentence_boundary_regex = re.compile(r'(?<=[.!?。！？])\s+')
        # 段落边界正则表达式
        self.paragraph_boundary_regex = re.compile(r'\n\s*\n')
        # 语义边界标记
        self.semantic_boundaries = [
            # 标题模式
            re.compile(r'^#{1,6}\s+.+$', re.MULTILINE),  # Markdown标题
            re.compile(r'^.+\n[=\-]{2,}$', re.MULTILINE),  # Markdown下划线标题
            re.compile(r'<h[1-6]>.*?</h[1-6]>', re.DOTALL),  # HTML标题

            # 列表模式
            re.compile(r'^\s*[-*+]\s+', re.MULTILINE),  # 无序列表
            re.compile(r'^\s*\d+\.\s+', re.MULTILINE),  # 有序列表

            # 代码块和表格
            re.compile(r'```.*?```', re.DOTALL),  # 代码块
            re.compile(r'\|.+\|.+\|', re.MULTILINE),  # 表格行
        ]

        logger.info(f"初始化并行处理器，最大工作线程数: {self.max_workers}，分块策略: {chunk_strategy.value}，分布式处理: {use_distributed}，内存高效模式: {memory_efficient}")

    def _split_by_strategy(
        self,
        text: str,
        chunk_size: int,
        strategy: ChunkingStrategy
    ) -> List[Tuple[int, int]]:
        """根据指定策略分割文本

        Args:
            text: 要分割的文本
            chunk_size: 目标块大小
            strategy: 分块策略

        Returns:
            分块边界列表，每个元素为(开始位置, 结束位置)
        """
        text_length = len(text)
        boundaries = []

        if strategy == ChunkingStrategy.FIXED_SIZE:
            # 固定大小分块，简单地按字符数分割
            for i in range(0, text_length, chunk_size):
                end = min(i + chunk_size, text_length)
                boundaries.append((i, end))

        elif strategy == ChunkingStrategy.SENTENCE_BOUNDARY:
            # 句子边界分块
            start = 0
            current_size = 0

            # 找到所有句子边界
            sentence_boundaries = [0]  # 起始位置
            for match in self.sentence_boundary_regex.finditer(text):
                sentence_boundaries.append(match.start())
            sentence_boundaries.append(text_length)  # 结束位置

            # 根据句子边界分块
            for i in range(1, len(sentence_boundaries)):
                boundary = sentence_boundaries[i]
                size = boundary - start

                if current_size + size > chunk_size and current_size > 0:
                    # 当前块已满，创建新块
                    boundaries.append((start, sentence_boundaries[i-1]))
                    start = sentence_boundaries[i-1]
                    current_size = boundary - start
                else:
                    # 继续添加到当前块
                    current_size += size

            # 添加最后一个块
            if start < text_length:
                boundaries.append((start, text_length))

        elif strategy == ChunkingStrategy.PARAGRAPH_BOUNDARY:
            # 段落边界分块
            start = 0
            current_size = 0

            # 找到所有段落边界
            paragraph_boundaries = [0]  # 起始位置
            for match in self.paragraph_boundary_regex.finditer(text):
                paragraph_boundaries.append(match.end())
            paragraph_boundaries.append(text_length)  # 结束位置

            # 根据段落边界分块
            for i in range(1, len(paragraph_boundaries)):
                boundary = paragraph_boundaries[i]
                size = boundary - start

                if current_size + size > chunk_size and current_size > 0:
                    # 当前块已满，创建新块
                    boundaries.append((start, paragraph_boundaries[i-1]))
                    start = paragraph_boundaries[i-1]
                    current_size = boundary - start
                else:
                    # 继续添加到当前块
                    current_size += size

            # 添加最后一个块
            if start < text_length:
                boundaries.append((start, text_length))

        elif strategy == ChunkingStrategy.SEMANTIC_BOUNDARY:
            # 语义边界分块
            # 找到所有语义边界
            semantic_boundaries = [0]  # 起始位置

            # 查找所有可能的语义边界
            for pattern in self.semantic_boundaries:
                for match in pattern.finditer(text):
                    # 对于标题，使用标题的结束位置
                    semantic_boundaries.append(match.end())

            # 排序并去重
            semantic_boundaries = sorted(set(semantic_boundaries))
            if text_length not in semantic_boundaries:
                semantic_boundaries.append(text_length)

            # 根据语义边界分块
            start = 0
            current_size = 0

            for boundary in semantic_boundaries[1:]:
                size = boundary - start

                if current_size + size > chunk_size and current_size > 0:
                    # 当前块已满，创建新块
                    # 找到最近的语义边界
                    nearest_boundary = start
                    for sb in semantic_boundaries:
                        if sb > start and sb - start <= chunk_size:
                            nearest_boundary = sb

                    boundaries.append((start, nearest_boundary))
                    start = nearest_boundary
                    current_size = boundary - start
                else:
                    # 继续添加到当前块
                    current_size += size

            # 添加最后一个块
            if start < text_length:
                boundaries.append((start, text_length))

        # 确保没有重叠或遗漏
        if boundaries:
            # 确保第一个块从0开始
            if boundaries[0][0] > 0:
                boundaries.insert(0, (0, boundaries[0][0]))

            # 确保最后一个块到文本结束
            if boundaries[-1][1] < text_length:
                boundaries.append((boundaries[-1][1], text_length))

            # 确保没有间隙
            for i in range(1, len(boundaries)):
                if boundaries[i][0] > boundaries[i-1][1]:
                    boundaries.insert(i, (boundaries[i-1][1], boundaries[i][0]))

        return boundaries

    async def _process_with_celery(
        self,
        chunks: List[Tuple[str, Dict[str, Any]]],
        processor_func_name: str
    ) -> List[BaseNode]:
        """使用Celery分布式处理文档块

        Args:
            chunks: 文档块列表，每个元素为(文本, 元数据)
            processor_func_name: 处理函数名称，必须是已注册的Celery任务

        Returns:
            处理后的节点列表
        """
        from celery import group

        # 创建任务组
        task_group = group(
            celery_app.signature(processor_func_name, args=(text, metadata))
            for text, metadata in chunks
        )

        # 执行任务组
        result = task_group.apply_async()

        # 等待所有任务完成
        while not result.ready():
            await asyncio.sleep(0.5)

        # 收集结果
        all_nodes = []
        for i, task_result in enumerate(result.get()):
            if isinstance(task_result, Exception):
                logger.error(f"处理块 {i+1} 时出错: {str(task_result)}")
            else:
                # 任务结果应该是节点列表
                all_nodes.extend(task_result)

        return all_nodes

    def _stream_document(self, document: Document, chunk_size: int) -> Iterator[Tuple[str, Dict[str, Any]]]:
        """流式处理文档，减少内存占用

        Args:
            document: 要处理的文档
            chunk_size: 块大小

        Returns:
            文档块迭代器
        """
        metadata = document.metadata or {}
        text = document.text
        text_length = len(text)

        # 使用选定的分块策略
        boundaries = self._split_by_strategy(text, chunk_size, self.chunk_strategy)

        # 生成文档块
        for i, (start, end) in enumerate(boundaries):
            chunk_text = text[start:end]
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["is_partial"] = len(boundaries) > 1
            chunk_metadata["chunk_start"] = start
            chunk_metadata["chunk_end"] = end

            yield chunk_text, chunk_metadata

    async def process_document_in_chunks(
        self,
        document: Document,
        processor_func: Callable[[str, Dict[str, Any]], List[BaseNode]],
        chunk_size: int = 100000,  # 每个块的字符数
        metadata: Optional[Dict[str, Any]] = None,
        preserve_order: bool = True,
        processor_func_name: Optional[str] = None  # Celery任务名称，用于分布式处理
    ) -> List[BaseNode]:
        """并行处理大型文档

        将文档分割成多个块，并行处理，然后合并结果

        Args:
            document: 要处理的文档
            processor_func: 处理函数，接收文本和元数据，返回节点列表
            chunk_size: 每个块的字符数
            metadata: 文档元数据
            preserve_order: 是否保持原始顺序
            processor_func_name: Celery任务名称，用于分布式处理

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

        # 根据选定的分块策略分割文档
        boundaries = self._split_by_strategy(text, chunk_size, self.chunk_strategy)

        # 创建文档块
        chunks = []
        for i, (start, end) in enumerate(boundaries):
            chunk_text = text[start:end]
            chunk_metadata = metadata.copy()
            chunk_metadata["chunk_index"] = i
            chunk_metadata["is_partial"] = True
            chunk_metadata["chunk_start"] = start
            chunk_metadata["chunk_end"] = end
            chunks.append((chunk_text, chunk_metadata))

        logger.info(f"将文档分割为 {len(chunks)} 个块进行并行处理，使用策略: {self.chunk_strategy.value}")

        # 根据处理模式选择处理方法
        if self.use_distributed and processor_func_name:
            # 使用Celery分布式处理
            logger.info(f"使用Celery分布式处理，任务名称: {processor_func_name}")
            all_nodes = await self._process_with_celery(chunks, processor_func_name)
        else:
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
                node.metadata.get("chunk_start", 0) if node.metadata else 0,
                node.metadata.get("node_position", 0) if node.metadata else 0
            ))

            # 清理临时元数据
            for node in all_nodes:
                if node.metadata:
                    node.metadata.pop("chunk_index", None)
                    node.metadata.pop("node_position", None)
                    node.metadata.pop("is_partial", None)
                    node.metadata.pop("chunk_start", None)
                    node.metadata.pop("chunk_end", None)

        logger.info(f"并行处理完成，总共生成 {len(all_nodes)} 个节点")
        return all_nodes

    async def process_multiple_documents(
        self,
        documents: List[Document],
        processor_func: Callable[[Document], List[BaseNode]],
        max_concurrent: Optional[int] = None,
        processor_func_name: Optional[str] = None,  # Celery任务名称，用于分布式处理
        batch_size: int = 10  # 批处理大小，用于内存优化
    ) -> List[BaseNode]:
        """并行处理多个文档

        Args:
            documents: 要处理的文档列表
            processor_func: 处理函数，接收文档，返回节点列表
            max_concurrent: 最大并发处理数，如果为None则使用max_workers
            processor_func_name: Celery任务名称，用于分布式处理
            batch_size: 批处理大小，用于内存优化

        Returns:
            处理后的节点列表
        """
        if not documents:
            return []

        max_concurrent = max_concurrent or self.max_workers

        logger.info(f"开始并行处理 {len(documents)} 个文档，最大并发数: {max_concurrent}")

        # 如果使用分布式处理
        if self.use_distributed and processor_func_name:
            from celery import group

            logger.info(f"使用Celery分布式处理，任务名称: {processor_func_name}")

            # 创建任务组
            task_group = group(
                celery_app.signature(processor_func_name, args=(doc.text, doc.metadata))
                for doc in documents
            )

            # 执行任务组
            result = task_group.apply_async()

            # 等待所有任务完成
            while not result.ready():
                await asyncio.sleep(0.5)

            # 收集结果
            all_nodes = []
            for i, task_result in enumerate(result.get()):
                if isinstance(task_result, Exception):
                    logger.error(f"处理文档 {i+1} 时出错: {str(task_result)}")
                else:
                    # 任务结果应该是节点列表
                    all_nodes.extend(task_result)

            return all_nodes

        # 如果使用内存高效模式，分批处理文档
        elif self.memory_efficient:
            logger.info(f"使用内存高效模式，批处理大小: {batch_size}")

            all_nodes = []

            # 分批处理文档
            for i in range(0, len(documents), batch_size):
                batch = documents[i:i+batch_size]
                logger.info(f"处理批次 {i//batch_size + 1}/{(len(documents) + batch_size - 1)//batch_size}，包含 {len(batch)} 个文档")

                # 创建信号量限制并发
                semaphore = asyncio.Semaphore(max_concurrent)

                async def process_with_semaphore(doc: Document) -> List[BaseNode]:
                    async with semaphore:
                        # 使用线程池执行CPU密集型任务
                        loop = asyncio.get_event_loop()
                        return await loop.run_in_executor(None, processor_func, doc)

                # 创建任务
                tasks = [process_with_semaphore(doc) for doc in batch]

                # 等待所有任务完成
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # 处理结果
                for j, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"处理文档 {i+j+1} 时出错: {str(result)}")
                    else:
                        all_nodes.extend(result)

                # 释放内存
                del batch
                del tasks
                del results

            logger.info(f"并行处理完成，总共生成 {len(all_nodes)} 个节点")
            return all_nodes

        # 使用标准并行处理
        else:
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

def get_parallel_processor(
    chunk_strategy: Optional[ChunkingStrategy] = None,
    use_distributed: Optional[bool] = None,
    memory_efficient: Optional[bool] = None,
    max_workers: Optional[int] = None
) -> ParallelProcessor:
    """获取并行处理器单例

    Args:
        chunk_strategy: 分块策略，如果为None则使用配置中的默认值
        use_distributed: 是否使用分布式处理，如果为None则使用配置中的默认值
        memory_efficient: 是否使用内存高效模式，如果为None则使用配置中的默认值
        max_workers: 最大工作线程数，如果为None则使用配置中的默认值

    Returns:
        并行处理器实例
    """
    global _parallel_processor

    # 从配置中获取默认值
    default_chunk_strategy = getattr(settings, "PARALLEL_CHUNK_STRATEGY", ChunkingStrategy.SENTENCE_BOUNDARY.value)
    default_use_distributed = getattr(settings, "PARALLEL_USE_DISTRIBUTED", False)
    default_memory_efficient = getattr(settings, "PARALLEL_MEMORY_EFFICIENT", False)
    default_max_workers = getattr(settings, "MAX_CONCURRENT_TASKS", None)

    # 如果没有指定参数，使用默认值
    chunk_strategy = chunk_strategy or ChunkingStrategy(default_chunk_strategy)
    use_distributed = use_distributed if use_distributed is not None else default_use_distributed
    memory_efficient = memory_efficient if memory_efficient is not None else default_memory_efficient
    max_workers = max_workers or default_max_workers

    # 如果实例不存在或参数与当前实例不同，创建新实例
    if (_parallel_processor is None or
        _parallel_processor.chunk_strategy != chunk_strategy or
        _parallel_processor.use_distributed != use_distributed or
        _parallel_processor.memory_efficient != memory_efficient or
        _parallel_processor.max_workers != max_workers):

        _parallel_processor = ParallelProcessor(
            max_workers=max_workers,
            chunk_strategy=chunk_strategy,
            use_distributed=use_distributed,
            memory_efficient=memory_efficient
        )

    return _parallel_processor
