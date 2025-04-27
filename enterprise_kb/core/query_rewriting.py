"""查询重写模块，用于改进检索质量"""
import logging
from typing import List, Optional, Dict, Any
import asyncio

from llama_index.llms.openai import OpenAI
from llama_index.core import Settings

from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

class QueryRewriter:
    """查询重写器，用于改进检索质量"""
    
    def __init__(self, model_name: str = "gpt-3.5-turbo"):
        """初始化查询重写器
        
        Args:
            model_name: 使用的LLM模型名称
        """
        self.llm = OpenAI(model=model_name, temperature=0.2)
        self.cache = {}  # 简单的内存缓存
    
    async def rewrite_query(
        self, 
        original_query: str, 
        num_variants: int = 3,
        domain: Optional[str] = None,
        language: str = "zh"
    ) -> List[str]:
        """重写查询以提高检索质量
        
        Args:
            original_query: 原始查询
            num_variants: 生成的变体数量
            domain: 查询领域，如"法律"、"医疗"等
            language: 查询语言，默认为中文
            
        Returns:
            重写后的查询列表，包括原始查询
        """
        # 检查缓存
        cache_key = f"{original_query}_{num_variants}_{domain}_{language}"
        if cache_key in self.cache:
            logger.info(f"使用缓存的查询重写结果: {original_query}")
            return self.cache[cache_key]
        
        # 构建提示
        domain_context = f"领域: {domain}\n" if domain else ""
        
        if language == "zh":
            prompt = f"""
            {domain_context}原始查询: {original_query}
            
            请生成{num_variants}个不同的查询变体，以帮助检索相关信息。这些变体应该:
            1. 使用不同的术语或同义词
            2. 重新表述问题
            3. 添加可能的上下文或细节
            
            仅返回查询变体，每行一个，不要添加任何解释或编号。
            """
        else:
            prompt = f"""
            {domain_context}Original query: {original_query}
            
            Please generate {num_variants} different query variants to help retrieve relevant information. These variants should:
            1. Use different terms or synonyms
            2. Rephrase the question
            3. Add possible context or details
            
            Return only the query variants, one per line, without any explanations or numbering.
            """
        
        try:
            # 调用LLM生成变体
            response = await self.llm.acomplete(prompt)
            variants = [q.strip() for q in response.text.split('\n') if q.strip()]
            
            # 确保原始查询也包含在内，并放在第一位
            all_queries = [original_query] + variants
            
            # 去除重复项并限制数量
            unique_queries = []
            for q in all_queries:
                if q not in unique_queries:
                    unique_queries.append(q)
            
            # 限制变体数量
            result = unique_queries[:num_variants + 1]  # +1 是因为包含了原始查询
            
            # 缓存结果
            self.cache[cache_key] = result
            
            logger.info(f"查询重写成功: {original_query} -> {len(result)-1}个变体")
            return result
            
        except Exception as e:
            logger.error(f"查询重写失败: {str(e)}")
            # 如果失败，返回原始查询
            return [original_query]
    
    async def rewrite_batch(
        self, 
        queries: List[str],
        num_variants: int = 2,
        domain: Optional[str] = None,
        language: str = "zh"
    ) -> Dict[str, List[str]]:
        """批量重写多个查询
        
        Args:
            queries: 原始查询列表
            num_variants: 每个查询生成的变体数量
            domain: 查询领域
            language: 查询语言
            
        Returns:
            字典，键为原始查询，值为重写后的查询列表
        """
        results = {}
        tasks = []
        
        # 创建异步任务
        for query in queries:
            task = self.rewrite_query(
                original_query=query,
                num_variants=num_variants,
                domain=domain,
                language=language
            )
            tasks.append((query, task))
        
        # 并行执行所有任务
        for query, task in tasks:
            try:
                variants = await task
                results[query] = variants
            except Exception as e:
                logger.error(f"批量查询重写失败 '{query}': {str(e)}")
                results[query] = [query]  # 失败时使用原始查询
        
        return results


# 单例实例
_query_rewriter = None

def get_query_rewriter() -> QueryRewriter:
    """获取查询重写器单例"""
    global _query_rewriter
    if _query_rewriter is None:
        _query_rewriter = QueryRewriter(
            model_name=settings.QUERY_REWRITE_MODEL or "gpt-3.5-turbo"
        )
    return _query_rewriter
