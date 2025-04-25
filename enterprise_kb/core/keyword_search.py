"""关键词搜索引擎模块，提供基于BM25的关键词检索功能"""
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
import re
import jieba
import jieba.analyse
from rank_bm25 import BM25Okapi
import numpy as np

from llama_index.core.schema import TextNode, NodeWithScore

logger = logging.getLogger(__name__)

# 停用词集合
STOPWORDS = set(['的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好', '自己', '这'])

class KeywordSearchEngine:
    """关键词搜索引擎，基于BM25算法"""
    
    def __init__(self):
        """初始化关键词搜索引擎"""
        self.documents = []  # 文档内容列表
        self.doc_ids = []    # 文档ID列表
        self.metadata = []   # 文档元数据列表
        self.corpus = []     # 分词后的语料库
        self.bm25 = None     # BM25模型
        self.initialized = False
        
        # 确保加载jieba词典
        jieba.initialize()
        
    def _preprocess_text(self, text: str) -> str:
        """文本预处理，去除特殊字符和多余空格"""
        # 去除特殊字符
        text = re.sub(r'[^\w\s\u4e00-\u9fff]', ' ', text)
        # 去除多余空格
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def _tokenize(self, text: str) -> List[str]:
        """文本分词"""
        # 预处理文本
        text = self._preprocess_text(text)
        # 使用jieba进行分词
        tokens = jieba.lcut(text)
        # 去除停用词
        tokens = [token for token in tokens if token not in STOPWORDS and len(token.strip()) > 0]
        return tokens
    
    def add_documents(self, nodes: List[TextNode]) -> None:
        """添加文档到搜索引擎
        
        Args:
            nodes: 文档节点列表
        """
        # 清除现有数据
        self.documents = []
        self.doc_ids = []
        self.metadata = []
        self.corpus = []
        
        # 添加新文档
        for node in nodes:
            # 获取文本内容
            text = node.text
            self.documents.append(text)
            
            # 获取文档ID
            doc_id = node.node_id
            self.doc_ids.append(doc_id)
            
            # 获取元数据
            metadata = node.metadata or {}
            self.metadata.append(metadata)
            
            # 分词
            tokens = self._tokenize(text)
            self.corpus.append(tokens)
        
        # 初始化BM25模型
        if len(self.corpus) > 0:
            self.bm25 = BM25Okapi(self.corpus)
            self.initialized = True
            logger.info(f"关键词索引已创建，包含 {len(self.documents)} 个文档")
    
    def extract_keywords(self, query: str, top_k: int = 5) -> List[str]:
        """从查询中提取关键词
        
        Args:
            query: 查询文本
            top_k: 返回的关键词数量
            
        Returns:
            关键词列表
        """
        # 使用jieba提取关键词
        keywords = jieba.analyse.extract_tags(query, topK=top_k)
        return keywords
    
    def search(
        self, 
        query: str, 
        top_k: int = 5, 
        use_keywords: bool = True
    ) -> List[NodeWithScore]:
        """基于关键词搜索文档
        
        Args:
            query: 查询文本
            top_k: 返回的最大结果数
            use_keywords: 是否使用关键词提取，如果为False则直接分词
            
        Returns:
            匹配文档列表
        """
        if not self.initialized or len(self.documents) == 0:
            logger.warning("关键词搜索引擎未初始化或没有文档")
            return []
        
        try:
            # 准备查询关键词
            if use_keywords:
                # 提取关键词
                query_tokens = self.extract_keywords(query)
                if not query_tokens:
                    # 如果没有提取到关键词，使用分词结果
                    query_tokens = self._tokenize(query)
            else:
                # 直接分词
                query_tokens = self._tokenize(query)
            
            # 如果没有有效的查询词，返回空结果
            if not query_tokens:
                logger.warning(f"查询文本 '{query}' 没有有效的关键词")
                return []
            
            # 使用BM25检索文档
            scores = self.bm25.get_scores(query_tokens)
            
            # 获取排序后的索引
            ranked_indices = np.argsort(scores)[::-1][:top_k]
            
            # 构建结果
            results = []
            for idx in ranked_indices:
                # 只返回有评分的结果
                if scores[idx] > 0:
                    # 构建节点
                    node = TextNode(
                        text=self.documents[idx],
                        node_id=self.doc_ids[idx],
                        metadata=self.metadata[idx]
                    )
                    
                    # 构建带分数的节点
                    result = NodeWithScore(
                        node=node,
                        score=float(scores[idx])
                    )
                    
                    results.append(result)
            
            logger.info(f"关键词检索 '{query}' 找到 {len(results)} 个结果")
            return results
        
        except Exception as e:
            logger.error(f"关键词搜索失败: {str(e)}")
            return [] 