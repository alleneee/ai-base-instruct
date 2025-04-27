#!/usr/bin/env python
"""并行处理示例脚本"""
import asyncio
import logging
import os
import time
from typing import Dict, List, Any

from llama_index.core import Document
from llama_index.core.schema import TextNode, BaseNode

from enterprise_kb.core.parallel_processor import get_parallel_processor, ChunkingStrategy
from enterprise_kb.core.config.settings import settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 示例处理函数
def process_text(text: str, metadata: Dict[str, Any]) -> List[BaseNode]:
    """处理文本块，返回节点列表"""
    # 模拟处理时间
    time.sleep(0.1)
    
    # 创建文本节点
    node = TextNode(
        text=text,
        metadata=metadata
    )
    
    return [node]

# 示例文档处理函数
def process_document(document: Document) -> List[BaseNode]:
    """处理整个文档，返回节点列表"""
    # 模拟处理时间
    time.sleep(0.5)
    
    # 创建文本节点
    node = TextNode(
        text=document.text,
        metadata=document.metadata
    )
    
    return [node]

async def test_parallel_processing():
    """测试并行处理功能"""
    # 创建测试文档
    large_text = "这是一个测试文档。" * 10000  # 约20万字符
    document = Document(
        text=large_text,
        metadata={"title": "测试文档", "source": "示例脚本"}
    )
    
    # 测试不同的分块策略
    strategies = [
        ChunkingStrategy.FIXED_SIZE,
        ChunkingStrategy.SENTENCE_BOUNDARY,
        ChunkingStrategy.PARAGRAPH_BOUNDARY,
        ChunkingStrategy.SEMANTIC_BOUNDARY
    ]
    
    for strategy in strategies:
        logger.info(f"测试分块策略: {strategy.value}")
        
        # 获取并行处理器
        parallel_processor = get_parallel_processor(
            chunk_strategy=strategy,
            max_workers=4
        )
        
        # 记录开始时间
        start_time = time.time()
        
        # 处理文档
        nodes = await parallel_processor.process_document_in_chunks(
            document=document,
            processor_func=process_text,
            chunk_size=50000
        )
        
        # 计算处理时间
        elapsed_time = time.time() - start_time
        
        logger.info(f"分块策略 {strategy.value} 处理完成，生成 {len(nodes)} 个节点，耗时 {elapsed_time:.2f} 秒")

async def test_multiple_documents():
    """测试处理多个文档"""
    # 创建测试文档列表
    documents = []
    for i in range(20):
        text = f"这是测试文档 {i+1}。" * 1000
        doc = Document(
            text=text,
            metadata={"title": f"测试文档 {i+1}", "doc_id": f"doc_{i+1}"}
        )
        documents.append(doc)
    
    logger.info(f"测试处理 {len(documents)} 个文档")
    
    # 测试标准并行处理
    parallel_processor = get_parallel_processor(
        max_workers=4
    )
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理文档
    nodes = await parallel_processor.process_multiple_documents(
        documents=documents,
        processor_func=process_document
    )
    
    # 计算处理时间
    elapsed_time = time.time() - start_time
    
    logger.info(f"标准并行处理完成，生成 {len(nodes)} 个节点，耗时 {elapsed_time:.2f} 秒")
    
    # 测试内存优化模式
    parallel_processor = get_parallel_processor(
        max_workers=4,
        memory_efficient=True
    )
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理文档
    nodes = await parallel_processor.process_multiple_documents(
        documents=documents,
        processor_func=process_document,
        batch_size=5
    )
    
    # 计算处理时间
    elapsed_time = time.time() - start_time
    
    logger.info(f"内存优化模式处理完成，生成 {len(nodes)} 个节点，耗时 {elapsed_time:.2f} 秒")

async def main():
    """主函数"""
    logger.info("开始测试并行处理功能")
    
    # 测试并行处理
    await test_parallel_processing()
    
    # 测试处理多个文档
    await test_multiple_documents()
    
    logger.info("测试完成")

if __name__ == "__main__":
    asyncio.run(main())
