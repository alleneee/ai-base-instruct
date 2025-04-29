import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends
from fastapi.responses import JSONResponse
from fastapi_pagination import Page, paginate
from pydantic import ValidationError

from enterprise_kb.api.dependencies.services import DocumentSvc
from enterprise_kb.api.dependencies.auth import UserWithReadPerm, UserWithWritePerm
from enterprise_kb.api.dependencies.common import PaginationDep, SortDep
from enterprise_kb.api.dependencies.responses import response
from enterprise_kb.core.cache import cached
from enterprise_kb.core.limiter import default_rate_limiter
from enterprise_kb.models.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse, 
    DocumentStatus, DocumentList, ErrorResponse
)
from enterprise_kb.models.users import User
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

@router.post(
    "",
    response_model=DocumentResponse,
    summary="上传并处理文档",
    description="上传文档文件并进行处理和索引",
    dependencies=[Depends(default_rate_limiter)]
)
async def create_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    document_service: DocumentSvc = Depends(),
    user: UserWithWritePerm = Depends()
):
    """上传并处理文档"""
    try:
        # 验证文件类型
        filename = file.filename
        file_ext = "." + filename.split(".")[-1].lower() if "." in filename else ""
        
        if file_ext not in settings.SUPPORTED_DOCUMENT_TYPES:
            return response.error(
                message=f"不支持的文件类型: {file_ext}。支持的类型: {', '.join(settings.SUPPORTED_DOCUMENT_TYPES)}",
                status_code=400
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
        return response.error(message=str(e), status_code=400)
    except Exception as e:
        logger.error(f"处理文档失败: {str(e)}")
        return response.error(message=f"处理文档失败: {str(e)}", status_code=500)

@router.get(
    "",
    response_model=Page[DocumentResponse],
    summary="获取文档列表",
    description="分页获取文档列表"
)
@cached(expire=60)  # 缓存1分钟
async def list_documents(
    status: Optional[DocumentStatus] = None,
    pagination: PaginationDep = Depends(),
    sort: SortDep = Depends(),
    document_service: DocumentSvc = Depends(),
    user: UserWithReadPerm = Depends()
):
    """获取文档列表"""
    try:
        skip = (pagination.page - 1) * pagination.size
        result = await document_service.list_documents(
            skip=skip,
            limit=pagination.size,
            status=status,
            user_id=str(user.id),
            **sort
        )
        
        # 使用fastapi-pagination进行分页
        return paginate(result.documents, total=result.total)
        
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}")
        return response.error(message=f"获取文档列表失败: {str(e)}", status_code=500)

@router.get(
    "/{doc_id}",
    response_model=DocumentResponse,
    summary="获取文档详情",
    description="根据文档ID获取详细信息"
)
async def get_document(
    doc_id: str,
    document_service: DocumentSvc = Depends(),
    user: UserWithReadPerm = Depends()
):
    """获取文档详情"""
    try:
        result = await document_service.get_document(doc_id)
        if not result:
            return response.error(message=f"文档 {doc_id} 不存在", status_code=404)
        return result
    except Exception as e:
        logger.error(f"获取文档详情失败: {str(e)}")
        return response.error(message=f"获取文档详情失败: {str(e)}", status_code=500)

@router.put(
    "/{doc_id}",
    response_model=DocumentResponse,
    summary="更新文档元数据",
    description="更新文档元数据信息"
)
async def update_document(
    doc_id: str,
    update_data: DocumentUpdate,
    document_service: DocumentSvc = Depends(),
    user: UserWithWritePerm = Depends()
):
    """更新文档元数据"""
    try:
        result = await document_service.update_document(doc_id, update_data)
        if not result:
            return response.error(message=f"文档 {doc_id} 不存在", status_code=404)
        return result
    except Exception as e:
        logger.error(f"更新文档失败: {str(e)}")
        return response.error(message=f"更新文档失败: {str(e)}", status_code=500)

@router.delete(
    "/{doc_id}",
    summary="删除文档",
    description="删除文档及其相关资源"
)
async def delete_document(
    doc_id: str,
    document_service: DocumentSvc = Depends(),
    user: UserWithWritePerm = Depends()
):
    """删除文档"""
    try:
        result = await document_service.delete_document(doc_id)
        if not result:
            return response.error(message=f"文档 {doc_id} 不存在", status_code=404)
        return response.success(message=f"已成功删除文档 {doc_id}")
    except Exception as e:
        logger.error(f"删除文档失败: {str(e)}")
        return response.error(message=f"删除文档失败: {str(e)}", status_code=500) 