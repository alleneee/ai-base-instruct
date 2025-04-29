"""
向量数据库连接池抽象基类
提供通用的连接池管理机制，支持不同类型的向量数据库
"""
from abc import ABC, abstractmethod
import logging
import time
from typing import Dict, Any, Optional, TypeVar, Generic, Type, Callable, List, Tuple
import threading
import queue
import asyncio
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# 连接对象类型变量
T = TypeVar('T')


class PoolConfig:
    """连接池配置"""
    
    def __init__(
        self,
        max_connections: int = 10,
        min_connections: int = 2,
        max_idle_time: int = 60,  # 最大空闲时间（秒）
        connection_timeout: int = 5,  # 连接超时（秒）
        retry_interval: float = 1.0,  # 重试间隔（秒）
        max_retries: int = 3,  # 最大重试次数
        **kwargs
    ):
        self.max_connections = max_connections
        self.min_connections = min_connections
        self.max_idle_time = max_idle_time
        self.connection_timeout = connection_timeout
        self.retry_interval = retry_interval
        self.max_retries = max_retries
        self.extra_config = kwargs
        
    def update(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                self.extra_config[key] = value


class ConnectionPool(Generic[T], ABC):
    """向量数据库连接池抽象基类"""
    
    def __init__(self, config: PoolConfig):
        self.config = config
        self._pool = queue.Queue(maxsize=config.max_connections)
        self._active_connections = 0
        self._lock = threading.RLock()
        self._last_connection_check = time.time()
        self._shutdown = False
        self._init_pool()
        
    def _init_pool(self):
        """初始化连接池，预创建最小连接数"""
        with self._lock:
            for _ in range(self.config.min_connections):
                try:
                    conn = self._create_connection()
                    self._pool.put(conn)
                    self._active_connections += 1
                except Exception as e:
                    logger.error(f"初始化连接池失败: {str(e)}")
    
    @abstractmethod
    def _create_connection(self) -> T:
        """创建新连接
        
        由子类实现，创建特定类型的连接
        """
        pass
        
    @abstractmethod
    def _validate_connection(self, conn: T) -> bool:
        """验证连接是否有效
        
        由子类实现，验证特定类型的连接
        """
        pass
    
    @abstractmethod
    def _close_connection(self, conn: T) -> None:
        """关闭连接
        
        由子类实现，关闭特定类型的连接
        """
        pass
    
    def get_connection(self) -> T:
        """获取连接，如果池中没有可用连接，则创建新连接"""
        if self._shutdown:
            raise RuntimeError("连接池已关闭")
            
        # 首先尝试从池中获取连接
        try:
            conn = self._pool.get(block=True, timeout=self.config.connection_timeout)
            # 验证连接有效性
            if self._validate_connection(conn):
                return conn
            else:
                # 连接无效，关闭并创建新连接
                self._close_connection(conn)
                with self._lock:
                    self._active_connections -= 1
                return self._create_and_count_connection()
        except queue.Empty:
            # 池中无可用连接，创建新连接
            return self._create_and_count_connection()
    
    def _create_and_count_connection(self) -> T:
        """创建新连接并计数"""
        with self._lock:
            if self._active_connections >= self.config.max_connections:
                raise RuntimeError(f"达到最大连接数限制 ({self.config.max_connections})")
            
            conn = self._create_connection()
            self._active_connections += 1
            return conn
    
    def release_connection(self, conn: T) -> None:
        """释放连接回池"""
        if self._shutdown:
            self._close_connection(conn)
            return
            
        # 检查连接有效性
        if not self._validate_connection(conn):
            with self._lock:
                self._close_connection(conn)
                self._active_connections -= 1
            return
            
        # 放回连接池
        try:
            self._pool.put_nowait(conn)
        except queue.Full:
            # 池已满，关闭多余连接
            with self._lock:
                self._close_connection(conn)
                self._active_connections -= 1
    
    def shutdown(self) -> None:
        """关闭连接池"""
        self._shutdown = True
        
        # 清空连接池
        with self._lock:
            while not self._pool.empty():
                try:
                    conn = self._pool.get_nowait()
                    self._close_connection(conn)
                    self._active_connections -= 1
                except queue.Empty:
                    break
            
            logger.info(f"连接池已关闭，关闭了 {self._active_connections} 个连接")
    
    @asynccontextmanager
    async def connection(self):
        """异步上下文管理器，用于获取和释放连接"""
        conn = None
        try:
            # 使用run_in_executor在线程池中执行阻塞操作
            loop = asyncio.get_event_loop()
            conn = await loop.run_in_executor(None, self.get_connection)
            yield conn
        finally:
            if conn:
                # 释放连接
                await loop.run_in_executor(None, self.release_connection, conn)
    
    def health_check(self) -> Dict[str, Any]:
        """检查连接池健康状态"""
        with self._lock:
            return {
                "active_connections": self._active_connections,
                "available_connections": self._pool.qsize(),
                "max_connections": self.config.max_connections,
                "min_connections": self.config.min_connections,
                "is_shutdown": self._shutdown
            }
    
    def stats(self) -> Dict[str, Any]:
        """获取连接池统计信息"""
        health = self.health_check()
        health.update({
            "idle_percentage": 
                (health["available_connections"] / max(health["active_connections"], 1)) * 100 
                if health["active_connections"] > 0 else 0,
            "utilization_percentage": 
                (health["active_connections"] / health["max_connections"]) * 100
        })
        return health


class BatchProcessor(Generic[T], ABC):
    """批量处理器抽象基类，用于批量操作数据"""
    
    def __init__(
        self, 
        connection_pool: ConnectionPool[T], 
        batch_size: int = 100, 
        max_queue_size: int = 1000,
        flush_interval: float = 1.0  # 自动刷新间隔（秒）
    ):
        self.connection_pool = connection_pool
        self.batch_size = batch_size
        self._queue = queue.Queue(maxsize=max_queue_size)
        self._flush_interval = flush_interval
        self._last_flush_time = time.time()
        self._flush_lock = threading.Lock()
        self._shutdown = False
        
        # 启动自动刷新线程
        self._flush_thread = threading.Thread(target=self._auto_flush_worker, daemon=True)
        self._flush_thread.start()
    
    def add(self, item: Any) -> None:
        """添加项到批处理队列"""
        if self._shutdown:
            raise RuntimeError("批处理器已关闭")
            
        # 将项添加到队列
        try:
            self._queue.put(item, block=True, timeout=5)
        except queue.Full:
            # 队列已满，尝试先刷新队列
            self.flush()
            self._queue.put(item, block=True, timeout=5)
            
        # 如果队列大小达到批处理阈值，自动刷新
        if self._queue.qsize() >= self.batch_size:
            self.flush()
    
    def add_batch(self, items: List[Any]) -> None:
        """批量添加项到处理队列"""
        if not items:
            return
            
        # 如果项数量大于批处理大小，分批添加
        if len(items) > self.batch_size:
            for i in range(0, len(items), self.batch_size):
                self.add_batch(items[i:i+self.batch_size])
            return
            
        # 添加所有项到队列
        for item in items:
            self.add(item)
    
    def flush(self) -> List[Any]:
        """刷新队列中的项，执行批处理"""
        if self._queue.empty():
            return []
            
        # 加锁确保线程安全
        with self._flush_lock:
            # 收集批处理项
            batch_items = []
            while not self._queue.empty() and len(batch_items) < self.batch_size:
                try:
                    batch_items.append(self._queue.get_nowait())
                except queue.Empty:
                    break
                    
            if not batch_items:
                return []
                
            # 更新最后刷新时间
            self._last_flush_time = time.time()
            
            # 获取连接并执行批处理
            conn = None
            try:
                conn = self.connection_pool.get_connection()
                results = self._process_batch(conn, batch_items)
                return results
            except Exception as e:
                logger.error(f"批处理失败: {str(e)}")
                # 将项放回队列以便重试
                for item in batch_items:
                    try:
                        self._queue.put(item, block=False)
                    except queue.Full:
                        logger.error(f"队列已满，无法重新加入项: {item}")
                raise
            finally:
                if conn:
                    self.connection_pool.release_connection(conn)
    
    async def async_flush(self) -> List[Any]:
        """异步刷新队列执行批处理"""
        if self._queue.empty():
            return []
            
        # 使用run_in_executor在线程池中执行阻塞操作
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.flush)
    
    def _auto_flush_worker(self) -> None:
        """自动刷新工作线程"""
        while not self._shutdown:
            try:
                # 检查是否需要刷新
                now = time.time()
                if not self._queue.empty() and (now - self._last_flush_time) >= self._flush_interval:
                    self.flush()
                    
                # 睡眠一段时间
                time.sleep(min(0.1, self._flush_interval / 10))
            except Exception as e:
                logger.error(f"自动刷新线程异常: {str(e)}")
    
    @abstractmethod
    def _process_batch(self, conn: T, batch_items: List[Any]) -> List[Any]:
        """执行批处理的具体实现
        
        由子类实现，处理特定类型的批处理逻辑
        
        Args:
            conn: 数据库连接
            batch_items: 待处理项列表
            
        Returns:
            处理结果列表
        """
        pass
    
    def shutdown(self) -> None:
        """关闭批处理器"""
        self._shutdown = True
        
        # 等待刷新线程结束
        if self._flush_thread.is_alive():
            self._flush_thread.join(timeout=5)
            
        # 最后一次刷新队列
        if not self._queue.empty():
            try:
                self.flush()
            except Exception as e:
                logger.error(f"最终刷新失败: {str(e)}")
