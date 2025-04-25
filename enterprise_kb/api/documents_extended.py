"""扩展的文档管理API路由"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body, Query, Depends
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

from enterprise_kb.models.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse, 
    DocumentStatus, DocumentMetadata, DocumentList
)
from enterprise_kb.services.document_service import DocumentService

router = APIRouter(prefix="/api/v1/documents", tags=["文档管理扩展"])

# 创建文档服务实例
document_service = DocumentService()

class BulkDeleteRequest(BaseModel):
    """批量删除请求模型"""
    doc_ids: List[str]

class DocumentProcessResponse(BaseModel):
    """文档处理响应模型"""
    success: bool
    doc_id: str
    message: Optional[str] = None

# 单文档操作
@router.post("/", status_code=201, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    datasource: Optional[str] = Form("primary"),
    metadata: Optional[str] = Form("{}")
):
    """
    上传文档并处理索引到向量库
    
    Args:
        file: 上传的文件
        title: 文档标题，如果为空则使用文件名
        description: 文档描述
        datasource: 数据源名称，默认为primary
        metadata: JSON格式的元数据
        
    Returns:
        处理后的文档信息
    """
    try:
        import json
        # 解析元数据
        metadata_dict = json.loads(metadata) if metadata else {}
        
        # 创建文档元数据
        doc_metadata = DocumentMetadata(**metadata_dict)
        document_data = DocumentCreate(
            title=title,
            description=description,
            metadata=doc_metadata
        )
        
        # 调用服务处理文档
        result = await document_service.create_document(
            file=file.file,
            filename=file.filename,
            document_data=document_data,
            datasource=datasource
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@router.get("/{doc_id}", response_model=DocumentResponse)
async def get_document(doc_id: str):
    """
    获取文档详情
    
    Args:
        doc_id: 文档ID
        
    Returns:
        文档详情
    """
    doc = await document_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc

@router.put("/{doc_id}", response_model=DocumentResponse)
async def update_document(doc_id: str, update_data: DocumentUpdate):
    """
    更新文档元数据
    
    Args:
        doc_id: 文档ID
        update_data: 更新数据
        
    Returns:
        更新后的文档信息
    """
    doc = await document_service.update_document(doc_id, update_data)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc

@router.delete("/{doc_id}", response_model=DocumentProcessResponse)
async def delete_document(doc_id: str):
    """
    删除文档
    
    Args:
        doc_id: 文档ID
        
    Returns:
        删除结果
    """
    success = await document_service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="文档不存在")
    
    return DocumentProcessResponse(
        success=True,
        doc_id=doc_id,
        message="文档已成功删除"
    )

# 批量操作
@router.post("/bulk/delete", response_model=List[DocumentProcessResponse])
async def bulk_delete_documents(request: BulkDeleteRequest):
    """
    批量删除文档
    
    Args:
        request: 包含文档ID列表的请求
        
    Returns:
        每个文档的删除结果
    """
    results = []
    
    for doc_id in request.doc_ids:
        try:
            success = await document_service.delete_document(doc_id)
            results.append(DocumentProcessResponse(
                success=success,
                doc_id=doc_id,
                message="文档已成功删除" if success else "文档不存在"
            ))
        except Exception as e:
            results.append(DocumentProcessResponse(
                success=False,
                doc_id=doc_id,
                message=f"删除失败: {str(e)}"
            ))
    
    return results

@router.get("/", response_model=DocumentList)
async def list_documents(
    skip: int = Query(0, description="跳过的记录数"),
    limit: int = Query(100, description="返回的最大记录数"),
    status: Optional[DocumentStatus] = Query(None, description="文档状态过滤"),
    datasource: Optional[str] = Query(None, description="数据源过滤")
):
    """
    获取文档列表
    
    Args:
        skip: 跳过的记录数
        limit: 返回的最大记录数
        status: 文档状态过滤
        datasource: 数据源过滤
        
    Returns:
        文档列表
    """
    return await document_service.list_documents(
        skip=skip,
        limit=limit,
        status=status,
        datasource=datasource
    ) 