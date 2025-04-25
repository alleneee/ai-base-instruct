import logging
from typing import Dict, List, Optional, Any

from enterprise_kb.core.retrieval_engine import get_retrieval_engine, RetrievalResult, SearchMode as EngineSearchMode
from enterprise_kb.schemas.search import SearchRequest, SearchResponse, SearchResult, SearchMode

logger = logging.getLogger(__name__)

class SearchService:
    """搜索服务，封装检索引擎功能"""
    
    def __init__(self):
        """初始化搜索服务"""
        self.retrieval_engine = None
    
    async def _get_retrieval_engine(self):
        """获取检索引擎实例"""
        if self.retrieval_engine is None:
            self.retrieval_engine = await get_retrieval_engine()
        return self.retrieval_engine
    
    async def search(self, search_request: SearchRequest) -> SearchResponse:
        """
        执行搜索
        
        Args:
            search_request: 搜索请求
            
        Returns:
            搜索响应
        """
        try:
            # 获取检索引擎
            retrieval_engine = await self._get_retrieval_engine()
            
            # 将搜索模式转换为检索引擎支持的模式
            engine_search_mode = EngineSearchMode.HYBRID
            if search_request.search_mode == SearchMode.VECTOR:
                engine_search_mode = EngineSearchMode.VECTOR
            elif search_request.search_mode == SearchMode.KEYWORD:
                engine_search_mode = EngineSearchMode.KEYWORD
            
            # 调用检索引擎
            retrieval_results = await retrieval_engine.retrieve(
                query=search_request.query,
                top_k=search_request.top_k or 5,
                filters=search_request.filters,
                min_score=search_request.min_score or 0.7,
                datasource_names=search_request.datasources,
                search_mode=engine_search_mode
            )
            
            # 转换为搜索结果
            results = []
            for result in retrieval_results:
                search_result = SearchResult(
                    text=result.text,
                    score=result.score,
                    doc_id=result.doc_id,
                    file_name=result.file_name,
                    datasource=result.datasource,
                    metadata=result.metadata,
                    search_source=result.search_source
                )
                results.append(search_result)
                
            return SearchResponse(
                query=search_request.query,
                results=results,
                total=len(results),
                search_mode=search_request.search_mode or SearchMode.HYBRID
            )
            
        except Exception as e:
            logger.error(f"搜索失败: {str(e)}")
            raise
    
    async def list_datasources(self) -> List[str]:
        """
        获取所有可用的数据源
        
        Returns:
            数据源名称列表
        """
        try:
            retrieval_engine = await self._get_retrieval_engine()
            return await retrieval_engine.list_datasources()
        except Exception as e:
            logger.error(f"获取数据源列表失败: {str(e)}")
            return [] 