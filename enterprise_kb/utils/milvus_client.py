"""Milvus向量数据库客户端模块"""
from pymilvus import connections, Collection, utility
from pymilvus import CollectionSchema, FieldSchema, DataType
import logging
from typing import List, Dict, Any, Optional

from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

class MilvusClient:
    """Milvus向量数据库客户端，提供连接和集合管理功能"""
    
    def __init__(
        self, 
        host: str = settings.MILVUS_HOST,
        port: int = settings.MILVUS_PORT,
        collection_name: str = settings.MILVUS_COLLECTION,
        dimension: int = settings.MILVUS_DIMENSION
    ):
        self.host = host
        self.port = port
        self.collection_name = collection_name
        self.dimension = dimension
        self.collection = None
        self._connect()
        
    def _connect(self) -> None:
        """连接到Milvus服务器"""
        try:
            connections.connect(
                alias="default", 
                host=self.host, 
                port=self.port
            )
            logger.info(f"成功连接到Milvus服务器: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"连接到Milvus服务器失败: {str(e)}")
            raise
    
    def create_collection(self) -> None:
        """创建向量集合（如果不存在）"""
        if utility.has_collection(self.collection_name):
            self.collection = Collection(self.collection_name)
            logger.info(f"加载已存在的集合: {self.collection_name}")
            return
            
        # 定义集合字段
        fields = [
            FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
            FieldSchema(name="doc_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="chunk_id", dtype=DataType.VARCHAR, max_length=100),
            FieldSchema(name="text", dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name="metadata", dtype=DataType.JSON),
            FieldSchema(name="vector", dtype=DataType.FLOAT_VECTOR, dim=self.dimension)
        ]
        
        # 创建集合模式
        schema = CollectionSchema(fields=fields, description="企业知识库向量存储")
        
        # 创建集合
        self.collection = Collection(
            name=self.collection_name, 
            schema=schema, 
            using='default', 
            shards_num=2
        )
        
        # 创建索引
        index_params = {
            "index_type": "HNSW",
            "metric_type": "COSINE",
            "params": {"M": 8, "efConstruction": 64}
        }
        self.collection.create_index(field_name="vector", index_params=index_params)
        logger.info(f"创建集合并构建索引: {self.collection_name}")
    
    def insert(self, doc_id: str, chunk_id: str, text: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        """向集合中插入文档向量数据"""
        if self.collection is None:
            self.create_collection()
            
        try:
            self.collection.insert([
                [doc_id],     # doc_id
                [chunk_id],   # chunk_id
                [text],       # text
                [metadata],   # metadata
                [vector]      # vector
            ])
            logger.debug(f"向集合 {self.collection_name} 插入文档块 {chunk_id}")
        except Exception as e:
            logger.error(f"向量插入失败: {str(e)}")
            raise
    
    def search(
        self, 
        query_vector: List[float], 
        limit: int = 5, 
        filter_expr: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """搜索最相似的向量"""
        if self.collection is None:
            self.create_collection()
            
        try:
            self.collection.load()
            search_params = {"metric_type": "COSINE", "params": {"ef": 64}}
            results = self.collection.search(
                data=[query_vector], 
                anns_field="vector", 
                param=search_params,
                limit=limit,
                expr=filter_expr,
                output_fields=["doc_id", "chunk_id", "text", "metadata"]
            )
            
            hits = []
            for hit in results[0]:
                hits.append({
                    "doc_id": hit.entity.get("doc_id"),
                    "chunk_id": hit.entity.get("chunk_id"),
                    "text": hit.entity.get("text"),
                    "metadata": hit.entity.get("metadata"),
                    "distance": hit.distance,
                    "score": 1 - hit.distance  # 转换余弦距离为相似度分数
                })
            
            return hits
        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            raise
    
    def delete(self, filter_expr: str) -> None:
        """根据表达式删除向量"""
        if self.collection is None:
            self.create_collection()
            
        try:
            self.collection.delete(filter_expr)
            logger.info(f"删除满足条件的向量: {filter_expr}")
        except Exception as e:
            logger.error(f"向量删除失败: {str(e)}")
            raise
            
    def close(self) -> None:
        """关闭连接"""
        try:
            connections.disconnect("default")
            logger.info("关闭Milvus连接")
        except Exception as e:
            logger.error(f"关闭Milvus连接失败: {str(e)}")

# 单例模式，提供全局Milvus客户端
milvus_client = None

def get_milvus_client() -> MilvusClient:
    """获取Milvus客户端单例"""
    global milvus_client
    if milvus_client is None:
        milvus_client = MilvusClient()
    return milvus_client 