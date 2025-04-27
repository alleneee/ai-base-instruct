"""Celery任务管理器，提供高级任务管理和监控功能"""
import logging
import time
import json
from typing import Dict, List, Any, Optional, Union, Callable
from datetime import datetime, timedelta
from functools import wraps

from celery import group, chain, chord
from celery.result import AsyncResult, GroupResult
from celery.exceptions import TimeoutError, TaskRevokedError

from enterprise_kb.core.unified_celery import celery_app
from enterprise_kb.core.config.settings import settings

logger = logging.getLogger(__name__)

class TaskManager:
    """Celery任务管理器，提供高级任务管理和监控功能"""
    
    def __init__(self):
        """初始化任务管理器"""
        self.app = celery_app
        self.task_cache = {}  # 简单的内存缓存，用于存储任务信息
    
    def get_task_info(self, task_id: str) -> Dict[str, Any]:
        """获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息
        """
        # 先从缓存中获取
        if task_id in self.task_cache:
            return self.task_cache[task_id]
        
        # 从Celery获取
        task = AsyncResult(task_id)
        
        info = {
            "task_id": task_id,
            "status": task.status,
            "created_at": None,
            "started_at": None,
            "completed_at": None,
            "runtime": None,
            "result": None,
            "error": None,
            "progress": None,
            "meta": {}
        }
        
        # 获取任务信息
        if hasattr(task, "info") and task.info:
            if isinstance(task.info, dict):
                info["meta"] = task.info
                if "progress" in task.info:
                    info["progress"] = task.info["progress"]
        
        # 获取任务结果
        if task.successful():
            info["result"] = task.result
            info["completed_at"] = datetime.now().isoformat()
        elif task.failed():
            info["error"] = str(task.result) if task.result else "任务失败"
            info["completed_at"] = datetime.now().isoformat()
        
        # 缓存任务信息
        self.task_cache[task_id] = info
        
        return info
    
    def get_group_info(self, group_id: str) -> Dict[str, Any]:
        """获取任务组信息
        
        Args:
            group_id: 任务组ID
            
        Returns:
            任务组信息
        """
        group_result = GroupResult.restore(group_id)
        
        if not group_result:
            return {
                "group_id": group_id,
                "status": "UNKNOWN",
                "task_count": 0,
                "completed": 0,
                "failed": 0,
                "progress": 0,
                "tasks": []
            }
        
        tasks = []
        completed = 0
        failed = 0
        
        for task in group_result.results:
            task_info = self.get_task_info(task.id)
            tasks.append(task_info)
            
            if task.successful():
                completed += 1
            elif task.failed():
                failed += 1
        
        total = len(group_result.results)
        progress = int((completed + failed) / total * 100) if total > 0 else 0
        
        return {
            "group_id": group_id,
            "status": group_result.completed() and "SUCCESS" or "PENDING",
            "task_count": total,
            "completed": completed,
            "failed": failed,
            "progress": progress,
            "tasks": tasks
        }
    
    def create_task_group(
        self, 
        task: Callable, 
        args_list: List[List[Any]], 
        kwargs_list: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """创建任务组
        
        Args:
            task: 任务函数
            args_list: 参数列表的列表
            kwargs_list: 关键字参数列表的列表
            
        Returns:
            任务组ID
        """
        if kwargs_list is None:
            kwargs_list = [{} for _ in range(len(args_list))]
        
        # 创建任务组
        task_group = group(task.s(*args, **kwargs) for args, kwargs in zip(args_list, kwargs_list))
        result = task_group.apply_async()
        
        # 保存任务组结果
        result.save()
        
        return result.id
    
    def create_task_chain(
        self, 
        tasks: List[Callable], 
        args_list: Optional[List[List[Any]]] = None,
        kwargs_list: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """创建任务链
        
        Args:
            tasks: 任务函数列表
            args_list: 参数列表的列表
            kwargs_list: 关键字参数列表的列表
            
        Returns:
            任务链ID
        """
        if args_list is None:
            args_list = [[] for _ in range(len(tasks))]
        
        if kwargs_list is None:
            kwargs_list = [{} for _ in range(len(tasks))]
        
        # 创建任务链
        task_chain = chain(
            task.s(*args, **kwargs) 
            for task, args, kwargs in zip(tasks, args_list, kwargs_list)
        )
        result = task_chain.apply_async()
        
        return result.id
    
    def create_task_chord(
        self,
        header_task: Callable,
        header_args_list: List[List[Any]],
        callback_task: Callable,
        callback_args: Optional[List[Any]] = None,
        callback_kwargs: Optional[Dict[str, Any]] = None
    ) -> str:
        """创建任务和弦
        
        Args:
            header_task: 头部任务函数
            header_args_list: 头部任务参数列表的列表
            callback_task: 回调任务函数
            callback_args: 回调任务参数列表
            callback_kwargs: 回调任务关键字参数
            
        Returns:
            任务和弦ID
        """
        if callback_args is None:
            callback_args = []
        
        if callback_kwargs is None:
            callback_kwargs = {}
        
        # 创建头部任务组
        header = group(header_task.s(*args) for args in header_args_list)
        
        # 创建任务和弦
        task_chord = chord(
            header=header,
            body=callback_task.s(*callback_args, **callback_kwargs)
        )
        result = task_chord.apply_async()
        
        return result.id
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功取消
        """
        try:
            self.app.control.revoke(task_id, terminate=True)
            
            # 从缓存中移除
            if task_id in self.task_cache:
                del self.task_cache[task_id]
                
            return True
        except Exception as e:
            logger.error(f"取消任务失败: {str(e)}")
            return False
    
    def cancel_group(self, group_id: str) -> bool:
        """取消任务组
        
        Args:
            group_id: 任务组ID
            
        Returns:
            是否成功取消
        """
        try:
            group_result = GroupResult.restore(group_id)
            
            if not group_result:
                return False
            
            # 取消所有任务
            for task in group_result.results:
                self.cancel_task(task.id)
            
            return True
        except Exception as e:
            logger.error(f"取消任务组失败: {str(e)}")
            return False
    
    def wait_for_task(
        self, 
        task_id: str, 
        timeout: Optional[int] = None, 
        interval: int = 1
    ) -> Dict[str, Any]:
        """等待任务完成
        
        Args:
            task_id: 任务ID
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）
            
        Returns:
            任务信息
        """
        task = AsyncResult(task_id)
        start_time = time.time()
        
        while True:
            # 检查是否超时
            if timeout and time.time() - start_time > timeout:
                raise TimeoutError(f"等待任务 {task_id} 超时")
            
            # 检查任务状态
            if task.ready():
                break
            
            # 等待一段时间
            time.sleep(interval)
        
        return self.get_task_info(task_id)
    
    def wait_for_group(
        self, 
        group_id: str, 
        timeout: Optional[int] = None, 
        interval: int = 1
    ) -> Dict[str, Any]:
        """等待任务组完成
        
        Args:
            group_id: 任务组ID
            timeout: 超时时间（秒）
            interval: 检查间隔（秒）
            
        Returns:
            任务组信息
        """
        group_result = GroupResult.restore(group_id)
        
        if not group_result:
            raise ValueError(f"找不到任务组 {group_id}")
        
        start_time = time.time()
        
        while True:
            # 检查是否超时
            if timeout and time.time() - start_time > timeout:
                raise TimeoutError(f"等待任务组 {group_id} 超时")
            
            # 检查任务组状态
            if group_result.ready():
                break
            
            # 等待一段时间
            time.sleep(interval)
        
        return self.get_group_info(group_id)
    
    def retry_failed_task(self, task_id: str) -> Optional[str]:
        """重试失败的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            新任务ID，如果重试失败则返回None
        """
        task = AsyncResult(task_id)
        
        if not task.failed():
            logger.warning(f"任务 {task_id} 未失败，无法重试")
            return None
        
        try:
            # 获取原始任务信息
            task_name = task.name
            task_args = task.args
            task_kwargs = task.kwargs
            
            # 重新提交任务
            new_task = self.app.send_task(
                task_name,
                args=task_args,
                kwargs=task_kwargs
            )
            
            return new_task.id
        except Exception as e:
            logger.error(f"重试任务失败: {str(e)}")
            return None
    
    def get_active_tasks(self) -> List[Dict[str, Any]]:
        """获取活动任务列表
        
        Returns:
            活动任务列表
        """
        try:
            # 获取所有活动任务
            active_tasks = self.app.control.inspect().active() or {}
            
            # 格式化任务信息
            result = []
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    result.append({
                        "task_id": task["id"],
                        "name": task["name"],
                        "worker": worker,
                        "args": task["args"],
                        "kwargs": task["kwargs"],
                        "started_at": task.get("time_start"),
                        "acknowledged": task.get("acknowledged", False)
                    })
            
            return result
        except Exception as e:
            logger.error(f"获取活动任务失败: {str(e)}")
            return []
    
    def get_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """获取计划任务列表
        
        Returns:
            计划任务列表
        """
        try:
            # 获取所有计划任务
            scheduled_tasks = self.app.control.inspect().scheduled() or {}
            
            # 格式化任务信息
            result = []
            for worker, tasks in scheduled_tasks.items():
                for task in tasks:
                    result.append({
                        "task_id": task["request"]["id"],
                        "name": task["request"]["name"],
                        "worker": worker,
                        "args": task["request"]["args"],
                        "kwargs": task["request"]["kwargs"],
                        "eta": task["eta"],
                        "priority": task["priority"]
                    })
            
            return result
        except Exception as e:
            logger.error(f"获取计划任务失败: {str(e)}")
            return []
    
    def get_worker_stats(self) -> Dict[str, Any]:
        """获取Worker统计信息
        
        Returns:
            Worker统计信息
        """
        try:
            # 获取Worker统计信息
            stats = self.app.control.inspect().stats() or {}
            
            # 格式化统计信息
            result = {}
            for worker, worker_stats in stats.items():
                result[worker] = {
                    "processes": worker_stats.get("pool", {}).get("processes", []),
                    "max_concurrency": worker_stats.get("pool", {}).get("max-concurrency", 0),
                    "broker": {
                        "transport": worker_stats.get("broker", {}).get("transport", ""),
                        "hostname": worker_stats.get("broker", {}).get("hostname", "")
                    },
                    "prefetch_count": worker_stats.get("prefetch_count", 0),
                    "uptime": worker_stats.get("uptime", 0)
                }
            
            return result
        except Exception as e:
            logger.error(f"获取Worker统计信息失败: {str(e)}")
            return {}

# 创建单例实例
_task_manager = None

def get_task_manager() -> TaskManager:
    """获取任务管理器单例"""
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager

# 任务装饰器
def tracked_task(**task_options):
    """跟踪任务装饰器，用于跟踪任务执行情况
    
    Args:
        **task_options: 任务选项
        
    Returns:
        装饰器函数
    """
    def decorator(func):
        # 创建Celery任务
        @celery_app.task(bind=True, **task_options)
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # 记录任务开始
            task_id = self.request.id
            logger.info(f"任务 {task_id} ({func.__name__}) 开始执行")
            start_time = time.time()
            
            # 更新任务状态
            self.update_state(state="STARTED", meta={
                "start_time": start_time,
                "task_name": func.__name__
            })
            
            try:
                # 执行任务
                result = func(self, *args, **kwargs)
                
                # 记录任务完成
                end_time = time.time()
                execution_time = end_time - start_time
                logger.info(f"任务 {task_id} ({func.__name__}) 完成，耗时: {execution_time:.2f}秒")
                
                # 更新任务状态
                self.update_state(state="SUCCESS", meta={
                    "start_time": start_time,
                    "end_time": end_time,
                    "execution_time": execution_time,
                    "task_name": func.__name__
                })
                
                return result
            except Exception as e:
                # 记录任务失败
                end_time = time.time()
                execution_time = end_time - start_time
                logger.error(f"任务 {task_id} ({func.__name__}) 失败，耗时: {execution_time:.2f}秒，错误: {str(e)}")
                
                # 更新任务状态
                self.update_state(state="FAILURE", meta={
                    "start_time": start_time,
                    "end_time": end_time,
                    "execution_time": execution_time,
                    "task_name": func.__name__,
                    "error": str(e)
                })
                
                # 重新抛出异常
                raise
        
        return wrapper
    
    return decorator
