"""数据源管理API路由"""
from fastapi import APIRouter, HTTPException, Body, Query
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from enterprise_kb.storage.vector_store_manager import get_vector_store_manager

router = APIRouter(prefix="/api/v1/datasources", tags=["数据源管理"])

class DataSourceCreateRequest(BaseModel):
    """数据源创建请求模型"""
    source_type: str
    name: str
    config: Dict[str, Any]
    
class DataSourceCreateResponse(BaseModel):
    """数据源创建响应模型"""
    name: str
    status: str
    
class DataSourceDeleteResponse(BaseModel):
    """数据源删除响应模型"""
    success: bool
    message: Optional[str] = None

@router.get("/types")
async def get_datasource_types():
    """
    获取所有可用的数据源类型
    
    Returns:
        可用的数据源类型和描述
    """
    manager = get_vector_store_manager()
    return manager.list_available_datasource_types()

@router.get("/")
async def list_datasources():
    """
    列出所有数据源
    
    Returns:
        数据源列表
    """
    manager = get_vector_store_manager()
    return await manager.list_data_sources()

@router.post("/", status_code=201, response_model=DataSourceCreateResponse)
async def create_datasource(request: DataSourceCreateRequest):
    """
    创建新数据源
    
    Args:
        request: 包含数据源类型、名称和配置的请求
        
    Returns:
        创建结果
    """
    manager = get_vector_store_manager()
    try:
        name = await manager.add_data_source(
            source_type=request.source_type,
            name=request.name,
            config=request.config
        )
        return DataSourceCreateResponse(name=name, status="created")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建数据源失败: {str(e)}")

@router.delete("/{name}", response_model=DataSourceDeleteResponse)
async def delete_datasource(name: str):
    """
    删除数据源
    
    Args:
        name: 数据源名称
        
    Returns:
        删除结果
    """
    manager = get_vector_store_manager()
    success = await manager.remove_data_source(name)
    if not success:
        raise HTTPException(status_code=404, detail="数据源不存在")
    
    return DataSourceDeleteResponse(
        success=True,
        message=f"数据源 {name} 已成功删除"
    )

@router.get("/{name}/health")
async def check_datasource_health(name: str):
    """
    检查数据源健康状态
    
    Args:
        name: 数据源名称
        
    Returns:
        健康检查结果
    """
    manager = get_vector_store_manager()
    health_status = await manager.health_check(name)
    
    if name not in health_status:
        raise HTTPException(status_code=404, detail="数据源不存在")
        
    return {"name": name, "is_healthy": health_status[name]} 