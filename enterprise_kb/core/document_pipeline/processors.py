"""文档处理器实现模块"""
import os
from typing import Dict, Any, List
import logging
import fitz  # PyMuPDF
import docx
import markitdown
from pathlib import Path

from enterprise_kb.core.document_pipeline.base import DocumentProcessor, PipelineFactory
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

@PipelineFactory.register_processor
class FileValidator(DocumentProcessor):
    """文件验证处理器"""
    
    SUPPORTED_TYPES = ['pdf', 'md', 'markdown', 'docx', 'txt', 'html']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """验证文件是否有效且可处理"""
        file_path = context.get('file_path')
        if not file_path or not os.path.exists(file_path):
            raise ValueError(f"文件不存在: {file_path}")
            
        file_type = context.get('file_type', '').lower()
        if not file_type or file_type not in self.SUPPORTED_TYPES:
            raise ValueError(f"不支持的文件类型: {file_type}")
            
        # 检查文件大小
        file_size = os.path.getsize(file_path)
        if file_size > settings.MAX_FILE_SIZE_BYTES:
            raise ValueError(f"文件过大: {file_size} 字节，最大支持 {settings.MAX_FILE_SIZE_BYTES} 字节")
            
        # 更新上下文
        context['file_size'] = file_size
        context['validation_passed'] = True
        
        logger.info(f"文件验证通过: {file_path}, 类型: {file_type}, 大小: {file_size} 字节")
        return context


@PipelineFactory.register_processor
class MarkItDownProcessor(DocumentProcessor):
    """通用MarkItDown文档处理器，适用于多种文档格式"""
    
    # 支持更多格式，包括HTML、RTF等MarkItDown支持的格式
    SUPPORTED_TYPES = ['pdf', 'md', 'markdown', 'docx', 'txt', 'html', 'htm', 'rtf', 'odt', 'pptx']
    
    def __init__(self):
        """初始化MarkItDown处理器"""
        super().__init__()
        self.markitdown_converter = markitdown.MarkItDown(enable_plugins=True)
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """使用MarkItDown处理文档，转换为标准Markdown格式"""
        file_path = context.get('file_path')
        file_type = context.get('file_type', '').lower()
        
        if not file_path or not os.path.exists(file_path) or file_type not in self.SUPPORTED_TYPES:
            return context
            
        try:
            # 检查是否需要转换为Markdown
            if context.get('convert_to_markdown', True):
                logger.info(f"使用MarkItDown转换文档: {file_path}")
                
                # 使用MarkItDown转换文件
                try:
                    markdown_content = self.markitdown_converter.convert(file_path)
                    context['markdown_content'] = markdown_content
                    
                    # 同时提供纯文本内容，方便后续处理
                    if 'text_content' not in context:
                        context['text_content'] = markdown_content
                        
                    logger.info(f"文档转换为Markdown成功: {file_path}")
                    
                    # 提取文档结构信息
                    self._extract_document_structure(markdown_content, context)
                    
                except Exception as e:
                    logger.warning(f"MarkItDown转换失败，尝试使用备用方法: {str(e)}")
                    # 如果MarkItDown转换失败，使用原始处理流程
                    context['markdown_conversion_failed'] = True
            
        except Exception as e:
            logger.error(f"文档处理失败: {str(e)}")
            raise
            
        return context
    
    def _extract_document_structure(self, markdown_content: str, context: Dict[str, Any]):
        """从Markdown内容中提取文档结构信息"""
        import re
        
        # 提取标题
        headings = []
        heading_pattern = re.compile(r'^(#{1,6})\s+(.*?)$', re.MULTILINE)
        for match in heading_pattern.finditer(markdown_content):
            level = len(match.group(1))
            title = match.group(2).strip()
            headings.append((level, title))
        
        # 提取代码块
        code_blocks = []
        code_pattern = re.compile(r'```(\w*)\n(.*?)```', re.DOTALL)
        for match in code_pattern.finditer(markdown_content):
            language = match.group(1)
            code = match.group(2)
            code_blocks.append((language, code))
        
        # 提取图片
        images = []
        image_pattern = re.compile(r'!\[(.*?)\]\((.*?)\)')
        for match in image_pattern.finditer(markdown_content):
            alt_text = match.group(1)
            image_path = match.group(2)
            images.append((alt_text, image_path))
        
        # 更新上下文
        context['document_structure'] = {
            'headings': headings,
            'code_blocks': code_blocks,
            'images': images
        }
        
        return context


