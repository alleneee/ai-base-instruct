"""检索引擎模块"""
from typing import Dict, List, Optional, Any, Union
import logging
from pydantic import BaseModel

from llama_index.core import VectorStoreIndex, Settings
from llama_index.core.schema import NodeWithScore
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.core.postprocessor import SimilarityPostprocessor
from llama_index.embeddings.openai import OpenAIEmbedding

from enterprise_kb.core.config.settings import settings
from enterprise_kb.storage.vector_store import get_storage_context, MilvusVectorStore

logger = logging.getLogger(__name__)

class RetrievalResult(BaseModel):
    """检索结果模型"""
    text: str
    score: float
    doc_id: str
    file_name: Optional[str] = None
    metadata: Dict[str, Any] = {}
    
class RetrievalEngine:
    """知识检索引擎"""
    
    def __init__(self):
        """初始化检索引擎"""
        # 设置LlamaIndex全局配置
        Settings.embed_model = OpenAIEmbedding()
        
        # 获取存储上下文
        self.storage_context = get_storage_context()
        
        # 创建向量索引
        self.index = VectorStoreIndex.from_vector_store(
            vector_store=self.storage_context.vector_store
        )
        
    def retrieve(
        self, 
        query: str, 
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
        min_score: float = 0.7
    ) -> List[RetrievalResult]:
        """
        根据查询文本检索相关文档
        
        Args:
            query: 查询文本
            top_k: 返回的最大文档数
            filters: 过滤条件，例如 {"file_type": ".pdf"}
            min_score: 最小相似度分数
            
        Returns:
            匹配文档列表
        """
        try:
            # 创建检索器
            retriever = VectorIndexRetriever(
                index=self.index,
                similarity_top_k=top_k,
                filters=filters
            )
            
            # 相似度后处理器
            similarity_postprocessor = SimilarityPostprocessor(similarity_cutoff=min_score)
            
            # 执行检索
            nodes = retriever.retrieve(query)
            
            # 应用相似度过滤
            filtered_nodes = similarity_postprocessor.postprocess_nodes(nodes)
            
            # 转换为检索结果
            results = []
            for node in filtered_nodes:
                node_obj = node if isinstance(node, NodeWithScore) else node
                
                # 提取元数据
                metadata = node_obj.metadata or {}
                doc_id = metadata.get("doc_id", "unknown")
                file_name = metadata.get("file_name", None)
                
                # 计算分数
                score = node.score if isinstance(node, NodeWithScore) else 1.0
                
                # 构建结果
                result = RetrievalResult(
                    text=node_obj.get_content(),
                    score=score,
                    doc_id=doc_id,
                    file_name=file_name,
                    metadata=metadata
                )
                results.append(result)
                
            logger.info(f"成功检索查询: '{query}'，返回 {len(results)} 个结果")
            return results
            
        except Exception as e:
            logger.error(f"检索失败: {str(e)}")
            raise

# 创建单例实例
_retrieval_engine = None

def get_retrieval_engine() -> RetrievalEngine:
    """获取检索引擎单例"""
    global _retrieval_engine
    if _retrieval_engine is None:
        _retrieval_engine = RetrievalEngine()
    return _retrieval_engine 