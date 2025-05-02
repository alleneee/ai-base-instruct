"""
增强文档处理示例

本模块展示如何使用增强的文档处理功能，包括:
1. 文档结构感知分块
2. 并行文档处理
3. 增量文档更新
4. 上下文压缩
5. 元数据感知分块
"""

import os
import asyncio
import logging
from typing import List, Dict, Any
from pprint import pprint

from enterprise_kb.core.document_pipeline.base import PipelineFactory
from enterprise_kb.core.document_pipeline.processors import (
    FileValidator,
    MarkItDownProcessor,
    PDFProcessor,
    DocxProcessor,
    MarkdownProcessor,
    TextProcessor,
    ChunkingProcessor,
    VectorizationProcessor,
    ParallelProcessor,
    AsyncDocumentPipeline,
    IncrementalChunkingProcessor,
    ContextCompressorProcessor,
    MetadataAwareChunkingProcessor,
)

# 配置日志
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class AdvancedDocumentProcessingDemo:
    """增强文档处理的演示类"""
    
    def __init__(self, data_dir="./data"):
        """
        初始化演示
        
        Args:
            data_dir: 数据目录
        """
        self.data_dir = data_dir
        
        # 确保目录存在
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """确保所需目录存在"""
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)
            
        uploads_dir = os.path.join(self.data_dir, "uploads")
        if not os.path.exists(uploads_dir):
            os.makedirs(uploads_dir)
            
        processed_dir = os.path.join(self.data_dir, "processed")
        if not os.path.exists(processed_dir):
            os.makedirs(processed_dir)
    
    def create_standard_pipeline(self):
        """创建标准文档处理管道"""
        processors = [
            FileValidator(),
            MarkItDownProcessor(),
            PDFProcessor(),
            DocxProcessor(),
            MarkdownProcessor(),
            TextProcessor(),
            ChunkingProcessor(),  # 使用标准分块处理器
            VectorizationProcessor(),
        ]
        
        return processors
    
    def create_enhanced_pipeline(self):
        """创建增强的文档处理管道"""
        processors = [
            FileValidator(),
            MarkItDownProcessor(),
            PDFProcessor(),
            DocxProcessor(),
            MarkdownProcessor(),
            TextProcessor(),
            IncrementalChunkingProcessor(),  # 使用增强分块处理器
            VectorizationProcessor(),
        ]
        
        return processors
    
    def create_metadata_aware_pipeline(self):
        """创建元数据感知的处理管道"""
        processors = [
            FileValidator(),
            MarkItDownProcessor(),
            PDFProcessor(),
            DocxProcessor(),
            MarkdownProcessor(),
            TextProcessor(),
            MetadataAwareChunkingProcessor(),  # 使用元数据感知分块处理器
            VectorizationProcessor(),
        ]
        
        return processors
    
    def process_single_document(self, file_path: str) -> Dict[str, Any]:
        """
        处理单个文档
        
        Args:
            file_path: 文件路径
            
        Returns:
            处理结果
        """
        # 创建管道
        processors = self.create_enhanced_pipeline()
        
        # 提取文件类型
        _, ext = os.path.splitext(file_path)
        file_type = ext.lstrip('.').lower()
        
        # 创建初始上下文
        context = {
            'file_path': file_path,
            'file_type': file_type,
            'metadata': {
                'filename': os.path.basename(file_path)
            }
        }
        
        # 依次应用每个处理器
        for processor in processors:
            context = processor.process(context)
        
        return context
    
    async def process_multiple_documents(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        """
        并行处理多个文档
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            处理结果列表
        """
        # 创建异步处理管道
        processors = self.create_enhanced_pipeline()
        pipeline = AsyncDocumentPipeline(processors, max_workers=4)
        
        # 并行处理
        results = await pipeline.process_documents(file_paths)
        
        return results
    
    def process_incremental_update(self, file_path: str, old_content: str) -> Dict[str, Any]:
        """
        增量更新文档
        
        Args:
            file_path: 文件路径
            old_content: 旧文档内容
            
        Returns:
            处理结果
        """
        # 创建增强管道
        processors = self.create_enhanced_pipeline()
        
        # 提取文件类型
        _, ext = os.path.splitext(file_path)
        file_type = ext.lstrip('.').lower()
        
        # 读取新内容
        with open(file_path, 'r', encoding='utf-8') as f:
            new_content = f.read()
        
        # 创建初始上下文
        context = {
            'file_path': file_path,
            'file_type': file_type,
            'text_content': new_content,
            'old_content': old_content,
            'incremental_update': True,
            'metadata': {
                'filename': os.path.basename(file_path)
            }
        }
        
        # 依次应用每个处理器
        for processor in processors:
            context = processor.process(context)
        
        return context
    
    def process_with_metadata_extraction(self, file_path: str) -> Dict[str, Any]:
        """
        处理文档并提取元数据
        
        Args:
            file_path: 文件路径
            
        Returns:
            处理结果
        """
        # 创建元数据感知管道
        processors = self.create_metadata_aware_pipeline()
        
        # 提取文件类型
        _, ext = os.path.splitext(file_path)
        file_type = ext.lstrip('.').lower()
        
        # 创建初始上下文
        context = {
            'file_path': file_path,
            'file_type': file_type,
            'embed_metadata_in_chunks': True,  # 在块中嵌入元数据（用于演示）
            'metadata': {
                'filename': os.path.basename(file_path)
            }
        }
        
        # 依次应用每个处理器
        for processor in processors:
            context = processor.process(context)
        
        return context
    
    def process_with_context_compression(self, file_path: str, query: str) -> Dict[str, Any]:
        """
        处理文档并应用上下文压缩
        
        Args:
            file_path: 文件路径
            query: 查询内容，用于压缩上下文
            
        Returns:
            处理结果
        """
        # 创建处理管道
        processors = self.create_enhanced_pipeline()
        
        # 添加上下文压缩处理器
        context_compressor = ContextCompressorProcessor(compression_ratio=0.6)
        
        # 提取文件类型
        _, ext = os.path.splitext(file_path)
        file_type = ext.lstrip('.').lower()
        
        # 创建初始上下文
        context = {
            'file_path': file_path,
            'file_type': file_type,
            'query': query,  # 添加查询
            'metadata': {
                'filename': os.path.basename(file_path)
            }
        }
        
        # 应用基本处理器
        for processor in processors:
            context = processor.process(context)
        
        # 应用上下文压缩
        context = context_compressor.process(context)
        
        return context
    
    def save_processed_result(self, result: Dict[str, Any], output_path: str):
        """
        保存处理结果
        
        Args:
            result: 处理结果
            output_path: 输出路径
        """
        # 提取文档块
        chunks = result.get('chunks', [])
        
        # 保存为Markdown文件
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"# 处理结果: {result.get('metadata', {}).get('filename', '')}\n\n")
            f.write(f"总块数: {len(chunks)}\n\n")
            
            # 文档信息
            f.write("## 文档信息\n\n")
            f.write(f"- 文件类型: {result.get('file_type', '')}\n")
            f.write(f"- 文件大小: {result.get('file_size', 0)} 字节\n")
            
            # 处理模式信息
            processing_modes = []
            if result.get('incremental_processed'):
                processing_modes.append('增量更新')
            if result.get('metadata_enhanced'):
                processing_modes.append('元数据增强')
            if result.get('compression_applied'):
                processing_modes.append(f'上下文压缩 (压缩率: {result.get("compression_ratio", 0)})')
            
            if processing_modes:
                f.write(f"- 处理模式: {', '.join(processing_modes)}\n")
            else:
                f.write(f"- 处理模式: 标准处理\n")
            
            # 元数据信息
            if 'chunk_metadata' in result:
                f.write("\n## 元数据摘要\n\n")
                
                # 提取和合并所有块的关键词
                all_keywords = set()
                all_entities = set()
                all_topics = set()
                
                for metadata in result['chunk_metadata']:
                    if 'keywords' in metadata:
                        all_keywords.update(metadata['keywords'])
                    if 'entities' in metadata:
                        all_entities.update(metadata['entities'])
                    if 'topic_areas' in metadata:
                        all_topics.update(metadata['topic_areas'])
                
                if all_keywords:
                    f.write(f"- 关键词: {', '.join(list(all_keywords)[:20])}\n")
                if all_entities:
                    f.write(f"- 实体: {', '.join(list(all_entities)[:20])}\n")
                if all_topics:
                    f.write(f"- 主题领域: {', '.join(all_topics)}\n")
            
            # 文档块
            f.write("\n## 文档块\n\n")
            for i, chunk in enumerate(chunks):
                f.write(f"### 块 {i+1}\n\n")
                f.write("```\n")
                f.write(chunk[:200] + ("..." if len(chunk) > 200 else ""))  # 限制显示长度
                f.write("\n```\n\n")
                
                # 如果有压缩，显示原始块
                if result.get('compression_applied') and 'original_chunks' in result:
                    f.write("原始块内容：\n")
                    f.write("```\n")
                    original_chunk = result['original_chunks'][i] if i < len(result['original_chunks']) else ""
                    f.write(original_chunk[:100] + ("..." if len(original_chunk) > 100 else ""))
                    f.write("\n```\n\n")
                
                # 如果有块级元数据，显示
                if 'chunk_metadata' in result and i < len(result['chunk_metadata']):
                    metadata = result['chunk_metadata'][i]
                    f.write("块级元数据：\n")
                    f.write(f"- 关键词: {', '.join(metadata.get('keywords', [])[:10])}\n")
                    f.write(f"- 实体: {', '.join(metadata.get('entities', [])[:5])}\n")
                    f.write(f"- 主题: {', '.join(metadata.get('topic_areas', []))}\n\n")


