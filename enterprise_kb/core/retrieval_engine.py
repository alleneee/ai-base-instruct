"""检索引擎模块，提供向量检索功能"""
from typing import Dict, List, Optional, Any, Union, Set
import logging
from pydantic import BaseModel, Field
from enum import Enum

from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.schema import NodeWithScore
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.embeddings.openai import OpenAIEmbedding

from enterprise_kb.core.config.settings import settings
from enterprise_kb.core.hybrid_retrieval import get_hybrid_retrieval_engine, SearchType

logger = logging.getLogger(__name__)

class SearchMode(str, Enum):
    """搜索模式枚举"""
    VECTOR = "vector"    # 仅向量搜索
    KEYWORD = "keyword"  # 仅关键词搜索
    HYBRID = "hybrid"    # 混合搜索（默认）

class RetrievalResult(BaseModel):
    """检索结果模型"""
    text: str
    score: float
    doc_id: str
    datasource: str = Field("未知", description="数据源名称")
    file_name: Optional[str] = None
    metadata: Dict[str, Any] = {}
    search_source: str = Field("hybrid", description="搜索来源")
    
class RetrievalEngine:
    """知识检索引擎"""
    
    def __init__(self):
        """初始化检索引擎"""
        # 设置LlamaIndex全局配置
        Settings.embed_model = OpenAIEmbedding()
        
        # 混合检索引擎实例
        self.hybrid_engine = None
    
    async def _get_hybrid_engine(self):
        """获取混合检索引擎实例"""
        if self.hybrid_engine is None:
            self.hybrid_engine = await get_hybrid_retrieval_engine()
        return self.hybrid_engine
    
    async def retrieve(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.7,
        datasource_names: Optional[List[str]] = None,
        search_mode: SearchMode = SearchMode.HYBRID
    ) -> List[RetrievalResult]:
        """根据查询文本检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回的最大文档数
            filters: 过滤条件，例如 {"file_type": ".pdf"}
            min_score: 最小相似度分数
            datasource_names: 要查询的数据源名称列表，如果为None则查询所有数据源
            search_mode: 搜索模式，可选向量搜索、关键词搜索或混合搜索
            
        Returns:
            匹配文档列表
        """
        try:
            # 获取混合检索引擎
            hybrid_engine = await self._get_hybrid_engine()
            
            # 根据搜索模式选择搜索类型
            search_type = SearchType.HYBRID
            if search_mode == SearchMode.VECTOR:
                search_type = SearchType.VECTOR
            elif search_mode == SearchMode.KEYWORD:
                search_type = SearchType.KEYWORD
            
            # 执行检索
            nodes = await hybrid_engine.retrieve(
                query=query,
                search_type=search_type,
                top_k=top_k,
                filters=filters,
                min_score=min_score,
                datasource_names=datasource_names,
                rerank=True
            )
            
            # 转换为检索结果
            results = []
            for node in nodes:
                # 提取元数据
                metadata = node.node.metadata or {}
                doc_id = metadata.get("doc_id", "unknown")
                file_name = metadata.get("file_name", None)
                datasource = metadata.get("datasource", "未知")
                
                # 获取搜索来源
                search_source = "hybrid"
                if hasattr(node, "extra_info") and "search_type" in node.extra_info:
                    search_source = node.extra_info["search_type"]
                
                # 构建结果
                result = RetrievalResult(
                    text=node.node.text,
                    score=node.score,
                    doc_id=doc_id,
                    file_name=file_name,
                    datasource=datasource,
                    metadata=metadata,
                    search_source=search_source
                )
                results.append(result)
            
            logger.info(f"成功检索查询: '{query}'，返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"检索失败: {str(e)}")
            raise
            
    async def list_datasources(self) -> List[str]:
        """获取所有可用的数据源名称
        
        Returns:
            数据源名称列表
        """
        try:
            hybrid_engine = await self._get_hybrid_engine()
            return await hybrid_engine.list_datasources()
        except Exception as e:
            logger.error(f"获取数据源列表失败: {str(e)}")
            return []

# 创建单例实例
_retrieval_engine = None

async def get_retrieval_engine() -> RetrievalEngine:
    """获取检索引擎单例"""
    global _retrieval_engine
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine()
    return _retrieval_engine 