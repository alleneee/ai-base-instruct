# Celery配置迁移指南

本文档提供了将现有代码迁移到统一Celery配置的详细步骤。

## 背景

我们之前的Celery配置分散在多个文件中：
- `enterprise_kb/core/celery.py`
- `enterprise_kb/core/celery_app.py`
- `enterprise_kb/core/celery/app.py`

这导致了配置混乱和潜在的冲突。为了解决这个问题，我们创建了一个统一的Celery配置文件：
- `enterprise_kb/core/unified_celery.py`

## 迁移步骤

### 1. 更新导入路径

将现有代码中的Celery导入路径更新为统一的导入路径：

```python
# 旧的导入路径
from enterprise_kb.core.celery import celery_app
from enterprise_kb.core.celery_app import app
from enterprise_kb.core.celery.app import celery_app

# 新的导入路径
from enterprise_kb.core.unified_celery import celery_app
```

我们提供了一个脚本来自动更新导入路径：

```bash
python scripts/update_celery_imports.py --directory enterprise_kb
```

### 2. 更新任务装饰器

确保所有任务装饰器使用统一的格式：

```python
# 旧的装饰器
@celery_app.task
@app.task
@shared_task

# 新的装饰器
@celery_app.task
```

### 3. 更新任务调用方式

确保所有任务调用使用统一的方式：

```python
# 旧的调用方式
result = my_task.delay(arg1, arg2)
result = my_task.apply_async(args=[arg1, arg2], queue='default')

# 新的调用方式（保持不变）
result = my_task.delay(arg1, arg2)
result = my_task.apply_async(args=[arg1, arg2], queue='default')
```

### 4. 更新任务队列

统一的Celery配置定义了以下队列：

```python
# 队列
default                # 默认队列
document_processing    # 文档处理队列
document_indexing      # 文档索引队列
document_splitting     # 文档分割队列
document_segment       # 文档段处理队列
document_merging       # 文档合并队列
index                  # 索引队列
priority               # 优先级队列
```

确保所有任务都路由到正确的队列：

```python
@celery_app.task(queue='document_processing')
def process_document(doc_id):
    # 处理文档
    pass
```

### 5. 更新启动命令

使用新的命令启动Celery worker：

```bash
# 旧的命令
celery -A enterprise_kb.core.celery worker -l info
celery -A enterprise_kb.core.celery_app worker -l info
celery -A enterprise_kb.core.celery.app worker -l info

# 新的命令
celery -A enterprise_kb.core.unified_celery worker -Q default,document_processing,document_splitting,document_segment,document_merging,index,priority -l info
```

使用新的命令启动Celery beat：

```bash
# 新的命令
celery -A enterprise_kb.core.unified_celery beat -l info
```

### 6. 更新监控命令

使用新的命令启动Flower监控：

```bash
# 新的命令
celery -A enterprise_kb.core.unified_celery flower --port=5555
```

## 兼容性说明

为了确保平稳过渡，我们保留了旧的Celery配置文件，但它们现在只是导入兼容层，并发出弃用警告。这些文件将在未来版本中移除。

## 测试迁移

在完成迁移后，请运行以下测试确保一切正常：

### 使用测试脚本

我们提供了一个测试脚本，用于验证迁移是否成功：

```bash
python scripts/test_celery_migration.py
```

这个脚本会测试以下内容：
- 导入路径是否正确
- 任务装饰器是否正常工作
- 任务路由是否正确
- 现有任务是否能正常调用

### 手动测试

如果你想手动测试，可以按照以下步骤进行：

1. 启动Celery worker：
```bash
# 使用提供的启动脚本
./scripts/start_celery.sh worker

# 或者直接使用Celery命令
celery -A enterprise_kb.core.unified_celery worker -Q default,document_processing -l info
```

2. 运行测试任务：
```python
from enterprise_kb.core.unified_celery import debug_task
result = debug_task.delay()
print(result.get())
```

3. 检查任务状态：
```python
from enterprise_kb.core.unified_celery import get_task_info
task_info = get_task_info(result.id)
print(task_info)
```

### 使用示例脚本

我们还提供了一个示例脚本，展示如何使用统一的Celery配置：

```bash
python examples/unified_celery_example.py
```

这个脚本展示了：
- 如何创建和调用任务
- 如何使用任务状态更新
- 如何处理任务结果
- 如何使用不同的队列

## 常见问题

### 1. 导入错误

如果遇到导入错误，请检查导入路径是否正确更新：

```python
# 正确的导入路径
from enterprise_kb.core.unified_celery import celery_app
```

### 2. 任务未执行

如果任务未执行，请检查：
- Celery worker是否启动
- 任务是否路由到正确的队列
- worker是否监听该队列

### 3. 任务执行失败

如果任务执行失败，请检查：
- 任务参数是否正确
- 任务依赖是否满足
- 查看Celery worker日志获取详细错误信息

## 迁移时间表

1. **第一阶段（当前）**：
   - 创建统一的Celery配置
   - 添加兼容层
   - 更新文档

2. **第二阶段（1-2周）**：
   - 更新所有任务导入路径
   - 测试所有任务

3. **第三阶段（2-4周）**：
   - 移除兼容层
   - 完全迁移到统一配置

## 联系人

如果在迁移过程中遇到任何问题，请联系项目维护人员。
