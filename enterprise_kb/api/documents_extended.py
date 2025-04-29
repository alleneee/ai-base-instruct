"""扩展的文档管理API路由"""
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body, Query, Depends, BackgroundTasks, Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, ConfigDict
import json
import os

from enterprise_kb.models.schemas import (
    DocumentCreate, DocumentUpdate, DocumentResponse,
    DocumentStatus, DocumentMetadata, DocumentList
)
from enterprise_kb.services.document_service import DocumentService
from enterprise_kb.storage.document_processor import get_document_processor
from enterprise_kb.core.config.settings import settings
from enterprise_kb.api.dependencies.services import get_document_service

router = APIRouter(
    prefix="/api/v1/documents", 
    tags=["文档管理"],
    responses={
        400: {
            "description": "请求参数错误",
            "content": {
                "application/json": {
                    "example": {"detail": "元数据必须是有效的JSON格式"}
                }
            }
        },
        404: {
            "description": "资源不存在",
            "content": {
                "application/json": {
                    "example": {"detail": "文档不存在"}
                }
            }
        },
        500: {
            "description": "服务器内部错误",
            "content": {
                "application/json": {
                    "example": {"detail": "文档处理失败: 无法处理PDF文件"}
                }
            }
        }
    }
)

# 这里不再直接初始化DocumentService，而是通过Depends获取

class BulkDeleteRequest(BaseModel):
    """批量删除请求模型"""
    doc_ids: List[str] = Field(..., description="要删除的文档ID列表")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doc_ids": ["doc123", "doc456", "doc789"]
            }
        }
    )

class DocumentProcessResponse(BaseModel):
    """文档处理响应模型"""
    success: bool = Field(..., description="操作是否成功")
    doc_id: str = Field(..., description="文档ID")
    message: Optional[str] = Field(None, description="处理消息")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "doc_id": "doc123",
                "message": "文档已成功处理"
            }
        }
    )

class DocumentMetadata(BaseModel):
    """文档元数据模型"""
    title: Optional[str] = Field(None, description="文档标题")
    author: Optional[str] = Field(None, description="文档作者")
    tags: Optional[List[str]] = Field(None, description="文档标签")
    description: Optional[str] = Field(None, description="文档描述")
    source: Optional[str] = Field(None, description="文档来源")
    custom_data: Optional[Dict[str, Any]] = Field(None, description="自定义元数据")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "title": "企业知识库介绍",
                "author": "张三",
                "tags": ["介绍", "知识库", "企业"],
                "description": "介绍企业知识库平台的基本功能和使用方法",
                "source": "内部文档",
                "custom_data": {
                    "department": "技术部",
                    "priority": "高"
                }
            }
        }
    )

class DocumentResponse(BaseModel):
    """文档处理响应模型"""
    doc_id: str = Field(..., description="文档ID")
    file_name: str = Field(..., description="文件名")
    status: str = Field(..., description="处理状态")
    node_count: int = Field(..., description="节点数量")
    text_chars: int = Field(..., description="文本字符数")
    metadata: Dict[str, Any] = Field(..., description="元数据")
    processing_strategy: Optional[Dict[str, Any]] = Field(None, description="处理策略")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "doc_id": "doc123",
                "file_name": "企业知识库介绍.pdf",
                "status": "success",
                "node_count": 15,
                "text_chars": 12500,
                "metadata": {
                    "title": "企业知识库介绍",
                    "author": "张三",
                    "file_type": ".pdf",
                    "upload_time": "2023-04-12T10:30:00"
                },
                "processing_strategy": {
                    "doc_type": "pdf",
                    "should_convert_to_markdown": True,
                    "chunking_params": {
                        "chunk_size": 1024,
                        "chunk_overlap": 20
                    }
                }
            }
        }
    )

