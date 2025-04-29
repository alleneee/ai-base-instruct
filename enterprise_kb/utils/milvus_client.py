"""Milvus向量数据库客户端模块"""
from pymilvus import connections, Collection, utility
from pymilvus import CollectionSchema, FieldSchema, DataType
import logging
from typing import List, Dict, Any, Optional, Union, Tuple
import json
import numpy as np
import time
from functools import wraps

from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

def retry_on_connection_error(max_retries=3, retry_delay=1.0):
    """重试装饰器，用于处理连接错误"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if "connection" in str(e).lower() or "timeout" in str(e).lower():
                        logger.warning(f"连接错误，尝试重新连接 ({attempt+1}/{max_retries}): {str(e)}")
                        time.sleep(retry_delay * (attempt + 1))  # 指数退避
                    else:
                        # 非连接错误，直接抛出
                        raise
            # 所有重试失败
            logger.error(f"重试 {max_retries} 次后仍然失败: {str(last_exception)}")
            raise last_exception
        return wrapper
    return decorator

class MilvusClient:
    """Milvus向量数据库客户端，提供连接和集合管理功能"""
    
    def __init__(
        self, 
        host: str = settings.MILVUS_HOST,
        port: int = settings.MILVUS_PORT,
        user: str = settings.MILVUS_USER,
        password: str = settings.MILVUS_PASSWORD,
        collection_name: str = settings.MILVUS_COLLECTION,
        dimension: int = settings.MILVUS_DIMENSION
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.uri = f"http://{host}:{port}"
        self.collection_name = collection_name
        self.dimension = dimension
        self.collection = None
        self._connection_alias = "default"
        self._connect()
        
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def _connect(self) -> None:
        """连接到Milvus服务器"""
        try:
            # 检查是否已连接
            if connections.has_connection(self._connection_alias):
                logger.debug(f"已有连接存在，重用现有连接: {self._connection_alias}")
                return
                
            conn_params = {
                "alias": self._connection_alias, 
                "host": self.host, 
                "port": self.port
            }
            
            # 如果提供了用户名和密码，添加到连接参数中
            if self.user and self.password:
                conn_params["user"] = self.user
                conn_params["password"] = self.password
                
            connections.connect(**conn_params)
            logger.info(f"成功连接到Milvus服务器: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"连接到Milvus服务器失败: {str(e)}")
            raise
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def create_collection(self, force_recreate: bool = False) -> None:
        """创建向量集合

        Args:
            force_recreate: 如果为True，将删除已存在的同名集合并重新创建
        """
        # 确保已连接
        self._connect()
        
        # 如果集合存在且不需要强制重建，直接加载
        if utility.has_collection(self.collection_name) and not force_recreate:
            self.collection = Collection(self.collection_name)
            self.collection.load()
            logger.info(f"加载已存在的集合: {self.collection_name}")
            return
            
        # 如果需要重建集合
        if utility.has_collection(self.collection_name) and force_recreate:
            try:
                # 先释放资源
                if self.collection:
                    self.collection.release()
                    self.collection = None
                utility.drop_collection(self.collection_name)
                logger.info(f"删除并重建集合: {self.collection_name}")
            except Exception as e:
                logger.error(f"删除集合失败: {str(e)}")
                raise
            
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
            using=self._connection_alias, 
            shards_num=2
        )
        
        # 创建索引
        self.create_index()
        logger.info(f"创建集合并构建索引: {self.collection_name}")
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def create_index(self) -> None:
        """为向量字段创建索引"""
        if not self.collection:
            self.create_collection()
            
        try:
            # 检查是否已经有索引
            if self.collection.has_index():
                logger.info(f"集合 {self.collection_name} 已有索引，跳过创建")
                return
                
            # 创建索引
            index_params = {
                "metric_type": "L2",          # 使用L2距离（欧氏距离）
                "index_type": "HNSW",         # 使用HNSW索引类型，适合高维向量
                "params": {
                    "M": 16,                  # 每个节点最多的出边数量
                    "efConstruction": 200     # 建立索引时的搜索宽度
                }
            }
            
            self.collection.create_index(
                field_name="vector",
                index_params=index_params
            )
            
            # 加载集合到内存
            self.collection.load()
            
            logger.info(f"成功为集合 {self.collection_name} 创建索引")
        except Exception as e:
            logger.error(f"创建索引失败: {str(e)}")
            raise
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def insert(self, doc_id: str, chunk_id: str, text: str, vector: List[float], metadata: Dict[str, Any]) -> None:
        """向集合中插入文档向量数据"""
        if self.collection is None:
            self.create_collection()
            
        try:
            # 确保metadata是JSON可序列化的
            metadata_str = metadata
            if not isinstance(metadata, str):
                metadata_str = json.dumps(metadata)
                
            # 插入数据
            data = [
                [doc_id],     # doc_id
                [chunk_id],   # chunk_id
                [text],       # text
                [metadata_str],   # metadata
                [vector]      # vector
            ]
            
            self.collection.insert(data)
            logger.debug(f"向集合 {self.collection_name} 插入文档块 {chunk_id}")
        except Exception as e:
            logger.error(f"向量插入失败: {str(e)}")
            raise
            
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def batch_insert(self, data_batch: List[Dict[str, Any]], batch_size: int = 100) -> int:
        """批量插入向量数据
        
        Args:
            data_batch: 数据字典列表，每个字典包含 doc_id, chunk_id, text, vector, metadata
            batch_size: 批量插入大小
            
        Returns:
            插入的记录数
        """
        if self.collection is None:
            self.create_collection()
            
        total_inserted = 0
        try:
            # 按批次处理
            for i in range(0, len(data_batch), batch_size):
                batch = data_batch[i:i+batch_size]
                
                # 准备批量插入数据
                doc_ids = []
                chunk_ids = []
                texts = []
                metadata_list = []
                vectors = []
                
                for item in batch:
                    doc_ids.append(item["doc_id"])
                    chunk_ids.append(item.get("chunk_id", item["doc_id"]))
                    texts.append(item["text"])
                    
                    # 处理元数据
                    metadata = item.get("metadata", {})
                    if not isinstance(metadata, str):
                        metadata = json.dumps(metadata)
                    metadata_list.append(metadata)
                    
                    # 处理向量
                    vectors.append(item["vector"])
                
                # 执行批量插入
                insert_data = [
                    doc_ids,
                    chunk_ids,
                    texts,
                    metadata_list,
                    vectors
                ]
                
                result = self.collection.insert(insert_data)
                inserted_count = result.insert_count if result else 0
                total_inserted += inserted_count
                
                logger.debug(f"批量插入第 {i//batch_size + 1} 批数据，共 {inserted_count} 条记录")
                
            logger.info(f"批量插入完成，总共插入 {total_inserted} 条记录")
            return total_inserted
        except Exception as e:
            logger.error(f"批量插入失败: {str(e)}")
            raise
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def search(self, vector: List[float], top_k: int = 5, expr: Optional[str] = None, output_fields: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """搜索最相似的向量
        
        Args:
            vector: 查询向量
            top_k: 返回的最大结果数
            expr: 过滤表达式
            output_fields: 要返回的字段列表
            
        Returns:
            匹配的文档列表
        """
        if self.collection is None:
            self.create_collection()
            
        try:
            # 确保集合已加载
            try:
                self.collection.load()
            except Exception as e:
                logger.warning(f"加载集合异常（集合可能已经加载）: {str(e)}")
                
            # 设置搜索参数
            search_params = {
                "metric_type": "L2",
                "params": {"ef": 64}  # 运行时搜索参数，较大的值会增加精度但降低速度
            }
            
            # 设置返回字段
            if output_fields is None:
                output_fields = ["doc_id", "chunk_id", "text", "metadata"]
                
            # 执行搜索
            results = self.collection.search(
                data=[vector],               # 查询向量
                anns_field="vector",         # 要搜索的向量字段
                param=search_params,         # 搜索参数
                limit=top_k,                 # 返回的最大结果数
                expr=expr,                   # 过滤表达式
                output_fields=output_fields  # 要返回的字段
            )
            
            # 处理结果
            processed_results = []
            for hits in results:
                for hit in hits:
                    item = {}
                    for i, field in enumerate(output_fields):
                        item[field] = hit.entity.get(field)
                    
                    # 添加距离和ID
                    item["distance"] = hit.distance
                    item["id"] = hit.id
                    
                    # 解析元数据JSON
                    if "metadata" in item and isinstance(item["metadata"], str):
                        try:
                            item["metadata"] = json.loads(item["metadata"])
                        except:
                            pass
                            
                    processed_results.append(item)
                    
            return processed_results
        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            raise
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def get_by_doc_id(self, doc_id: str) -> List[Dict[str, Any]]:
        """根据文档ID获取向量数据
        
        Args:
            doc_id: 文档ID
            
        Returns:
            匹配的文档列表
        """
        if self.collection is None:
            self.create_collection()
            
        try:
            # 确保集合已加载
            try:
                self.collection.load()
            except Exception as e:
                logger.warning(f"加载集合异常（集合可能已经加载）: {str(e)}")
                
            # 构造查询表达式
            expr = f'doc_id == "{doc_id}"'
            
            # 设置输出字段
            output_fields = ["doc_id", "chunk_id", "text", "metadata"]
            
            # 执行查询
            results = self.collection.query(
                expr=expr,
                output_fields=output_fields
            )
            
            # 处理元数据
            for item in results:
                if "metadata" in item and isinstance(item["metadata"], str):
                    try:
                        item["metadata"] = json.loads(item["metadata"])
                    except:
                        pass
                        
            return results
        except Exception as e:
            logger.error(f"获取文档 {doc_id} 失败: {str(e)}")
            raise
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def delete_by_doc_id(self, doc_id: str) -> int:
        """根据文档ID删除向量数据
        
        Args:
            doc_id: 文档ID
            
        Returns:
            删除的记录数
        """
        if self.collection is None:
            self.create_collection()
            
        try:
            # 确保集合已加载
            try:
                self.collection.load()
            except Exception as e:
                logger.warning(f"加载集合异常（集合可能已经加载）: {str(e)}")
                
            # 构造删除表达式
            expr = f'doc_id == "{doc_id}"'
            
            # 执行删除
            result = self.collection.delete(expr=expr)
            
            # 返回删除的记录数
            delete_count = result.delete_count if result else 0
            logger.info(f"删除文档 {doc_id}，共删除 {delete_count} 条记录")
            return delete_count
        except Exception as e:
            logger.error(f"删除文档 {doc_id} 失败: {str(e)}")
            raise
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def batch_delete_by_doc_ids(self, doc_ids: List[str]) -> int:
        """批量删除向量数据
        
        Args:
            doc_ids: 文档ID列表
            
        Returns:
            删除的记录数
        """
        if not doc_ids:
            logger.warning("批量删除传入了空的文档ID列表")
            return 0
            
        if self.collection is None:
            self.create_collection()
            
        try:
            # 确保集合已加载
            try:
                self.collection.load()
            except Exception as e:
                logger.warning(f"加载集合异常（集合可能已经加载）: {str(e)}")
                
            # 构造删除表达式，使用IN表达式
            ids_str = ", ".join([f'"{id_}"' for id_ in doc_ids])
            expr = f'doc_id in [{ids_str}]'
            
            # 执行删除
            result = self.collection.delete(expr=expr)
            
            # 返回删除的记录数
            delete_count = result.delete_count if result else 0
            logger.info(f"批量删除文档，共删除 {delete_count} 条记录")
            return delete_count
        except Exception as e:
            logger.error(f"批量删除文档失败: {str(e)}")
            raise
            
    def close(self) -> None:
        """关闭连接"""
        try:
            # 释放集合资源
            if self.collection:
                try:
                    self.collection.release()
                except Exception as e:
                    logger.warning(f"释放集合资源异常: {str(e)}")
                self.collection = None
                
            # 断开连接
            try:
                if connections.has_connection(self._connection_alias):
                    connections.disconnect(self._connection_alias)
            except Exception as e:
                logger.warning(f"断开连接异常: {str(e)}")
                
            logger.info("关闭Milvus连接")
        except Exception as e:
            logger.error(f"关闭Milvus连接失败: {str(e)}")
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息
        
        Returns:
            集合统计信息字典
        """
        if self.collection is None:
            if not utility.has_collection(self.collection_name):
                return {
                    "name": self.collection_name,
                    "exists": False,
                    "error": f"集合 {self.collection_name} 不存在"
                }
            self.collection = Collection(self.collection_name)
            
        try:
            # 获取基本信息
            stats = {
                "name": self.collection_name,
                "exists": True,
                "row_count": self.collection.num_entities,
                "fields": [field.name for field in self.collection.schema.fields]
            }
            
            # 获取索引信息
            if self.collection.has_index():
                index_info = self.collection.index().to_dict()
                stats["index"] = index_info
                
            return stats
        except Exception as e:
            logger.error(f"获取集合统计信息失败: {str(e)}")
            return {
                "name": self.collection_name,
                "exists": utility.has_collection(self.collection_name),
                "error": str(e)
            }
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def flush(self) -> None:
        """将内存中的数据刷新到存储中"""
        if self.collection is None:
            self.create_collection()
        
        try:
            self.collection.flush()
            logger.info(f"成功刷新集合 {self.collection_name}")
        except Exception as e:
            logger.error(f"刷新集合失败: {str(e)}")
            raise
    
    @retry_on_connection_error(max_retries=3, retry_delay=1.0)
    def compact(self) -> None:
        """压缩集合，清理已删除的数据空间"""
        if self.collection is None:
            self.create_collection()
        
        try:
            self.collection.compact()
            logger.info(f"成功压缩集合 {self.collection_name}")
        except Exception as e:
            logger.error(f"压缩集合失败: {str(e)}")
            raise

# 单例模式，提供全局Milvus客户端
milvus_client = None

def get_milvus_client() -> MilvusClient:
    """获取Milvus客户端单例"""
    global milvus_client
    if milvus_client is None:
        milvus_client = MilvusClient()
    return milvus_client 