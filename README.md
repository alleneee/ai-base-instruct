# 企业级知识库平台

基于LlamaIndex、FastAPI、Pydantic v2和Milvus构建的企业级知识库平台。

## 主要功能

- **文档处理**：支持PDF、Word、文本等多种格式文档的上传和处理
- **Markdown转换**：使用MarkItDown自动将各种文档格式转换为标准Markdown格式
- **智能文档分析**：自动分析文档复杂度和结构，选择最佳处理路径
- **自适应分块策略**：根据文档类型和特性优化分块参数
- **向量化存储**：使用Milvus向量数据库高效存储和检索文档向量
- **语义检索**：基于LlamaIndex实现高精度语义检索
- **RESTful API**：提供完整的REST API，便于集成到现有系统

## 系统优化

项目包含以下主要优化：

- **异步文档处理**：使用Celery实现文档处理的异步任务，提高系统响应性能
- **依赖注入模式**：通过FastAPI的依赖注入系统实现服务和仓库层的松耦合架构
- **插件式文档处理管道**：支持可扩展的文档处理器，可以灵活添加和配置不同的处理步骤
- **统一数据访问层**：使用SQLAlchemy实现对文档元数据的一致性管理
- **请求性能优化**：通过异步处理和缓存机制提升API响应速度
- **令牌使用跟踪**：使用TokenCountingHandler跟踪嵌入和LLM令牌使用情况
- **改进的Milvus集成**：使用LlamaIndex官方Milvus集成，支持索引管理策略配置
- **现代化应用生命周期管理**：使用FastAPI最新的lifespan装饰器管理应用资源的生命周期

## 技术栈

- **后端框架**：FastAPI
- **数据验证**：Pydantic v2
- **向量数据库**：Milvus
- **知识检索**：LlamaIndex (模块化版本)
- **文档处理**：MarkItDown, Unstructured, PyMuPDF等
- **异步任务**：Celery + Redis
- **数据库**：PostgreSQL + SQLAlchemy
- **令牌计数**：tiktoken

### LlamaIndex模块化依赖

本项目使用LlamaIndex的最新模块化依赖结构：

- **llama-index-core**：核心功能
- **llama-index-vector-stores-milvus**：Milvus集成
- **llama-index-embeddings-openai**：OpenAI嵌入模型
- **llama-index-llms-openai**：OpenAI语言模型
- **llama-index-readers-file**：文件加载器

## 系统架构

系统采用模块化设计，主要包括以下组件：

- **智能文档处理系统**：分析文档特征，自动选择最佳处理路径
- **文档处理管道**：负责解析、切分和向量化文档
- **向量存储适配器**：与Milvus交互，管理向量数据
- **检索引擎**：实现高效的语义检索
- **REST API**：提供Web服务接口
- **应用生命周期管理**：使用FastAPI lifespan管理缓存、速率限制等资源

## 快速开始

### 环境要求

- Python 3.12+
- PostgreSQL 14+
- Milvus 2.3+
- Redis 7.0+
- OpenAI API Key (用于嵌入模型)

### 安装

1. 克隆仓库

```bash
git clone https://github.com/yourusername/enterprise-kb.git
cd enterprise-kb
```

2. 安装依赖

```bash
pip install -r requirements.txt
```

3. 配置环境变量

复制环境变量示例文件，并修改为你的配置：

```bash
cp environment.env.example .env
```

编辑`.env`文件，设置数据库、Milvus和OpenAI API密钥等配置。

4. 初始化数据库

```bash
alembic upgrade head
```

5. 启动应用

```bash
uvicorn enterprise_kb.main:app --reload
```

应用将在`http://localhost:8000`上运行，API文档可通过`http://localhost:8000/api/docs`访问。

## API接口

本平台提供以下主要API：

- **文档管理**
  - `POST /api/v1/documents`：上传并处理文档
  - `POST /api/v1/documents/analyze`：分析文档并获取推荐处理策略
  - `GET /api/v1/documents`：获取文档列表
  - `GET /api/v1/documents/{doc_id}`：获取文档详情
  - `GET /api/v1/documents/markdown/{doc_id}`：获取文档的Markdown内容
  - `PUT /api/v1/documents/{doc_id}`：更新文档元数据
  - `DELETE /api/v1/documents/{doc_id}`：删除文档