class ProcessingStrategyRequest(BaseModel):
    """处理策略请求"""
    prefer_markdown: Optional[bool] = Field(None, description="是否优先使用Markdown转换")
    custom_chunk_size: Optional[int] = Field(None, description="自定义分块大小")
    custom_chunk_overlap: Optional[int] = Field(None, description="自定义分块重叠")
    use_parallel: Optional[bool] = Field(None, description="是否使用并行处理")
    use_semantic_chunking: Optional[bool] = Field(None, description="是否使用语义分块")
    use_incremental: Optional[bool] = Field(None, description="是否使用增量更新")
    chunking_type: Optional[str] = Field(None, description="分块类型: semantic, hierarchical")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "prefer_markdown": True,
                "custom_chunk_size": 1200,
                "custom_chunk_overlap": 50,
                "use_parallel": True,
                "use_semantic_chunking": True,
                "chunking_type": "semantic"
            }
        }
    )

async def process_document_background(
    file_path: str,
    metadata: Dict[str, Any],
    datasource_name: Optional[str] = "primary",
    use_parallel: Optional[bool] = None,
    use_semantic_chunking: Optional[bool] = None,
    use_incremental: Optional[bool] = None,
    chunking_type: Optional[str] = None
):
    """后台处理文档"""
    document_processor = get_document_processor()
    try:
        await document_processor.process_document(
            file_path=file_path,
            metadata=metadata,
            datasource_name=datasource_name,
            use_parallel=use_parallel,
            use_semantic_chunking=use_semantic_chunking,
            use_incremental=use_incremental,
            chunking_type=chunking_type
        )
    except Exception as e:
        # 这里可以添加更多的错误处理逻辑
        print(f"文档处理失败: {str(e)}")