# 使用示例
async def main():
    # 创建演示实例
    demo = AdvancedDocumentProcessingDemo()
    
    # 示例文件路径 (请替换为实际文件)
    markdown_file = "./data/uploads/sample.md"  # 示例Markdown文件
    pdf_file = "./data/uploads/sample.pdf"  # 示例PDF文件
    docx_file = "./data/uploads/sample.docx"  # 示例Word文件
    
    # 示例1: 处理单个文档
    logger.info("示例1: 处理单个文档")
    if os.path.exists(markdown_file):
        result = demo.process_single_document(markdown_file)
        demo.save_processed_result(
            result, 
            os.path.join("./data/processed", "single_result.md")
        )
        logger.info(f"已处理文档，生成了 {result.get('chunk_count', 0)} 个块")
    else:
        logger.warning(f"文件不存在: {markdown_file}")
    
    # 示例2: 并行处理多个文档
    logger.info("示例2: 并行处理多个文档")
    file_list = [f for f in [markdown_file, pdf_file, docx_file] if os.path.exists(f)]
    if file_list:
        results = await demo.process_multiple_documents(file_list)
        for i, result in enumerate(results):
            demo.save_processed_result(
                result,
                os.path.join("./data/processed", f"parallel_result_{i+1}.md")
            )
        logger.info(f"已并行处理 {len(results)} 个文档")
    else:
        logger.warning("没有找到可处理的文件")
    
    # 示例3: 增量更新文档
    logger.info("示例3: 增量更新文档")
    if os.path.exists(markdown_file):
        # 读取旧内容
        with open(markdown_file, 'r', encoding='utf-8') as f:
            old_content = f.read()
        
        # 模拟更新文件内容
        new_content = old_content + "\n\n## 新添加的部分\n\n这是新添加的内容，只有这部分会被重新处理。\n"
        with open(markdown_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        # 进行增量处理
        result = demo.process_incremental_update(markdown_file, old_content)
        demo.save_processed_result(
            result,
            os.path.join("./data/processed", "incremental_result.md")
        )
        logger.info(f"已增量处理文档，生成了 {result.get('chunk_count', 0)} 个块")
    else:
        logger.warning(f"文件不存在: {markdown_file}")
    
    # 示例4: 元数据感知分块
    logger.info("示例4: 元数据感知分块")
    if os.path.exists(markdown_file):
        result = demo.process_with_metadata_extraction(markdown_file)
        demo.save_processed_result(
            result,
            os.path.join("./data/processed", "metadata_result.md")
        )
        logger.info(f"已处理文档并提取元数据，生成了 {len(result.get('chunks', []))} 个块")
    else:
        logger.warning(f"文件不存在: {markdown_file}")
    
    # 示例5: 上下文压缩
    logger.info("示例5: 上下文压缩")
    if os.path.exists(markdown_file):
        # 使用示例查询
        query = "如何进行文档处理和分块"
        
        result = demo.process_with_context_compression(markdown_file, query)
        demo.save_processed_result(
            result,
            os.path.join("./data/processed", "compressed_result.md")
        )
        logger.info(f"已处理文档并应用上下文压缩，压缩后块数: {len(result.get('chunks', []))}")
    else:
        logger.warning(f"文件不存在: {markdown_file}")


if __name__ == "__main__":
    asyncio.run(main()) 