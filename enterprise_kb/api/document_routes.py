import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from fastapi_pagination import Page, paginate
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.config.database import get_async_session
from enterprise_kb.core.cache import cached
from enterprise_kb.core.limiter import default_rate_limiter
from enterprise_kb.models.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse, 
    DocumentStatus, DocumentList, ErrorResponse
)
from enterprise_kb.models.users import User, current_active_user
from enterprise_kb.services.document_service import DocumentService
from enterprise_kb.config.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/documents",
    tags=["文档管理"],
    responses={
        404: {"model": ErrorResponse, "description": "未找到资源"},
        500: {"model": ErrorResponse, "description": "服务器内部错误"}
    }
)

# 依赖注入
async def get_document_service(session: AsyncSession = Depends(get_async_session)):
    """获取文档服务实例"""
    return DocumentService(session)

@router.post(
    "",
    response_model=DocumentResponse,
    summary="上传并处理文档",
    description="上传文档文件并进行处理和索引",
    dependencies=[Depends(current_active_user), Depends(default_rate_limiter)]
)
async def create_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    document_service: DocumentService = Depends(get_document_service),
    user: User = Depends(current_active_user)
):
    """上传并处理文档"""
    try:
        # 验证文件类型
        filename = file.filename
        file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
        
        if file_ext not in settings.SUPPORTED_DOCUMENT_TYPES:
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(settings.SUPPORTED_DOCUMENT_TYPES)}"
            )
            
        # 创建文档数据对象
        document_data = DocumentCreate(
            title=title,
            description=description,
        )
        
        # 调用服务处理文档
        result = await document_service.create_document(
            file=file.file,
            filename=filename,
            document_data=document_data,
            user_id=str(user.id)
        )
        
        return result
        
    except ValidationError as e:
        logger.error(f"验证错误: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"处理文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"处理文档失败: {str(e)}")

@router.get(
    "",
    response_model=Page[DocumentResponse],
    summary="获取文档列表",
    description="分页获取文档列表"
)
@cached(expire=60)  # 缓存1分钟
async def list_documents(
    page: int = 1,
    size: int = 20,
    status: Optional[DocumentStatus] = None,
    document_service: DocumentService = Depends(get_document_service),
    user: User = Depends(current_active_user)
):
    """获取文档列表"""
    try:
        result = await document_service.list_documents(
            skip=(page - 1) * size,
            limit=size,
            status=status,
            user_id=str(user.id)
        )
        
        # 使用fastapi-pagination进行分页
        return paginate(result.documents, total=result.total)
        
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")

@router.get(
    "/{doc_id}",
    response_model=DocumentResponse,
    summary="获取文档详情",
    description="根据文档ID获取详细信息"
)
async def get_document(
    doc_id: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """获取文档详情"""
    try:
        result = await document_service.get_document(doc_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档详情失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文档详情失败: {str(e)}")

@router.put(
    "/{doc_id}",
    response_model=DocumentResponse,
    summary="更新文档元数据",
    description="更新文档元数据信息"
)
async def update_document(
    doc_id: str,
    update_data: DocumentUpdate,
    document_service: DocumentService = Depends(get_document_service)
):
    """更新文档元数据"""
    try:
        result = await document_service.update_document(doc_id, update_data)
        if not result:
            raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新文档失败: {str(e)}")

@router.delete(
    "/{doc_id}",
    summary="删除文档",
    description="删除文档及其相关资源"
)
async def delete_document(
    doc_id: str,
    document_service: DocumentService = Depends(get_document_service)
):
    """删除文档"""
    try:
        result = await document_service.delete_document(doc_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"文档 {doc_id} 不存在")
        return JSONResponse(content={"message": f"已成功删除文档 {doc_id}"})
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}") 