- **知识检索**
  - `POST /api/v1/search`：语义检索相关知识

## 自适应文档处理系统

本系统实现了智能文档处理能力，可以根据文档类型和特征自动选择最佳处理路径：

### 文档分析

系统会自动分析上传文档的特征：

- 检测文档类型（PDF、Word、代码、表格等）
- 识别文档中的表格、图片、代码等特殊内容
- 评估文档的结构复杂度
- 分析文本密度和语言特征
- 估算文档的令牌数和处理资源需求

### 处理策略决策

基于分析结果，系统自动决定：

- 是否需要将文档转换为Markdown格式
  - 代码文件和结构简单的文本通常不需要转换
  - 复杂的PDF和Word文档通常先转为Markdown
- 使用哪种分块策略和参数
  - 按内容类型选择适当的解析器
  - 动态调整块大小和重叠度

### 智能分块

系统会根据文档特性选择最合适的分块方式：

- Markdown文档 - 使用基于标记的分块，遵循标题和段落结构
- 代码文件 - 使用语法感知分块，按函数和类分割
- 表格数据 - 使用表格感知分块，保留行列关系
- PDF文档 - 根据内容密度调整分块大小
- 长句文本 - 使用更大的重叠确保上下文完整

### API集成

通过API可以控制处理过程：

- 自动分析并处理 - 系统全自动选择最佳路径
- 仅分析 - 获取建议策略，人工决定是否继续
- 自定义处理 - 提供明确的处理参数，覆盖系统建议

### 使用示例

```python
# 分析文档
response = requests.post(
    "http://localhost:8000/api/v1/documents/analyze",
    files={"file": open("document.pdf", "rb")}
)
analysis = response.json()

# 自动处理文档
response = requests.post(
    "http://localhost:8000/api/v1/documents",
    files={"file": open("document.pdf", "rb")},
    data={"auto_process": "true"}
)
```

## 部署说明

### Docker部署

1. 构建Docker镜像

```bash
docker build -t enterprise-kb .
```

2. 使用Docker Compose启动服务

```bash
docker-compose up -d
```

### 生产环境部署

生产环境部署建议：

1. 使用Nginx作为反向代理
2. 将Celery任务队列与Web服务分离
3. 配置适当的监控和日志收集
4. 设置数据库和向量库的备份策略

## 开发指南

### 本地开发环境设置

1. 创建并激活Python虚拟环境
2. 安装开发依赖: `pip install -r requirements-dev.txt`
3. 安装pre-commit钩子: `pre-commit install`
4. 运行测试: `pytest tests/`

### 添加新的文档处理器

要添加新的文档处理器，请执行以下步骤：

1. 在`enterprise_kb/core/document_pipeline/processors.py`中创建新的处理器类
2. 继承`DocumentProcessor`基类并实现`process`方法
3. 使用`@PipelineFactory.register_processor`装饰器注册处理器

示例：

```python
@PipelineFactory.register_processor
class MyNewProcessor(DocumentProcessor):
    """我的新处理器"""
    
    SUPPORTED_TYPES = ['pdf', 'docx']
    
    def process(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 实现处理逻辑
        return context
```

## 许可证

本项目采用MIT许可证。详见[LICENSE](LICENSE)文件。

## 先进特性

### 现代化应用生命周期管理

项目使用FastAPI的现代lifespan模式管理应用生命周期：

```python
@app.lifespan
async def lifespan(app: FastAPI):
    # 应用启动时执行的初始化代码
    yield
    # 应用关闭时执行的清理代码
```

这种方式相比传统的`on_event`装饰器有以下优势：

- 将相关的启动和关闭逻辑放在同一个函数中
- 更好的资源管理和异常处理
- 支持多个模块化的lifespan函数

详细文档请参阅[FastAPI生命周期管理](docs/fastapi_lifespan.md)。

### 自适应文档处理系统

本系统实现了智能文档处理能力，可以根据文档类型和特征自动选择最佳处理路径：