@PipelineFactory.register_processor
class PDFProcessor(DocumentProcessor):
    """PDF文档处理器"""
    
    SUPPORTED_TYPES = ['pdf']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理PDF文档"""
        if context.get('file_type') != 'pdf':
            return context
            
        # 如果已经通过MarkItDown转换过，跳过额外处理
        if context.get('markdown_content') and not context.get('markdown_conversion_failed'):
            logger.info(f"PDF已通过MarkItDown处理，跳过额外处理")
            return context
            
        file_path = context.get('file_path')
        try:
            # 使用PyMuPDF提取文本
            doc = fitz.open(file_path)
            text_content = ""
            toc = doc.get_toc()  # 获取目录
            
            # 提取文本
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                text_content += page.get_text()
                
            # 更新上下文
            context['text_content'] = text_content
            context['page_count'] = len(doc)
            context['toc'] = toc if toc else []
            
            # 如果需要转换为Markdown，但MarkItDown失败，使用备用方法
            if context.get('convert_to_markdown', True) and context.get('markdown_conversion_failed'):
                try:
                    # 尝试备用方法转换为Markdown
                    md_content = self._convert_to_basic_markdown(text_content, toc)
                    context['markdown_content'] = md_content
                    logger.info(f"PDF使用备用方法转换为Markdown成功: {file_path}")
                except Exception as e:
                    logger.error(f"PDF备用转换失败: {str(e)}")
                    
            logger.info(f"PDF处理完成: {file_path}, 页数: {len(doc)}")
            
        except Exception as e:
            logger.error(f"PDF处理失败: {str(e)}")
            raise
            
        return context
    
    def _convert_to_basic_markdown(self, text: str, toc: List) -> str:
        """简单地将文本转换为Markdown格式"""
        # 如果有目录，创建Markdown标题
        md_content = ""
        if toc:
            md_content += "# 文档目录\n\n"
            for level, title, page in toc:
                indent = "  " * (level - 1)
                md_content += f"{indent}- {title} (页码: {page})\n"
            md_content += "\n\n# 文档内容\n\n"
        
        # 添加文本内容，按段落分割
        paragraphs = text.split("\n\n")
        for para in paragraphs:
            para = para.strip()
            if para:
                md_content += para + "\n\n"
        
        return md_content


@PipelineFactory.register_processor
class DocxProcessor(DocumentProcessor):
    """Word文档处理器"""
    
    SUPPORTED_TYPES = ['docx']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理Word文档"""
        if context.get('file_type') != 'docx':
            return context
            
        # 如果已经通过MarkItDown转换过，跳过额外处理
        if context.get('markdown_content') and not context.get('markdown_conversion_failed'):
            logger.info(f"Word文档已通过MarkItDown处理，跳过额外处理")
            return context
            
        file_path = context.get('file_path')
        try:
            # 使用python-docx提取文本
            doc = docx.Document(file_path)
            text_content = "\n".join([para.text for para in doc.paragraphs])
            
            # 更新上下文
            context['text_content'] = text_content
            context['paragraph_count'] = len(doc.paragraphs)
            
            # 如果需要转换为Markdown，可以在这里调用MarkItDown
            if context.get('convert_to_markdown', True):
                context['markdown_content'] = self._convert_to_markdown(file_path)
                
            logger.info(f"Word文档处理完成: {file_path}, 段落数: {len(doc.paragraphs)}")
            
        except Exception as e:
            logger.error(f"Word文档处理失败: {str(e)}")
            raise
            
        return context
        
    def _convert_to_markdown(self, file_path: str) -> str:
        """
        将Word文档转换为Markdown
        
        Args:
            file_path: Word文件路径
            
        Returns:
            Markdown内容
        """
        try:
            # 使用MarkItDown转换
            md_content = markitdown.markitdown(file_path)
            return md_content
        except Exception as e:
            logger.error(f"Word转Markdown失败: {str(e)}")
            raise