# 单文档操作
@router.post(
    "/", 
    status_code=201, 
    response_model=DocumentResponse,
    summary="上传并处理文档",
    description="""
    上传文档并处理索引到向量库。支持多种文档格式，包括PDF、Word、文本等。
    
    文档会根据其类型和特征进行智能分析，选择最合适的处理路径。系统支持自动决定是否需要
    将文档转换为Markdown格式，以及使用何种分块策略。
    
    可以选择在后台处理文档，这样API会立即返回，而文档处理将异步进行。
    也可以提供自定义的处理策略，覆盖系统默认的自动分析结果。
    """,
    response_description="处理后的文档信息",
    responses={
        201: {
            "description": "文档上传并处理成功",
            "content": {
                "application/json": {
                    "example": {
                        "doc_id": "doc123",
                        "file_name": "企业知识库介绍.pdf",
                        "status": "success",
                        "node_count": 15,
                        "text_chars": 12500,
                        "metadata": {
                            "title": "企业知识库介绍",
                            "file_type": ".pdf",
                            "upload_time": "2023-04-12T10:30:00"
                        },
                        "processing_strategy": {
                            "doc_type": "pdf",
                            "should_convert_to_markdown": True
                        }
                    }
                }
            }
        }
    }
)
async def upload_document(
    file: UploadFile = File(..., description="要上传的文件"),
    title: Optional[str] = Form(None, description="文档标题，如果为空则使用文件名"),
    description: Optional[str] = Form(None, description="文档描述"),
    datasource: Optional[str] = Form("primary", description="数据源名称，默认为primary"),
    metadata: Optional[str] = Form(None, description="JSON格式的元数据"),
    background_processing: bool = Form(False, description="是否在后台处理"),
    convert_to_markdown: Optional[bool] = Form(None, description="是否将文档转换为Markdown格式(None表示自动决定)"),
    auto_process: bool = Form(True, description="是否自动分析并处理文档"),
    strategy_json: Optional[str] = Form(None, description="自定义处理策略(JSON格式)"),
    use_parallel: Optional[bool] = Form(None, description="是否使用并行处理，如果为None则使用配置中的默认值"),
    use_semantic_chunking: Optional[bool] = Form(None, description="是否使用语义分块，如果为None则使用配置中的默认值"),
    use_incremental: Optional[bool] = Form(None, description="是否使用增量更新，如果为None则使用配置中的默认值"),
    chunking_type: Optional[str] = Form(None, description="分块类型，如果为None则使用配置中的默认值"),
    background_tasks: BackgroundTasks = None,
    document_service: DocumentService = Depends(get_document_service)
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
        use_parallel: 是否使用并行处理，如果为None则使用配置中的默认值
        use_semantic_chunking: 是否使用语义分块，如果为None则使用配置中的默认值
        use_incremental: 是否使用增量更新，如果为None则使用配置中的默认值
        chunking_type: 分块类型，如果为None则使用配置中的默认值

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
        result = await document_processor.process_document(
            file_path=file_path,
            metadata=parsed_metadata,
            datasource_name=datasource,
            use_parallel=use_parallel,
            use_semantic_chunking=use_semantic_chunking,
            use_incremental=use_incremental,
            chunking_type=chunking_type
        )

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文档处理失败: {str(e)}")

@router.post(
    "/analyze", 
    response_model=Dict[str, Any],
    summary="分析文档并获取处理策略",
    description="""
    上传文档进行分析，获取系统推荐的处理策略，但不进行实际处理。
    
    分析结果包括文档类型、复杂度评估、以及系统建议的处理参数，如分块大小、是否转换为Markdown等。
    如果设置了`process_after_analyze=true`，系统会在返回分析结果的同时在后台开始处理文档。
    
    此接口适用于希望先了解处理策略，再决定是否处理的场景，也可用于调试或自定义处理流程。
    """,
    response_description="文档分析结果和推荐处理策略",
    responses={
        200: {
            "description": "文档分析成功",
            "content": {
                "application/json": {
                    "example": {
                        "file_name": "企业知识库介绍.pdf",
                        "file_path": "/tmp/uploads/doc123_企业知识库介绍.pdf",
                        "analysis_result": {
                            "doc_type": "pdf",
                            "complexity": "medium",
                            "features": {
                                "page_count": 5,
                                "has_tables": True,
                                "has_images": True,
                                "text_density": 0.85,
                                "estimated_tokens": 4500
                            },
                            "should_convert_to_markdown": True,
                            "chunking_params": {
                                "chunk_size": 1024,
                                "chunk_overlap": 50,
                                "chunking_type": "semantic"
                            }
                        }
                    }
                }
            }
        }
    }
)
async def analyze_document(
    file: UploadFile = File(..., description="要分析的文件"),
    process_after_analyze: bool = Form(False, description="分析后是否立即处理文档"),
    background_tasks: BackgroundTasks = None,
    document_service: DocumentService = Depends(get_document_service)
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

@router.get(
    "/{doc_id}", 
    response_model=DocumentResponse,
    summary="获取文档详情",
    description="""
    根据文档ID获取文档的详细信息，包括元数据、处理状态和统计信息。
    
    返回的信息包括文档基本信息（ID、文件名、状态等）、处理统计（节点数量、文本字符数）
    以及元数据和处理策略。
    """,
    response_description="文档详细信息",
    responses={
        200: {
            "description": "成功获取文档详情",
            "content": {
                "application/json": {
                    "example": {
                        "doc_id": "doc123",
                        "file_name": "企业知识库介绍.pdf",
                        "status": "success",
                        "node_count": 15,
                        "text_chars": 12500,
                        "metadata": {
                            "title": "企业知识库介绍",
                            "file_type": ".pdf",
                            "upload_time": "2023-04-12T10:30:00"
                        },
                        "processing_strategy": {
                            "doc_type": "pdf",
                            "should_convert_to_markdown": True
                        }
                    }
                }
            }
        },
        404: {
            "description": "文档不存在"
        }
    }
)
async def get_document(
    doc_id: str = Path(..., description="文档ID"),
    document_service: DocumentService = Depends(get_document_service)
):
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

@router.put(
    "/{doc_id}", 
    response_model=DocumentResponse,
    summary="更新文档元数据",
    description="""
    更新指定文档的元数据信息。
    
    可以更新文档的标题、描述和元数据等信息。元数据以JSON字符串形式提供，
    系统会将其解析并更新到文档中。
    """,
    response_description="更新后的文档信息",
    responses={
        200: {
            "description": "文档元数据更新成功",
            "content": {
                "application/json": {
                    "example": {
                        "doc_id": "doc123",
                        "file_name": "企业知识库介绍.pdf",
                        "status": "success",
                        "node_count": 15,
                        "text_chars": 12500,
                        "metadata": {
                            "title": "更新后的标题",
                            "description": "更新后的描述",
                            "file_type": ".pdf",
                            "upload_time": "2023-04-12T10:30:00"
                        }
                    }
                }
            }
        },
        400: {
            "description": "无效的元数据格式"
        },
        404: {
            "description": "文档不存在"
        }
    }
)
async def update_document(
    doc_id: str = Path(..., description="文档ID"),
    title: Optional[str] = Form(None, description="新标题（可选）"),
    description: Optional[str] = Form(None, description="新描述（可选）"),
    metadata_json: Optional[str] = Form(None, description="新元数据JSON字符串（可选）"),
    document_service: DocumentService = Depends(get_document_service)
):
    """
    更新文档元数据

    Args:
        doc_id: 文档ID
        title: 新标题（可选）
        description: 新描述（可选）
        metadata_json: 新元数据JSON字符串（可选）

    Returns:
        更新后的文档信息
    """
    try:
        # 解析元数据
        metadata = None
        if metadata_json:
            import json
            try:
                metadata_dict = json.loads(metadata_json)
                metadata = DocumentMetadata(**metadata_dict)
            except json.JSONDecodeError:
                raise HTTPException(status_code=400, detail="元数据JSON格式无效")
                
        # 创建更新模型
        update_data = DocumentUpdate(
            title=title,
            description=description,
            metadata=metadata
        )
        
        # 更新文档
        document = await document_service.update_document(doc_id, update_data)
        if not document:
            raise HTTPException(status_code=404, detail=f"文档不存在: {doc_id}")
            
        return document
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新文档失败: {str(e)}")

@router.delete(
    "/{doc_id}", 
    response_model=DocumentProcessResponse,
    summary="删除文档",
    description="""
    删除指定ID的文档及其相关的所有资源。
    
    删除后，文档的元数据、向量数据和原始文件（如果存在）都会被清除。
    此操作不可逆，请谨慎使用。
    """,
    response_description="删除操作结果",
    responses={
        200: {
            "description": "文档删除成功",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "doc_id": "doc123",
                        "message": "文档已成功删除"
                    }
                }
            }
        },
        404: {
            "description": "文档不存在"
        }
    }
)
async def delete_document(
    doc_id: str = Path(..., description="文档ID"),
    document_service: DocumentService = Depends(get_document_service)
):
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
@router.post(
    "/bulk/delete", 
    response_model=List[DocumentProcessResponse],
    summary="批量删除文档",
    description="""
    批量删除多个文档。
    
    接受一个文档ID列表，并尝试删除每个文档。返回每个文档的删除结果，
    包括成功或失败的状态和消息。即使部分文档删除失败，其他文档的删除操作仍会继续执行。
    """,
    response_description="批量删除操作结果",
    responses={
        200: {
            "description": "批量删除请求处理完成",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "success": True,
                            "doc_id": "doc123",
                            "message": "文档已成功删除"
                        },
                        {
                            "success": False,
                            "doc_id": "doc456",
                            "message": "文档不存在"
                        }
                    ]
                }
            }
        }
    }
)
async def bulk_delete_documents(
    request: BulkDeleteRequest = Body(..., description="包含要删除的文档ID列表的请求")
):
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

