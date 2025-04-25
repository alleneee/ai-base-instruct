# 企业级知识库平台

基于LlamaIndex、FastAPI、Pydantic v2和Milvus构建的企业级知识库平台。

## 主要功能

- **文档处理**：支持PDF、Word、文本等多种格式文档的上传和处理
- **向量化存储**：使用Milvus向量数据库高效存储和检索文档向量
- **语义检索**：基于LlamaIndex实现高精度语义检索
- **RESTful API**：提供完整的REST API，便于集成到现有系统

## 技术栈

- **后端框架**：FastAPI
- **数据验证**：Pydantic v2
- **向量数据库**：Milvus
- **知识检索**：LlamaIndex
- **文档处理**：Unstructured, PyMuPDF等

## 系统架构

系统采用模块化设计，主要包括以下组件：

- 文档处理管道：负责解析、切分和向量化文档
- 向量存储适配器：与Milvus交互，管理向量数据
- 检索引擎：实现高效的语义检索
- REST API：提供Web服务接口

## 快速开始

### 环境要求

- Python 3.9+
- Milvus 2.3+
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

编辑`.env`文件，设置Milvus和OpenAI API密钥等配置。

4. 启动应用

```bash
python -m enterprise_kb.main
```

应用将在`http://localhost:8000`上运行，API文档可通过`http://localhost:8000/docs`访问。

## API接口

本平台提供以下主要API：

- **文档管理**
  - `POST /api/v1/documents`：上传并处理文档
  - `GET /api/v1/documents`：获取文档列表
  - `GET /api/v1/documents/{doc_id}`：获取文档详情
  - `PUT /api/v1/documents/{doc_id}`：更新文档元数据
  - `DELETE /api/v1/documents/{doc_id}`：删除文档

- **知识检索**
  - `POST /api/v1/search`：语义检索相关知识

## 部署说明

### Docker部署

提供Docker部署指南（待完善）。

### 生产环境部署

生产环境部署建议（待完善）。

## 开发指南

开发环境设置和扩展指南（待完善）。

## 许可证

本项目采用MIT许可证。详见[LICENSE](LICENSE)文件。
