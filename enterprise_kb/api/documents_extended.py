"""扩展的文档管理API路由"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body, Query, Depends, BackgroundTasks
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import json
import os

from enterprise_kb.models.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse, 
    DocumentStatus, DocumentMetadata, DocumentList
)
from enterprise_kb.services.document_service import DocumentService
from enterprise_kb.storage.document_processor import get_document_processor
from enterprise_kb.core.config.settings import settings

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

class DocumentMetadata(BaseModel):
    """文档元数据模型"""
    title: Optional[str] = Field(None, description="文档标题")
    author: Optional[str] = Field(None, description="文档作者")
    tags: Optional[List[str]] = Field(None, description="文档标签")
    description: Optional[str] = Field(None, description="文档描述")
    source: Optional[str] = Field(None, description="文档来源")
    custom_data: Optional[Dict[str, Any]] = Field(None, description="自定义元数据")

class DocumentResponse(BaseModel):
    """文档处理响应模型"""
    doc_id: str = Field(..., description="文档ID")
    file_name: str = Field(..., description="文件名")
    status: str = Field(..., description="处理状态")
    node_count: int = Field(..., description="节点数量")
    text_chars: int = Field(..., description="文本字符数")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    processing_strategy: Optional[Dict[str, Any]] = Field(None, description="处理策略")

class ProcessingStrategyRequest(BaseModel):
    """处理策略请求"""
    prefer_markdown: Optional[bool] = Field(None, description="是否优先使用Markdown转换")
    custom_chunk_size: Optional[int] = Field(None, description="自定义分块大小")
    custom_chunk_overlap: Optional[int] = Field(None, description="自定义分块重叠")

async def process_document_background(
    file_path: str,
    metadata: Dict[str, Any],
    convert_to_md: Optional[bool] = None,
    strategy: Optional[Dict[str, Any]] = None
):
    """后台处理文档"""
    document_processor = get_document_processor()
    try:
        document_processor.process_document(
            file_path=file_path, 
            metadata=metadata, 
            convert_to_md=convert_to_md,
            strategy=strategy
        )
    except Exception as e:
        # 这里可以添加更多的错误处理逻辑
        print(f"文档处理失败: {str(e)}")

# 单文档操作
@router.post("/", status_code=201, response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    datasource: Optional[str] = Form("primary"),
    metadata: Optional[str] = Form(None),
    background_processing: bool = Form(False),
    convert_to_markdown: Optional[bool] = Form(None),
    auto_process: bool = Form(True),
    strategy_json: Optional[str] = Form(None),
    background_tasks: BackgroundTasks = None
):
    """
    上传文档并处理索引到向量库
    
    Args:
        file: 上传的文件
        title: 文档标题，如果为空则使用文件名
        description: 文档描述
        datasource: 数据源名称，默认为primary
        metadata: JSON格式的元数据
        background_processing: 是否在后台处理
        convert_to_markdown: 是否将文档转换为Markdown格式(None表示自动决定)
        auto_process: 是否自动分析并处理文档
        strategy_json: 自定义处理策略(JSON格式)
        
    Returns:
        处理后的文档信息
    """
    try:
        # 获取文档处理器
        document_processor = get_document_processor()
        
        # 读取上传的文件内容
        file_content = await file.read()
        
        # 保存文件
        file_path = document_processor.save_uploaded_file(file_content, file.filename)
        
        # 解析元数据
        parsed_metadata = {}
        if metadata:
            try:
                parsed_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="元数据必须是有效的JSON格式")
                
        # 设置基本元数据
        if title:
            parsed_metadata["title"] = title
        if description:
            parsed_metadata["description"] = description
            
        # 解析处理策略
        custom_strategy = None
        if strategy_json:
            try:
                custom_strategy = json.loads(strategy_json)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="处理策略必须是有效的JSON格式")
                
        # 如果需要自动处理，先分析文档
        document_strategy = None
        if auto_process and not custom_strategy:
            # 分析文档并确定处理策略
            document_strategy = document_processor.determine_processing_strategy(file_path)
        elif custom_strategy:
            # 使用自定义策略
            document_strategy = custom_strategy
        
        # 如果在后台处理
        if background_processing:
            background_tasks.add_task(
                process_document_background, 
                file_path, 
                parsed_metadata,
                convert_to_markdown,
                document_strategy
            )
            
            # 返回临时响应
            return DocumentResponse(
                doc_id="pending",
                file_name=file.filename,
                status="processing",
                node_count=0,
                text_chars=0,
                metadata={
                    "file_path": file_path,
                    "original_filename": file.filename,
                    **parsed_metadata
                },
                processing_strategy=document_strategy
            )
        
        # 处理文档
        result = document_processor.process_document(
            file_path=file_path, 
            metadata=parsed_metadata,
            convert_to_md=convert_to_markdown,
            strategy=document_strategy
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_document(
    file: UploadFile = File(...),
    process_after_analyze: bool = Form(False),
    background_tasks: BackgroundTasks = None
):
    """
    分析文档并返回推荐的处理策略
    
    Args:
        file: 上传的文件
        process_after_analyze: 分析后是否立即处理文档
        
    Returns:
        文档分析结果和推荐处理策略
    """
    try:
        # 获取文档处理器
        document_processor = get_document_processor()
        
        # 读取上传的文件内容
        file_content = await file.read()
        
        # 保存文件
        file_path = document_processor.save_uploaded_file(file_content, file.filename)
        
        # 分析文档
        strategy = document_processor.determine_processing_strategy(file_path)
        
        # 如果需要处理文档
        if process_after_analyze:
            background_tasks.add_task(
                process_document_background,
                file_path,
                {"analysis_result": True},  # 基本元数据
                strategy["should_convert_to_markdown"],
                strategy
            )
            strategy["processing_status"] = "started"
        
        return {
            "file_name": file.filename,
            "file_path": file_path,
            "analysis_result": strategy
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档分析失败: {str(e)}")

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

@router.post("/batch/process", response_model=List[DocumentResponse])
async def batch_process_documents(
    files: List[UploadFile] = File(...),
    metadata: Optional[str] = Form(None),
    auto_process: bool = Form(True),
    background_processing: bool = Form(True),
    background_tasks: BackgroundTasks = None
):
    """
    批量上传并处理文档
    
    Args:
        files: 上传的文件列表
        metadata: 共享元数据(JSON格式)
        auto_process: 是否自动分析处理
        background_processing: 是否在后台处理
        
    Returns:
        批处理结果
    """
    try:
        # 获取文档处理器
        document_processor = get_document_processor()
        
        # 解析元数据
        shared_metadata = {}
        if metadata:
            try:
                shared_metadata = json.loads(metadata)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="元数据必须是有效的JSON格式")
                
        results = []
        for file in files:
            try:
                # 读取上传的文件内容
                file_content = await file.read()
                
                # 保存文件
                file_path = document_processor.save_uploaded_file(file_content, file.filename)
                
                # 如果自动处理，分析文档
                strategy = None
                if auto_process:
                    strategy = document_processor.determine_processing_strategy(file_path)
                
                # 创建每个文件的专有元数据
                file_metadata = {
                    **shared_metadata,
                    "file_name": file.filename,
                    "batch_processing": True
                }
                
                if background_processing:
                    # 添加后台任务
                    background_tasks.add_task(
                        process_document_background,
                        file_path,
                        file_metadata,
                        None,  # 让系统自动决定是否转为Markdown
                        strategy
                    )
                    
                    # 添加临时响应
                    results.append(DocumentResponse(
                        doc_id="pending",
                        file_name=file.filename,
                        status="processing",
                        node_count=0,
                        text_chars=0,
                        metadata={
                            "file_path": file_path,
                            **file_metadata
                        },
                        processing_strategy=strategy
                    ))
                else:
                    # 立即处理
                    result = document_processor.process_document(
                        file_path=file_path,
                        metadata=file_metadata,
                        strategy=strategy
                    )
                    results.append(result)
                    
            except Exception as e:
                # 单个文件失败不应该影响整个批处理
                results.append(DocumentResponse(
                    doc_id="failed",
                    file_name=file.filename,
                    status="failed",
                    node_count=0,
                    text_chars=0,
                    metadata={
                        "error": str(e),
                        **shared_metadata
                    },
                    processing_strategy=None
                ))
                
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"批量处理文档失败: {str(e)}")

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

@router.get("/markdown/{doc_id}", response_model=Dict[str, Any])
async def get_markdown_content(doc_id: str):
    """
    获取文档的Markdown内容
    
    Args:
        doc_id: 文档ID
        
    Returns:
        Markdown内容和元数据
    """
    try:
        # 这里需要实现从数据库中获取文档元数据的逻辑
        # 为了简化示例，假设我们已经有了获取文档元数据的函数
        # metadata = get_document_metadata(doc_id)
        
        # 简化示例：直接查询向量库
        from enterprise_kb.storage.vector_store_manager import get_vector_store_manager
        vector_store_manager = get_vector_store_manager()
        
        # 查询向量库获取文档信息
        # 这里需要根据实际情况实现查询逻辑
        # 简化示例：假设我们直接知道markdown文件路径
        
        # 如果找不到文档
        # if not metadata or "markdown_path" not in metadata:
        #    raise HTTPException(status_code=404, detail=f"找不到文档的Markdown内容: {doc_id}")
        
        # 示例路径，实际应从数据库获取
        # markdown_path = metadata["markdown_path"]
        
        # 简化演示：从processed/markdown目录中查找
        markdown_dir = os.path.join(settings.PROCESSED_DIR, "markdown")
        markdown_files = os.listdir(markdown_dir)
        
        # 查找包含doc_id的文件
        markdown_path = None
        for file in markdown_files:
            if doc_id in file:
                markdown_path = os.path.join(markdown_dir, file)
                break
        
        if not markdown_path or not os.path.exists(markdown_path):
            raise HTTPException(status_code=404, detail=f"找不到文档的Markdown内容: {doc_id}")
        
        # 读取Markdown内容
        with open(markdown_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        return {
            "doc_id": doc_id,
            "content": content,
            "markdown_path": markdown_path
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取Markdown内容失败: {str(e)}") 