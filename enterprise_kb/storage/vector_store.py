"""向量存储模块"""
from typing import Any, Dict, List, Optional, cast

from llama_index.core import StorageContext
from llama_index.vector_stores.milvus import MilvusVectorStore, IndexManagement
from llama_index.core.schema import TextNode, BaseNode

import logging

from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

def get_storage_context() -> StorageContext:
    """获取基于Milvus的存储上下文"""
    # 使用官方Milvus实现
    vector_store = MilvusVectorStore(
        uri=f"http://{settings.MILVUS_HOST}:{settings.MILVUS_PORT}",
        collection_name=settings.MILVUS_COLLECTION,
        dim=settings.MILVUS_DIMENSION,
        index_management=IndexManagement.CREATE_IF_NOT_EXISTS,  # 仅在不存在时创建索引
        overwrite=False  # 不覆盖现有集合
    )
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return storage_context