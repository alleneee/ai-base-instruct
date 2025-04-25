"""
数据库查询示例

演示如何使用SQLAlchemy执行各种复杂查询
"""
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

from sqlalchemy import and_, or_, not_, func, desc, select, text
from sqlalchemy.orm import Session, joinedload, aliased

from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User, Role, Permission


def get_active_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    """获取活跃用户"""
    return db.query(User).filter(User.is_active == True).offset(skip).limit(limit).all()


def search_users_by_email(db: Session, email_pattern: str) -> List[User]:
    """通过邮箱模式搜索用户"""
    return db.query(User).filter(User.email.like(f"%{email_pattern}%")).all()


def get_users_with_roles(db: Session) -> List[User]:
    """获取带有角色的用户"""
    return db.query(User).options(joinedload(User.roles)).all()


def get_users_by_creation_date(
    db: Session, start_date: datetime, end_date: datetime
) -> List[User]:
    """按创建日期获取用户"""
    return db.query(User).filter(
        User.created_at.between(start_date, end_date)
    ).all()


def get_users_by_role_name(db: Session, role_name: str) -> List[User]:
    """按角色名称获取用户"""
    return db.query(User).join(User.roles).filter(Role.name == role_name).all()


def get_roles_with_permissions(db: Session) -> List[Role]:
    """获取带有权限的角色"""
    return db.query(Role).options(joinedload(Role.permissions)).all()


def get_user_count_by_role(db: Session) -> Dict[str, int]:
    """获取每个角色的用户数量"""
    result = {}
    query = db.query(Role.name, func.count(User.id)).join(
        Role.users
    ).group_by(Role.name).all()
    
    for role_name, count in query:
        result[role_name] = count
    
    return result


def get_recently_active_users(db: Session, days: int = 7) -> List[User]:
    """获取最近活跃的用户"""
    since_date = datetime.utcnow() - timedelta(days=days)
    
    return db.query(User).filter(
        User.updated_at >= since_date
    ).order_by(desc(User.updated_at)).all()


def find_users_with_permission(
    db: Session, resource: str, action: str
) -> List[User]:
    """查找具有特定权限的用户"""
    return db.query(User).join(
        User.roles
    ).join(
        Role.permissions
    ).filter(
        and_(
            Permission.resource == resource,
            Permission.action == action
        )
    ).distinct().all()


def complex_user_query(
    db: Session,
    username_pattern: Optional[str] = None,
    email_pattern: Optional[str] = None,
    is_active: Optional[bool] = None,
    role_names: Optional[List[str]] = None,
) -> List[User]:
    """复杂用户查询示例"""
    # 构建基础查询
    query = db.query(User).distinct()
    
    # 条件过滤
    filters = []
    
    if username_pattern:
        filters.append(User.username.like(f"%{username_pattern}%"))
    
    if email_pattern:
        filters.append(User.email.like(f"%{email_pattern}%"))
    
    if is_active is not None:
        filters.append(User.is_active == is_active)
    
    if role_names:
        query = query.join(User.roles)
        filters.append(Role.name.in_(role_names))
    
    # 应用过滤器
    if filters:
        query = query.filter(and_(*filters))
    
    # 执行查询
    return query.all()


def raw_sql_example(db: Session) -> List[Dict[str, Any]]:
    """原始SQL查询示例"""
    # 使用text()构造SQL查询
    sql = text("""
        SELECT u.id, u.username, u.email, r.name as role_name
        FROM users u
        JOIN user_role ur ON u.id = ur.user_id
        JOIN roles r ON r.id = ur.role_id
        WHERE u.is_active = :is_active
        ORDER BY u.username
    """)
    
    # 执行查询
    result = db.execute(sql, {"is_active": True})
    
    # 转换结果为字典列表
    return [dict(row) for row in result] 