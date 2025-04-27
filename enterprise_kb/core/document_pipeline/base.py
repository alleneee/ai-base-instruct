"""文档处理管道基础模块，定义文档处理器基类和处理管道"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Type, Optional

class DocumentProcessor(ABC):
    """文档处理器基类"""
    
    # 每个处理器子类应该定义其支持的文件类型
    SUPPORTED_TYPES = []
    
    @abstractmethod
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理文档的抽象方法
        
        Args:
            context: 处理上下文，包含文档信息和中间处理结果
            
        Returns:
            更新后的处理上下文
        """
        pass
    
    @classmethod
    def supports_file_type(cls, file_type: str) -> bool:
        """
        判断处理器是否支持该文件类型
        
        Args:
            file_type: 文件类型
            
        Returns:
            是否支持
        """
        return file_type.lower() in cls.SUPPORTED_TYPES
        
class DocumentPipeline:
    """文档处理管道，管理处理器链"""
    
    def __init__(self):
        self.processors: List[DocumentProcessor] = []
        
    def add_processor(self, processor: DocumentProcessor) -> 'DocumentPipeline':
        """
        添加处理器到管道
        
        Args:
            processor: 处理器实例
            
        Returns:
            处理管道自身，支持链式调用
        """
        self.processors.append(processor)
        return self
        
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        按顺序执行管道中的处理器
        
        Args:
            context: 初始处理上下文
            
        Returns:
            最终处理结果
        """
        for processor in self.processors:
            context = processor.process(context)
        return context
        
class PipelineFactory:
    """处理管道工厂，根据文件类型创建合适的处理管道"""
    
    _processors: Dict[str, Type[DocumentProcessor]] = {}
    
    @classmethod
    def register_processor(cls, processor_class: Type[DocumentProcessor]):
        """
        注册处理器类
        
        Args:
            processor_class: 处理器类
            
        Returns:
            处理器类，支持作为装饰器使用
        """
        cls._processors[processor_class.__name__] = processor_class
        return processor_class
    
    @classmethod
    def create_pipeline(cls, file_type: str, custom_processors: Optional[List[str]] = None) -> DocumentPipeline:
        """
        创建处理管道
        
        Args:
            file_type: 文件类型
            custom_processors: 自定义处理器列表，如果提供则按顺序使用这些处理器
            
        Returns:
            配置好的处理管道
        """
        pipeline = DocumentPipeline()
        
        # 如果指定了自定义处理器，按顺序添加
        if custom_processors:
            for processor_name in custom_processors:
                if processor_name in cls._processors:
                    pipeline.add_processor(cls._processors[processor_name]())
            return pipeline
        
        # 否则，添加支持该文件类型的所有处理器
        for processor_class in cls._processors.values():
            if processor_class.supports_file_type(file_type):
                pipeline.add_processor(processor_class())
                
        return pipeline 