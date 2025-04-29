"""通用依赖项模块"""
from enum import Enum
from typing import Annotated, Dict, List, Optional, Type, TypeVar

from fastapi import Depends, Query
from fastapi_pagination import Page, Params, paginate
from pydantic import BaseModel, create_model

# 泛型类型变量
T = TypeVar('T')

# 排序方向枚举
class SortDirection(str, Enum):
    """排序方向枚举"""
    ASC = "asc"
    DESC = "desc"

# 分页参数依赖
def pagination_params(
    page: int = Query(1, ge=1, description="页码，从1开始"),
    size: int = Query(20, ge=1, le=100, description="每页条数，最大100")
) -> Params:
    """
    分页参数依赖
    
    Args:
        page: 页码，从1开始
        size: 每页条数，最大100
        
    Returns:
        分页参数对象
    """
    return Params(page=page, size=size)

# 分页结果类型构造函数
def paginated_response_model(item_model: Type[BaseModel]) -> Type[Page]:
    """
    创建分页响应模型
    
    Args:
        item_model: 列表项模型
        
    Returns:
        分页响应模型
    """
    return Page[item_model]

# 排序参数依赖
def sort_params(
    sort_by: Optional[str] = Query(None, description="排序字段"),
    sort_dir: SortDirection = Query(SortDirection.ASC, description="排序方向")
) -> Dict[str, str]:
    """
    排序参数依赖
    
    Args:
        sort_by: 排序字段
        sort_dir: 排序方向
        
    Returns:
        排序参数字典
    """
    if not sort_by:
        return {}
        
    return {"sort_by": sort_by, "sort_dir": sort_dir}

# 创建过滤器模型
def create_filter_model(
    name: str,
    **field_definitions
) -> Type[BaseModel]:
    """
    创建过滤器模型
    
    Args:
        name: 模型名称
        field_definitions: 字段定义
        
    Returns:
        过滤器模型类
    """
    return create_model(
        name,
        **{
            key: (Optional[val_type], None)
            for key, val_type in field_definitions.items()
        }
    )

# 通用依赖类型
PaginationDep = Annotated[Params, Depends(pagination_params)]
SortDep = Annotated[Dict[str, str], Depends(sort_params)] 