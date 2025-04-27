# 并行文档处理指南

本文档介绍了企业知识库平台中的并行文档处理功能，该功能可以显著提高大型文档的处理效率。

## 功能特点

* **多策略分块**：支持固定大小、句子边界、段落边界和语义边界四种分块策略
* **分布式处理**：利用Celery实现分布式文档处理，提高处理效率
* **内存优化**：支持流式处理和批处理，减少内存占用
* **自适应并发**：根据系统资源自动调整并发度

## 配置选项

在`settings.py`中添加了以下配置选项：

```python
# 并行处理配置
PARALLEL_PROCESSING_ENABLED: bool = Field(default=True)
PARALLEL_MAX_WORKERS: int = Field(default=None)  # None表示使用CPU核心数
PARALLEL_CHUNK_SIZE: int = Field(default=100000)  # 并行处理的块大小（字符数）
PARALLEL_CHUNK_STRATEGY: str = Field(default="sentence")  # 分块策略：fixed_size, sentence, paragraph, semantic
PARALLEL_USE_DISTRIBUTED: bool = Field(default=False)  # 是否使用分布式处理(Celery)
PARALLEL_MEMORY_EFFICIENT: bool = Field(default=False)  # 是否使用内存高效模式
PARALLEL_BATCH_SIZE: int = Field(default=10)  # 批处理大小，用于内存优化
```

## 使用方法

### 基本用法

```python
from enterprise_kb.core.parallel_processor import get_parallel_processor, ChunkingStrategy
from llama_index.core import Document

# 获取并行处理器
parallel_processor = get_parallel_processor()

# 处理大型文档
document = Document(text="大型文档内容...", metadata={"title": "示例文档"})
nodes = await parallel_processor.process_document_in_chunks(
    document=document,
    processor_func=process_text,
    chunk_size=100000
)
```

### 使用不同的分块策略

```python
# 使用句子边界分块
parallel_processor = get_parallel_processor(
    chunk_strategy=ChunkingStrategy.SENTENCE_BOUNDARY
)

# 使用段落边界分块
parallel_processor = get_parallel_processor(
    chunk_strategy=ChunkingStrategy.PARAGRAPH_BOUNDARY
)

# 使用语义边界分块
parallel_processor = get_parallel_processor(
    chunk_strategy=ChunkingStrategy.SEMANTIC_BOUNDARY
)
```

### 使用分布式处理

```python
# 启用分布式处理
parallel_processor = get_parallel_processor(
    use_distributed=True
)

# 处理大型文档
nodes = await parallel_processor.process_document_in_chunks(
    document=document,
    processor_func=process_text,
    processor_func_name="enterprise_kb.tasks.document_chunk_tasks.process_text_chunk"
)
```

### 使用内存优化模式

```python
# 启用内存优化模式
parallel_processor = get_parallel_processor(
    memory_efficient=True
)

# 处理多个文档
nodes = await parallel_processor.process_multiple_documents(
    documents=documents,
    processor_func=process_document,
    batch_size=5  # 每批处理5个文档
)
```

## 分块策略详解

### 固定大小分块

最简单的分块策略，按照固定字符数分割文档。适用于纯文本文档。

```python
parallel_processor = get_parallel_processor(
    chunk_strategy=ChunkingStrategy.FIXED_SIZE
)
```

### 句子边界分块

在句子边界处分割文档，避免切断句子。适用于大多数文本文档。

```python
parallel_processor = get_parallel_processor(
    chunk_strategy=ChunkingStrategy.SENTENCE_BOUNDARY
)
```

### 段落边界分块

在段落边界处分割文档，保持段落完整性。适用于结构化文档。

```python
parallel_processor = get_parallel_processor(
    chunk_strategy=ChunkingStrategy.PARAGRAPH_BOUNDARY
)
```

### 语义边界分块

在语义边界处分割文档，如标题、列表、代码块等。最适合Markdown和HTML等结构化文档。

```python
parallel_processor = get_parallel_processor(
    chunk_strategy=ChunkingStrategy.SEMANTIC_BOUNDARY
)
```

## 性能优化建议

1. **选择合适的分块策略**：根据文档类型选择合适的分块策略，可以提高处理质量
2. **调整块大小**：对于不同类型的文档，可能需要不同的块大小
3. **启用分布式处理**：对于大型文档集，启用分布式处理可以显著提高处理速度
4. **使用内存优化模式**：处理超大型文档时，启用内存优化模式可以避免内存溢出

## 示例场景

### 处理大型PDF文档

```python
# 获取并行处理器，使用语义边界分块
parallel_processor = get_parallel_processor(
    chunk_strategy=ChunkingStrategy.SEMANTIC_BOUNDARY,
    use_distributed=True
)

# 处理PDF文档
nodes = await parallel_processor.process_document_in_chunks(
    document=pdf_document,
    processor_func=process_pdf_text,
    processor_func_name="enterprise_kb.tasks.document_chunk_tasks.process_text_with_chunking"
)
```

### 批量处理多个文档

```python
# 获取并行处理器，启用内存优化
parallel_processor = get_parallel_processor(
    memory_efficient=True,
    max_workers=4  # 限制并发数
)

# 批量处理文档
nodes = await parallel_processor.process_multiple_documents(
    documents=document_list,
    processor_func=process_document,
    batch_size=10
)
```

## 故障排除

1. **内存错误**：如果遇到内存错误，尝试减小块大小或启用内存优化模式
2. **处理速度慢**：检查是否启用了分布式处理，以及Celery worker是否正常运行
3. **结果不完整**：检查分块策略是否合适，可能需要调整块大小或选择不同的分块策略
