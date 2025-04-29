from typing import Any, Dict, List, Optional, cast
from llama_index.core import StorageContext
from llama_index.vector_stores.milvus import MilvusVectorStore, IndexManagement
from llama_index.core.schema import TextNode, BaseNode
import time
import logging
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

def get_storage_context(retry_attempts: int = 3, retry_delay: float = 1.0) -> StorageContext:
    """获取基于Milvus的存储上下文
    
    Args:
        retry_attempts: 连接重试次数
        retry_delay: 重试延迟（秒）
        
    Returns:
        存储上下文对象
        
    Raises:
        ConnectionError: 连接失败时抛出
    """
    # 确定索引管理策略
    index_management_str = settings.MILVUS_INDEX_MANAGEMENT
    index_management = IndexManagement.CREATE_IF_NOT_EXISTS
    if index_management_str == "NO_VALIDATION":
        index_management = IndexManagement.NO_VALIDATION
    
    # 使用重试机制连接Milvus
    last_exception = None
    for attempt in range(retry_attempts):
        try:
            # 使用官方Milvus实现
            vector_store = MilvusVectorStore(
                uri=settings.MILVUS_URI,
                collection_name=settings.MILVUS_COLLECTION,
                dim=settings.MILVUS_DIMENSION,
                text_field=settings.MILVUS_TEXT_FIELD,
                embedding_field=settings.MILVUS_EMBEDDING_FIELD,
                metadata_field=settings.MILVUS_METADATA_FIELD,
                id_field=settings.MILVUS_ID_FIELD,
                index_management=index_management,
                overwrite=settings.MILVUS_OVERWRITE
            )
            storage_context = StorageContext.from_defaults(vector_store=vector_store)
            logger.info(f"成功连接Milvus向量存储: {settings.MILVUS_URI}")
            return storage_context
        except Exception as e:
            last_exception = e
            logger.warning(f"连接Milvus失败 (尝试 {attempt+1}/{retry_attempts}): {str(e)}")
            if attempt < retry_attempts - 1:
                time.sleep(retry_delay * (attempt + 1))  # 指数退避
    
    # 所有重试都失败
    logger.error(f"无法连接Milvus向量存储，重试 {retry_attempts} 次后失败: {str(last_exception)}")
    raise ConnectionError(f"无法连接Milvus向量存储: {str(last_exception)}")
    
def add_texts_to_vector_store(
    texts: List[str],
    metadatas: List[Dict[str, Any]],
    ids: Optional[List[str]] = None,
    batch_size: int = 100
) -> List[str]:
    """将文本添加到向量存储
    
    Args:
        texts: 文本列表
        metadatas: 元数据列表
        ids: ID列表（可选）
        batch_size: 批量处理大小
        
    Returns:
        添加的文档ID列表
        
    Raises:
        ValueError: 参数错误
        ConnectionError: 连接失败
    """
    if len(texts) != len(metadatas):
        raise ValueError("texts和metadatas长度必须相同")
    
    if ids is not None and len(ids) != len(texts):
        raise ValueError("ids长度必须与texts长度相同")
    
    try:
        # 获取存储上下文
        storage_context = get_storage_context()
        vector_store = storage_context.vector_store
        
        # 创建节点列表
        nodes = []
        for i, text in enumerate(texts):
            node_id = ids[i] if ids is not None else None
            metadata = metadatas[i]
            
            # 创建文本节点
            node = TextNode(
                text=text,
                id_=node_id,
                metadata=metadata
            )
            nodes.append(node)
        
        # 分批添加节点
        all_ids = []
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i+batch_size]
            batch_ids = vector_store.add(batch)
            all_ids.extend(batch_ids)
            logger.info(f"已添加 {len(batch)} 个文档到向量存储 (批次 {i//batch_size + 1})")
        
        return all_ids
    except Exception as e:
        logger.error(f"添加文本到向量存储失败: {str(e)}")
        raise
        
def delete_texts_from_vector_store(doc_ids: List[str]) -> bool:
    """从向量存储中删除文本
    
    Args:
        doc_ids: 文档ID列表
        
    Returns:
        是否成功
        
    Raises:
        ConnectionError: 连接失败
    """
    try:
        # 获取存储上下文
        storage_context = get_storage_context()
        vector_store = storage_context.vector_store
        
        # 构建删除过滤器
        from llama_index.core.vector_stores.types import MetadataFilters, FilterOperator, FilterCondition
        
        # 删除文档
        for doc_id in doc_ids:
            try:
                # 构建过滤条件
                filter_condition = FilterCondition(
                    key="doc_id", 
                    value=doc_id, 
                    operator=FilterOperator.EQ
                )
                metadata_filter = MetadataFilters(filters=[filter_condition])
                
                # 执行删除
                vector_store.delete(filter=metadata_filter)
                logger.info(f"从向量存储中删除文档: {doc_id}")
            except Exception as e:
                logger.warning(f"删除文档 {doc_id} 失败: {str(e)}")
        
        return True
    except Exception as e:
        logger.error(f"从向量存储中删除文档失败: {str(e)}")
        raise