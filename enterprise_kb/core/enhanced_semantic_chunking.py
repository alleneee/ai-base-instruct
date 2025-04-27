"""增强的语义分块策略模块，提供更智能的文档分块功能"""
import re
import logging
import json
from typing import Dict, List, Optional, Any, Tuple, Union, Callable, Set
import nltk
from nltk.tokenize import sent_tokenize
import numpy as np

from llama_index.core import Document
from llama_index.core.schema import BaseNode, TextNode
from llama_index.core.node_parser import NodeParser, SentenceSplitter

from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

# 确保NLTK资源已下载
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

class SemanticBoundary:
    """语义边界类型"""
    HEADING = "heading"           # 标题
    PARAGRAPH = "paragraph"       # 段落
    LIST_ITEM = "list_item"       # 列表项
    CODE_BLOCK = "code_block"     # 代码块
    TABLE = "table"               # 表格
    QUOTE = "quote"               # 引用
    HORIZONTAL_RULE = "hr"        # 水平线
    SENTENCE = "sentence"         # 句子
    SECTION_BREAK = "section"     # 章节分隔符

class EnhancedSemanticChunker(NodeParser):
    """增强的语义分块器，提供更智能的文档分块功能"""
    
    def __init__(
        self,
        chunk_size: int = 1024,
        chunk_overlap: int = 20,
        context_window: int = 100,  # 上下文窗口大小
        preserve_boundary_content: bool = True,  # 是否保留边界内容
        respect_document_structure: bool = True,  # 是否尊重文档结构
        boundary_importance: Optional[Dict[str, float]] = None,  # 边界重要性权重
        min_chunk_size: int = 100,  # 最小块大小
        max_chunk_size: Optional[int] = None,  # 最大块大小
        include_metadata: bool = True,  # 是否在节点元数据中包含结构信息
        language: str = "chinese"  # 文档语言
    ):
        """初始化增强的语义分块器
        
        Args:
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 块之间的重叠大小
            context_window: 上下文窗口大小，用于保留边界上下文
            preserve_boundary_content: 是否保留边界内容（如标题、列表标记等）
            respect_document_structure: 是否尊重文档结构（如不拆分代码块、表格等）
            boundary_importance: 边界重要性权重，用于决定在哪里分割
            min_chunk_size: 最小块大小，避免生成过小的块
            max_chunk_size: 最大块大小，如果为None则使用chunk_size的2倍
            include_metadata: 是否在节点元数据中包含结构信息
            language: 文档语言，用于句子分割
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.context_window = context_window
        self.preserve_boundary_content = preserve_boundary_content
        self.respect_document_structure = respect_document_structure
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size or (chunk_size * 2)
        self.include_metadata = include_metadata
        self.language = language
        
        # 设置边界重要性权重
        self.boundary_importance = boundary_importance or {
            SemanticBoundary.HEADING: 1.0,
            SemanticBoundary.PARAGRAPH: 0.8,
            SemanticBoundary.LIST_ITEM: 0.6,
            SemanticBoundary.CODE_BLOCK: 0.9,
            SemanticBoundary.TABLE: 0.9,
            SemanticBoundary.QUOTE: 0.7,
            SemanticBoundary.HORIZONTAL_RULE: 0.8,
            SemanticBoundary.SENTENCE: 0.5,
            SemanticBoundary.SECTION_BREAK: 0.9
        }
        
        # 编译正则表达式
        self.patterns = {
            # Markdown标题
            "md_heading": re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE),
            # HTML标题
            "html_heading": re.compile(r'<h([1-6])>(.*?)</h\1>', re.DOTALL),
            # Markdown列表项
            "md_list_item": re.compile(r'^(\s*[-*+]|\s*\d+\.)\s+(.+)$', re.MULTILINE),
            # Markdown代码块
            "md_code_block": re.compile(r'```[\s\S]*?```', re.DOTALL),
            # Markdown表格
            "md_table": re.compile(r'(\|[^\n]+\|\n)((?:\|[-:]+)+\|)(\n(?:\|[^\n]+\|\n?)+)', re.DOTALL),
            # Markdown引用
            "md_quote": re.compile(r'^>\s+(.+)$', re.MULTILINE),
            # Markdown水平线
            "md_hr": re.compile(r'^(---|\*\*\*|___)\s*$', re.MULTILINE),
            # HTML段落
            "html_paragraph": re.compile(r'<p>(.*?)</p>', re.DOTALL),
            # 章节分隔符（连续多个换行）
            "section_break": re.compile(r'\n{3,}'),
            # 句子结束符
            "sentence_end": re.compile(r'[.!?。！？]\s+')
        }
        
        # 用于回退的句子分割器
        self.sentence_splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    def get_nodes_from_documents(self, documents: List[Document]) -> List[BaseNode]:
        """从文档列表中获取节点
        
        Args:
            documents: 文档列表
            
        Returns:
            节点列表
        """
        all_nodes = []
        
        for doc in documents:
            try:
                nodes = self._get_nodes_from_document(doc)
                all_nodes.extend(nodes)
            except Exception as e:
                logger.error(f"增强语义分块失败: {str(e)}，回退到句子分割")
                # 回退到句子分割
                nodes = self.sentence_splitter.get_nodes_from_documents([doc])
                all_nodes.extend(nodes)
        
        return all_nodes
    
    def _get_nodes_from_document(self, document: Document) -> List[BaseNode]:
        """从单个文档中获取节点
        
        Args:
            document: 文档
            
        Returns:
            节点列表
        """
        text = document.text
        metadata = document.metadata or {}
        
        # 检查文档类型
        file_type = metadata.get("file_type", "").lower()
        
        # 识别文档结构和语义边界
        boundaries = self._identify_semantic_boundaries(text, file_type)
        
        # 根据语义边界分块
        chunks = self._chunk_by_semantic_boundaries(text, boundaries)
        
        # 创建节点
        nodes = []
        for i, chunk_info in enumerate(chunks):
            chunk_text = chunk_info["text"]
            
            # 创建节点元数据
            node_metadata = metadata.copy()
            node_metadata["chunk_index"] = i
            
            # 添加结构信息到元数据
            if self.include_metadata:
                if "heading" in chunk_info:
                    node_metadata["heading"] = chunk_info["heading"]
                if "level" in chunk_info:
                    node_metadata["heading_level"] = chunk_info["level"]
                if "boundaries" in chunk_info:
                    node_metadata["boundary_types"] = [b["type"] for b in chunk_info["boundaries"]]
                if "context" in chunk_info:
                    node_metadata["context"] = chunk_info["context"]
            
            # 创建节点
            node = TextNode(
                text=chunk_text,
                metadata=node_metadata,
                id_=f"{metadata.get('doc_id', '')}_chunk_{i}" if "doc_id" in metadata else None
            )
            nodes.append(node)
        
        return nodes
    
    def _identify_semantic_boundaries(self, text: str, file_type: str) -> List[Dict[str, Any]]:
        """识别文本中的语义边界
        
        Args:
            text: 文本内容
            file_type: 文件类型
            
        Returns:
            边界列表，每个边界包含类型、位置和重要性
        """
        boundaries = []
        
        # 检查是否是Markdown或HTML文件
        is_markdown = file_type in [".md", ".markdown"]
        is_html = file_type in [".html", ".htm"]
        
        # 识别Markdown标题
        if is_markdown or self.respect_document_structure:
            for match in self.patterns["md_heading"].finditer(text):
                level = len(match.group(1))  # '#' 的数量
                heading_text = match.group(2).strip()
                importance = self.boundary_importance[SemanticBoundary.HEADING] * (1.0 - (level - 1) * 0.1)
                boundaries.append({
                    "type": SemanticBoundary.HEADING,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "content": heading_text,
                    "level": level,
                    "importance": importance
                })
        
        # 识别HTML标题
        if is_html or self.respect_document_structure:
            for match in self.patterns["html_heading"].finditer(text):
                level = int(match.group(1))
                heading_text = match.group(2).strip()
                importance = self.boundary_importance[SemanticBoundary.HEADING] * (1.0 - (level - 1) * 0.1)
                boundaries.append({
                    "type": SemanticBoundary.HEADING,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "content": heading_text,
                    "level": level,
                    "importance": importance
                })
        
        # 识别Markdown列表项
        if is_markdown or self.respect_document_structure:
            for match in self.patterns["md_list_item"].finditer(text):
                boundaries.append({
                    "type": SemanticBoundary.LIST_ITEM,
                    "start": match.start(),
                    "end": match.start() + len(match.group(1)),  # 只将列表标记作为边界
                    "text": match.group(1),
                    "content": match.group(2),
                    "importance": self.boundary_importance[SemanticBoundary.LIST_ITEM]
                })
        
        # 识别Markdown代码块
        if is_markdown or self.respect_document_structure:
            for match in self.patterns["md_code_block"].finditer(text):
                # 代码块的开始和结束都是边界
                code_text = match.group(0)
                code_lines = code_text.split('\n')
                
                # 代码块开始
                boundaries.append({
                    "type": SemanticBoundary.CODE_BLOCK,
                    "start": match.start(),
                    "end": match.start() + len(code_lines[0]) + 1,  # 包括换行符
                    "text": code_lines[0],
                    "content": "代码块开始",
                    "importance": self.boundary_importance[SemanticBoundary.CODE_BLOCK]
                })
                
                # 代码块结束
                if len(code_lines) > 1:
                    end_start = match.end() - len(code_lines[-1])
                    boundaries.append({
                        "type": SemanticBoundary.CODE_BLOCK,
                        "start": end_start,
                        "end": match.end(),
                        "text": code_lines[-1],
                        "content": "代码块结束",
                        "importance": self.boundary_importance[SemanticBoundary.CODE_BLOCK]
                    })
        
        # 识别Markdown表格
        if is_markdown or self.respect_document_structure:
            for match in self.patterns["md_table"].finditer(text):
                # 表格的开始和结束都是边界
                table_text = match.group(0)
                table_lines = table_text.split('\n')
                
                # 表格开始（表头）
                header_end = match.start() + len(table_lines[0]) + len(table_lines[1]) + 2  # 包括两个换行符
                boundaries.append({
                    "type": SemanticBoundary.TABLE,
                    "start": match.start(),
                    "end": header_end,
                    "text": table_lines[0] + '\n' + table_lines[1],
                    "content": "表格头",
                    "importance": self.boundary_importance[SemanticBoundary.TABLE]
                })
                
                # 表格结束
                if len(table_lines) > 2:
                    boundaries.append({
                        "type": SemanticBoundary.TABLE,
                        "start": match.end() - len(table_lines[-1]),
                        "end": match.end(),
                        "text": table_lines[-1],
                        "content": "表格尾",
                        "importance": self.boundary_importance[SemanticBoundary.TABLE]
                    })
        
        # 识别Markdown引用
        if is_markdown or self.respect_document_structure:
            for match in self.patterns["md_quote"].finditer(text):
                boundaries.append({
                    "type": SemanticBoundary.QUOTE,
                    "start": match.start(),
                    "end": match.start() + 2,  # 只将引用标记作为边界
                    "text": "> ",
                    "content": match.group(1),
                    "importance": self.boundary_importance[SemanticBoundary.QUOTE]
                })
        
        # 识别Markdown水平线
        if is_markdown or self.respect_document_structure:
            for match in self.patterns["md_hr"].finditer(text):
                boundaries.append({
                    "type": SemanticBoundary.HORIZONTAL_RULE,
                    "start": match.start(),
                    "end": match.end(),
                    "text": match.group(0),
                    "content": "水平线",
                    "importance": self.boundary_importance[SemanticBoundary.HORIZONTAL_RULE]
                })
        
        # 识别HTML段落
        if is_html:
            for match in self.patterns["html_paragraph"].finditer(text):
                boundaries.append({
                    "type": SemanticBoundary.PARAGRAPH,
                    "start": match.start(),
                    "end": match.start() + 3,  # <p>
                    "text": "<p>",
                    "content": match.group(1),
                    "importance": self.boundary_importance[SemanticBoundary.PARAGRAPH]
                })
                boundaries.append({
                    "type": SemanticBoundary.PARAGRAPH,
                    "start": match.end() - 4,  # </p>
                    "end": match.end(),
                    "text": "</p>",
                    "content": "段落结束",
                    "importance": self.boundary_importance[SemanticBoundary.PARAGRAPH]
                })
        
        # 识别章节分隔符
        for match in self.patterns["section_break"].finditer(text):
            boundaries.append({
                "type": SemanticBoundary.SECTION_BREAK,
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
                "content": "章节分隔",
                "importance": self.boundary_importance[SemanticBoundary.SECTION_BREAK]
            })
        
        # 识别段落边界（双换行）
        paragraph_pattern = re.compile(r'\n\n+')
        for match in paragraph_pattern.finditer(text):
            boundaries.append({
                "type": SemanticBoundary.PARAGRAPH,
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
                "content": "段落分隔",
                "importance": self.boundary_importance[SemanticBoundary.PARAGRAPH]
            })
        
        # 识别句子边界
        if self.language == "chinese":
            # 中文句子边界
            sentence_pattern = re.compile(r'[。！？；.!?;]\s*')
        else:
            # 英文句子边界
            sentence_pattern = re.compile(r'[.!?]\s+')
            
        for match in sentence_pattern.finditer(text):
            boundaries.append({
                "type": SemanticBoundary.SENTENCE,
                "start": match.start(),
                "end": match.end(),
                "text": match.group(0),
                "content": "句子结束",
                "importance": self.boundary_importance[SemanticBoundary.SENTENCE]
            })
        
        # 按位置排序
        boundaries.sort(key=lambda x: x["start"])
        
        return boundaries
    
    def _chunk_by_semantic_boundaries(self, text: str, boundaries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """根据语义边界分块
        
        Args:
            text: 文本内容
            boundaries: 边界列表
            
        Returns:
            块列表，每个块包含文本和元数据
        """
        if not boundaries:
            # 如果没有识别到边界，使用句子分割器
            return [{"text": text}]
        
        # 初始化块列表
        chunks = []
        
        # 当前块的开始位置
        current_start = 0
        
        # 当前块的长度
        current_length = 0
        
        # 当前块的边界
        current_boundaries = []
        
        # 当前块的上下文
        current_context = {}
        
        # 当前标题
        current_heading = None
        current_heading_level = None
        
        # 处理每个边界
        for i, boundary in enumerate(boundaries):
            # 计算从当前位置到边界开始的文本长度
            text_before_boundary = text[current_start:boundary["start"]]
            text_before_length = len(text_before_boundary)
            
            # 如果添加此文本会超过最大块大小，则结束当前块
            if current_length + text_before_length > self.max_chunk_size and current_length > self.min_chunk_size:
                # 创建当前块
                chunk_text = text[current_start:boundary["start"]]
                chunk = {
                    "text": chunk_text,
                    "boundaries": current_boundaries
                }
                
                # 添加上下文信息
                if current_context:
                    chunk["context"] = current_context
                
                # 添加标题信息
                if current_heading:
                    chunk["heading"] = current_heading
                    chunk["level"] = current_heading_level
                
                chunks.append(chunk)
                
                # 重置当前块
                current_start = boundary["start"]
                current_length = 0
                current_boundaries = []
                # 保留上下文和标题信息
            
            # 更新当前块的长度
            current_length += text_before_length
            
            # 如果是标题，更新当前标题
            if boundary["type"] == SemanticBoundary.HEADING:
                current_heading = boundary["content"]
                current_heading_level = boundary.get("level", 1)
                
                # 添加到上下文
                current_context["heading"] = current_heading
                current_context["heading_level"] = current_heading_level
            
            # 添加边界到当前块
            current_boundaries.append(boundary)
            
            # 如果边界重要性高，考虑在此处分块
            if boundary["importance"] >= 0.8 and current_length >= self.min_chunk_size:
                # 创建当前块
                chunk_text = text[current_start:boundary["end"]]
                chunk = {
                    "text": chunk_text,
                    "boundaries": current_boundaries
                }
                
                # 添加上下文信息
                if current_context:
                    chunk["context"] = current_context
                
                # 添加标题信息
                if current_heading:
                    chunk["heading"] = current_heading
                    chunk["level"] = current_heading_level
                
                chunks.append(chunk)
                
                # 重置当前块
                current_start = boundary["end"]
                current_length = 0
                current_boundaries = []
                # 保留上下文和标题信息
            
            # 如果当前块长度达到目标大小，寻找下一个合适的分割点
            elif current_length >= self.chunk_size:
                # 查找后续的高重要性边界
                next_important_boundary = None
                for j in range(i + 1, min(i + 10, len(boundaries))):
                    if boundaries[j]["importance"] >= 0.7:
                        next_important_boundary = boundaries[j]
                        break
                
                # 如果找到高重要性边界且不会使块过大，则等待该边界
                if next_important_boundary and (next_important_boundary["start"] - current_start) <= self.max_chunk_size:
                    continue
                
                # 否则在当前边界分块
                chunk_text = text[current_start:boundary["end"]]
                chunk = {
                    "text": chunk_text,
                    "boundaries": current_boundaries
                }
                
                # 添加上下文信息
                if current_context:
                    chunk["context"] = current_context
                
                # 添加标题信息
                if current_heading:
                    chunk["heading"] = current_heading
                    chunk["level"] = current_heading_level
                
                chunks.append(chunk)
                
                # 重置当前块
                current_start = boundary["end"]
                current_length = 0
                current_boundaries = []
                # 保留上下文和标题信息
        
        # 添加最后一个块
        if current_start < len(text):
            chunk_text = text[current_start:]
            chunk = {
                "text": chunk_text,
                "boundaries": current_boundaries
            }
            
            # 添加上下文信息
            if current_context:
                chunk["context"] = current_context
            
            # 添加标题信息
            if current_heading:
                chunk["heading"] = current_heading
                chunk["level"] = current_heading_level
            
            chunks.append(chunk)
        
        # 处理块重叠
        if self.chunk_overlap > 0:
            overlapped_chunks = []
            
            for i in range(len(chunks)):
                chunk = chunks[i].copy()
                
                # 添加与下一个块的重叠
                if i < len(chunks) - 1:
                    next_chunk_text = chunks[i + 1]["text"]
                    overlap_size = min(self.chunk_overlap, len(next_chunk_text))
                    chunk["text"] = chunk["text"] + next_chunk_text[:overlap_size]
                
                overlapped_chunks.append(chunk)
            
            chunks = overlapped_chunks
        
        return chunks

def create_enhanced_chunker(
    chunk_size: int = None,
    chunk_overlap: int = None,
    chunking_type: str = "semantic",
    language: str = "chinese"
) -> NodeParser:
    """创建增强的分块器
    
    Args:
        chunk_size: 块大小，如果为None则使用配置中的默认值
        chunk_overlap: 块重叠大小，如果为None则使用配置中的默认值
        chunking_type: 分块类型，可以是"semantic"或"hierarchical"
        language: 文档语言，用于句子分割
        
    Returns:
        分块器实例
    """
    # 从配置中获取默认值
    default_chunk_size = settings.DOCUMENT_CHUNK_SIZE
    default_chunk_overlap = settings.DOCUMENT_CHUNK_OVERLAP
    
    # 使用提供的值或默认值
    chunk_size = chunk_size or default_chunk_size
    chunk_overlap = chunk_overlap or default_chunk_overlap
    
    # 根据分块类型创建分块器
    if chunking_type == "hierarchical":
        from enterprise_kb.core.semantic_chunking import HierarchicalChunker
        return HierarchicalChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    else:  # semantic
        return EnhancedSemanticChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            language=language
        )