@PipelineFactory.register_processor
class MarkdownProcessor(DocumentProcessor):
    """Markdown文档处理器"""
    
    SUPPORTED_TYPES = ['md', 'markdown']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理Markdown文档"""
        if context.get('file_type') not in ['md', 'markdown']:
            return context
            
        file_path = context.get('file_path')
        try:
            # 读取Markdown文件
            with open(file_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
                
            # 更新上下文
            context['text_content'] = markdown_content
            context['markdown_content'] = markdown_content  # 已经是Markdown格式
            
            logger.info(f"Markdown文档处理完成: {file_path}")
            
        except Exception as e:
            logger.error(f"Markdown处理失败: {str(e)}")
            raise
            
        return context


@PipelineFactory.register_processor
class TextProcessor(DocumentProcessor):
    """文本文件处理器"""
    
    SUPPORTED_TYPES = ['txt']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理纯文本文件"""
        if context.get('file_type') != 'txt':
            return context
            
        file_path = context.get('file_path')
        try:
            # 读取文本文件
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
                
            # 更新上下文
            context['text_content'] = text_content
            
            logger.info(f"文本文件处理完成: {file_path}")
            
        except Exception as e:
            logger.error(f"文本处理失败: {str(e)}")
            raise
            
        return context


@PipelineFactory.register_processor
class ChunkingProcessor(DocumentProcessor):
    """文档分块处理器"""
    
    SUPPORTED_TYPES = ['pdf', 'md', 'markdown', 'docx', 'txt', 'html']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """根据文档类型选择合适的分块策略"""
        text_content = context.get('text_content')
        if not text_content:
            return context
            
        file_type = context.get('file_type')
        
        # 根据文件类型选择分块策略
        if file_type in ['md', 'markdown']:
            chunks = self._chunk_markdown(text_content)
        elif file_type == 'pdf':
            chunks = self._chunk_pdf(text_content)
        else:
            chunks = self._chunk_text(text_content)
            
        # 更新上下文
        context['chunks'] = chunks
        context['chunk_count'] = len(chunks)
        
        logger.info(f"文档分块完成，共 {len(chunks)} 个块")
        return context
        
    def _chunk_markdown(self, text: str) -> List[str]:
        """
        按Markdown结构分块
        
        Args:
            text: Markdown文本
            
        Returns:
            文本块列表
        """
        # 这里应该实现基于Markdown结构的分块
        # 简单示例，实际应该更复杂
        return self._chunk_by_headings(text, ['# ', '## ', '### '])
        
    def _chunk_pdf(self, text: str) -> List[str]:
        """
        PDF文本分块
        
        Args:
            text: PDF提取的文本
            
        Returns:
            文本块列表
        """
        # PDF分块逻辑
        return self._chunk_text(text)
        
    def _chunk_text(self, text: str) -> List[str]:
        """
        通用文本分块
        
        Args:
            text: 文本内容
            
        Returns:
            文本块列表
        """
        # 简单按段落分块
        chunks = []
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            # 如果段落本身超过最大块大小，单独作为一个块
            if para_size > settings.MAX_CHUNK_SIZE:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                    current_size = 0
                
                # 大段落再切分
                para_chunks = self._split_large_paragraph(para)
                chunks.extend(para_chunks)
                continue
                
            # 如果加上这个段落会超过最大块大小，则开始新块
            if current_size + para_size > settings.MAX_CHUNK_SIZE:
                chunks.append(current_chunk)
                current_chunk = para
                current_size = para_size
            else:
                if current_chunk:
                    current_chunk += "\n\n" + para
                else:
                    current_chunk = para
                current_size += para_size
                
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
        
    def _chunk_by_headings(self, text: str, heading_markers: List[str]) -> List[str]:
        """
        按标题分块
        
        Args:
            text: 文本内容
            heading_markers: 标题标记列表
            
        Returns:
            文本块列表
        """
        chunks = []
        lines = text.split('\n')
        
        current_chunk = ""
        current_size = 0
        
        for line in lines:
            # 检查是否为标题行
            is_heading = any(line.startswith(marker) for marker in heading_markers)
            
            # 如果是标题行且当前块非空，则开始新块
            if is_heading and current_chunk:
                chunks.append(current_chunk)
                current_chunk = line
                current_size = len(line)
            else:
                if current_chunk:
                    current_chunk += "\n" + line
                else:
                    current_chunk = line
                current_size += len(line) + 1  # +1 for newline
                
            # 如果当前块太大，也开始新块
            if current_size > settings.MAX_CHUNK_SIZE:
                chunks.append(current_chunk)
                current_chunk = ""
                current_size = 0
                
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks
        
    def _split_large_paragraph(self, paragraph: str) -> List[str]:
        """
        分割大段落
        
        Args:
            paragraph: 大段落文本
            
        Returns:
            分割后的文本块列表
        """
        chunks = []
        sentences = paragraph.replace('. ', '.\n').split('\n')
        
        current_chunk = ""
        current_size = 0
        
        for sentence in sentences:
            sentence_size = len(sentence)
            
            # 如果句子本身超过最大块大小，按固定长度分割
            if sentence_size > settings.MAX_CHUNK_SIZE:
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                    current_size = 0
                    
                # 按固定长度分割大句子
                for i in range(0, sentence_size, settings.MAX_CHUNK_SIZE):
                    chunk = sentence[i:i + settings.MAX_CHUNK_SIZE]
                    chunks.append(chunk)
                continue
                
            # 如果加上这个句子会超过最大块大小，则开始新块
            if current_size + sentence_size > settings.MAX_CHUNK_SIZE:
                chunks.append(current_chunk)
                current_chunk = sentence
                current_size = sentence_size
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_size += sentence_size + 1  # +1 for space
                
        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)
            
        return chunks


