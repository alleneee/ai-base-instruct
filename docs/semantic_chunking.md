# 语义分块策略指南

本文档介绍了企业知识库平台中的语义分块策略，该功能可以显著提高文档检索质量。

## 功能特点

* **智能边界识别**：自动识别文档中的语义边界，如标题、段落、列表、代码块等
* **上下文保留**：在分块时保留必要的上下文信息，提高检索相关性
* **结构感知**：尊重文档原有结构，避免破坏语义完整性
* **多语言支持**：支持中文和英文等多种语言的语义分块

## 分块策略类型

### 增强语义分块

增强语义分块器能够识别多种语义边界，并根据边界的重要性决定分块位置。它支持以下边界类型：

1. **标题边界**：识别Markdown和HTML标题，根据标题级别赋予不同的重要性
2. **段落边界**：识别段落分隔符，保持段落的完整性
3. **列表边界**：识别列表项，避免在列表中间分块
4. **代码块边界**：识别代码块，保持代码的完整性
5. **表格边界**：识别表格，避免破坏表格结构
6. **引用边界**：识别引用块，保持引用的完整性
7. **水平线边界**：识别水平分隔线，作为章节分隔符
8. **句子边界**：识别句子结束符，在必要时在句子边界分块

### 层次化分块

层次化分块器基于文档的层次结构进行分块，特别适合具有明确标题层次的文档：

1. **保留层次结构**：根据标题层次构建文档结构树
2. **层次元数据**：在节点元数据中包含层次信息，如面包屑路径
3. **智能合并**：根据内容相关性合并小段落

## 配置选项

在`settings.py`中添加了以下配置选项：

```python
# 语义分块配置
SEMANTIC_CHUNKING_ENABLED: bool = Field(default=True)
SEMANTIC_CHUNKING_TYPE: str = Field(default="hierarchical")  # semantic, hierarchical
SEMANTIC_RESPECT_MARKDOWN: bool = Field(default=True)
```

## 使用方法

### 基本用法

```python
from enterprise_kb.core.enhanced_semantic_chunking import create_enhanced_chunker
from llama_index.core import Document

# 创建增强语义分块器
chunker = create_enhanced_chunker(
    chunk_size=1024,
    chunk_overlap=20,
    chunking_type="semantic"
)

# 处理文档
document = Document(text="文档内容...", metadata={"file_type": ".md"})
nodes = chunker.get_nodes_from_documents([document])
```

### 使用层次化分块

```python
# 创建层次化分块器
chunker = create_enhanced_chunker(
    chunk_size=1024,
    chunk_overlap=20,
    chunking_type="hierarchical"
)

# 处理文档
document = Document(text="文档内容...", metadata={"file_type": ".md"})
nodes = chunker.get_nodes_from_documents([document])
```

### 自定义增强语义分块器

```python
from enterprise_kb.core.enhanced_semantic_chunking import EnhancedSemanticChunker, SemanticBoundary

# 自定义边界重要性
boundary_importance = {
    SemanticBoundary.HEADING: 1.0,
    SemanticBoundary.PARAGRAPH: 0.8,
    SemanticBoundary.LIST_ITEM: 0.7,
    SemanticBoundary.CODE_BLOCK: 1.0,
    SemanticBoundary.TABLE: 1.0,
    SemanticBoundary.QUOTE: 0.8,
    SemanticBoundary.HORIZONTAL_RULE: 0.9,
    SemanticBoundary.SENTENCE: 0.5,
    SemanticBoundary.SECTION_BREAK: 1.0
}

# 创建自定义分块器
chunker = EnhancedSemanticChunker(
    chunk_size=1024,
    chunk_overlap=50,
    context_window=200,
    preserve_boundary_content=True,
    respect_document_structure=True,
    boundary_importance=boundary_importance,
    language="chinese"
)
```

## 性能优化建议

1. **调整块大小**：根据文档类型和检索需求调整块大小
2. **增加上下文窗口**：对于需要更多上下文的应用，增加上下文窗口大小
3. **调整边界重要性**：根据文档特点调整不同边界类型的重要性
4. **选择合适的分块策略**：对于结构化文档使用层次化分块，对于一般文档使用增强语义分块

## 示例场景

### 处理技术文档

技术文档通常包含大量的代码块、表格和列表，使用增强语义分块可以保持这些结构的完整性：

```python
chunker = create_enhanced_chunker(
    chunk_size=1500,  # 使用较大的块大小
    chunk_overlap=100,  # 增加重叠以保持上下文
    chunking_type="semantic"
)
```

### 处理学术论文

学术论文通常具有明确的章节结构，使用层次化分块可以保留这种结构：

```python
chunker = create_enhanced_chunker(
    chunk_size=1024,
    chunk_overlap=50,
    chunking_type="hierarchical"
)
```

### 处理中文文档

中文文档的句子边界识别需要特殊处理：

```python
chunker = EnhancedSemanticChunker(
    chunk_size=1024,
    chunk_overlap=20,
    language="chinese"
)
```

## 故障排除

1. **分块不当**：如果发现分块位置不合理，尝试调整边界重要性权重
2. **上下文丢失**：增加上下文窗口大小和块重叠大小
3. **处理速度慢**：减小块大小或禁用某些不必要的边界类型识别
4. **特殊格式处理错误**：确保`respect_document_structure`设置为`True`
