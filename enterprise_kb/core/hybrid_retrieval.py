"""混合检索引擎模块，结合向量搜索和关键词搜索"""
import logging
from typing import Dict, List, Optional, Any, Set, Tuple, Union
from enum import Enum
import numpy as np
import random

from llama_index.core import Settings
from llama_index.core.schema import NodeWithScore, TextNode, BaseNode
from llama_index.embeddings.openai import OpenAIEmbedding

from enterprise_kb.core.keyword_search import KeywordSearchEngine
from enterprise_kb.storage.vector_store_manager import get_vector_store_manager
from enterprise_kb.core.config.settings import settings

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
        # 设置嵌入模型
        Settings.embed_model = OpenAIEmbedding()

        # 获取向量存储管理器
        self.vector_store_manager = get_vector_store_manager()

        # 创建关键词搜索引擎
        self.keyword_engine = KeywordSearchEngine()

        # 关键词搜索和向量搜索的权重
        self.keyword_weight = 0.3
        self.vector_weight = 0.7

        # 文档节点缓存
        self.nodes_cache = {}

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
        min_score: float = 0.7,
        datasource_names: Optional[List[str]] = None,
        rerank: bool = True
    ) -> List[NodeWithScore]:
        """执行检索

        Args:
            query: 查询文本
            search_type: 搜索类型，可以是向量搜索、关键词搜索或混合搜索
            top_k: 返回的最大结果数
            filters: 过滤条件，例如 {"file_type": ".pdf"}
            min_score: 最小相似度分数
            datasource_names: 要查询的数据源名称列表，如果为None则查询所有数据源
            rerank: 是否对结果重新排序

        Returns:
            匹配文档列表
        """
        try:
            # 根据搜索类型执行不同的检索策略
            if search_type == SearchType.VECTOR:
                # 只执行向量搜索
                return await self._vector_search(
                    query=query,
                    top_k=top_k,
                    filters=filters,
                    min_score=min_score,
                    datasource_names=datasource_names
                )

            elif search_type == SearchType.KEYWORD:
                # 只执行关键词搜索
                return self._keyword_search(
                    query=query,
                    top_k=top_k
                )

            else:  # 混合搜索
                # 执行向量搜索和关键词搜索，然后融合结果
                vector_results = await self._vector_search(
                    query=query,
                    top_k=top_k * 2,  # 获取更多结果，以便融合后仍有足够结果
                    filters=filters,
                    min_score=min_score,
                    datasource_names=datasource_names
                )

                keyword_results = self._keyword_search(
                    query=query,
                    top_k=top_k * 2
                )

                # 融合结果
                hybrid_results = self._merge_results(
                    vector_results=vector_results,
                    keyword_results=keyword_results,
                    top_k=top_k
                )

                # 重排序结果
                if rerank and hybrid_results:
                    hybrid_results = self._rerank_results(
                        results=hybrid_results,
                        query=query
                    )

                return hybrid_results

        except Exception as e:
            logger.error(f"混合检索失败: {str(e)}")
            # 如果混合检索失败，尝试回退到向量搜索
            try:
                return await self._vector_search(
                    query=query,
                    top_k=top_k,
                    filters=filters,
                    min_score=min_score,
                    datasource_names=datasource_names
                )
            except Exception as e2:
                logger.error(f"回退向量搜索也失败: {str(e2)}")
                return []

    async def _vector_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.7,
        datasource_names: Optional[List[str]] = None
    ) -> List[NodeWithScore]:
        """执行向量搜索

        Args:
            query: 查询文本
            top_k: 返回的最大结果数
            filters: 过滤条件
            min_score: 最小相似度分数
            datasource_names: 要查询的数据源名称列表，如果为None则查询所有数据源

        Returns:
            匹配文档列表
        """
        try:
            # 获取嵌入向量
            embed_model = Settings.embed_model
            query_embedding = embed_model.get_text_embedding(query)

            # 使用向量存储管理器查询
            results = await self.vector_store_manager.query(
                query_embedding=query_embedding,
                datasource_name=datasource_names[0] if datasource_names and len(datasource_names) == 1 else None,
                top_k=top_k,
                filters=filters
            )

            # 过滤低分结果
            filtered_results = []
            for node in results:
                if hasattr(node, "score") and node.score >= min_score:
                    # 标记结果来源
                    if hasattr(node, "extra_info"):
                        node.extra_info["search_type"] = "vector"

                    filtered_results.append(node)

            logger.info(f"向量搜索 '{query}' 找到 {len(filtered_results)} 个结果")
            return filtered_results

        except Exception as e:
            logger.error(f"向量搜索失败: {str(e)}")
            return []

    def _keyword_search(
        self,
        query: str,
        top_k: int = 5
    ) -> List[NodeWithScore]:
        """执行关键词搜索

        Args:
            query: 查询文本
            top_k: 返回的最大结果数

        Returns:
            匹配文档列表
        """
        try:
            # 调用关键词检索引擎
            results = self.keyword_engine.search(
                query=query,
                top_k=top_k,
                use_keywords=True
            )

            # 标记结果来源
            for node in results:
                if hasattr(node, "extra_info"):
                    node.extra_info["search_type"] = "keyword"

            logger.info(f"关键词搜索 '{query}' 找到 {len(results)} 个结果")
            return results

        except Exception as e:
            logger.error(f"关键词搜索失败: {str(e)}")
            return []

    def _merge_results(
        self,
        vector_results: List[NodeWithScore],
        keyword_results: List[NodeWithScore],
        top_k: int = 5
    ) -> List[NodeWithScore]:
        """融合向量搜索和关键词搜索结果

        Args:
            vector_results: 向量搜索结果
            keyword_results: 关键词搜索结果
            top_k: 返回的最大结果数

        Returns:
            融合后的结果列表
        """
        # 使用字典记录所有结果，以节点ID为键，避免重复
        merged = {}

        # 添加向量搜索结果
        for node in vector_results:
            node_id = node.node.node_id

            # 标准化分数
            normalized_score = node.score

            # 记录结果
            merged[node_id] = {
                "node": node,
                "vector_score": normalized_score,
                "keyword_score": 0.0
            }

        # 添加关键词搜索结果
        for node in keyword_results:
            node_id = node.node.node_id

            # 标准化分数
            normalized_score = node.score / max(1.0, max([n.score for n in keyword_results]))

            if node_id in merged:
                # 已存在，添加关键词分数
                merged[node_id]["keyword_score"] = normalized_score
            else:
                # 新结果
                merged[node_id] = {
                    "node": node,
                    "vector_score": 0.0,
                    "keyword_score": normalized_score
                }

        # 计算混合得分
        for node_id, data in merged.items():
            # 加权融合分数
            hybrid_score = (
                self.vector_weight * data["vector_score"] +
                self.keyword_weight * data["keyword_score"]
            )

            # 更新分数
            data["hybrid_score"] = hybrid_score

        # 按混合分数排序
        sorted_results = sorted(
            merged.values(),
            key=lambda x: x["hybrid_score"],
            reverse=True
        )

        # 构建最终结果
        results = []
        for data in sorted_results[:top_k]:
            node = data["node"]
            # 更新分数为混合分数
            node.score = data["hybrid_score"]

            # 添加分数明细到extra_info
            if hasattr(node, "extra_info"):
                node.extra_info["vector_score"] = data["vector_score"]
                node.extra_info["keyword_score"] = data["keyword_score"]
                node.extra_info["search_type"] = "hybrid"

            results.append(node)

        logger.info(f"混合搜索找到 {len(results)} 个结果")
        return results

    def _rerank_results(
        self,
        results: List[NodeWithScore],
        query: str
    ) -> List[NodeWithScore]:
        """重排序结果（内部方法）

        Args:
            results: 初始结果列表
            query: 查询文本

        Returns:
            重排序后的结果列表
        """
        # 简单实现：对结果按相似度排序
        # 如果有更复杂的重排序需求，可以集成外部重排序模型

        # 确保分数在[0,1]范围内
        for node in results:
            if node.score > 1.0:
                node.score = min(1.0, node.score / 10.0)

        # 简单调整：提升包含查询关键词的结果分数
        keywords = self.keyword_engine.extract_keywords(query)
        if keywords:
            for node in results:
                text = node.node.text.lower()
                # 计算文本中包含的关键词数量
                keyword_count = sum(1 for kw in keywords if kw.lower() in text)
                if keyword_count > 0:
                    # 提升分数
                    bonus = 0.1 * (keyword_count / len(keywords))
                    node.score = min(1.0, node.score + bonus)

        # 按分数重新排序
        results.sort(key=lambda x: x.score, reverse=True)

        return results

    async def rerank_results(
        self,
        results: List[NodeWithScore],
        query: str
    ) -> List[NodeWithScore]:
        """重排序结果（公共方法）

        Args:
            results: 初始结果列表
            query: 查询文本

        Returns:
            重排序后的结果列表
        """
        # 如果结果为空，直接返回
        if not results:
            return []

        # 调用内部重排序方法
        reranked_results = self._rerank_results(results, query)

        # 对于查询重写的结果，进行额外处理
        for node in reranked_results:
            # 检查是否有查询变体信息
            if hasattr(node, "extra_info") and "query_variant" in node.extra_info:
                variant = node.extra_info["query_variant"]
                # 如果变体与原始查询不同，稍微降低分数
                if variant != query:
                    # 降低10%的分数，但保持排序相对稳定
                    node.score = node.score * 0.9

                # 添加变体信息到元数据，方便前端展示
                if node.node.metadata is None:
                    node.node.metadata = {}
                node.node.metadata["query_variant"] = variant

        # 再次按分数排序
        reranked_results.sort(key=lambda x: x.score, reverse=True)

        return reranked_results

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