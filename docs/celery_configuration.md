# Celery配置指南

本文档介绍了企业知识库平台中的Celery配置，用于处理异步任务。

## 统一配置

为了消除混淆，我们统一了Celery配置，将之前分散在多个文件中的配置整合到一个文件中：`enterprise_kb/core/unified_celery.py`。

## 主要功能

* **统一配置**：所有Celery配置集中在一个文件中，避免冲突和混淆
* **队列分离**：根据任务类型分离队列，提高处理效率
* **任务路由**：自动将任务路由到合适的队列
* **错误处理**：统一的错误处理和日志记录
* **监控支持**：支持Flower等监控工具

## 队列设计

系统使用以下队列处理不同类型的任务：

1. **default**：默认队列，处理一般任务
2. **document_processing**：文档处理队列，处理文档解析和处理任务
3. **document_indexing**：文档索引队列，处理文档索引任务
4. **document_splitting**：文档分割队列，处理大型文档的分割任务
5. **document_segment**：文档段处理队列，处理文档段的处理任务
6. **document_merging**：文档合并队列，处理文档段的合并任务
7. **index**：索引队列，处理索引优化和管理任务
8. **priority**：优先级队列，处理高优先级任务

## 使用方法

### 在代码中使用Celery

```python
from enterprise_kb.core.unified_celery import get_celery_app

# 获取Celery应用实例
celery_app = get_celery_app()

# 创建任务
@celery_app.task(bind=True)
def my_task(self, arg1, arg2):
    """自定义任务"""
    # 任务实现
    return {"status": "success", "result": arg1 + arg2}

# 调用任务
result = my_task.delay(1, 2)
task_id = result.id
```

### 定义任务路由

任务路由已在统一配置中定义，但如果需要添加新的路由，可以修改`unified_celery.py`中的`task_routes`字典：

```python
task_routes = {
    # 现有路由...
    
    # 添加新路由
    'your_module.your_tasks.*': {
        'queue': 'your_queue',
        'routing_key': 'your.routing.key'
    },
}
```

### 启动Celery Worker

使用以下命令启动Celery worker：

```bash
# 启动所有队列的worker
celery -A enterprise_kb.core.unified_celery worker -Q default,document_processing,document_splitting,document_segment,document_merging,index,priority -l info

# 启动特定队列的worker
celery -A enterprise_kb.core.unified_celery worker -Q document_processing,document_splitting -l info
```

### 启动Celery Beat

使用以下命令启动Celery beat（定时任务调度器）：

```bash
celery -A enterprise_kb.core.unified_celery beat -l info
```

### 启动Flower监控

使用以下命令启动Flower监控：

```bash
celery -A enterprise_kb.core.unified_celery flower --port=5555
```

## 配置选项

在`settings.py`中添加了以下配置选项：

```python
# Celery配置
CELERY_BROKER_URL: str = Field(default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND: str = Field(default="redis://localhost:6379/0")
CELERY_ALWAYS_EAGER: bool = Field(default=False)  # 设置为True时会同步执行任务，便于调试
CELERY_TASK_TIME_LIMIT: int = Field(default=3600)  # 任务硬时间限制（秒）
CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=3300)  # 任务软时间限制（秒）
CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(default=200)  # 每个worker子进程处理的最大任务数
CELERY_WORKER_PREFETCH_MULTIPLIER: int = Field(default=4)  # worker预取任务数乘数
CELERY_TASK_ACKS_LATE: bool = Field(default=True)  # 任务完成后再确认
CELERY_RESULT_EXPIRES: int = Field(default=86400 * 7)  # 结果过期时间（秒）
CELERY_WORKER_CONCURRENCY: int = Field(default=None)  # worker并发数，None表示使用CPU核心数
```

## 任务类型

系统中的主要任务类型包括：

### 文档处理任务

处理文档的上传、解析和处理：

```python
# 处理单个文档
result = process_document_task.delay(doc_id, file_path, metadata)

# 批量处理文档
result = batch_process_documents_task.delay(doc_ids, file_paths, metadata)
```

### 文档分段处理任务

处理大型文档的分段处理：

```python
# 分割文档
result = split_document.delay(doc_id, file_path, metadata)

# 处理文档段
result = process_segment.delay(segment_id, segment_text, metadata)

# 合并结果
result = merge_results.delay(doc_id, segment_results)
```

### 文档块处理任务

处理文档块的并行处理：

```python
# 处理文本块
result = process_text_chunk.delay(text, metadata)

# 处理文本并分块
result = process_text_with_chunking.delay(text, metadata, chunk_size, chunk_overlap)
```

### 索引任务

处理索引的优化和管理：

```python
# 优化索引
result = optimize_index.delay(index_name)

# 重建索引
result = rebuild_index.delay(index_name)
```

## 错误处理

所有任务都继承自自定义的`BaseTask`类，该类提供了统一的错误处理和日志记录：

```python
class BaseTask(celery_app.Task):
    """自定义任务基类，添加错误处理和日志记录"""
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """任务失败时的处理"""
        logger.error(f"任务 {self.name}[{task_id}] 失败: {exc}", exc_info=einfo)
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    # 其他处理方法...
```

## 最佳实践

1. **使用任务绑定**：使用`bind=True`参数绑定任务，以便在任务中访问任务实例
2. **设置重试**：对可能失败的任务设置重试参数
3. **使用任务状态更新**：使用`self.update_state()`更新任务状态
4. **合理设置超时**：根据任务复杂度设置合理的超时时间
5. **使用任务队列**：将不同类型的任务路由到不同的队列
6. **监控任务执行**：使用Flower监控任务执行情况

## 故障排除

1. **任务不执行**：检查worker是否启动，队列是否正确
2. **任务执行失败**：检查日志，查看错误信息
3. **任务执行缓慢**：检查worker并发数，考虑增加worker数量
4. **任务结果丢失**：检查结果后端配置，可能是结果过期时间设置过短
