"""
数据集API端点

提供数据集管理功能
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User as UserModel
from enterprise_kb.schemas.dataset import (
    DatasetCreate, 
    DatasetUpdate, 
    DatasetDeleteRequest,
    Dataset,
    DatasetResponse,
    DatasetListResponse
)
from enterprise_kb.services.auth import AuthService
from enterprise_kb.services.dataset import DatasetService

router = APIRouter(prefix="/datasets", tags=["数据集"])


@router.post("", response_model=DatasetResponse, status_code=status.HTTP_201_CREATED)
async def create_dataset(
    dataset_data: DatasetCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    创建数据集
    """
    dataset_service = DatasetService(db)
    
    try:
        dataset = await dataset_service.create_dataset(
            dataset_data=dataset_data,
            user_id=current_user.id
        )
        
        return {
            "code": 0,
            "data": dataset
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.delete("", status_code=status.HTTP_200_OK)
async def delete_datasets(
    delete_data: DatasetDeleteRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    删除数据集
    """
    dataset_service = DatasetService(db)
    
    try:
        await dataset_service.delete_datasets(
            dataset_ids=delete_data.ids,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.put("/{dataset_id}", status_code=status.HTTP_200_OK)
async def update_dataset(
    dataset_id: str,
    dataset_data: DatasetUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    更新数据集
    """
    dataset_service = DatasetService(db)
    
    try:
        await dataset_service.update_dataset(
            dataset_id=dataset_id,
            dataset_data=dataset_data,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.get("", response_model=DatasetListResponse)
async def list_datasets(
    page: int = Query(1, description="页码，默认为1"),
    page_size: int = Query(30, description="每页大小，默认为30"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序排序"),
    name: Optional[str] = Query(None, description="数据集名称"),
    id: Optional[str] = Query(None, description="数据集ID"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    获取数据集列表
    """
    dataset_service = DatasetService(db)
    
    try:
        datasets = await dataset_service.list_datasets(
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            orderby=orderby,
            desc=desc,
            name=name,
            id=id
        )
        
        return {
            "code": 0,
            "data": datasets
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        ) 