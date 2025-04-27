# Celery 优化方案文档

## 1. 概述

本文档详细介绍了企业知识库平台中 Celery 的优化方案，包括高级任务管理、队列和路由系统、配置优化以及文档分段处理等方面。这些优化旨在提高系统的性能、可靠性和可扩展性，特别是在处理大型文档和批量任务时。

## 2. 高级任务管理和监控

### 2.1 TaskManager 类

我们实现了 `TaskManager` 类，提供以下功能：

- 任务状态跟踪和监控
- 任务组管理（批量任务）
- 任务取消和重试
- Worker 状态监控
- 任务执行统计

```python
from enterprise_kb.core.celery.task_manager import get_task_manager

# 获取任务管理器
task_manager = get_task_manager()

# 获取任务信息
task_info = task_manager.get_task_info(task_id)

# 取消任务
success = task_manager.cancel_task(task_id)

# 重试任务
new_task_id = task_manager.retry_failed_task(task_id)
```

### 2.2 任务跟踪装饰器

创建了 `tracked_task` 装饰器，提供：

- 自动任务开始和结束日志
- 执行时间跟踪
- 错误处理和状态更新
- 元数据记录

```python
from enterprise_kb.core.celery.task_manager import tracked_task

@tracked_task(
    name="my_task",
    retry_backoff=True,
    max_retries=3
)
def my_task(self, arg1, arg2):
    # 任务逻辑
    return result
```

## 3. 改进的队列和路由系统

### 3.1 队列定义

我们定义了多个专用队列，以便更好地管理不同类型的任务：

```python
# 定义队列
default_exchange = Exchange('default', type='direct')
document_exchange = Exchange('document', type='direct')
priority_exchange = Exchange('priority', type='direct')

task_queues = [
    Queue('default', default_exchange, routing_key='default'),
    Queue('document_processing', document_exchange, routing_key='document.processing'),
    Queue('document_indexing', document_exchange, routing_key='document.indexing'),
    Queue('priority', priority_exchange, routing_key='priority'),
]
```

### 3.2 路由规则

实现了更细粒度的路由规则，将不同类型的任务路由到不同的队列：

```python
# 定义路由
task_routes = {
    # 文档处理任务
    'enterprise_kb.tasks.document_tasks_v2.*': {
        'queue': 'document_processing',
        'routing_key': 'document.processing'
    },
    
    # 文档分段处理任务
    'enterprise_kb.tasks.document_segment_tasks.split_document': {
        'queue': 'document_processing',
        'routing_key': 'document.splitting'
    },
    'enterprise_kb.tasks.document_segment_tasks.process_segment': {
        'queue': 'document_processing',
        'routing_key': 'document.segment'
    },
    
    # 优先级任务
    'enterprise_kb.tasks.priority_tasks.*': {
        'queue': 'priority',
        'routing_key': 'priority'
    },
}
```

## 4. 配置优化

### 4.1 基本配置

```python
# Celery配置
celery_app.conf.update(
    # 基本配置
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
)
```

### 4.2 任务执行配置

```python
# 任务执行配置
task_track_started=True,
task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
worker_max_tasks_per_child=settings.CELERY_WORKER_MAX_TASKS_PER_CHILD,
worker_prefetch_multiplier=settings.CELERY_WORKER_PREFETCH_MULTIPLIER,
task_acks_late=settings.CELERY_TASK_ACKS_LATE,
task_reject_on_worker_lost=True,
task_acks_on_failure_or_timeout=False,
```

### 4.3 结果配置

```python
# 结果配置
result_expires=settings.CELERY_RESULT_EXPIRES,
result_persistent=True,
```

### 4.4 并发配置

```python
# 并发配置
worker_concurrency=settings.CELERY_WORKER_CONCURRENCY,
```

### 4.5 重试配置

```python
# 重试配置
task_default_retry_delay=60,  # 默认重试延迟（秒）
task_max_retries=3,           # 最大重试次数
```

## 5. 文档分段处理

### 5.1 任务分解

我们将文档处理分解为多个阶段，每个阶段作为独立的 Celery 任务：

1. **`split_document_task`**：将文档分割成多个段落
2. **`process_segment_task`**：处理单个段落，包括向量化和存储
3. **`merge_results_task`**：合并所有段落的处理结果
4. **`process_document_segmented_task`**：协调整个分段处理流程
5. **`batch_process_segmented_task`**：批量处理多个文档

### 5.2 任务编排

使用 Celery 的高级功能编排和协调任务：

```python
# 第一步：分割文档
split_task = split_document_task.s(
    file_path=file_path,
    metadata=metadata,
    chunking_type=chunking_type
)

# 第二步：处理每个段落（使用回调）
def process_segments_callback(split_result):
    segments = split_result["segments"]
    
    # 创建段落处理任务
    segment_tasks = []
    for segment in segments:
        task = process_segment_task.s(
            segment=segment,
            datasource_name=datasource_name
        )
        segment_tasks.append(task)
    
    # 创建任务组
    segment_group = group(segment_tasks)
    
    # 第三步：合并结果
    merge_task = merge_results_task.s(
        doc_id=doc_id,
        metadata=metadata
    )
    
    # 创建和弦（任务组 + 回调）
    segment_chord = chord(
        header=segment_group,
        body=merge_task
    )
    
    # 执行和弦
    return segment_chord()
```

