#!/usr/bin/env python
"""
统一Celery配置示例

此脚本展示了如何使用统一的Celery配置创建和调用任务。
"""
import os
import sys
import time
import logging
from typing import Dict, Any, List
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from enterprise_kb.core.unified_celery import celery_app, get_task_info

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 示例任务
@celery_app.task(bind=True)
def example_task(self, name: str, delay: int = 1) -> Dict[str, Any]:
    """示例任务，演示如何使用统一的Celery配置

    Args:
        name: 名称
        delay: 延迟时间（秒）

    Returns:
        结果字典
    """
    logger.info(f"开始执行示例任务: {name}")

    # 更新任务状态
    self.update_state(state="PROGRESS", meta={"progress": 0, "status": "开始处理"})

    # 模拟处理过程
    for i in range(1, 11):
        # 模拟处理时间
        time.sleep(delay / 10)

        # 更新任务状态
        progress = i * 10
        self.update_state(
            state="PROGRESS",
            meta={"progress": progress, "status": f"处理中 {progress}%"}
        )

        logger.info(f"任务 {name} 进度: {progress}%")

    # 返回结果
    result = {
        "name": name,
        "status": "完成",
        "time_taken": delay,
        "message": f"任务 {name} 已完成"
    }

    logger.info(f"任务 {name} 完成")
    return result

@celery_app.task(bind=True, queue="document_processing")
def process_document_example(self, doc_id: str, content: str) -> Dict[str, Any]:
    """文档处理示例任务

    Args:
        doc_id: 文档ID
        content: 文档内容

    Returns:
        处理结果
    """
    logger.info(f"开始处理文档: {doc_id}")

    # 更新任务状态
    self.update_state(state="PROGRESS", meta={"progress": 0, "status": "开始处理文档"})

    # 模拟文档处理
    time.sleep(2)

    # 计算一些简单的统计信息
    word_count = len(content.split())
    char_count = len(content)

    # 更新任务状态
    self.update_state(
        state="PROGRESS",
        meta={"progress": 50, "status": "文档处理中", "word_count": word_count}
    )

    # 模拟更多处理
    time.sleep(1)

    # 返回结果
    result = {
        "doc_id": doc_id,
        "status": "处理完成",
        "word_count": word_count,
        "char_count": char_count,
        "message": f"文档 {doc_id} 处理完成"
    }

    logger.info(f"文档 {doc_id} 处理完成")
    return result

@celery_app.task(
    bind=True,
    queue="priority",
    max_retries=5,
    default_retry_delay=30
)
def priority_task_example(self, task_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """优先级任务示例

    Args:
        task_id: 任务ID
        data: 任务数据

    Returns:
        处理结果
    """
    logger.info(f"开始执行优先级任务: {task_id}")

    try:
        # 模拟处理
        time.sleep(1)

        # 模拟可能的错误
        if data.get("simulate_error", False):
            raise ValueError("模拟错误")

        # 返回结果
        result = {
            "task_id": task_id,
            "status": "成功",
            "data": data,
            "message": f"优先级任务 {task_id} 执行成功"
        }

        logger.info(f"优先级任务 {task_id} 执行成功")
        return result

    except Exception as e:
        logger.error(f"优先级任务 {task_id} 执行失败: {str(e)}")

        # 重试任务
        self.retry(exc=e)

@celery_app.task(bind=True)
def chain_task_example(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """链式任务示例，处理前面任务的结果

    Args:
        results: 前面任务的结果列表

    Returns:
        处理结果
    """
    logger.info(f"开始执行链式任务，处理 {len(results)} 个结果")

    # 合并结果
    combined_result = {
        "count": len(results),
        "items": results,
        "summary": {
            "successful": sum(1 for r in results if r.get("status") == "成功" or r.get("status") == "完成"),
            "failed": sum(1 for r in results if r.get("status") != "成功" and r.get("status") != "完成")
        }
    }

    logger.info(f"链式任务执行完成，成功: {combined_result['summary']['successful']}, 失败: {combined_result['summary']['failed']}")
    return combined_result

def run_example_tasks():
    """运行示例任务"""
    logger.info("开始运行示例任务")

    # 运行简单任务
    logger.info("运行简单任务")
    result1 = example_task.delay("示例任务1", 2)
    logger.info(f"任务ID: {result1.id}")

    # 等待任务完成
    while not result1.ready():
        # 获取任务状态
        task_info = get_task_info(result1.id)
        logger.info(f"任务状态: {task_info}")
        time.sleep(0.5)

    # 获取任务结果
    task_result = result1.get()
    logger.info(f"任务结果: {task_result}")

    # 运行文档处理任务
    logger.info("运行文档处理任务")
    result2 = process_document_example.delay(
        "doc-123",
        "这是一个示例文档，用于测试统一的Celery配置。"
    )
    logger.info(f"任务ID: {result2.id}")

    # 运行优先级任务
    logger.info("运行优先级任务")
    result3 = priority_task_example.delay(
        "priority-456",
        {"key": "value", "simulate_error": False}
    )
    logger.info(f"任务ID: {result3.id}")

    # 等待所有任务完成
    logger.info("等待所有任务完成")
    all_results = [result1.get(), result2.get(), result3.get()]

    # 运行链式任务
    logger.info("运行链式任务")
    result4 = chain_task_example.delay(all_results)
    logger.info(f"任务ID: {result4.id}")

    # 等待链式任务完成
    while not result4.ready():
        time.sleep(0.5)

    # 获取链式任务结果
    chain_result = result4.get()
    logger.info(f"链式任务结果: {chain_result}")

    logger.info("所有示例任务完成")

if __name__ == "__main__":
    # 检查是否在EAGER模式下运行
    if celery_app.conf.task_always_eager:
        logger.info("在EAGER模式下运行，任务将同步执行")
    else:
        logger.info("在异步模式下运行，确保Celery worker已启动")

    # 运行示例任务
    run_example_tasks()
