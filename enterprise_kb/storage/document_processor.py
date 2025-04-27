"""文档处理器模块"""
import os
import logging
import uuid
import re
import mimetypes
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, BinaryIO, Tuple
from pathlib import Path
import json
import math

from llama_index.core import Document, Settings
from llama_index.core.ingestion import IngestionPipeline
from llama_index.core.node_parser import SentenceSplitter, MarkdownNodeParser, HTMLNodeParser, CodeSplitter
from llama_index.readers.file import PyMuPDFReader, DocxReader, UnstructuredReader
from llama_index.embeddings.openai import OpenAIEmbedding
from markitdown import MarkItDown
from llama_index.core.callbacks import CallbackManager, TokenCountingHandler
import tiktoken

from enterprise_kb.core.config.settings import settings
from enterprise_kb.storage.vector_store import get_storage_context
from enterprise_kb.utils.milvus_client import get_milvus_client

logger = logging.getLogger(__name__)

class DocumentComplexity:
    """文档复杂度评估结果"""
    LOW = "low"        # 简单文本，适合直接处理
    MEDIUM = "medium"  # 中等复杂度，标准处理
    HIGH = "high"      # 高复杂度，需要特殊处理

class DocumentFeatures:
    """文档特征"""
    def __init__(self):
        self.page_count: int = 0            # 页数
        self.has_tables: bool = False       # 是否包含表格
        self.has_images: bool = False       # 是否包含图片
        self.has_code: bool = False         # 是否包含代码
        self.text_density: float = 0.0      # 文本密度
        self.estimated_tokens: int = 0      # 估计的令牌数
        self.language: str = "unknown"      # 文档语言
        self.structure_level: int = 0       # 结构层级数量（标题等）
        self.avg_sentence_length: float = 0 # 平均句子长度
        self.metadata: Dict[str, Any] = {}  # 其他元数据
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "page_count": self.page_count,
            "has_tables": self.has_tables,
            "has_images": self.has_images,
            "has_code": self.has_code,
            "text_density": self.text_density,
            "estimated_tokens": self.estimated_tokens,
            "language": self.language,
            "structure_level": self.structure_level,
            "avg_sentence_length": self.avg_sentence_length,
            "metadata": self.metadata
        }

