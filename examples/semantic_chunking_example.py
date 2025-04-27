#!/usr/bin/env python
"""语义分块示例脚本"""
import logging
import os
import time
from typing import List

from llama_index.core import Document
from llama_index.core.schema import BaseNode

from enterprise_kb.core.enhanced_semantic_chunking import (
    create_enhanced_chunker,
    EnhancedSemanticChunker,
    SemanticBoundary
)
from enterprise_kb.core.semantic_chunking import (
    SemanticChunker,
    HierarchicalChunker
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def load_test_document(file_path: str) -> Document:
    """加载测试文档
    
    Args:
        file_path: 文档路径
        
    Returns:
        文档对象
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 获取文件类型
    _, ext = os.path.splitext(file_path)
    
    return Document(
        text=content,
        metadata={
            "file_type": ext,
            "file_name": os.path.basename(file_path),
            "doc_id": f"test_{os.path.basename(file_path)}"
        }
    )

def print_nodes(nodes: List[BaseNode], show_content: bool = True):
    """打印节点信息
    
    Args:
        nodes: 节点列表
        show_content: 是否显示节点内容
    """
    logger.info(f"共生成 {len(nodes)} 个节点")
    
    for i, node in enumerate(nodes):
        logger.info(f"节点 {i+1}:")
        
        # 打印元数据
        if node.metadata:
            logger.info(f"  元数据: {node.metadata}")
        
        # 打印内容
        if show_content:
            content = node.text[:100] + "..." if len(node.text) > 100 else node.text
            logger.info(f"  内容: {content}")
        
        logger.info(f"  长度: {len(node.text)} 字符")
        logger.info("-" * 40)

def test_original_chunkers(document: Document):
    """测试原始分块器
    
    Args:
        document: 测试文档
    """
    logger.info("测试原始语义分块器")
    
    # 创建语义分块器
    semantic_chunker = SemanticChunker(
        chunk_size=1024,
        chunk_overlap=20
    )
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理文档
    nodes = semantic_chunker.get_nodes_from_documents([document])
    
    # 计算处理时间
    elapsed_time = time.time() - start_time
    
    logger.info(f"原始语义分块器处理完成，耗时 {elapsed_time:.2f} 秒")
    print_nodes(nodes, show_content=False)
    
    logger.info("测试层次化分块器")
    
    # 创建层次化分块器
    hierarchical_chunker = HierarchicalChunker(
        chunk_size=1024,
        chunk_overlap=20
    )
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理文档
    nodes = hierarchical_chunker.get_nodes_from_documents([document])
    
    # 计算处理时间
    elapsed_time = time.time() - start_time
    
    logger.info(f"层次化分块器处理完成，耗时 {elapsed_time:.2f} 秒")
    print_nodes(nodes, show_content=False)

def test_enhanced_chunker(document: Document):
    """测试增强语义分块器
    
    Args:
        document: 测试文档
    """
    logger.info("测试增强语义分块器")
    
    # 创建增强语义分块器
    enhanced_chunker = EnhancedSemanticChunker(
        chunk_size=1024,
        chunk_overlap=20,
        context_window=100,
        preserve_boundary_content=True,
        respect_document_structure=True,
        language="chinese"
    )
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理文档
    nodes = enhanced_chunker.get_nodes_from_documents([document])
    
    # 计算处理时间
    elapsed_time = time.time() - start_time
    
    logger.info(f"增强语义分块器处理完成，耗时 {elapsed_time:.2f} 秒")
    print_nodes(nodes)
    
    # 测试不同的配置
    logger.info("测试自定义边界重要性")
    
    # 自定义边界重要性
    boundary_importance = {
        SemanticBoundary.HEADING: 1.0,
        SemanticBoundary.PARAGRAPH: 0.7,
        SemanticBoundary.LIST_ITEM: 0.8,
        SemanticBoundary.CODE_BLOCK: 1.0,
        SemanticBoundary.TABLE: 1.0,
        SemanticBoundary.QUOTE: 0.6,
        SemanticBoundary.HORIZONTAL_RULE: 0.9,
        SemanticBoundary.SENTENCE: 0.4,
        SemanticBoundary.SECTION_BREAK: 0.9
    }
    
    # 创建自定义分块器
    custom_chunker = EnhancedSemanticChunker(
        chunk_size=1024,
        chunk_overlap=50,
        context_window=200,
        boundary_importance=boundary_importance,
        language="chinese"
    )
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理文档
    nodes = custom_chunker.get_nodes_from_documents([document])
    
    # 计算处理时间
    elapsed_time = time.time() - start_time
    
    logger.info(f"自定义分块器处理完成，耗时 {elapsed_time:.2f} 秒")
    print_nodes(nodes, show_content=False)

def test_factory_function(document: Document):
    """测试工厂函数
    
    Args:
        document: 测试文档
    """
    logger.info("测试分块器工厂函数")
    
    # 创建语义分块器
    semantic_chunker = create_enhanced_chunker(
        chunk_size=1024,
        chunk_overlap=20,
        chunking_type="semantic"
    )
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理文档
    nodes = semantic_chunker.get_nodes_from_documents([document])
    
    # 计算处理时间
    elapsed_time = time.time() - start_time
    
    logger.info(f"工厂函数创建的语义分块器处理完成，耗时 {elapsed_time:.2f} 秒")
    print_nodes(nodes, show_content=False)
    
    # 创建层次化分块器
    hierarchical_chunker = create_enhanced_chunker(
        chunk_size=1024,
        chunk_overlap=20,
        chunking_type="hierarchical"
    )
    
    # 记录开始时间
    start_time = time.time()
    
    # 处理文档
    nodes = hierarchical_chunker.get_nodes_from_documents([document])
    
    # 计算处理时间
    elapsed_time = time.time() - start_time
    
    logger.info(f"工厂函数创建的层次化分块器处理完成，耗时 {elapsed_time:.2f} 秒")
    print_nodes(nodes, show_content=False)

def main():
    """主函数"""
    logger.info("开始测试语义分块功能")
    
    # 加载测试文档
    doc_path = "docs/semantic_chunking.md"
    if not os.path.exists(doc_path):
        logger.error(f"测试文档 {doc_path} 不存在")
        return
    
    document = load_test_document(doc_path)
    logger.info(f"加载测试文档: {doc_path}, 大小: {len(document.text)} 字符")
    
    # 测试原始分块器
    test_original_chunkers(document)
    
    # 测试增强分块器
    test_enhanced_chunker(document)
    
    # 测试工厂函数
    test_factory_function(document)
    
    logger.info("测试完成")

if __name__ == "__main__":
    main()
