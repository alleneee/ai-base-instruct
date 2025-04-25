"""文档管理端点模块"""
import logging
from typing import Optional, Query
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Depends, status
from fastapi.responses import JSONResponse
from fastapi_pagination import Page, paginate
from sqlalchemy.ext.asyncio import AsyncSession

from enterprise_kb.core.auth import User, current_active_user
from enterprise_kb.core.cache import cached, cache
from enterprise_kb.core.limiter import default_rate_limiter
from enterprise_kb.db.session import get_async_session
from enterprise_kb.schemas.documents import (
    DocumentCreate, DocumentUpdate, DocumentResponse, DocumentStatus, DocumentList
)
from enterprise_kb.schemas.auth import ErrorResponse
from enterprise_kb.services.document_service import DocumentService
from enterprise_kb.core.config.settings import settings

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
    status_code=status.HTTP_201_CREATED,
    summary="上传新文档",
    description="上传新文档并处理"
)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    datasource: Optional[str] = Query(None, description="数据源名称"),
    user: User = Depends(current_active_user)
):
    """上传新文档"""
    try:
        # 创建文档服务实例
        service = DocumentService()
        
        # 创建文档请求对象
        document_data = DocumentCreate(
            title=title,
            description=description
        )
        
        # 上传文档
        result = await service.create_document(
            file.file, 
            file.filename, 
            document_data,
            datasource=datasource
        )
        
        return result
    except Exception as e:
        logger.error(f"上传文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"上传文档失败: {str(e)}")

@router.get(
    "",
    response_model=DocumentList,
    summary="获取文档列表",
    description="获取所有文档的列表"
)
async def list_documents(
    skip: int = Query(0, ge=0, description="跳过的记录数"),
    limit: int = Query(100, ge=1, le=1000, description="返回的记录数"),
    status: Optional[DocumentStatus] = Query(None, description="文档状态过滤"),
    datasource: Optional[str] = Query(None, description="数据源过滤"),
    user: User = Depends(current_active_user)
):
    """获取文档列表"""
    try:
        service = DocumentService()
        documents = await service.list_documents(
            skip=skip, 
            limit=limit, 
            status=status,
            datasource=datasource
        )
        
        return documents
    except Exception as e:
        logger.error(f"获取文档列表失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文档列表失败: {str(e)}")

@router.get(
    "/{doc_id}",
    response_model=DocumentResponse,
    summary="获取文档详情",
    description="获取文档的详细信息"
)
@cached(expire=60)  # 缓存1分钟
async def get_document(
    doc_id: str,
    user: User = Depends(current_active_user)
):
    """获取文档详情"""
    try:
        service = DocumentService()
        document = await service.get_document(doc_id)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文档 {doc_id} 不存在"
            )
            
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取文档失败: {str(e)}")

@router.put(
    "/{doc_id}",
    response_model=DocumentResponse,
    summary="更新文档信息",
    description="更新文档的元数据信息"
)
async def update_document(
    doc_id: str,
    update_data: DocumentUpdate,
    user: User = Depends(current_active_user)
):
    """更新文档信息"""
    try:
        service = DocumentService()
        document = await service.update_document(doc_id, update_data)
        
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文档 {doc_id} 不存在"
            )
            
        # 清除缓存
        cache.delete(f"document:{doc_id}")
        
        return document
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"更新文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"更新文档失败: {str(e)}")

@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除文档",
    description="删除文档及其相关数据"
)
async def delete_document(
    doc_id: str,
    user: User = Depends(current_active_user)
):
    """删除文档"""
    try:
        service = DocumentService()
        success = await service.delete_document(doc_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文档 {doc_id} 不存在"
            )
            
        # 清除缓存
        cache.delete(f"document:{doc_id}")
        cache.delete("documents:list")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除文档失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"删除文档失败: {str(e)}") 