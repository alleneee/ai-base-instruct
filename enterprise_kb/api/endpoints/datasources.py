"""数据源管理API端点"""
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from enterprise_kb.storage.vector_store_manager import get_vector_store_manager, VectorStoreInfo
from enterprise_kb.storage.datasource.registry import list_datasource_types
from enterprise_kb.core.auth import get_current_active_user
from enterprise_kb.db.models.users import User

router = APIRouter(prefix="/datasources", tags=["数据源管理"])


class DataSourceCreate(BaseModel):
    """数据源创建模型"""
    
    type: str = Field(..., description="数据源类型")
    name: str = Field(..., description="数据源名称")
    description: Optional[str] = Field(None, description="数据源描述")
    config: Dict[str, Any] = Field(default_factory=dict, description="数据源配置")


@router.get("/types", response_model=Dict[str, str])
async def get_datasource_types(
    current_user: User = Depends(get_current_active_user)
):
    """获取所有可用的数据源类型"""
    return list_datasource_types()


@router.get("/", response_model=List[VectorStoreInfo])
async def list_datasources(
    current_user: User = Depends(get_current_active_user)
):
    """列出所有数据源"""
    vector_store_manager = get_vector_store_manager()
    return await vector_store_manager.list_data_sources()


@router.get("/{name}", response_model=VectorStoreInfo)
async def get_datasource(
    name: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取数据源详细信息"""
    vector_store_manager = get_vector_store_manager()
    info = await vector_store_manager.get_data_source_info(name)
    
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据源 '{name}' 不存在"
        )
        
    return info


@router.post("/", response_model=VectorStoreInfo)
async def create_datasource(
    datasource: DataSourceCreate,
    current_user: User = Depends(get_current_active_user)
):
    """创建新数据源"""
    vector_store_manager = get_vector_store_manager()
    
    # 检查数据源类型是否有效
    datasource_types = list_datasource_types()
    if datasource.type not in datasource_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"不支持的数据源类型: {datasource.type}"
        )
    
    try:
        # 添加数据源
        config = datasource.config.copy()
        if datasource.description:
            config["description"] = datasource.description
            
        await vector_store_manager.add_data_source(
            source_type=datasource.type,
            name=datasource.name,
            config=config
        )
        
        # 获取新创建的数据源信息
        info = await vector_store_manager.get_data_source_info(datasource.name)
        if not info:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="创建数据源成功，但获取信息失败"
            )
            
        return info
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建数据源失败: {str(e)}"
        )


@router.delete("/{name}", response_model=Dict[str, bool])
async def delete_datasource(
    name: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除数据源"""
    vector_store_manager = get_vector_store_manager()
    
    # 检查数据源是否存在
    info = await vector_store_manager.get_data_source_info(name)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据源 '{name}' 不存在"
        )
    
    # 删除数据源
    success = await vector_store_manager.remove_data_source(name)
    return {"success": success}


@router.get("/{name}/health", response_model=Dict[str, bool])
async def check_datasource_health(
    name: str,
    current_user: User = Depends(get_current_active_user)
):
    """检查数据源健康状态"""
    vector_store_manager = get_vector_store_manager()
    
    # 检查数据源是否存在
    info = await vector_store_manager.get_data_source_info(name)
    if not info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"数据源 '{name}' 不存在"
        )
    
    # 检查健康状态
    health = await vector_store_manager.health_check(name)
    return health 