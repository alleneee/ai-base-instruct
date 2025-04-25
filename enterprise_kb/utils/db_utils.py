"""
数据库工具函数

提供数据库事务和批量操作的辅助函数
"""
from contextlib import contextmanager
from typing import Callable, Any, List, Dict, Generator

from sqlalchemy.orm import Session

from enterprise_kb.db.database import SessionLocal


@contextmanager
def get_db_transaction() -> Generator[Session, None, None]:
    """
    提供具有事务控制的数据库会话上下文管理器
    
    使用示例:
    ```python
    with get_db_transaction() as db:
        # 在事务中执行数据库操作
        db.add(some_object)
        # 如果没有异常，事务将自动提交
        # 如果有异常，事务将自动回滚
    ```
    
    Yields:
        Session: 具有事务控制的数据库会话
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


def execute_in_transaction(
    func: Callable[[Session], Any], *args: Any, **kwargs: Any
) -> Any:
    """
    在事务中执行函数
    
    Args:
        func: 要在事务中执行的函数，第一个参数必须是Session
        args: 传递给func的位置参数
        kwargs: 传递给func的关键字参数
        
    Returns:
        Any: 函数的返回值
    """
    with get_db_transaction() as db:
        return func(db, *args, **kwargs)


def batch_insert(
    db: Session, model_class: Any, records: List[Dict[str, Any]]
) -> None:
    """
    批量插入记录
    
    Args:
        db: 数据库会话
        model_class: SQLAlchemy模型类
        records: 要插入的记录字典列表
    """
    db.bulk_insert_mappings(model_class, records)
    db.commit()


def batch_update(
    db: Session, model_class: Any, records: List[Dict[str, Any]]
) -> None:
    """
    批量更新记录
    
    Args:
        db: 数据库会话
        model_class: SQLAlchemy模型类
        records: 要更新的记录字典列表，每个字典必须包含主键
    """
    db.bulk_update_mappings(model_class, records)
    db.commit() 