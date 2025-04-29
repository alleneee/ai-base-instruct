"""混合检索引擎模块，结合向量搜索和关键词搜索"""
import logging
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from enum import Enum
import numpy as np
import random

from llama_index.core import Settings
from llama_index.core.schema import NodeWithScore, TextNode, BaseNode
from llama_index.embeddings.openai import OpenAIEmbedding
from sentence_transformers import CrossEncoder

from enterprise_kb.core.keyword_search import KeywordSearchEngine
from enterprise_kb.storage.vector_store_manager import get_vector_store_manager
from enterprise_kb.core.config.settings import settings
from enterprise_kb.storage.datasource.milvus import MilvusDataSource

logger = logging.getLogger(__name__)


class SearchType(Enum):
    """搜索类型"""
    VECTOR = "vector"       # 向量搜索
    KEYWORD = "keyword"     # 关键词搜索
    HYBRID = "hybrid"       # 混合搜索


class HybridRetrievalEngine:
    """混合检索引擎，结合向量搜索和关键词搜索"""

    def __init__(self):
        """初始化混合检索引擎"""
        # 设置嵌入模型 - R E M O V E D (Handled by settings.py)
        # Settings.embed_model = OpenAIEmbedding()

        # 获取向量存储管理器
        self.vector_store_manager = get_vector_store_manager()

        # 创建关键词搜索引擎
        self.keyword_engine = KeywordSearchEngine()

        # 关键词搜索和向量搜索的权重
        self.keyword_weight = 0.3
        self.vector_weight = 0.7

        # 文档节点缓存
        self.nodes_cache = {}

        # 初始化 Reranker 模型 (懒加载或预加载)
        self.reranker_model_name = settings.RERANKER_MODEL_NAME
        self.reranker_model = None
        self.rerank_top_n = settings.RERANK_TOP_N
        self._load_reranker()

    def _load_reranker(self):
        """加载 Reranker 模型"""
        if not self.reranker_model and self.reranker_model_name:
            try:
                logger.info(f"Loading reranker model: {self.reranker_model_name}")
                # Consider adding device='cuda' or device='mps' if GPU is available
                self.reranker_model = CrossEncoder(self.reranker_model_name)
                logger.info("Reranker model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load reranker model '{self.reranker_model_name}': {e}", exc_info=True)
                self.reranker_model = None # Ensure it's None if loading failed
        elif not self.reranker_model_name:
             logger.warning("RERANKER_MODEL_NAME is not set in settings. Reranking will be disabled.")
             self.reranker_model = None

    async def index_documents(self, datasource_name: Optional[str] = None):
        """从向量存储中索引文档到关键词引擎

        Args:
            datasource_name: 数据源名称，如果为None则索引所有数据源
        """
        try:
            # 获取所有文档节点
            nodes = await self._get_nodes_from_datasources(datasource_name)

            # 添加到关键词索引
            if nodes:
                self.keyword_engine.add_documents(nodes)
                logger.info(f"已为关键词搜索引擎索引 {len(nodes)} 个文档")
            else:
                logger.warning("没有找到要索引的文档")

        except Exception as e:
            logger.error(f"索引文档失败: {str(e)}")
            raise

    async def _get_nodes_from_datasources(self, datasource_name: Optional[str] = None) -> List[TextNode]:
        """从数据源获取文档节点

        Args:
            datasource_name: 数据源名称，如果为None则获取所有数据源

        Returns:
            文档节点列表
        """
        # 生成缓存键
        cache_key = datasource_name or "all_datasources"

        # 如果缓存中存在，直接返回
        if cache_key in self.nodes_cache:
            return self.nodes_cache[cache_key]

        nodes = []
        try:
            # 获取数据源列表
            if datasource_name:
                datasources = [datasource_name]
            else:
                datasource_infos = await self.vector_store_manager.list_data_sources()
                datasources = [ds.name for ds in datasource_infos]

            # 获取每个数据源中的所有文档
            for ds_name in datasources:
                try:
                    # 使用随机查询向量检索所有文档
                    # 这里使用一个较大的top_k值，以尽可能获取所有文档

                    # 生成随机查询向量
                    random_query_vector = np.random.rand(settings.MILVUS_DIMENSION).tolist()

                    # 获取向量存储中的所有文档
                    results = await self.vector_store_manager.query(
                        query_embedding=random_query_vector,
                        datasource_name=ds_name,
                        top_k=10000,  # 设置一个很大的值以获取尽可能多的文档
                        filters=None
                    )

                    # 如果需要可以用多次查询并合并结果的方式获取更完整的文档集
                    # 这里简化为单次查询

                    for node in results:
                        # 创建新的TextNode以避免对原始对象的修改
                        text_node = TextNode(
                            text=node.node.text,
                            node_id=node.node.node_id,
                            metadata=node.node.metadata.copy() if node.node.metadata else {}
                        )
                        # 如果节点中没有数据源信息，添加数据源信息
                        if text_node.metadata and "datasource" not in text_node.metadata:
                            text_node.metadata["datasource"] = ds_name

                        nodes.append(text_node)

                    logger.info(f"从数据源 {ds_name} 检索到 {len(results)} 个文档节点")

                except Exception as e:
                    logger.error(f"从数据源 {ds_name} 获取文档失败: {str(e)}")
                    continue

            # 去重：有时不同数据源可能包含相同文档
            unique_nodes = {}
            for node in nodes:
                node_id = node.node_id
                if node_id not in unique_nodes:
                    unique_nodes[node_id] = node

            nodes = list(unique_nodes.values())

            # 缓存结果以便后续使用
            self.nodes_cache[cache_key] = nodes
            logger.info(f"总共从{len(datasources)}个数据源获取到{len(nodes)}个唯一文档节点")

            return nodes

        except Exception as e:
            logger.error(f"获取数据源节点失败: {str(e)}")
            return []

    async def retrieve(
        self,
        query: str,
        search_type: SearchType = SearchType.HYBRID,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        milvus_filter_expr: Optional[str] = None,
        min_score: float = 0.0,
        datasource_names: Optional[List[str]] = None,
        rerank: bool = True # Default rerank to True if model is available
    ) -> List[NodeWithScore]:
        """执行检索

        Args:
            query: 查询文本
            search_type: 搜索类型
            top_k: 返回结果数量
            filters: 应用层过滤条件 (LlamaIndex style) - 可能需要转换为milvus_filter_expr
            milvus_filter_expr: Milvus原生过滤表达式 (e.g., "category == 'news'")
            min_score: 最小分数阈值 (注意Milvus分数体系可能不同)
            datasource_names: 目标数据源列表
            rerank: 是否在检索后执行额外的应用层重排序 (通常不需要，因为Milvus有内置ranker)

        Returns:
            匹配文档列表
        """
        try:
            initial_results: List[NodeWithScore] = []

            if search_type == SearchType.HYBRID:
                # --- Use Native Milvus Hybrid Search ---
                if not datasource_names:
                    # 查找第一个类型为milvus的数据源作为默认目标
                    datasource_infos = await self.vector_store_manager.list_data_sources()
                    milvus_sources = [ds.name for ds in datasource_infos if ds.type == 'milvus']
                    if not milvus_sources:
                        logger.error("No Milvus datasource found for hybrid search.")
                        return []
                    target_datasource_name = milvus_sources[0]
                    logger.info(f"No datasource specified, defaulting to first Milvus source: {target_datasource_name}")
                elif len(datasource_names) > 1:
                    # 当前实现仅支持对单个Milvus源执行原生混合搜索
                    target_datasource_name = datasource_names[0]
                    logger.warning(f"Multiple datasources provided, using the first one for native hybrid search: {target_datasource_name}")
                else:
                    target_datasource_name = datasource_names[0]

                datasource = self.vector_store_manager.data_sources.get(target_datasource_name)

                # 检查是否是MilvusDataSource并且支持原生混合搜索
                if isinstance(datasource, MilvusDataSource) and hasattr(datasource, 'hybrid_search'):
                    logger.info(f"Executing native hybrid search on datasource: {target_datasource_name}")
                    # 生成查询嵌入
                    query_embedding = Settings.embed_model.get_query_embedding(query)

                    # TODO: Convert LlamaIndex filters (dict) to Milvus expr (str) if needed
                    # if filters and not milvus_filter_expr:
                    #     milvus_filter_expr = self._convert_filters_to_expr(filters)

                    # 调用原生混合搜索方法
                    # Request more initial results for reranking if rerank=True
                    initial_top_k = self.rerank_top_n if rerank and self.reranker_model else top_k
                    initial_results = await datasource.hybrid_search(
                        query_text=query,
                        query_vector=query_embedding,
                        top_k=initial_top_k,
                        filter_expr=milvus_filter_expr,
                    )

                else:
                    logger.warning(f"Datasource '{target_datasource_name}' is not a MilvusDataSource or does not support native hybrid_search. Falling back to vector search.")
                    # 回退到纯向量搜索
                    initial_results = await self._vector_search(query, self.rerank_top_n if rerank and self.reranker_model else top_k, filters, 0.0, [target_datasource_name] if target_datasource_name else None)

            elif search_type == SearchType.VECTOR:
                logger.info("Executing vector-only search.")
                initial_results = await self._vector_search(query, self.rerank_top_n if rerank and self.reranker_model else top_k, filters, 0.0, datasource_names)

            elif search_type == SearchType.KEYWORD:
                 logger.info("Executing keyword-only search.")
                 initial_results = self._keyword_search(query, self.rerank_top_n if rerank and self.reranker_model else top_k, datasource_names)

            # --- Re-ranking Step --- (Moved outside the specific search type blocks)
            if rerank and self.reranker_model and initial_results:
                logger.info(f"Applying reranking to top {len(initial_results)} results...")
                # Ensure reranker model is loaded
                if not self.reranker_model:
                    self._load_reranker()
                
                if self.reranker_model:
                    reranked_results = await self.rerank_results(initial_results, query)
                    # Apply min_score filter *after* reranking
                    final_results = [node for node in reranked_results if node.score >= min_score]
                    # Limit to final top_k after reranking
                    final_results = final_results[:top_k]
                    logger.info(f"Reranking completed. Returning {len(final_results)} results.")
                    return final_results
                else:
                     logger.warning("Reranker model not available, skipping reranking.")
                     # Fallback to initial results, apply min_score and top_k
                     final_results = [node for node in initial_results if node.score >= min_score]
                     final_results = final_results[:top_k]
                     return final_results
            else:
                # No reranking requested or possible, apply min_score and top_k to initial results
                final_results = [node for node in initial_results if node.score >= min_score]
                final_results = final_results[:top_k]
                logger.info(f"No reranking applied. Returning {len(final_results)} initial results.")
                return final_results

        except Exception as e:
            logger.exception(f"Retrieval failed (type: {search_type}): {str(e)}")
            # Fallback logic can be kept or adjusted
            try:
                logger.warning("Falling back to vector search...")
                return await self._vector_search(query, top_k, filters, min_score, datasource_names)
            except Exception as e2:
                logger.exception(f"Fallback vector search also failed: {str(e2)}")
                return []

    async def _vector_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.0,
        datasource_names: Optional[List[str]] = None
    ) -> List[NodeWithScore]:
        """执行向量搜索 (使用 VectorStoreManager)"""
        try:
            query_embedding = Settings.embed_model.get_query_embedding(query)

            # TODO: Improve handling of multiple datasources for vector search if needed
            target_ds_name = datasource_names[0] if datasource_names else None
            if not target_ds_name:
                 datasource_infos = await self.vector_store_manager.list_data_sources()
                 # Find first available datasource
                 if datasource_infos:
                     target_ds_name = datasource_infos[0].name
                     logger.info(f"No datasource specified for vector search, defaulting to: {target_ds_name}")
                 else:
                     logger.error("No datasources available for vector search.")
                     return []

            logger.debug(f"Performing vector search on '{target_ds_name}' with top_k={top_k}, filters={filters}")

            # 使用 VectorStoreManager 查询
            # 注意：这里的 filters 是 LlamaIndex 格式的字典过滤器
            # 如果目标是 MilvusDataSource，VectorStoreManager 可能需要转换它
            # 或者直接调用 datasource.search_documents 如果原生实现更优

            datasource = self.vector_store_manager.data_sources.get(target_ds_name)
            if isinstance(datasource, MilvusDataSource):
                logger.debug("Targeting MilvusDataSource, attempting native vector search.")
                # Convert LlamaIndex filters to Milvus expr if possible
                milvus_expr = self._convert_filters_to_expr(filters) if filters else None
                results = await datasource.search_documents(
                    query_vector=query_embedding,
                    top_k=top_k,
                    filter_expr=milvus_expr
                )
            elif target_ds_name in self.vector_store_manager.indices: # Fallback to LlamaIndex general query if not Milvus or native fails
                logger.debug("Targeting non-Milvus or using LlamaIndex query fallback.")
                # Use LlamaIndex VectorStoreQuery for potentially broader compatibility
                from llama_index.core.vector_stores.types import VectorStoreQuery, MetadataFilters
                metadata_filters_obj = MetadataFilters.from_dict(filters) if filters else None
                vector_query = VectorStoreQuery(
                    query_embedding=query_embedding,
                    similarity_top_k=top_k,
                    filters=metadata_filters_obj
                )
                # LlamaIndex query might return different structure, adapt if needed
                index = self.vector_store_manager.indices[target_ds_name]
                retriever = index.as_retriever(similarity_top_k=top_k)
                results = retriever.retrieve(vector_query)
                # Convert results if necessary, LlamaIndex retriever might return nodes directly
            else:
                logger.error(f"Datasource '{target_ds_name}' not found or incompatible for vector search.")
                results = []

            final_results = [node for node in results if node.score >= min_score]
            logger.info(f"Vector search completed. Returning {len(final_results)} results.")
            return final_results
        except Exception as e:
            logger.exception(f"Vector search failed: {str(e)}")
            return []

    def _keyword_search(
        self,
        query: str,
        top_k: int = 5,
        datasource_names: Optional[List[str]] = None
    ) -> List[NodeWithScore]:
        """执行关键词搜索 (使用 KeywordSearchEngine)"""
        try:
            logger.debug(f"Performing keyword search with query: '{query}', top_k={top_k}")
            # TODO: Enhance KeywordSearchEngine to support filtering by datasource_names if required
            results = self.keyword_engine.search(query, top_k=top_k)

            # Ensure results are in NodeWithScore format
            final_results = []
            for node in results:
                if isinstance(node, NodeWithScore):
                    final_results.append(node)
                elif isinstance(node, BaseNode):
                    # Assign a default score if keyword search doesn't provide one
                    final_results.append(NodeWithScore(node=node, score=1.0))

            logger.info(f"Keyword search completed. Returning {len(final_results)} results.")
            return final_results
        except Exception as e:
            logger.exception(f"Keyword search failed: {str(e)}")
            return []

    def _convert_filters_to_expr(self, filters: Dict[str, Any]) -> Optional[str]:
        """(Helper) 将 LlamaIndex 字典过滤器转换为 Milvus expr 字符串 (简化版)"""
        # TODO: Implement robust conversion logic based on supported operators
        parts = []
        for key, value in filters.items():
            if isinstance(value, str):
                # Basic equality for strings (needs proper escaping)
                safe_value = value.replace("'", "''")
                parts.append(f"metadata['{key}'] == '{safe_value}'")
            elif isinstance(value, (int, float)):
                parts.append(f"metadata['{key}'] == {value}")
            elif isinstance(value, bool):
                 parts.append(f"metadata['{key}'] == {str(value).lower()}")
            # Add more type/operator handling here (e.g., >, <, in, etc.)
        if not parts:
            return None
        return " and ".join(parts)

    async def rerank_results(
        self,
        results: List[NodeWithScore],
        query: str
    ) -> List[NodeWithScore]:
        """使用 Cross-Encoder 模型重排序初步检索结果。

        Args:
            results: 初步检索到的 NodeWithScore 列表。
            query: 原始用户查询。

        Returns:
            经过重排序的 NodeWithScore 列表。
        """
        if not results:
            return []
        if not self.reranker_model:
            logger.warning("Reranker model is not loaded. Cannot perform reranking.")
            return results # Return original results if no model

        try:
            # 1. 准备模型输入：[query, document_text] 对
            pairs = [[query, node.get_content()] for node in results]

            # 2. 使用模型预测分数 (这部分是同步/CPU密集型，可以在异步函数中运行)
            # Consider running in executor if it becomes a bottleneck: asyncio.to_thread
            logger.debug(f"Reranking {len(pairs)} pairs with model {self.reranker_model_name}...")
            scores = self.reranker_model.predict(pairs, show_progress_bar=False) # Set True for debugging progress
            logger.debug("Reranking prediction completed.")

            # 3. 更新节点分数并组合
            reranked_results = []
            for i, node_with_score in enumerate(results):
                new_score = scores[i]
                # Cross-encoder scores are typically relevance scores, higher is better.
                # No need to normalize unless required by downstream tasks.
                reranked_node = NodeWithScore(node=node_with_score.node, score=float(new_score))
                reranked_results.append(reranked_node)

            # 4. 按新分数降序排序
            reranked_results.sort(key=lambda x: x.score, reverse=True)

            return reranked_results

        except Exception as e:
            logger.error(f"Reranking failed: {e}", exc_info=True)
            return results # Return original results on error

    async def list_datasources(self) -> List[str]:
        """获取所有可用的数据源名称

        Returns:
            数据源名称列表
        """
        try:
            data_sources = await self.vector_store_manager.list_data_sources()
            return [ds.name for ds in data_sources]
        except Exception as e:
            logger.error(f"获取数据源列表失败: {str(e)}")
            return []


# 创建单例实例
_hybrid_retrieval_engine = None

async def get_hybrid_retrieval_engine() -> HybridRetrievalEngine:
    """获取混合检索引擎单例"""
    global _hybrid_retrieval_engine
    if _hybrid_retrieval_engine is None:
        _hybrid_retrieval_engine = HybridRetrievalEngine()
        # 初始化关键词索引
        await _hybrid_retrieval_engine.index_documents()
    return _hybrid_retrieval_engine