@router.post(
    "/batch/process", 
    response_model=List[DocumentResponse],
    summary="批量处理文档",
    description="""
    上传并处理多个文档。
    
    此接口允许一次性上传多个文件，并可选择在后台进行处理。对于每个文件，
    可以使用共享的元数据，并根据`auto_process`参数决定是否自动分析和处理文档。
    
    适用于需要批量导入文档的场景，可以显著提高处理效率。
    """,
    response_description="批处理结果列表",
    responses={
        200: {
            "description": "批量处理请求已接受",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "doc_id": "doc123",
                            "file_name": "文档1.pdf",
                            "status": "processing",
                            "node_count": 0,
                            "text_chars": 0,
                            "metadata": {
                                "file_path": "/tmp/uploads/doc123_文档1.pdf",
                                "batch_processing": True
                            }
                        },
                        {
                            "doc_id": "doc124",
                            "file_name": "文档2.docx",
                            "status": "processing",
                            "node_count": 0,
                            "text_chars": 0,
                            "metadata": {
                                "file_path": "/tmp/uploads/doc124_文档2.docx",
                                "batch_processing": True
                            }
                        }
                    ]
                }
            }
        }
    }
)
async def batch_process_documents(
    files: List[UploadFile] = File(..., description="要上传的文件列表"),
    metadata: Optional[str] = Form(None, description="共享元数据(JSON格式)"),
    auto_process: bool = Form(True, description="是否自动分析处理"),
    background_processing: bool = Form(True, description="是否在后台处理"),
    background_tasks: BackgroundTasks = None,
    document_service: DocumentService = Depends(get_document_service)
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

@router.get(
    "/", 
    response_model=DocumentList,
    summary="获取文档列表",
    description="""
    获取文档列表，支持分页和过滤。
    
    可以通过`skip`和`limit`参数实现分页，通过`status`和`datasource`参数
    过滤文档列表。返回的文档列表包括文档的基本信息和统计数据。
    """,
    response_description="文档列表和分页信息",
    responses={
        200: {
            "description": "成功获取文档列表",
            "content": {
                "application/json": {
                    "example": {
                        "items": [
                            {
                                "doc_id": "doc123",
                                "file_name": "文档1.pdf",
                                "title": "企业知识库介绍",
                                "status": "success",
                                "created_at": "2023-04-12T10:30:00",
                                "node_count": 15
                            },
                            {
                                "doc_id": "doc124",
                                "file_name": "文档2.docx",
                                "title": "操作指南",
                                "status": "success",
                                "created_at": "2023-04-13T14:20:00",
                                "node_count": 8
                            }
                        ],
                        "total": 25,
                        "page": 1,
                        "size": 10
                    }
                }
            }
        }
    }
)
async def list_documents(
    skip: int = Query(0, description="跳过的记录数", ge=0),
    limit: int = Query(100, description="返回的最大记录数", ge=1, le=500),
    status: Optional[DocumentStatus] = Query(None, description="文档状态过滤"),
    datasource: Optional[str] = Query(None, description="数据源过滤"),
    document_service: DocumentService = Depends(get_document_service)
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

@router.get(
    "/markdown/{doc_id}", 
    response_model=Dict[str, Any],
    summary="获取文档的Markdown内容",
    description="""
    获取指定文档的Markdown内容。
    
    如果文档已经转换为Markdown格式，将返回其Markdown内容。
    对于已经是Markdown格式的文档，将直接返回其内容。
    对于其他格式的文档，如果尚未转换为Markdown，将返回错误。
    """,
    response_description="文档的Markdown内容",
    responses={
        200: {
            "description": "成功获取Markdown内容",
            "content": {
                "application/json": {
                    "example": {
                        "content": "# 企业知识库平台\n\n## 简介\n\n企业知识库平台是一个基于...",
                        "doc_id": "doc123",
                        "file_name": "企业知识库介绍.md"
                    }
                }
            }
        },
        404: {
            "description": "文档不存在或Markdown内容不可用"
        }
    }
)
async def get_markdown_content(
    doc_id: str = Path(..., description="文档ID")
):
    """获取文档的Markdown内容"""
    try:
        # 这里假设有一个服务来获取Markdown内容
        # 实际实现可能需要查询文档记录，然后读取关联的Markdown文件
        
        # 示例返回
        markdown_content = "# 示例Markdown内容\n\n这是文档的Markdown内容示例。"
        
        return {
            "content": markdown_content,
            "doc_id": doc_id,
            "file_name": f"document_{doc_id}.md"
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"无法获取Markdown内容: {str(e)}")