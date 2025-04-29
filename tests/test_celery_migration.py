#!/usr/bin/env python
"""
测试Celery迁移的脚本

此脚本用于测试Celery迁移是否成功，包括导入路径、任务装饰器和任务调用。
"""
import os
import sys
import time
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def test_imports():
    """测试导入路径"""
    logger.info("测试导入路径...")
    
    try:
        # 测试导入统一的Celery配置
        from enterprise_kb.core.unified_celery import celery_app, get_celery_app, get_task_info, BaseTask
        logger.info("导入统一的Celery配置成功")
        
        # 测试导入兼容层
        from enterprise_kb.core.celery import celery_app as celery_app_compat
        logger.info("导入兼容层成功")
        
        # 测试导入旧的Celery配置
        from enterprise_kb.core.celery_app import app
        logger.info("导入旧的Celery配置成功")
        
        # 测试导入旧的Celery/app配置
        from enterprise_kb.core.celery.app import celery_app as celery_app_old
        logger.info("导入旧的Celery/app配置成功")
        
        # 检查是否是同一个Celery应用实例
        logger.info(f"统一的Celery配置: {celery_app}")
        logger.info(f"兼容层: {celery_app_compat}")
        logger.info(f"旧的Celery配置: {app}")
        logger.info(f"旧的Celery/app配置: {celery_app_old}")
        
        # 检查是否是同一个对象
        if celery_app is celery_app_compat and celery_app is app and celery_app is celery_app_old:
            logger.info("所有Celery应用实例都是同一个对象，迁移成功")
        else:
            logger.warning("Celery应用实例不是同一个对象，迁移可能不完整")
        
        return True
    except ImportError as e:
        logger.error(f"导入失败: {str(e)}")
        return False

def test_task_decorator():
    """测试任务装饰器"""
    logger.info("测试任务装饰器...")
    
    try:
        from enterprise_kb.core.unified_celery import celery_app
        
        # 测试任务装饰器
        @celery_app.task(bind=True)
        def test_task(self, name):
            logger.info(f"执行测试任务: {name}")
            return {"status": "success", "name": name}
        
        logger.info("任务装饰器测试成功")
        
        # 测试任务调用
        result = test_task.delay("测试任务")
        logger.info(f"任务ID: {result.id}")
        
        # 等待任务完成
        if celery_app.conf.task_always_eager:
            logger.info("在EAGER模式下运行，任务已同步执行")
            task_result = result.get()
            logger.info(f"任务结果: {task_result}")
        else:
            logger.info("在异步模式下运行，等待任务完成...")
            while not result.ready():
                time.sleep(0.5)
            
            # 获取任务结果
            task_result = result.get()
            logger.info(f"任务结果: {task_result}")
        
        return True
    except Exception as e:
        logger.error(f"任务装饰器测试失败: {str(e)}")
        return False

def test_task_routing():
    """测试任务路由"""
    logger.info("测试任务路由...")
    
    try:
        from enterprise_kb.core.unified_celery import celery_app
        
        # 测试不同队列的任务
        @celery_app.task(bind=True, queue="document_processing")
        def document_task(self, doc_id):
            logger.info(f"处理文档: {doc_id}")
            return {"status": "success", "doc_id": doc_id}
        
        @celery_app.task(bind=True, queue="priority")
        def priority_task(self, task_id):
            logger.info(f"执行优先级任务: {task_id}")
            return {"status": "success", "task_id": task_id}
        
        # 提交任务
        doc_result = document_task.delay("doc-123")
        priority_result = priority_task.delay("priority-456")
        
        logger.info(f"文档任务ID: {doc_result.id}")
        logger.info(f"优先级任务ID: {priority_result.id}")
        
        # 在EAGER模式下，任务会立即执行
        if celery_app.conf.task_always_eager:
            logger.info("在EAGER模式下运行，任务已同步执行")
        else:
            logger.info("在异步模式下运行，任务已提交到队列")
        
        return True
    except Exception as e:
        logger.error(f"任务路由测试失败: {str(e)}")
        return False

def test_existing_tasks():
    """测试现有任务"""
    logger.info("测试现有任务...")
    
    try:
        # 测试导入现有任务
        from enterprise_kb.services.tasks import process_document, batch_process_documents
        logger.info("导入现有任务成功")
        
        # 创建测试文件
        test_file = os.path.join(os.getcwd(), "test_document.txt")
        with open(test_file, "w") as f:
            f.write("这是一个测试文档，用于测试Celery迁移。")
        
        # 提交任务
        result = process_document.delay(test_file, {"test": True})
        logger.info(f"任务ID: {result.id}")
        
        # 清理测试文件
        os.remove(test_file)
        
        return True
    except Exception as e:
        logger.error(f"现有任务测试失败: {str(e)}")
        return False

def main():
    """主函数"""
    logger.info("开始测试Celery迁移...")
    
    # 测试导入路径
    if not test_imports():
        logger.error("导入路径测试失败")
        return
    
    # 测试任务装饰器
    if not test_task_decorator():
        logger.error("任务装饰器测试失败")
        return
    
    # 测试任务路由
    if not test_task_routing():
        logger.error("任务路由测试失败")
        return
    
    # 测试现有任务
    if not test_existing_tasks():
        logger.error("现有任务测试失败")
        return
    
    logger.info("Celery迁移测试成功")

if __name__ == "__main__":
    main()