### 5.3 API 端点

创建了 API 端点，使用户可以通过 HTTP 请求使用分段处理功能：

- `/api/v1/documents/segmented/process`：处理单个文档
- `/api/v1/documents/segmented/batch`：批量处理多个文档
- `/api/v1/documents/segmented/tasks/{task_id}`：获取任务状态
- `/api/v1/documents/segmented/tasks/{task_id}/cancel`：取消任务

## 6. 使用方法

### 6.1 处理单个文档

```python
from enterprise_kb.tasks.document_segment_tasks import process_document_segmented_task

task = process_document_segmented_task.delay(
    file_path="path/to/document.pdf",
    metadata={"title": "示例文档"},
    datasource_name="primary",
    chunking_type="hierarchical",
    chunk_size=500,
    chunk_overlap=50
)
```

### 6.2 批量处理文档

```python
from enterprise_kb.tasks.document_segment_tasks import batch_process_segmented_task

task = batch_process_segmented_task.delay(
    file_paths=["doc1.pdf", "doc2.pdf", "doc3.pdf"],
    shared_metadata={"batch": "示例批次"},
    datasource_name="primary",
    chunking_type="hierarchical"
)
```

### 6.3 通过 API 使用

处理单个文档：
```
POST /api/v1/documents/segmented/process
Content-Type: multipart/form-data

file: [文件内容]
title: 示例文档
chunking_type: hierarchical
chunk_size: 500
chunk_overlap: 50
```

批量处理文档：
```
POST /api/v1/documents/segmented/batch
Content-Type: multipart/form-data

files: [文件1内容, 文件2内容, ...]
metadata: {"batch_name": "示例批次"}
chunking_type: hierarchical
```

## 7. 优势

### 7.1 性能优势

- **更好的并行性**：可以并行处理多个段落，充分利用多核 CPU
- **更好的可扩展性**：可以在多个 worker 之间分配任务，实现水平扩展
- **更好的资源利用**：可以根据段落大小和复杂度动态分配资源

### 7.2 可靠性优势

- **更好的容错性**：单个段落处理失败不会影响整个文档处理
- **更好的错误处理**：提供了更全面的错误处理和重试机制
- **更好的监控**：提供了更全面的任务监控和统计

### 7.3 用户体验优势

- **更好的进度跟踪**：可以跟踪每个段落的处理进度
- **更好的响应性**：可以更快地返回初步结果
- **更好的控制**：提供了取消和重试任务的能力

## 8. 最佳实践

### 8.1 Worker 配置

- 根据服务器资源配置适当的 worker 数量
- 使用 `--concurrency` 参数控制每个 worker 的并发任务数
- 使用 `--prefetch-multiplier` 参数控制预取任务数

```bash
celery -A enterprise_kb.core.celery.app worker -l info --concurrency=4 --prefetch-multiplier=2 -Q document_processing
```

### 8.2 任务设计

- 将大型任务分解为多个小型任务
- 使用任务组、链和和弦编排任务
- 为任务设置适当的超时和重试策略

### 8.3 监控

- 使用 Flower 监控 Celery 任务和 worker
- 定期检查任务队列长度和处理时间
- 设置适当的告警机制

```bash
celery -A enterprise_kb.core.celery.app flower --port=5555
```

## 9. 故障排除

### 9.1 常见问题

- **任务卡住**：检查 worker 状态和任务队列
- **任务失败**：检查任务日志和错误信息
- **性能问题**：检查 worker 数量和并发设置

### 9.2 调试技巧

- 使用 `--loglevel=DEBUG` 启动 worker 获取详细日志
- 使用 `task.apply()` 同步执行任务进行调试
- 使用 Flower 查看任务详情和统计信息

## 10. 未来改进

### 10.1 优先级队列

实现更细粒度的任务优先级，确保重要任务优先处理。

### 10.2 自适应并发

根据系统负载和资源使用情况动态调整并发任务数。

### 10.3 分布式追踪

集成分布式追踪系统（如 Jaeger、Zipkin），跟踪任务执行路径和性能瓶颈。

### 10.4 更多任务类型

添加更多专用任务类型，如图像处理、视频处理等。

## 11. 结论

通过实现高级任务管理、改进队列和路由系统、优化配置以及文档分段处理，我们显著提高了 Celery 任务的管理和执行效率，特别是对于大型文档和批量处理任务。这些优化使系统更加健壮、可靠和可扩展，能够处理更复杂的文档处理需求。

未来，我们将继续优化和扩展这些功能，以支持更多的任务类型和处理需求，进一步提高系统的性能和可用性。
