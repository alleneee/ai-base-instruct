from typing import Any, Dict, List, Optional, cast
from llama_index.core import StorageContext
from llama_index.core.schema import TextNode, BaseNode
from llama_index.core.vector_stores.types import VectorStore, VectorStoreQuery
from llama_index.core.vector_stores.utils import metadata_dict_to_node, node_to_metadata_dict

import logging
import uuid
from enterprise_kb.utils.milvus_client import get_milvus_client
from enterprise_kb.config.settings import settings

logger = logging.getLogger(__name__)

class MilvusVectorStore(VectorStore):
    """基于Milvus的LlamaIndex向量存储实现"""
    
    stores_text: bool = True
    
    def __init__(
        self,
        collection_name: str = settings.MILVUS_COLLECTION,
        host: str = settings.MILVUS_HOST,
        port: int = settings.MILVUS_PORT,
        dimension: int = settings.MILVUS_DIMENSION,
    ) -> None:
        """初始化Milvus向量存储"""
        self.collection_name = collection_name
        self.host = host
        self.port = port
        self.dimension = dimension
        
        # 获取Milvus客户端
        self.client = get_milvus_client()
        self.client.create_collection()  # 确保集合已创建
    
    def add(self, nodes: List[BaseNode]) -> List[str]:
        """添加节点到向量存储"""
        ids = []
        
        for node in nodes:
            node_id = node.node_id or str(uuid.uuid4())
            ids.append(node_id)
            
            # 获取节点元数据
            metadata = node_to_metadata_dict(node)
            
            # 获取嵌入向量
            if node.embedding is None:
                logger.warning(f"节点 {node_id} 没有嵌入向量，跳过")
                continue
                
            # 获取文本内容
            text = node.get_content(metadata_mode="all")
            
            # 将数据插入到Milvus
            try:
                doc_id = metadata.get("doc_id", "unknown")
                self.client.insert(
                    doc_id=doc_id,
                    chunk_id=node_id,
                    text=text,
                    vector=node.embedding,
                    metadata=metadata
                )
            except Exception as e:
                logger.error(f"向量插入失败: {str(e)}")
                raise
                
        return ids
    
    def delete(self, doc_id: str) -> None:
        """根据文档ID删除向量"""
        try:
            self.client.delete(f"doc_id == '{doc_id}'")
        except Exception as e:
            logger.error(f"向量删除失败: {str(e)}")
            raise
    
    def query(self, query: VectorStoreQuery) -> List[BaseNode]:
        """查询向量存储"""
        query_embedding = query.query_embedding
        if query_embedding is None:
            raise ValueError("查询嵌入向量不能为空")
            
        # 构建过滤表达式
        filter_expr = None
        if query.filters is not None:
            filter_clauses = []
            for k, v in query.filters.items():
                if isinstance(v, str):
                    filter_clauses.append(f"metadata['{k}'] == '{v}'")
                else:
                    filter_clauses.append(f"metadata['{k}'] == {v}")
            
            if filter_clauses:
                filter_expr = " && ".join(filter_clauses)
                
        # 执行搜索
        try:
            results = self.client.search(
                query_vector=query_embedding,
                limit=query.similarity_top_k,
                filter_expr=filter_expr
            )
            
            # 将搜索结果转换为节点
            nodes = []
            for hit in results:
                node = metadata_dict_to_node(hit["metadata"])
                node.embedding = query_embedding
                node.text = hit["text"]
                node.extra_info["score"] = hit["score"]
                nodes.append(node)
                
            return nodes
        except Exception as e:
            logger.error(f"向量查询失败: {str(e)}")
            raise

    @property
    def client_id(self) -> str:
        """返回客户端标识符"""
        return f"milvus:{self.host}:{self.port}:{self.collection_name}"


def get_storage_context() -> StorageContext:
    """获取基于Milvus的存储上下文"""
    vector_store = MilvusVectorStore()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    return storage_context 