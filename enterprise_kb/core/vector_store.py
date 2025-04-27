from typing import Any, Dict, List, Optional, cast
from llama_index.core import StorageContext
from llama_index.vector_stores.milvus import MilvusVectorStore, IndexManagement
from llama_index.core.schema import TextNode, BaseNode

import logging
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

def get_storage_context() -> StorageContext:
    """获取基于Milvus的存储上下文"""
    # 确定索引管理策略
    index_management_str = settings.MILVUS_INDEX_MANAGEMENT
    index_management = IndexManagement.CREATE_IF_NOT_EXISTS
    if index_management_str == "NO_VALIDATION":
        index_management = IndexManagement.NO_VALIDATION
    
    # 使用官方Milvus实现
    vector_store = MilvusVectorStore(
        uri=settings.MILVUS_URI,
        collection_name=settings.MILVUS_COLLECTION,
        dim=settings.MILVUS_DIMENSION,
        index_management=index_management,
        overwrite=settings.MILVUS_OVERWRITE
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return storage_context