"""
文档API端点

提供数据集内文档管理功能
"""
from typing import Any, List, Optional, Dict
import os
from fastapi import (
    APIRouter, 
    Depends, 
    HTTPException, 
    Query, 
    status, 
    UploadFile, 
    File, 
    Form,
    BackgroundTasks
)
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session
from pathlib import Path
from uuid import uuid4
from fastapi_pagination import Page, paginate
from fastapi_limiter.depends import RateLimiter

from enterprise_kb.core.config.settings import settings
from enterprise_kb.db.database import get_db
from enterprise_kb.db.models.user import User as UserModel
from enterprise_kb.schemas.document import (
    DocumentUpdate,
    DocumentDeleteRequest,
    DocumentParseRequest,
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentCreate,
    DocumentResponse,
    DocumentBatchRequest
)
from enterprise_kb.services.auth import AuthService
from enterprise_kb.services.document import DocumentService
from enterprise_kb.services.tasks import process_document, batch_process_documents

router = APIRouter()
logger = logging.getLogger(__name__)


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


@router.post(
    "/upload",
    response_model=Dict[str, Any],
    dependencies=[Depends(RateLimiter(times=5, seconds=60))],
    summary="上传单个文档并将其加入处理队列"
)
async def upload_document(
    file: UploadFile = File(...),
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    上传单个文档并通过Celery异步处理
    
    Args:
        file: 要上传的文件
        metadata: 文档的额外元数据
        
    Returns:
        包含任务ID和文件信息的字典
    """
    try:
        # 确保上传目录存在
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一文件名并保存文件
        file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
        unique_filename = f"{uuid4()}{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)
        
        # 保存上传的文件
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        # 准备文档元数据
        file_metadata = {
            "original_filename": file.filename,
            "content_type": file.content_type,
            "size": os.path.getsize(file_path)
        }
        
        # 合并用户提供的元数据
        if metadata:
            file_metadata.update(metadata)
        
        # 提交Celery任务进行处理
        task_result = process_document.delay(file_path, file_metadata)
        
        return {
            "status": "success",
            "message": "文档已上传并加入处理队列",
            "task_id": task_result.id,
            "file_info": {
                "path": file_path,
                "original_filename": file.filename,
                "size": os.path.getsize(file_path)
            }
        }
    except Exception as e:
        logger.error(f"文档上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"文档上传失败: {str(e)}"
        )


@router.post(
    "/batch-upload",
    response_model=Dict[str, Any],
    dependencies=[Depends(RateLimiter(times=2, seconds=60))],
    summary="批量上传多个文档并将其加入处理队列"
)
async def batch_upload_documents(
    files: List[UploadFile] = File(...),
    common_metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    批量上传多个文档并通过Celery异步处理
    
    Args:
        files: 要上传的文件列表
        common_metadata: 所有文档共享的元数据
        
    Returns:
        包含批处理任务信息的字典
    """
    try:
        if not files:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="至少需要上传一个文件"
            )
        
        # 确保上传目录存在
        upload_dir = Path(settings.UPLOAD_DIR)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # 保存所有上传的文件
        file_paths = []
        for file in files:
            file_ext = os.path.splitext(file.filename)[1] if file.filename else ""
            unique_filename = f"{uuid4()}{file_ext}"
            file_path = os.path.join(upload_dir, unique_filename)
            
            # 保存文件
            with open(file_path, "wb") as buffer:
                buffer.write(await file.read())
            
            file_paths.append(file_path)
        
        # 提交批处理任务
        task_result = batch_process_documents.delay(file_paths, common_metadata)
        
        return {
            "status": "success",
            "message": f"已提交 {len(files)} 个文档进行批量处理",
            "task_id": task_result.id,
            "files_count": len(files)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"批量文档上传失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量文档上传失败: {str(e)}"
        )


@router.get(
    "/task/{task_id}",
    response_model=Dict[str, Any],
    summary="获取文档处理任务的状态"
)
async def get_task_status(task_id: str) -> Dict[str, Any]:
    """
    获取指定任务ID的处理状态
    
    Args:
        task_id: Celery任务ID
        
    Returns:
        包含任务状态信息的字典
    """
    try:
        from celery.result import AsyncResult
        from enterprise_kb.core.celery_app import celery_app
        
        # 获取任务结果
        task_result = AsyncResult(task_id, app=celery_app)
        
        response = {
            "task_id": task_id,
            "status": task_result.status,
        }
        
        # 添加结果或错误信息（如果有）
        if task_result.successful():
            response["result"] = task_result.result
        elif task_result.failed():
            response["error"] = str(task_result.result)
        elif task_result.status == "PROGRESS":
            response["progress"] = task_result.info
        
        return response
    except Exception as e:
        logger.error(f"获取任务状态失败: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取任务状态失败: {str(e)}"
        ) 