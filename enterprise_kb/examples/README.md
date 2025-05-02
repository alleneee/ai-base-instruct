# 企业知识库文档处理增强功能

本目录包含企业知识库文档处理系统的增强功能示例，展示了如何使用高级文档结构感知分块、并行处理和增量更新功能。

## 增强功能概述

主要增强功能包括：

### 1. 文档结构感知分块

- **递归重叠分块**：智能识别文档中的段落、句子和语义边界，确保分块更加合理
- **结构识别与保留**：识别代码块、表格、列表等特殊结构，保持其完整性
- **引用关系追踪**：识别并解析文档内部的引用关系，在分块时保持引用的上下文
- **多层级处理**：按照文档层级结构递归处理，保持层级信息

### 2. 并行文档处理

- **异步并行处理**：支持多文档并行处理，提高处理效率
- **处理器池**：创建处理器实例池，避免重复初始化开销
- **自动线程管理**：根据系统资源自动调整并行度

### 3. 增量文档更新

- **差异比较**：比较新旧文档内容，仅处理变更部分
- **上下文保留**：保留变更部分周围的上下文，确保语义连贯
- **智能分块**：对变更部分应用结构感知分块

### 4. 上下文压缩（新增）

- **动态压缩**：根据查询内容动态调整文本块的大小
- **相关性分数**：基于相关性分数决定压缩程度，保留高相关内容
- **核心句提取**：从长文本中提取与查询相关的核心句子
- **智能摘要**：对低相关性内容生成摘要，减少上下文长度

### 5. 元数据感知分块（新增）

- **自动元数据提取**：从文档内容中提取关键词、实体、主题等元数据
- **多维度分析**：对文档进行多维度分析，识别主题领域
- **时间引用识别**：检测和标记文档中的时间引用
- **结构元数据关联**：将元数据与文档结构（标题、图片、代码块等）关联

## 如何使用

### 安装依赖

```bash
pip install -r requirements.txt
```

### 运行示例

```bash
# 进入项目根目录
cd enterprise_kb

# 运行示例脚本
python -m examples.advanced_document_processing
```

### 示例代码

#### 基本用法

```python
# 创建增强的处理管道
processors = [
    FileValidator(),
    MarkItDownProcessor(),
    # ... 其他处理器
    IncrementalChunkingProcessor(),  # 使用增强分块处理器
    VectorizationProcessor(),
]

# 并行处理多个文档
async def process_documents(file_list):
    pipeline = AsyncDocumentPipeline(processors, max_workers=4)
    results = await pipeline.process_documents(file_list)
    return results

# 增量更新文档
def update_document(file_path, old_content):
    # 读取新内容
    with open(file_path, 'r') as f:
        new_content = f.read()
    
    # 创建上下文
    context = {
        'file_path': file_path,
        'file_type': 'md',
        'text_content': new_content,
        'old_content': old_content,
        'incremental_update': True
    }
    
    # 处理
    for processor in processors:
        context = processor.process(context)
    
    return context
```

#### 使用上下文压缩（新增）

```python
# 创建处理管道
processors = [
    FileValidator(),
    MarkItDownProcessor(),
    # ... 其他处理器
    ChunkingProcessor(),
]

# 添加上下文压缩处理器
context_compressor = ContextCompressorProcessor(
    compression_ratio=0.7  # 压缩比例
)

# 处理文档
def process_with_compression(file_path, query):
    # 创建上下文
    context = {
        'file_path': file_path,
        'file_type': 'md',
        'query': query  # 提供查询以进行压缩
    }
    
    # 基本处理
    for processor in processors:
        context = processor.process(context)
    
    # 应用上下文压缩
    context = context_compressor.process(context)
    
    return context
```

#### 使用元数据感知分块（新增）

```python
# 创建元数据感知处理管道
processors = [
    FileValidator(),
    MarkItDownProcessor(),
    # ... 其他处理器
    MetadataAwareChunkingProcessor(),  # 元数据感知分块处理器
    VectorizationProcessor()
]

# 处理文档并提取元数据
def process_with_metadata(file_path):
    # 创建上下文
    context = {
        'file_path': file_path,
        'file_type': 'md',
        'embed_metadata_in_chunks': True  # 可选：在块内容中嵌入元数据
    }
    
    # 处理
    for processor in processors:
        context = processor.process(context)
    
    # 获取处理结果和元数据
    chunks = context['chunks']
    chunk_metadata = context['chunk_metadata']  # 每个块的元数据
    
    return context
```

## 文件说明

- `advanced_document_processing.py`: 增强文档处理的示例实现和使用方法
- `processors.py`: 核心处理器实现 (位于 `enterprise_kb/core/document_pipeline/` 目录)

## 配置参数

可以在 `settings.py` 中调整以下参数：

- `MAX_CHUNK_SIZE`: 最大块大小
- `PARALLEL_WORKERS`: 并行处理的工作线程数
- `OVERLAP_SIZE`: 块重叠大小
- `COMPRESSION_RATIO`: 默认压缩比例
- `METADATA_EXTRACTION_ENABLED`: 是否启用元数据提取

## 高级使用

### 自定义元数据提取（新增）

可以自定义元数据提取逻辑，以适应特定领域的需求：

```python
class CustomMetadataAwareChunkingProcessor(MetadataAwareChunkingProcessor):
    def _extract_metadata_from_content(self, content):
        # 调用父类方法获取基本元数据
        metadata = super()._extract_metadata_from_content(content)
        
        # 添加领域特定的元数据提取
        metadata['custom_field'] = self._extract_custom_field(content)
        
        return metadata
        
    def _extract_custom_field(self, text):
        # 实现领域特定的提取逻辑
        pass
```

### 自定义上下文压缩（新增）

可以自定义上下文压缩策略，以适应不同的应用场景：

```python
class CustomContextCompressor(ContextCompressorProcessor):
    def _compress_context(self, chunks, query):
        # 实现自定义压缩逻辑
        compressed_chunks = []
        
        # 例如：基于特定领域知识进行压缩
        for chunk in chunks:
            if self._is_domain_relevant(chunk, query):
                compressed_chunks.append(chunk)
                
        return compressed_chunks
        
    def _is_domain_relevant(self, text, query):
        # 实现领域相关性判断
        pass
```
