"""
文档API端点

提供数据集内文档管理功能
"""
from typing import Any, List, Optional
import os
from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    Query, 
    status, 
    UploadFile, 
    File, 
    Form
)
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User as UserModel
from enterprise_kb.schemas.document import (
    DocumentUpdate,
    DocumentDeleteRequest,
    DocumentParseRequest,
    DocumentUploadResponse,
    DocumentListResponse
)
from enterprise_kb.services.auth import AuthService
from enterprise_kb.services.document import DocumentService

router = APIRouter()


@router.post("/datasets/{dataset_id}/documents", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    dataset_id: str,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    上传文档到指定数据集
    """
    document_service = DocumentService(db)
    
    try:
        documents = await document_service.upload_documents(
            dataset_id=dataset_id,
            files=files,
            user_id=current_user.id
        )
        
        return {
            "code": 0,
            "data": documents
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.put("/datasets/{dataset_id}/documents/{document_id}", status_code=status.HTTP_200_OK)
async def update_document(
    dataset_id: str,
    document_id: str,
    document_data: DocumentUpdate,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    更新指定文档的配置
    """
    document_service = DocumentService(db)
    
    try:
        await document_service.update_document(
            dataset_id=dataset_id,
            document_id=document_id,
            document_data=document_data,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.get("/datasets/{dataset_id}/documents/{document_id}")
async def download_document(
    dataset_id: str,
    document_id: str,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    从指定数据集下载文档
    """
    document_service = DocumentService(db)
    
    try:
        file_path = await document_service.get_document_path(
            dataset_id=dataset_id,
            document_id=document_id,
            user_id=current_user.id
        )
        
        filename = os.path.basename(file_path)
        return FileResponse(
            path=file_path, 
            filename=filename,
            media_type="application/octet-stream"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.get("/datasets/{dataset_id}/documents", response_model=DocumentListResponse)
async def list_documents(
    dataset_id: str,
    page: int = Query(1, description="页码，默认为1"),
    page_size: int = Query(30, description="每页大小，默认为30"),
    orderby: str = Query("create_time", description="排序字段"),
    desc: bool = Query(True, description="是否降序排序"),
    keywords: Optional[str] = Query(None, description="关键词"),
    id: Optional[str] = Query(None, description="文档ID"),
    name: Optional[str] = Query(None, description="文档名称"),
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    获取指定数据集中的文档列表
    """
    document_service = DocumentService(db)
    
    try:
        documents = await document_service.list_documents(
            dataset_id=dataset_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            orderby=orderby,
            desc=desc,
            keywords=keywords,
            id=id,
            name=name
        )
        
        return {
            "code": 0,
            "data": documents
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.delete("/datasets/{dataset_id}/documents", status_code=status.HTTP_200_OK)
async def delete_documents(
    dataset_id: str,
    delete_data: DocumentDeleteRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    删除指定数据集中的文档
    """
    document_service = DocumentService(db)
    
    try:
        await document_service.delete_documents(
            dataset_id=dataset_id,
            document_ids=delete_data.ids,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.post("/datasets/{dataset_id}/chunks", status_code=status.HTTP_200_OK)
async def parse_documents(
    dataset_id: str,
    parse_data: DocumentParseRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    解析指定数据集中的文档
    """
    document_service = DocumentService(db)
    
    try:
        await document_service.parse_documents(
            dataset_id=dataset_id,
            document_ids=parse_data.document_ids,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        )


@router.delete("/datasets/{dataset_id}/chunks", status_code=status.HTTP_200_OK)
async def stop_parsing_documents(
    dataset_id: str,
    parse_data: DocumentParseRequest,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(AuthService.get_current_active_user)
) -> Any:
    """
    停止解析指定数据集中的文档
    """
    document_service = DocumentService(db)
    
    try:
        await document_service.stop_parsing_documents(
            dataset_id=dataset_id,
            document_ids=parse_data.document_ids,
            user_id=current_user.id
        )
        
        return {"code": 0}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": 102, "message": str(e)}
        ) 