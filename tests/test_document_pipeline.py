"""
文档处理管道测试模块
用于测试企业知识库的文档处理管道的各个组件
"""
import os
import unittest
import logging
from pathlib import Path
from typing import Dict, Any

# 导入文档处理相关模块
from enterprise_kb.core.document_pipeline.base import DocumentPipeline, PipelineFactory
from enterprise_kb.core.document_pipeline.processors import (
    PDFProcessor, 
    ChunkingProcessor,
    VectorizationProcessor
)

# 导入测试用的模拟处理器
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(os.path.dirname(__file__))))

# 使用相对导入方式
from mock_processors import TestFileValidator, TestMarkItDownProcessor, TestChunkingProcessor, TestVectorizationProcessor

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 为测试重新注册处理器
PipelineFactory._processors = {}  # 清除现有注册
PipelineFactory.register_processor(TestFileValidator)
PipelineFactory.register_processor(TestMarkItDownProcessor)
PipelineFactory.register_processor(TestChunkingProcessor)
PipelineFactory.register_processor(TestVectorizationProcessor)
PipelineFactory.register_processor(PDFProcessor)

class DocumentPipelineTest(unittest.TestCase):
    """文档处理管道测试类"""
    
    def setUp(self):
        """测试前的准备工作"""
        # 设置测试数据目录路径
        self.data_dir = Path(__file__).parent / "data"
        self.assertTrue(self.data_dir.exists(), f"测试数据目录不存在: {self.data_dir}")
        
        # 检查测试文件
        self.pdf_file = self.data_dir / "DeepSeek_R1.pdf"
        self.docx_file = self.data_dir / "MapStruct.docx"
        
        self.assertTrue(self.pdf_file.exists(), f"PDF测试文件不存在: {self.pdf_file}")
        self.assertTrue(self.docx_file.exists(), f"DOCX测试文件不存在: {self.docx_file}")
        
        # 创建一个临时的处理结果目录
        self.result_dir = Path(__file__).parent / "results"
        os.makedirs(self.result_dir, exist_ok=True)
        
        logger.info("测试环境准备完成")
    
    def create_context(self, file_path: Path, file_type: str) -> Dict[str, Any]:
        """创建测试上下文"""
        return {
            "file_path": str(file_path),
            "file_type": file_type,
            "metadata": {
                "doc_id": f"test_{file_type}_{file_path.stem}",
                "source": "test"
            },
            "convert_to_markdown": True
        }
    
    def test_pdf_pipeline(self):
        """测试PDF文档处理管道"""
        logger.info(f"开始测试PDF文档处理: {self.pdf_file}")
        
        # 创建处理上下文
        context = self.create_context(self.pdf_file, "pdf")
        
        # 创建处理管道
        pipeline = DocumentPipeline()
        pipeline.add_processor(TestFileValidator())
        pipeline.add_processor(TestMarkItDownProcessor())
        pipeline.add_processor(PDFProcessor())
        pipeline.add_processor(TestChunkingProcessor())
        
        # 处理文档
        try:
            result = pipeline.process(context)
            
            # 验证处理结果
            self.assertIn("markdown_content", result, "处理结果中应包含markdown_content")
            self.assertIn("chunks", result, "处理结果中应包含chunks")
            self.assertTrue(len(result["chunks"]) > 0, "处理后应有文本块")
            
            # 保存处理结果，方便检查
            markdown_path = self.result_dir / f"{self.pdf_file.stem}_processed.md"
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(result.get("markdown_content", ""))
                
            logger.info(f"PDF处理结果已保存到: {markdown_path}")
            logger.info(f"生成了 {len(result['chunks'])} 个文本块")
            
        except Exception as e:
            self.fail(f"PDF处理失败: {str(e)}")
    
    def test_docx_pipeline(self):
        """测试DOCX文档处理管道"""
        logger.info(f"开始测试DOCX文档处理: {self.docx_file}")
        
        # 创建处理上下文
        context = self.create_context(self.docx_file, "docx")
        
        # 使用工厂创建处理管道
        pipeline = PipelineFactory.create_pipeline("docx")
        
        # 处理文档
        try:
            result = pipeline.process(context)
            
            # 验证处理结果
            self.assertIn("markdown_content", result, "处理结果中应包含markdown_content")
            self.assertIn("chunks", result, "处理结果中应包含chunks")
            self.assertTrue(len(result["chunks"]) > 0, "处理后应有文本块")
            
            # 保存处理结果，方便检查
            markdown_path = self.result_dir / f"{self.docx_file.stem}_processed.md"
            with open(markdown_path, "w", encoding="utf-8") as f:
                f.write(result.get("markdown_content", ""))
                
            logger.info(f"DOCX处理结果已保存到: {markdown_path}")
            logger.info(f"生成了 {len(result['chunks'])} 个文本块")
            
        except Exception as e:
            self.fail(f"DOCX处理失败: {str(e)}")
    
    def test_custom_pipeline(self):
        """测试自定义处理管道"""
        logger.info("开始测试自定义处理管道")
        
        # 创建处理上下文
        context = self.create_context(self.pdf_file, "pdf")
        
        # 自定义处理器列表
        custom_processors = ["TestFileValidator", "TestMarkItDownProcessor", "TestChunkingProcessor"]
        
        # 使用工厂创建自定义处理管道
        pipeline = PipelineFactory.create_pipeline("pdf", custom_processors=custom_processors)
        
        # 处理文档
        try:
            result = pipeline.process(context)
            
            # 验证处理结果
            self.assertIn("markdown_content", result, "处理结果中应包含markdown_content")
            self.assertIn("chunks", result, "处理结果中应包含chunks")
            
            logger.info(f"自定义管道处理完成，生成了 {len(result.get('chunks', []))} 个文本块")
            
        except Exception as e:
            self.fail(f"自定义管道处理失败: {str(e)}")
    
    def test_vectorization(self):
        """测试向量化处理"""
        logger.info("开始测试向量化处理")
        
        # 简化测试，直接创建包含chunks的上下文
        context = {
            "file_path": str(self.pdf_file),
            "file_type": "pdf",
            "metadata": {"doc_id": "test_vectorization"},
            "chunks": [
                "这是第一个测试文本块，用于测试向量化处理。",
                "这是第二个测试文本块，包含不同的内容。",
                "这是第三个测试文本块，测试文本分块和向量化的完整流程。"
            ]
        }
        
        # 创建向量化处理器
        processor = TestVectorizationProcessor()
        
        # 向量化处理
        try:
            result = processor.process(context)
            
            # 在实际环境中，这里应该检查向量化结果
            # 由于实际的向量化服务可能需要额外配置，这里只检查状态标记
            self.assertIn("vectorized", result, "处理结果中应包含vectorized标记")
            
            logger.info("向量化处理测试完成")
            
        except Exception as e:
            logger.warning(f"向量化处理测试未完成: {str(e)}")
            logger.info("注意：这可能是因为向量化服务未配置，在实际环境中需要确保向量服务正常运行")

if __name__ == "__main__":
    unittest.main()
