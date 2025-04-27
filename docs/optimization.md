# 系统优化说明

本文档描述了企业知识库平台的主要优化内容和实现方式。

## 1. 异步任务处理

### 问题

原系统在API请求中同步处理文档，导致用户请求响应时间过长，特别是对于大型文档或复杂处理流程。

### 解决方案

使用Celery实现异步任务处理：

- 创建`process_document_task`Celery任务处理文档
- 文档上传后立即返回响应，文档处理在后台进行
- 实现任务状态跟踪和错误处理机制

### 实现

```python
@shared_task(name="process_document")
def process_document_task(
    doc_id: str, 
    file_path: str, 
    metadata: Dict[str, Any],
    datasource_name: Optional[str] = None,
    custom_processors: Optional[List[str]] = None
) -> Dict[str, Any]:
    """异步处理文档任务"""
    try:
        # 更新文档状态为处理中
        doc_repo = DocumentRepository()
        doc_repo.update_status(doc_id, DocumentStatus.PROCESSING)
        
        # 获取处理器并处理文档
        processor = get_document_processor()
        result = processor.process_document(
            file_path=file_path,
            metadata=metadata,
            datasource_name=datasource_name,
            custom_processors=custom_processors
        )
        
        # 更新文档状态为完成
        doc_repo.update(
            doc_id,
            {
                "status": DocumentStatus.COMPLETED,
                "node_count": result["node_count"],
                "datasource": result.get("datasource", "primary")
            }
        )
        
        return result
    except Exception as e:
        # 更新文档状态为失败
        doc_repo.update(
            doc_id,
            {
                "status": DocumentStatus.FAILED,
                "error": str(e)
            }
        )
        raise
```

## 2. 依赖注入优化

### 问题

服务层与数据访问层紧耦合，难以单独测试和维护，且不便于替换实现。

### 解决方案

使用FastAPI的依赖注入系统：

- 创建依赖提供器统一管理服务实例
- 在API路由中通过依赖注入获取服务
- 支持单元测试时轻松替换服务实现

### 实现

```python
# 服务依赖
def get_document_service(
    doc_repo: DocumentRepository = Depends(get_document_repository)
) -> DocumentService:
    """获取文档服务实例"""
    return DocumentService(doc_repo)

# 在路由中使用
@router.post("/documents")
async def create_document(
    file: UploadFile = File(...),
    document_service: DocumentService = Depends(get_document_service)
):
    # 使用服务实例
    ...
```

## 3. 文档处理管道优化

### 问题

原系统文档处理逻辑固定，难以根据不同文档类型定制处理流程，扩展新功能复杂。

### 解决方案

实现插件式文档处理管道：

- 创建处理器基类和处理管道
- 实现管道工厂，根据文件类型动态组装处理管道
- 支持通过装饰器注册新的处理器

### 实现

```python
class DocumentProcessor(ABC):
    """文档处理器基类"""
    
    SUPPORTED_TYPES = []
    
    @abstractmethod
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """处理文档的抽象方法"""
        pass

class PipelineFactory:
    """处理管道工厂"""
    
    _processors: Dict[str, Type[DocumentProcessor]] = {}
    
    @classmethod
    def register_processor(cls, processor_class: Type[DocumentProcessor]):
        """注册处理器类"""
        cls._processors[processor_class.__name__] = processor_class
        return processor_class
    
    @classmethod
    def create_pipeline(cls, file_type: str, custom_processors: Optional[List[str]] = None) -> DocumentPipeline:
        """创建处理管道"""
        pipeline = DocumentPipeline()
        
        # 如果指定了自定义处理器，按顺序添加
        if custom_processors:
            for processor_name in custom_processors:
                if processor_name in cls._processors:
                    pipeline.add_processor(cls._processors[processor_name]())
            return pipeline
        
        # 否则，添加支持该文件类型的所有处理器
        for processor_class in cls._processors.values():
            if processor_class.supports_file_type(file_type):
                pipeline.add_processor(processor_class())
                
        return pipeline
```

## 4. 统一数据访问层

### 问题

原系统同时使用文件系统(JSON文件)和数据库存储元数据，导致数据一致性问题和管理复杂。

### 解决方案

统一使用SQLAlchemy实现数据访问层：

- 创建统一的文档仓库类处理数据库操作
- 使用会话上下文管理器确保事务一致性
- 实现全面的CRUD操作支持

### 实现

```python
class DocumentRepository:
    """文档仓库，处理文档数据库操作"""
    
    async def create(self, document_data: Dict[str, Any]) -> str:
        """创建文档"""
        async with get_session() as session:
            document = DocumentModel(**document_data)
            session.add(document)
            await session.commit()
            await session.refresh(document)
            return document.id
    
    async def get(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """获取文档"""
        async with get_session() as session:
            result = await session.execute(
                select(DocumentModel).where(DocumentModel.id == doc_id)
            )
            document = result.scalars().first()
            
            if not document:
                return None
                
            return self._model_to_dict(document)
```

## 5. 性能优化

### 问题

API响应速度不足，特别是在并发请求和大型文档处理时。

### 解决方案

实施多层性能优化：

- 异步数据库会话和查询
- 使用上下文变量管理会话状态
- 针对热门路径实现缓存
- 文档处理分块并行化

### 实现

```python
# 创建会话工厂
async_session_factory = async_sessionmaker(
    engine, 
    expire_on_commit=False,
    class_=AsyncSession
)

# 上下文变量，用于存储当前请求的会话
session_context = ContextVar("session_context", default=None)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话"""
    session = async_session_factory()
    try:
        # 将会话存储到上下文变量
        token = session_context.set(session)
        yield session
    finally:
        session_context.reset(token)
        await session.close()
```

## 6. 文档处理器实现

为不同类型的文档提供了专用处理器：

1. **FileValidator** - 验证文件有效性和大小限制
2. **PDFProcessor** - 专用PDF文档处理和Markdown转换
3. **DocxProcessor** - Word文档处理和Markdown转换
4. **MarkdownProcessor** - 原生Markdown文档处理
5. **TextProcessor** - 普通文本文件处理
6. **ChunkingProcessor** - 根据文档类型实现智能分块
7. **VectorizationProcessor** - 将文档块向量化存储

这些处理器按需组合成处理管道，提供灵活高效的文档处理能力。

## 总结

通过这些优化，系统实现了：

- 更高的响应性能和用户体验
- 更好的代码可维护性和可测试性
- 更灵活的扩展能力
- 更可靠的数据一致性保障
- 更强大的文档处理能力
