"""基于语义边界的分块策略模块"""
import re
import logging
from typing import Dict, List, Optional, Any, Tuple, Union, Callable
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

class SemanticChunker(NodeParser):
    """基于语义边界的分块器"""
    
    def __init__(
        self,
        chunk_size: int = 1024,
        chunk_overlap: int = 20,
        paragraph_separator: str = "\n\n",
        sentence_separator: str = ". ",
        heading_pattern: str = r"^(#{1,6}|\*\*|__|\d+\.)\s+.+$",
        list_pattern: str = r"^(\s*[-*+]\s+|\s*\d+\.\s+)",
        code_block_pattern: str = r"```[\s\S]*?```",
        table_pattern: str = r"\|.+\|.+\|",
        respect_markdown: bool = True
    ):
        """初始化语义分块器
        
        Args:
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 块之间的重叠大小
            paragraph_separator: 段落分隔符
            sentence_separator: 句子分隔符
            heading_pattern: 标题匹配模式
            list_pattern: 列表项匹配模式
            code_block_pattern: 代码块匹配模式
            table_pattern: 表格匹配模式
            respect_markdown: 是否尊重Markdown格式
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.paragraph_separator = paragraph_separator
        self.sentence_separator = sentence_separator
        self.heading_pattern = re.compile(heading_pattern, re.MULTILINE)
        self.list_pattern = re.compile(list_pattern, re.MULTILINE)
        self.code_block_pattern = re.compile(code_block_pattern, re.DOTALL)
        self.table_pattern = re.compile(table_pattern)
        self.respect_markdown = respect_markdown
        
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
                logger.error(f"语义分块失败: {str(e)}，回退到句子分割")
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
        is_markdown = file_type in [".md", ".markdown"] or self.respect_markdown
        
        # 根据文档类型选择分块策略
        if is_markdown:
            chunks = self._chunk_markdown(text)
        else:
            chunks = self._chunk_text(text)
        
        # 创建节点
        nodes = []
        for i, chunk in enumerate(chunks):
            # 创建节点元数据
            node_metadata = metadata.copy()
            node_metadata["chunk_index"] = i
            
            # 创建节点
            node = TextNode(
                text=chunk,
                metadata=node_metadata,
                id_=f"{metadata.get('doc_id', '')}_chunk_{i}" if "doc_id" in metadata else None
            )
            nodes.append(node)
        
        return nodes
    
    def _chunk_markdown(self, text: str) -> List[str]:
        """基于Markdown结构分块
        
        Args:
            text: Markdown文本
            
        Returns:
            文本块列表
        """
        # 保存特殊块（代码块、表格等）
        special_blocks = {}
        block_id = 0
        
        # 替换代码块
        def replace_code_block(match):
            nonlocal block_id
            placeholder = f"__CODE_BLOCK_{block_id}__"
            special_blocks[placeholder] = match.group(0)
            block_id += 1
            return placeholder
        
        text = self.code_block_pattern.sub(replace_code_block, text)
        
        # 分割文本
        sections = []
        current_section = []
        current_length = 0
        
        # 按行处理
        lines = text.split("\n")
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # 检查是否是标题
            is_heading = bool(self.heading_pattern.match(line))
            
            # 如果是标题且当前段落不为空，则结束当前段落
            if is_heading and current_section and current_length > 0:
                sections.append("\n".join(current_section))
                current_section = []
                current_length = 0
            
            # 添加当前行
            current_section.append(line)
            current_length += len(line) + 1  # +1 for newline
            
            # 如果当前段落达到目标大小，则结束当前段落
            if current_length >= self.chunk_size and not is_heading:
                sections.append("\n".join(current_section))
                current_section = []
                current_length = 0
            
            i += 1
        
        # 添加最后一个段落
        if current_section:
            sections.append("\n".join(current_section))
        
        # 合并小段落
        merged_sections = []
        current_merged = []
        current_length = 0
        
        for section in sections:
            section_length = len(section)
            
            # 如果添加此段落会超过目标大小，则结束当前合并段落
            if current_length + section_length > self.chunk_size and current_merged:
                merged_sections.append("\n\n".join(current_merged))
                current_merged = []
                current_length = 0
            
            # 添加当前段落
            current_merged.append(section)
            current_length += section_length + 2  # +2 for paragraph separator
        
        # 添加最后一个合并段落
        if current_merged:
            merged_sections.append("\n\n".join(current_merged))
        
        # 恢复特殊块
        chunks = []
        for section in merged_sections:
            for placeholder, original in special_blocks.items():
                section = section.replace(placeholder, original)
            chunks.append(section)
        
        return chunks
    
    def _chunk_text(self, text: str) -> List[str]:
        """基于段落和句子边界分块
        
        Args:
            text: 文本
            
        Returns:
            文本块列表
        """
        # 分割为段落
        paragraphs = re.split(self.paragraph_separator, text)
        
        # 合并段落成块
        chunks = []
        current_chunk = []
        current_length = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
                
            paragraph_length = len(paragraph)
            
            # 如果段落本身超过块大小，则进一步分割
            if paragraph_length > self.chunk_size:
                # 如果当前块不为空，先添加它
                if current_chunk:
                    chunks.append(self.paragraph_separator.join(current_chunk))
                    current_chunk = []
                    current_length = 0
                
                # 分割大段落为句子
                try:
                    sentences = sent_tokenize(paragraph)
                    
                    # 合并句子成块
                    sentence_chunk = []
                    sentence_length = 0
                    
                    for sentence in sentences:
                        sentence = sentence.strip()
                        if not sentence:
                            continue
                            
                        sentence_length_with_sep = len(sentence) + len(self.sentence_separator)
                        
                        # 如果添加此句子会超过目标大小，则结束当前块
                        if sentence_length + sentence_length_with_sep > self.chunk_size and sentence_chunk:
                            chunks.append(self.sentence_separator.join(sentence_chunk))
                            sentence_chunk = []
                            sentence_length = 0
                        
                        # 添加当前句子
                        sentence_chunk.append(sentence)
                        sentence_length += sentence_length_with_sep
                    
                    # 添加最后一个句子块
                    if sentence_chunk:
                        chunks.append(self.sentence_separator.join(sentence_chunk))
                
                except Exception as e:
                    logger.error(f"句子分割失败: {str(e)}")
                    # 回退到简单分割
                    for i in range(0, paragraph_length, self.chunk_size - self.chunk_overlap):
                        end = min(i + self.chunk_size, paragraph_length)
                        chunks.append(paragraph[i:end])
            
            # 如果添加此段落会超过目标大小，则结束当前块
            elif current_length + paragraph_length > self.chunk_size and current_chunk:
                chunks.append(self.paragraph_separator.join(current_chunk))
                current_chunk = [paragraph]
                current_length = paragraph_length
            
            # 添加当前段落
            else:
                current_chunk.append(paragraph)
                current_length += paragraph_length + len(self.paragraph_separator)
        
        # 添加最后一个块
        if current_chunk:
            chunks.append(self.paragraph_separator.join(current_chunk))
        
        return chunks

class HierarchicalChunker(NodeParser):
    """层次化分块器，保留文档结构"""
    
    def __init__(
        self,
        chunk_size: int = 1024,
        chunk_overlap: int = 20,
        heading_level_weight: Dict[int, float] = None,
        include_heading_in_chunk: bool = True,
        include_metadata: bool = True
    ):
        """初始化层次化分块器
        
        Args:
            chunk_size: 目标块大小（字符数）
            chunk_overlap: 块之间的重叠大小
            heading_level_weight: 标题级别权重，用于计算语义边界强度
            include_heading_in_chunk: 是否在块中包含标题
            include_metadata: 是否在节点元数据中包含层次信息
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.include_heading_in_chunk = include_heading_in_chunk
        self.include_metadata = include_metadata
        
        # 默认标题级别权重
        self.heading_level_weight = heading_level_weight or {
            1: 1.0,  # h1
            2: 0.9,  # h2
            3: 0.8,  # h3
            4: 0.7,  # h4
            5: 0.6,  # h5
            6: 0.5   # h6
        }
        
        # 用于回退的句子分割器
        self.sentence_splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
        
        # 编译正则表达式
        self.heading_pattern = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)
        self.html_heading_pattern = re.compile(r'<h([1-6])>(.*?)</h\1>', re.DOTALL)
    
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
                logger.error(f"层次化分块失败: {str(e)}，回退到句子分割")
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
        
        # 解析文档结构
        if file_type in [".md", ".markdown"]:
            sections = self._parse_markdown_structure(text)
        elif file_type in [".html", ".htm"]:
            sections = self._parse_html_structure(text)
        else:
            # 对于其他文档类型，尝试检测标题模式
            sections = self._parse_generic_structure(text)
        
        # 创建节点
        nodes = []
        for i, section in enumerate(sections):
            # 提取节点内容和元数据
            section_text = section["text"]
            section_metadata = metadata.copy()
            
            # 添加层次信息到元数据
            if self.include_metadata:
                section_metadata["heading"] = section.get("heading")
                section_metadata["heading_level"] = section.get("level")
                section_metadata["section_index"] = i
                
                # 构建面包屑路径
                if "heading" in section and "level" in section:
                    breadcrumbs = []
                    current_level = section["level"]
                    for j in range(i, -1, -1):
                        prev_section = sections[j]
                        if "level" in prev_section and prev_section["level"] < current_level:
                            breadcrumbs.insert(0, prev_section.get("heading", ""))
                            current_level = prev_section["level"]
                    
                    if breadcrumbs:
                        section_metadata["breadcrumbs"] = " > ".join(breadcrumbs)
            
            # 创建节点
            node = TextNode(
                text=section_text,
                metadata=section_metadata,
                id_=f"{metadata.get('doc_id', '')}_section_{i}" if "doc_id" in metadata else None
            )
            nodes.append(node)
        
        return nodes
    
    def _parse_markdown_structure(self, text: str) -> List[Dict[str, Any]]:
        """解析Markdown文档结构
        
        Args:
            text: Markdown文本
            
        Returns:
            段落列表，每个段落包含文本和元数据
        """
        # 查找所有标题
        headings = []
        for match in self.heading_pattern.finditer(text):
            level = len(match.group(1))  # '#' 的数量
            heading_text = match.group(2).strip()
            headings.append({
                "level": level,
                "text": heading_text,
                "start": match.start(),
                "end": match.end()
            })
        
        # 如果没有标题，将整个文档作为一个段落
        if not headings:
            return [{"text": text}]
        
        # 构建段落
        sections = []
        for i, heading in enumerate(headings):
            # 确定段落结束位置
            if i < len(headings) - 1:
                section_end = headings[i + 1]["start"]
            else:
                section_end = len(text)
            
            # 提取段落文本
            if self.include_heading_in_chunk:
                section_text = text[heading["start"]:section_end].strip()
            else:
                section_text = text[heading["end"]:section_end].strip()
            
            # 创建段落
            section = {
                "level": heading["level"],
                "heading": heading["text"],
                "text": section_text
            }
            
            # 如果段落太长，进一步分割
            if len(section_text) > self.chunk_size:
                subsections = self._split_long_section(section_text, heading["text"], heading["level"])
                sections.extend(subsections)
            else:
                sections.append(section)
        
        return sections
    
    def _parse_html_structure(self, text: str) -> List[Dict[str, Any]]:
        """解析HTML文档结构
        
        Args:
            text: HTML文本
            
        Returns:
            段落列表，每个段落包含文本和元数据
        """
        # 查找所有HTML标题
        headings = []
        for match in self.html_heading_pattern.finditer(text):
            level = int(match.group(1))
            heading_text = match.group(2).strip()
            headings.append({
                "level": level,
                "text": heading_text,
                "start": match.start(),
                "end": match.end()
            })
        
        # 如果没有标题，将整个文档作为一个段落
        if not headings:
            return [{"text": text}]
        
        # 构建段落
        sections = []
        for i, heading in enumerate(headings):
            # 确定段落结束位置
            if i < len(headings) - 1:
                section_end = headings[i + 1]["start"]
            else:
                section_end = len(text)
            
            # 提取段落文本
            if self.include_heading_in_chunk:
                section_text = text[heading["start"]:section_end].strip()
            else:
                section_text = text[heading["end"]:section_end].strip()
            
            # 创建段落
            section = {
                "level": heading["level"],
                "heading": heading["text"],
                "text": section_text
            }
            
            # 如果段落太长，进一步分割
            if len(section_text) > self.chunk_size:
                subsections = self._split_long_section(section_text, heading["text"], heading["level"])
                sections.extend(subsections)
            else:
                sections.append(section)
        
        return sections
    
    def _parse_generic_structure(self, text: str) -> List[Dict[str, Any]]:
        """解析通用文档结构
        
        Args:
            text: 文本
            
        Returns:
            段落列表，每个段落包含文本和元数据
        """
        # 尝试按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        
        # 构建段落
        sections = []
        current_section = {"text": ""}
        current_length = 0
        
        for paragraph in paragraphs:
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            
            paragraph_length = len(paragraph)
            
            # 检查是否可能是标题
            is_heading = False
            heading_level = 0
            
            # 简单的启发式方法检测标题
            if len(paragraph.split('\n')) == 1:  # 单行
                if len(paragraph) < 100:  # 不太长
                    if paragraph.endswith(':') or paragraph.isupper() or paragraph.istitle():
                        is_heading = True
                        heading_level = 3  # 假设是h3级别
            
            # 如果是标题且当前段落不为空，则结束当前段落
            if is_heading and current_section["text"] and current_length > 0:
                sections.append(current_section)
                current_section = {
                    "level": heading_level,
                    "heading": paragraph,
                    "text": paragraph if self.include_heading_in_chunk else ""
                }
                current_length = len(current_section["text"])
                continue
            
            # 如果添加此段落会超过目标大小，则结束当前段落
            if current_length + paragraph_length + 2 > self.chunk_size and current_section["text"]:
                sections.append(current_section)
                current_section = {"text": paragraph}
                current_length = paragraph_length
            else:
                # 添加段落到当前段落
                if current_section["text"]:
                    current_section["text"] += "\n\n" + paragraph
                    current_length += paragraph_length + 2
                else:
                    current_section["text"] = paragraph
                    current_length = paragraph_length
        
        # 添加最后一个段落
        if current_section["text"]:
            sections.append(current_section)
        
        return sections
    
    def _split_long_section(self, text: str, heading: str, level: int) -> List[Dict[str, Any]]:
        """分割长段落
        
        Args:
            text: 段落文本
            heading: 段落标题
            level: 标题级别
            
        Returns:
            分割后的段落列表
        """
        # 按句子分割
        try:
            sentences = sent_tokenize(text)
        except:
            # 回退到简单分割
            sentences = re.split(r'[.!?]+\s+', text)
        
        # 构建子段落
        subsections = []
        current_subsection = ""
        current_length = 0
        
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
            
            sentence_length = len(sentence)
            
            # 如果添加此句子会超过目标大小，则结束当前子段落
            if current_length + sentence_length + 1 > self.chunk_size and current_subsection:
                subsections.append({
                    "level": level,
                    "heading": heading,
                    "text": current_subsection,
                    "is_continuation": len(subsections) > 0
                })
                current_subsection = sentence
                current_length = sentence_length
            else:
                # 添加句子到当前子段落
                if current_subsection:
                    current_subsection += " " + sentence
                    current_length += sentence_length + 1
                else:
                    current_subsection = sentence
                    current_length = sentence_length
        
        # 添加最后一个子段落
        if current_subsection:
            subsections.append({
                "level": level,
                "heading": heading,
                "text": current_subsection,
                "is_continuation": len(subsections) > 0
            })
        
        return subsections

# 创建分块器工厂
def create_chunker(chunking_type: str, **kwargs) -> NodeParser:
    """创建分块器
    
    Args:
        chunking_type: 分块器类型
        **kwargs: 分块器参数
        
    Returns:
        分块器实例
    """
    if chunking_type == "semantic":
        return SemanticChunker(**kwargs)
    elif chunking_type == "hierarchical":
        return HierarchicalChunker(**kwargs)
    else:
        # 默认使用句子分割器
        return SentenceSplitter(**kwargs)
