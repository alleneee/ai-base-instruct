# document_tasks 迁移指南

本文档提供了从 `enterprise_kb.tasks.document_tasks` 迁移到 `enterprise_kb.tasks.document_tasks_v2` 的详细步骤和指导。

## 背景

`document_tasks.py` 是早期版本中的文档处理任务模块。随着系统演进，我们开发了更强大、功能更丰富的 `document_tasks_v2.py` 来替代它。
新版本包含了多项改进，包括更好的任务追踪、大型文档处理、递归Markdown分块等高级功能。

## 迁移时间表

1. **当前阶段**: 弃用警告 - 旧模块会发出警告但仍然可用
2. **下一版本**: 运行时警告 - 使用旧模块会发出警告并记录日志  
3. **未来版本**: 完全移除 - 旧模块将被删除

## 函数对应关系

| 旧函数 | 新函数 | 主要区别 |
|--------|--------|---------|
| `process_document_task` | `process_document_task` | 新增参数: `use_parallel`, `use_semantic_chunking`, `use_incremental`, `chunking_type` |
| `batch_process_documents_task` | `batch_process_documents_task` | 新增参数: `use_parallel`, `use_semantic_chunking`, `use_incremental`, `chunking_type`, `max_concurrent` |
| `cleanup_task` | `cleanup_task` | 参数相同 |
| - | `process_large_document_task` | 新增功能: 专门处理大型文档 |

## 参数变化

### process_document_task

**旧版参数**:

```python
process_document_task(
    file_path, 
    metadata, 
    convert_to_md=None, 
    strategy=None
)
```

**新版参数**:

```python
process_document_task(
    file_path, 
    metadata, 
    datasource_name=None, 
    use_parallel=None, 
    use_semantic_chunking=None, 
    use_incremental=None, 
    chunking_type=None
)
```

### 迁移指南

1. 替换 `convert_to_md` 参数:

   ```python
   # 旧版
   process_document_task(file_path, metadata, convert_to_md=True)
   
   # 新版 
   process_document_task(file_path, metadata, chunking_type="recursive_markdown")
   ```

2. 替换 `strategy` 参数:

   ```python
   # 旧版
   process_document_task(file_path, metadata, strategy={"chunk_size": 500})
   
   # 新版
   process_document_task(file_path, metadata, chunking_type="hierarchical")
   ```

## 示例

### 基本使用

```python
# 旧版
from enterprise_kb.tasks.document_tasks import process_document_task
process_document_task.delay(
    file_path=path,
    metadata=metadata,
    convert_to_md=True
)

# 新版
from enterprise_kb.tasks.document_tasks_v2 import process_document_task
process_document_task.delay(
    file_path=path,
    metadata=metadata,
    chunking_type="recursive_markdown"
)
```

### 高级使用

```python
# 新版 - 处理大型文档
from enterprise_kb.tasks.document_tasks_v2 import process_large_document_task
process_large_document_task.delay(
    file_path=path,
    metadata=metadata,
    chunk_size=1000000,  # 1MB
    chunking_type="hierarchical"
)
```

## 特殊处理

对于Markdown文件，建议使用新版的递归分割功能:

```python
chunking_type = "recursive_markdown" if file_type in ["md", "markdown"] else "hierarchical"
process_document_task.delay(
    file_path=path,
    metadata=metadata,
    chunking_type=chunking_type
)
```

## 完整API接口

请参考 `enterprise_kb/api/celery_tasks_v2.py` 中的API实现，了解新版任务模块的完整用法。
