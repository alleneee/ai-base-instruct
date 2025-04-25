"""
块API端点

提供数据集内块管理功能
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User as UserModel
from enterprise_kb.schemas.chunk import (
    ChunkCreate,
    ChunkUpdate,
    ChunkDeleteRequest,
    ChunkResponse,
    ChunkListResponse
)
from enterprise_kb.services.auth import AuthService
from enterprise_kb.services.chunk import ChunkService

router = APIRouter()


@router.post("/datasets/{dataset_id}/documents/{document_id}/chunks", response_model=ChunkResponse, status_code=status.HTTP_201_CREATED)
async def add_chunk(
    dataset_id: str,
    document_id: str,
    chunk_data: ChunkCreate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    向指定文档添加块
    """
    chunk_service = ChunkService(db)
    
    try:
        chunk = await chunk_service.add_chunk(
            dataset_id=dataset_id,
            document_id=document_id,
            chunk_data=chunk_data,
            user_id=current_user.id
        )
        
        return {
            "code": 0,
            "data": {"chunk": chunk}
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.get("/datasets/{dataset_id}/documents/{document_id}/chunks", response_model=ChunkListResponse)
async def list_chunks(
    dataset_id: str,
    document_id: str,
    keywords: Optional[str] = Query(None, description="关键词"),
    page: int = Query(1, description="页码，默认为1"),
    page_size: int = Query(1024, description="每页大小，默认为1024"),
    id: Optional[str] = Query(None, description="块ID"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    获取指定文档中的块列表
    """
    chunk_service = ChunkService(db)
    
    try:
        chunks = await chunk_service.list_chunks(
            dataset_id=dataset_id,
            document_id=document_id,
            user_id=current_user.id,
            keywords=keywords,
            page=page,
            page_size=page_size,
            chunk_id=id
        )
        
        return {
            "code": 0,
            "data": chunks
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.delete("/datasets/{dataset_id}/documents/{document_id}/chunks", status_code=status.HTTP_200_OK)
async def delete_chunks(
    dataset_id: str,
    document_id: str,
    delete_data: ChunkDeleteRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    删除指定文档中的块
    """
    chunk_service = ChunkService(db)
    
    try:
        await chunk_service.delete_chunks(
            dataset_id=dataset_id,
            document_id=document_id,
            chunk_ids=delete_data.chunk_ids,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.put("/datasets/{dataset_id}/documents/{document_id}/chunks/{chunk_id}", status_code=status.HTTP_200_OK)
async def update_chunk(
    dataset_id: str,
    document_id: str,
    chunk_id: str,
    chunk_data: ChunkUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    更新指定块的内容或配置
    """
    chunk_service = ChunkService(db)
    
    try:
        await chunk_service.update_chunk(
            dataset_id=dataset_id,
            document_id=document_id,
            chunk_id=chunk_id,
            chunk_data=chunk_data,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        ) 