@PipelineFactory.register_processor
class VectorizationProcessor(DocumentProcessor):
    """文档向量化处理器"""
    
    SUPPORTED_TYPES = ['pdf', 'md', 'markdown', 'docx', 'txt', 'html']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理文档向量化"""
        chunks = context.get('chunks', [])
        if not chunks:
            logger.warning("没有找到文本块，跳过向量化")
            return context
            
        try:
            # 这里应该调用向量化服务
            # 简化示例，实际应连接到向量数据库
            node_count = len(chunks)
            doc_id = context.get('metadata', {}).get('doc_id')
            
            # 更新上下文
            context['vectorized'] = True
            context['node_count'] = node_count
            
            logger.info(f"向量化完成，文档ID: {doc_id}, 节点数: {node_count}")
            
        except Exception as e:
            logger.error(f"向量化失败: {str(e)}")
            raise
            
        return context 


@PipelineFactory.register_processor
class HTMLProcessor(DocumentProcessor):
    """HTML文档处理器"""
    
    SUPPORTED_TYPES = ['html', 'htm']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理HTML文档"""
        if context.get('file_type') not in ['html', 'htm']:
            return context
            
        # 如果已经通过MarkItDown转换过，跳过额外处理
        if context.get('markdown_content') and not context.get('markdown_conversion_failed'):
            logger.info(f"HTML文档已通过MarkItDown处理，跳过额外处理")
            return context
            
        file_path = context.get('file_path')
        try:
            # 读取HTML文件
            with open(file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
                
            # 尝试提取纯文本
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                text_content = soup.get_text(separator='\n')
            except ImportError:
                # 如果没有BeautifulSoup，使用简单替换
                import re
                text_content = re.sub(r'<[^>]*>', ' ', html_content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                
            # 更新上下文
            context['text_content'] = text_content
            
            logger.info(f"HTML文档处理完成: {file_path}")
            
        except Exception as e:
            logger.error(f"HTML处理失败: {str(e)}")
            raise
            
        return context 