class DocumentAnalyzer:
    """文档分析器，用于评估文档复杂度和特征"""
    
    def __init__(self):
        """初始化文档分析器"""
        # mime类型初始化
        mimetypes.init()
    
    def analyze_document(self, file_path: str) -> Tuple[DocumentFeatures, DocumentComplexity]:
        """分析文档并返回特征和复杂度评估
        
        Args:
            file_path: 文档路径
            
        Returns:
            文档特征和复杂度评估
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        features = DocumentFeatures()
        
        # 根据文件类型选择适当的分析方法
        if file_ext in ['.pdf']:
            self._analyze_pdf(file_path, features)
        elif file_ext in ['.docx', '.doc']:
            self._analyze_word(file_path, features)
        elif file_ext in ['.md', '.markdown']:
            self._analyze_markdown(file_path, features)
        elif file_ext in ['.html', '.htm']:
            self._analyze_html(file_path, features)
        elif file_ext in ['.py', '.js', '.java', '.cpp', '.c', '.rb']:
            self._analyze_code(file_path, features)
        elif file_ext in ['.csv', '.xlsx', '.xls']:
            self._analyze_table(file_path, features)
        elif file_ext in ['.txt']:
            self._analyze_text(file_path, features)
        elif file_ext in ['.ppt', '.pptx']:
            self._analyze_presentation(file_path, features)
        else:
            self._analyze_generic(file_path, features)
            
        # 根据特征判断复杂度
        complexity = self._determine_complexity(features)
            
        return features, complexity
    
    def _analyze_pdf(self, file_path: str, features: DocumentFeatures):
        """分析PDF文档"""
        try:
            import fitz  # PyMuPDF
            
            doc = fitz.open(file_path)
            features.page_count = len(doc)
            
            # 统计图片数
            image_count = 0
            table_count = 0
            text_blocks = 0
            total_text_length = 0
            
            # 分析前10页或全部页面（取较小值）
            analyze_pages = min(10, features.page_count)
            for page_idx in range(analyze_pages):
                page = doc[page_idx]
                
                # 文本分析
                text = page.get_text()
                if text:
                    text_blocks += 1
                    total_text_length += len(text)
                
                # 提取图片
                image_list = page.get_images(full=True)
                image_count += len(image_list)
                
                # 简单表格检测（基于文本模式）
                if '|' in text or '\t' in text:
                    table_count += 1
            
            # 设置特征
            features.has_images = image_count > 0
            features.has_tables = table_count > 0
            
            # 估算文本密度和结构
            if analyze_pages > 0:
                features.text_density = total_text_length / analyze_pages if analyze_pages else 0
                
            # 估算token数
            features.estimated_tokens = total_text_length // 4  # 粗略估计：平均每个token 4个字符
            
            # 检测语言
            features.language = self._detect_language(doc[0].get_text(100))  # 使用第一页的前100个字符
            
            # 结构分析
            toc = doc.get_toc()
            features.structure_level = len(set(lvl for lvl, _, _ in toc)) if toc else 0
        
        except Exception as e:
            logger.error(f"PDF分析失败: {str(e)}")
    
    def _analyze_word(self, file_path: str, features: DocumentFeatures):
        """分析Word文档"""
        try:
            from docx import Document as DocxDocument
            
            doc = DocxDocument(file_path)
            
            # 分析段落数和表格
            features.page_count = len(doc.paragraphs) // 40  # 粗略估计：每页40段
            features.has_tables = len(doc.tables) > 0
            
            # 分析图片（间接判断）
            try:
                for rel in doc.part.rels.values():
                    if "image" in rel.target_ref:
                        features.has_images = True
                        break
            except:
                pass
                
            # 文本分析
            text = "\n".join(p.text for p in doc.paragraphs)
            features.estimated_tokens = len(text) // 4
            
            # 语言检测
            if text:
                features.language = self._detect_language(text[:100])
                
            # 简单结构分析
            headings = 0
            for p in doc.paragraphs:
                if p.style and "Heading" in p.style.name:
                    headings += 1
            
            features.structure_level = 3 if headings > 10 else (2 if headings > 3 else 1)
            
        except Exception as e:
            logger.error(f"Word文档分析失败: {str(e)}")
    
    def _analyze_markdown(self, file_path: str, features: DocumentFeatures):
        """分析Markdown文档"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 分析标题等级
            heading_pattern = re.compile(r'^(#{1,6})\s+', re.MULTILINE)
            headings = heading_pattern.findall(content)
            heading_levels = [len(h) for h in headings]
            features.structure_level = len(set(heading_levels)) if heading_levels else 0
            
            # 分析代码块
            code_blocks = re.findall(r'```[\s\S]*?```', content)
            features.has_code = len(code_blocks) > 0
            
            # 分析表格
            features.has_tables = '|---' in content or '| ---' in content
            
            # 分析图片
            features.has_images = '![' in content
            
            # 文本分析
            features.page_count = content.count('\n') // 40 + 1  # 粗略估计
            features.estimated_tokens = len(content) // 4
            
            # 语言检测
            features.language = self._detect_language(content[:100])
            
        except Exception as e:
            logger.error(f"Markdown分析失败: {str(e)}")
    
    def _analyze_html(self, file_path: str, features: DocumentFeatures):
        """分析HTML文档"""
        try:
            from bs4 import BeautifulSoup
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # 基本特征分析
            features.has_tables = len(soup.find_all('table')) > 0
            features.has_images = len(soup.find_all('img')) > 0
            features.has_code = len(soup.find_all(['code', 'pre'])) > 0
            
            # 文本分析
            text = soup.get_text()
            features.estimated_tokens = len(text) // 4
            features.page_count = len(text) // 3000 + 1  # 粗略估计
            
            # 结构分析
            headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
            features.structure_level = len(set(h.name for h in headings)) if headings else 0
            
            # 语言检测
            features.language = self._detect_language(text[:100])
            
        except Exception as e:
            logger.error(f"HTML分析失败: {str(e)}")
    
    def _analyze_code(self, file_path: str, features: DocumentFeatures):
        """分析代码文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            features.has_code = True
            features.page_count = content.count('\n') // 50 + 1
            features.estimated_tokens = len(content) // 3  # 代码token比自然语言短
            
            # 检测注释占比、类/函数定义等
            # 这里只是简化实现，实际上可以针对不同编程语言有更专门的分析
            comment_lines = 0
            if file_path.endswith('.py'):
                comment_lines = content.count('#') + content.count('"""') // 2
            elif file_path.endswith(('.js', '.java', '.cpp', '.c')):
                comment_lines = content.count('//') + content.count('/*') + content.count('*/')
                
            features.metadata['comment_ratio'] = comment_lines / (content.count('\n') + 1) if content.count('\n') > 0 else 0
            features.language = os.path.splitext(file_path)[1][1:]  # 使用文件扩展名作为语言
            
        except Exception as e:
            logger.error(f"代码分析失败: {str(e)}")
    
    def _analyze_table(self, file_path: str, features: DocumentFeatures):
        """分析表格文件(CSV/Excel)"""
        try:
            features.has_tables = True
            
            if file_path.endswith('.csv'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                rows = content.count('\n') + 1
                features.page_count = max(1, rows // 100)  # 粗略估计：每页100行
                features.estimated_tokens = len(content) // 5
                
                # 分析列数
                if '\n' in content:
                    first_line = content.split('\n')[0]
                    features.metadata['columns'] = first_line.count(',') + 1
            
            elif file_path.endswith(('.xlsx', '.xls')):
                try:
                    import pandas as pd
                    df = pd.read_excel(file_path)
                    features.page_count = max(1, len(df) // 100)
                    features.estimated_tokens = df.size * 2  # 每个单元格约2个token
                    features.metadata['columns'] = len(df.columns)
                    features.metadata['rows'] = len(df)
                except ImportError:
                    # 如果pandas未安装，使用更基本的方法
                    features.page_count = 1
            
        except Exception as e:
            logger.error(f"表格分析失败: {str(e)}")
    
    def _analyze_text(self, file_path: str, features: DocumentFeatures):
        """分析纯文本文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            features.page_count = content.count('\n') // 40 + 1
            features.estimated_tokens = len(content) // 4
            
            # 检测是否包含表格式文本
            lines = content.split('\n')
            if len(lines) > 3:
                table_like_lines = sum(1 for line in lines if line.count('\t') > 2 or line.count('|') > 2)
                features.has_tables = table_like_lines > 3
            
            # 语言检测
            features.language = self._detect_language(content[:100])
            
            # 简单分析句子长度
            sentences = re.split(r'[.!?]+', content)
            if sentences:
                features.avg_sentence_length = sum(len(s) for s in sentences) / len(sentences)
            
        except Exception as e:
            logger.error(f"文本分析失败: {str(e)}")
    
    def _analyze_presentation(self, file_path: str, features: DocumentFeatures):
        """分析演示文稿"""
        try:
            import pptx
            presentation = pptx.Presentation(file_path)
            
            features.page_count = len(presentation.slides)
            
            text_content = []
            image_count = 0
            table_count = 0
            
            # 分析每个幻灯片
            for slide in presentation.slides:
                # 提取文本
                for shape in slide.shapes:
                    if hasattr(shape, "text"):
                        text_content.append(shape.text)
                        
                    # 检测图片
                    if shape.shape_type == 13:  # MSO_SHAPE_TYPE.PICTURE
                        image_count += 1
                        
                    # 检测表格
                    if shape.shape_type == 19:  # MSO_SHAPE_TYPE.TABLE
                        table_count += 1
            
            # 设置特征
            features.has_images = image_count > 0
            features.has_tables = table_count > 0
            features.estimated_tokens = sum(len(text) for text in text_content) // 4
            
            # 语言检测
            if text_content:
                sample_text = text_content[0][:100] if text_content[0] else ""
                features.language = self._detect_language(sample_text)
                
        except Exception as e:
            logger.error(f"演示文稿分析失败: {str(e)}")
            # 基本估计
            features.page_count = 1
            features.has_images = True
    
    def _analyze_generic(self, file_path: str, features: DocumentFeatures):
        """通用文件分析"""
        # 尝试判断MIME类型
        mime_type, _ = mimetypes.guess_type(file_path)
        
        # 设置基本特征
        features.page_count = 1
        
        if mime_type:
            features.metadata['mime_type'] = mime_type
            
            if 'image' in mime_type:
                features.has_images = True
            elif 'text' in mime_type:
                self._analyze_text(file_path, features)
        
        # 文件大小作为复杂度参考
        try:
            file_size = os.path.getsize(file_path)
            features.metadata['file_size'] = file_size
            features.estimated_tokens = file_size // 10  # 非常粗略的估计
        except:
            pass
    
    def _detect_language(self, text_sample: str) -> str:
        """检测文本语言
        
        这是一个非常简化的实现，实际应用中可以使用更复杂的语言检测库如langdetect
        """
        if not text_sample:
            return "unknown"
            
        # 简化的语言检测逻辑
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text_sample))
        if chinese_chars > len(text_sample) * 0.2:
            return "zh"
            
        # 可以添加其他语言的检测
        # 默认返回英文
        return "en"
    
    def _determine_complexity(self, features: DocumentFeatures) -> DocumentComplexity:
        """根据特征确定文档复杂度"""
        # 高复杂度指标
        if features.page_count > 50 or features.estimated_tokens > 50000:
            return DocumentComplexity.HIGH
            
        # 包含复杂元素且规模较大
        if (features.has_tables or features.has_images) and features.page_count > 20:
            return DocumentComplexity.HIGH
            
        # 中等复杂度指标
        if features.page_count > 10 or features.estimated_tokens > 10000:
            return DocumentComplexity.MEDIUM
            
        if features.has_tables or features.has_images or features.has_code:
            return DocumentComplexity.MEDIUM
            
        # 其他为低复杂度
        return DocumentComplexity.LOW

class AdaptiveChunkingStrategy:
    """自适应分块策略"""
    
    def __init__(self):
        """初始化自适应分块策略"""
        self.default_chunk_size = settings.LLAMA_INDEX_CHUNK_SIZE
        self.default_chunk_overlap = settings.LLAMA_INDEX_CHUNK_OVERLAP
        
    def get_chunking_parameters(
        self, 
        doc_type: str,
        features: DocumentFeatures, 
        complexity: DocumentComplexity
    ) -> Dict[str, Any]:
        """获取分块参数
        
        Args:
            doc_type: 文档类型
            features: 文档特征
            complexity: 文档复杂度
            
        Returns:
            分块参数
        """
        # 根据文档类型优化
        if doc_type == "markdown":
            return self._get_markdown_parameters(features, complexity)
        elif doc_type == "code":
            return self._get_code_parameters(features)
        elif doc_type == "table":
            return self._get_table_parameters(features)
        elif doc_type == "pdf":
            return self._get_pdf_parameters(features, complexity)
        elif doc_type == "text":
            return self._get_text_parameters(features, complexity)
        else:
            # 通用参数
            return self._get_generic_parameters(features, complexity)
    
    def _get_markdown_parameters(self, features: DocumentFeatures, complexity: DocumentComplexity) -> Dict[str, Any]:
        """获取Markdown文档的分块参数"""
        # Markdown文档可以使用专门的解析器
        params = {
            "chunking_type": "markdown",
            "parser_type": "markdown",
            "chunk_size": self.default_chunk_size,
            "chunk_overlap": self.default_chunk_overlap
        }
        
        # 根据结构复杂度调整
        if features.structure_level > 3:
            # 有丰富的标题层级，可以适当增加块大小
            params["chunk_size"] = min(2048, self.default_chunk_size * 1.5)
            
        # 复杂度调整
        if complexity == DocumentComplexity.HIGH:
            # 更小的块以处理复杂内容
            params["chunk_size"] = max(512, params["chunk_size"] // 2)
            params["chunk_overlap"] = min(150, params["chunk_overlap"] * 2)
        elif complexity == DocumentComplexity.LOW:
            # 较大的块以保持上下文连贯性
            params["chunk_size"] = min(2048, params["chunk_size"] * 1.5)
            
        return params
    
    def _get_code_parameters(self, features: DocumentFeatures) -> Dict[str, Any]:
        """获取代码文件的分块参数"""
        return {
            "chunking_type": "code",
            "parser_type": "code",
            "language": features.language,
            "chunk_size": min(1024, self.default_chunk_size),
            "chunk_overlap": min(100, self.default_chunk_overlap),
            "max_lines": 100
        }
    
    def _get_table_parameters(self, features: DocumentFeatures) -> Dict[str, Any]:
        """获取表格文件的分块参数"""
        # 表格文件可能需要特殊处理
        return {
            "chunking_type": "table",
            "parser_type": "table",
            "chunk_size": min(1024, self.default_chunk_size),
            "chunk_overlap": 0,  # 表格数据通常不需要重叠
            "metadata": {
                "columns": features.metadata.get("columns", 0),
                "rows": features.metadata.get("rows", 0)
            }
        }
    
    def _get_pdf_parameters(self, features: DocumentFeatures, complexity: DocumentComplexity) -> Dict[str, Any]:
        """获取PDF文档的分块参数"""
        params = {
            "chunking_type": "pdf",
            "parser_type": "sentence",
            "chunk_size": self.default_chunk_size,
            "chunk_overlap": self.default_chunk_overlap
        }
        
        # 有图表的PDF可能需要更细粒度的分块
        if features.has_images or features.has_tables:
            params["chunk_size"] = max(512, params["chunk_size"] // 2)
            params["chunk_overlap"] = min(200, params["chunk_overlap"] * 1.5)
            
        # 根据复杂度调整
        if complexity == DocumentComplexity.HIGH:
            params["chunk_size"] = max(256, params["chunk_size"] // 2)
        elif complexity == DocumentComplexity.LOW:
            params["chunk_size"] = min(2048, params["chunk_size"] * 1.2)
            
        return params
    
    def _get_text_parameters(self, features: DocumentFeatures, complexity: DocumentComplexity) -> Dict[str, Any]:
        """获取文本文件的分块参数"""
        params = {
            "chunking_type": "text",
            "parser_type": "sentence",
            "chunk_size": self.default_chunk_size,
            "chunk_overlap": self.default_chunk_overlap
        }
        
        # 根据复杂度调整
        if complexity == DocumentComplexity.HIGH:
            params["chunk_size"] = max(512, params["chunk_size"] // 1.5)
        elif complexity == DocumentComplexity.LOW:
            params["chunk_size"] = min(2048, params["chunk_size"] * 1.2)
            
        # 考虑句子长度
        if features.avg_sentence_length > 100:
            # 长句子需要更大的重叠
            params["chunk_overlap"] = min(200, params["chunk_overlap"] * 1.5)
            
        return params
    
    def _get_generic_parameters(self, features: DocumentFeatures, complexity: DocumentComplexity) -> Dict[str, Any]:
        """获取通用参数"""
        params = {
            "chunking_type": "generic",
            "parser_type": "sentence",
            "chunk_size": self.default_chunk_size,
            "chunk_overlap": self.default_chunk_overlap
        }
        
        # 根据复杂度调整
        if complexity == DocumentComplexity.HIGH:
            params["chunk_size"] = max(512, params["chunk_size"] // 1.5)
            params["chunk_overlap"] = min(200, params["chunk_overlap"] * 1.5)
        elif complexity == DocumentComplexity.LOW:
            params["chunk_size"] = min(2048, params["chunk_size"] * 1.2)
            
        return params
    
    def create_parser(self, params: Dict[str, Any]):
        """创建解析器
        
        根据参数创建适当的分块解析器
        
        Args:
            params: 分块参数
            
        Returns:
            节点解析器
        """
        parser_type = params.get("parser_type", "sentence")
        
        if parser_type == "markdown":
            return MarkdownNodeParser(
                chunk_size=params["chunk_size"],
                chunk_overlap=params["chunk_overlap"]
            )
        elif parser_type == "code":
            return CodeSplitter(
                language=params.get("language", ""),
                chunk_size=params["chunk_size"],
                chunk_overlap=params["chunk_overlap"],
                max_lines=params.get("max_lines", 100)
            )
        elif parser_type == "html":
            return HTMLNodeParser(
                chunk_size=params["chunk_size"],
                chunk_overlap=params["chunk_overlap"]
            )
        else:
            # 默认使用句子分块器
            return SentenceSplitter(
                chunk_size=params["chunk_size"],
                chunk_overlap=params["chunk_overlap"]
            )

class DocumentProcessor:
    """文档处理器，用于加载、处理和索引文档"""
    
    def __init__(self):
        """初始化文档处理器"""
        # 创建令牌计数器
        if settings.TOKEN_COUNTING_ENABLED:
            token_counter = TokenCountingHandler(
                tokenizer=tiktoken.encoding_for_model(settings.TOKEN_COUNTER_MODEL).encode,
                verbose=settings.TOKEN_COUNTING_VERBOSE
            )
            
            # 设置全局配置
            Settings.callback_manager = CallbackManager([token_counter])
        
        # 设置嵌入模型和分块配置
        Settings.embed_model = OpenAIEmbedding()
        Settings.chunk_size = settings.LLAMA_INDEX_CHUNK_SIZE
        Settings.chunk_overlap = settings.LLAMA_INDEX_CHUNK_OVERLAP
        
        # 创建文档存储目录
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        os.makedirs(settings.PROCESSED_DIR, exist_ok=True)
        os.makedirs(os.path.join(settings.PROCESSED_DIR, "markdown"), exist_ok=True)
        
        # 初始化Milvus客户端
        self.vector_store_client = get_milvus_client()
        
        # 初始化LlamaIndex存储上下文
        self.storage_context = get_storage_context()
        
        # 创建文档加载器映射
        self.file_readers = {
            ".pdf": PyMuPDFReader(),
            ".docx": DocxReader(),
            ".doc": UnstructuredReader(),
            ".txt": UnstructuredReader(),
            ".md": UnstructuredReader(),
            ".ppt": UnstructuredReader(),
            ".pptx": UnstructuredReader(),
        }
        
        # 创建摘要管道
        self.ingestion_pipeline = IngestionPipeline(
            transformations=[
                SentenceSplitter(
                    chunk_size=settings.LLAMA_INDEX_CHUNK_SIZE,
                    chunk_overlap=settings.LLAMA_INDEX_CHUNK_OVERLAP
                )
            ],
            vector_store=self.storage_context.vector_store
        )
        
        # 初始化MarkItDown转换器
        self.markitdown = MarkItDown(enable_plugins=True)
        
        # 初始化文档分析器
        self.analyzer = DocumentAnalyzer()
        
        # 初始化自适应分块策略
        self.chunking_strategy = AdaptiveChunkingStrategy()
    
    def get_reader_for_file(self, file_path: str):
        """根据文件扩展名获取合适的文档读取器"""
        file_ext = os.path.splitext(file_path)[1].lower()
        reader = self.file_readers.get(file_ext)
        
        if not reader:
            raise ValueError(f"不支持的文件类型: {file_ext}")
            
        return reader
    
    def save_uploaded_file(self, file_content: bytes, filename: str) -> str:
        """保存上传的文件并返回唯一文件ID"""
        # 生成唯一ID
        file_id = str(uuid.uuid4())
        
        # 确保文件名唯一
        file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}_{filename}")
        
        # 写入文件
        with open(file_path, "wb") as f:
            f.write(file_content)
            
        logger.info(f"保存上传的文件: {file_path}")
        return file_path
    
    def convert_to_markdown(self, file_path: str) -> str:
        """使用MarkItDown将文档转换为Markdown格式
        
        Args:
            file_path: 原始文件路径
            
        Returns:
            Markdown文件路径
        """
        try:
            logger.info(f"开始将文件转换为Markdown: {file_path}")
            
            # 使用MarkItDown转换文件
            result = self.markitdown.convert(file_path)
            
            # 生成Markdown文件路径
            file_name = os.path.basename(file_path)
            md_file_name = f"{os.path.splitext(file_name)[0]}.md"
            md_file_path = os.path.join(settings.PROCESSED_DIR, "markdown", md_file_name)
            
            # 写入Markdown内容
            with open(md_file_path, "w", encoding="utf-8") as f:
                f.write(result.text_content)
                
            logger.info(f"文件已转换为Markdown: {md_file_path}")
            return md_file_path
            
        except Exception as e:
            logger.error(f"转换文件到Markdown失败: {str(e)}")
            # 转换失败时返回原始文件路径
            return file_path
    
    def determine_processing_strategy(self, file_path: str) -> Dict[str, Any]:
        """确定文档处理策略
        
        Args:
            file_path: 文件路径
            
        Returns:
            处理策略参数
        """
        file_ext = os.path.splitext(file_path)[1].lower()
        
        # 分析文档
        features, complexity = self.analyzer.analyze_document(file_path)
        
        # 确定文档类型
        if file_ext in ['.md', '.markdown']:
            doc_type = "markdown"
        elif file_ext in ['.py', '.js', '.java', '.cpp', '.c', '.rb']:
            doc_type = "code"
        elif file_ext in ['.csv', '.xlsx', '.xls']:
            doc_type = "table"
        elif file_ext in ['.pdf']:
            doc_type = "pdf"
        elif file_ext in ['.txt']:
            doc_type = "text"
        elif file_ext in ['.html', '.htm']:
            doc_type = "html"
        else:
            doc_type = "generic"
        
        # 确定是否需要转换为Markdown
        should_convert_to_markdown = self._should_convert_to_markdown(doc_type, features, complexity)
        
        # 获取分块参数
        chunking_params = self.chunking_strategy.get_chunking_parameters(doc_type, features, complexity)
        
        # 策略信息
        strategy = {
            "doc_type": doc_type,
            "features": features.to_dict(),
            "complexity": complexity,
            "should_convert_to_markdown": should_convert_to_markdown,
            "chunking_params": chunking_params
        }
        
        logger.info(f"文档处理策略: {strategy}")
        return strategy
    
    def _should_convert_to_markdown(
        self, 
        doc_type: str, 
        features: DocumentFeatures,
        complexity: DocumentComplexity
    ) -> bool:
        """判断是否应该转换为Markdown
        
        Args:
            doc_type: 文档类型
            features: 文档特征
            complexity: 文档复杂度
            
        Returns:
            是否应转换为Markdown
        """
        # 已经是Markdown的不需要转换
        if doc_type == "markdown":
            return False
            
        # 代码文件通常不适合转换为Markdown
        if doc_type == "code":
            return False
            
        # 表格数据通常保持原格式更好
        if doc_type == "table" and not features.has_images:
            return False
            
        # 纯文本如果结构简单，可以直接处理
        if doc_type == "text" and complexity == DocumentComplexity.LOW:
            return False
            
        # HTML可以直接使用HTML解析器
        if doc_type == "html":
            # 除非有复杂图表，才需要转换
            return features.has_images or features.has_tables
            
        # 其他情况默认转换为Markdown
        return True
    
    async def process_document(
        self,
        file_path: str,
        metadata: Dict[str, Any],
        datasource_name: Optional[str] = "primary",
        use_parallel: Optional[bool] = None,
        use_semantic_chunking: Optional[bool] = None,
        use_incremental: Optional[bool] = None,
        chunking_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """处理文档并索引到向量库

        Args:
            file_path: 文档路径
            metadata: 文档元数据
            datasource_name: 数据源名称
            use_parallel: 是否使用并行处理，如果为None则使用配置中的默认值
            use_semantic_chunking: 是否使用语义分块，如果为None则使用配置中的默认值
            use_incremental: 是否使用增量更新，如果为None则使用配置中的默认值
            chunking_type: 分块类型，如果为None则使用配置中的默认值

        Returns:
            处理结果
        """
        try:
            # 重置令牌计数器
            token_counter = None
            if settings.TOKEN_COUNTING_ENABLED and Settings.callback_manager and Settings.callback_manager.handlers:
                for handler in Settings.callback_manager.handlers:
                    if isinstance(handler, TokenCountingHandler):
                        token_counter = handler
                        token_counter.reset_counts()
                        break

            # 准备元数据
            if metadata is None:
                metadata = {}
                
            # 添加基本元数据
            file_name = os.path.basename(file_path)
            doc_id = str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            base_metadata = {
                "doc_id": doc_id,
                "file_name": file_name,
                "file_path": file_path,
                "file_type": os.path.splitext(file_path)[1].lower(),
                "upload_time": now,
                "process_time": now
            }
            
            # 合并元数据
            metadata = {**base_metadata, **metadata}
            
            # 如果没有提供策略，则自动确定
            strategy = self.determine_processing_strategy(file_path)
            metadata["processing_strategy"] = strategy
            
            # 确定是否转换为Markdown
            should_convert = strategy["should_convert_to_markdown"]
            
            # 将文档转换为Markdown格式（如果需要）
            processing_path = file_path
            if should_convert:
                md_file_path = self.convert_to_markdown(file_path)
                metadata["markdown_path"] = md_file_path
                metadata["original_file_path"] = file_path
                
                # 使用转换后的Markdown文件进行处理
                if md_file_path != file_path and os.path.exists(md_file_path):
                    processing_path = md_file_path
                    metadata["file_type"] = ".md"
                    
                    # 更新策略的文档类型
                    strategy["doc_type"] = "markdown"
            
            # 创建适当的解析器
            chunking_params = strategy["chunking_params"]
            parser = self.chunking_strategy.create_parser(chunking_params)
            
            # 加载文档
            reader = self.get_reader_for_file(processing_path)
            documents = reader.load(processing_path)
            
            # 添加元数据到文档
            for doc in documents:
                doc.metadata.update(metadata)
            
            # 使用适当的解析器处理文档
            ingestion_pipeline = IngestionPipeline(
                transformations=[parser],
                vector_store=self.storage_context.vector_store
            )
            nodes = ingestion_pipeline.run(documents=documents)
            
            # 处理完成后可以记录令牌使用情况
            token_usage = {}
            if token_counter:
                token_usage = {
                    "embedding_tokens": token_counter.total_embedding_token_count,
                    "llm_prompt_tokens": token_counter.prompt_llm_token_count,
                    "llm_completion_tokens": token_counter.completion_llm_token_count,
                    "total_llm_tokens": token_counter.total_llm_token_count
                }
                logger.info(f"文档处理令牌使用情况: {token_usage}")
            
            # 添加令牌使用信息到元数据
            if token_usage:
                metadata["token_usage"] = token_usage
            
            # 返回处理结果
            result = {
                "doc_id": doc_id,
                "file_name": file_name,
                "metadata": metadata,
                "status": "success",
                "node_count": len(nodes),
                "text_chars": sum(len(node.get_content()) for node in nodes),
                "processing_strategy": strategy
            }
            
            logger.info(f"成功处理文档: {file_name}, ID: {doc_id}")
            return result
            
        except Exception as e:
            logger.error(f"处理文档失败: {str(e)}")
            raise
    
    def delete_document(self, doc_id: str) -> bool:
        """删除文档及其向量数据"""
        try:
            # 删除向量数据
            self.vector_store_client.delete(f"doc_id == '{doc_id}'")
            
            # 可以在这里添加删除原始文件的逻辑
            logger.info(f"成功删除文档 ID: {doc_id}")
            return True
        except Exception as e:
            logger.error(f"删除文档失败: {str(e)}")
            return False

# 创建单例实例
_document_processor = None

def get_document_processor() -> DocumentProcessor:
    """获取文档处理器单例"""
    global _document_processor
    if _document_processor is None:
        _document_processor = DocumentProcessor()
    return _document_processor 