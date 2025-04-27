"""文档块处理任务模块，用于分布式处理大型文档"""
import logging
from typing import Dict, List, Any, Optional

from llama_index.core.schema import TextNode, BaseNode

from enterprise_kb.core.celery.app import celery_app
from enterprise_kb.core.celery.task_manager import tracked_task

logger = logging.getLogger(__name__)

@tracked_task(
    name="enterprise_kb.tasks.document_chunk_tasks.process_text_chunk",
    soft_time_limit=300,  # 5分钟
    time_limit=360,       # 6分钟
)
def process_text_chunk(text: str, metadata: Dict[str, Any]) -> List[BaseNode]:
    """处理文本块
    
    Args:
        text: 文本内容
        metadata: 元数据
        
    Returns:
        处理后的节点列表
    """
    try:
        logger.info(f"开始处理文本块，长度: {len(text)}")
        
        # 创建简单的文本节点
        # 在实际应用中，这里可能会有更复杂的处理逻辑
        node = TextNode(
            text=text,
            metadata=metadata
        )
        
        logger.info(f"文本块处理完成")
        return [node]
    except Exception as e:
        logger.error(f"处理文本块时出错: {str(e)}")
        raise

@tracked_task(
    name="enterprise_kb.tasks.document_chunk_tasks.process_text_with_chunking",
    soft_time_limit=600,  # 10分钟
    time_limit=720,       # 12分钟
)
def process_text_with_chunking(
    text: str, 
    metadata: Dict[str, Any],
    chunk_size: int = 1024,
    chunk_overlap: int = 20
) -> List[BaseNode]:
    """处理文本并进行分块
    
    Args:
        text: 文本内容
        metadata: 元数据
        chunk_size: 块大小
        chunk_overlap: 块重叠大小
        
    Returns:
        处理后的节点列表
    """
    try:
        from llama_index.core.node_parser import SentenceSplitter
        
        logger.info(f"开始处理并分块文本，长度: {len(text)}")
        
        # 使用SentenceSplitter进行分块
        splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # 创建文档并分块
        from llama_index.core import Document
        doc = Document(text=text, metadata=metadata)
        nodes = splitter.get_nodes_from_documents([doc])
        
        logger.info(f"文本分块完成，生成 {len(nodes)} 个节点")
        return nodes
    except Exception as e:
        logger.error(f"处理文本并分块时出错: {str(e)}")
        raise

@tracked_task(
    name="enterprise_kb.tasks.document_chunk_tasks.merge_nodes",
    soft_time_limit=300,  # 5分钟
    time_limit=360,       # 6分钟
)
def merge_nodes(node_lists: List[List[BaseNode]]) -> List[BaseNode]:
    """合并多个节点列表
    
    Args:
        node_lists: 节点列表的列表
        
    Returns:
        合并后的节点列表
    """
    try:
        # 合并所有节点
        all_nodes = []
        for nodes in node_lists:
            all_nodes.extend(nodes)
        
        # 按照元数据中的索引排序
        all_nodes.sort(key=lambda node: (
            node.metadata.get("chunk_index", 0) if node.metadata else 0,
            node.metadata.get("node_position", 0) if node.metadata else 0
        ))
        
        logger.info(f"节点合并完成，总共 {len(all_nodes)} 个节点")
        return all_nodes
    except Exception as e:
        logger.error(f"合并节点时出错: {str(e)}")
        raise
