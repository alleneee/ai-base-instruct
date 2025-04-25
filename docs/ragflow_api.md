# RAGFlow API 文档

本文档提供RAGFlow HTTP API的完整参考。在开始使用前，请确保您已经准备好RAGFlow API密钥用于认证。

## 目录

- [错误码](#错误码)
- [数据集管理](#数据集管理)
- [文档管理](#文档管理)
- [块管理](#块管理)
- [检索](#检索)
- [聊天助手管理](#聊天助手管理)
- [代理管理](#代理管理)
- [OpenAI兼容API](#openai兼容api)

## 错误码

| 代码 | 消息 | 描述 |
|------|------|------|
| 0 | Success | 成功 |
| 400 | Bad Request | 无效的请求参数 |
| 401 | Unauthorized | 未授权访问 |
| 403 | Forbidden | 访问被拒绝 |
| 404 | Not Found | 资源未找到 |
| 500 | Internal Server Error | 服务器内部错误 |
| 1001 | Invalid Chunk ID | 无效的块ID |
| 1002 | Chunk Update Failed | 块更新失败 |

## 数据集管理

### 创建数据集

```
POST /api/v1/datasets
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "name": "测试数据集",
  "avatar": "Base64编码的头像",
  "description": "这是一个测试数据集",
  "embedding_model": "BAAI/bge-zh-v1.5",
  "permission": "me",
  "chunk_method": "naive",
  "parser_config": {
    "chunk_token_num": 128,
    "delimiter": "\\n",
    "html4excel": false,
    "layout_recognize": true
  }
}
```

**响应**:

```json
{
  "code": 0,
  "data": {
    "id": "527fa74891e811ef9c650242ac120006",
    "name": "测试数据集",
    "avatar": null,
    "description": null,
    "chunk_count": 0,
    "chunk_method": "naive",
    "document_count": 0,
    "embedding_model": "BAAI/bge-large-zh-v1.5",
    "language": "English",
    "parser_config": {
      "chunk_token_num": 128,
      "delimiter": "\\n",
      "html4excel": false,
      "layout_recognize": true,
      "raptor": {
        "use_raptor": false
      }
    },
    "permission": "me",
    "similarity_threshold": 0.2,
    "status": "1",
    "tenant_id": "69736c5e723611efb51b0242ac120007",
    "token_num": 0,
    "vector_similarity_weight": 0.3,
    "created_by": "69736c5e723611efb51b0242ac120007",
    "create_time": 1729761247434,
    "update_time": 1729761247434,
    "create_date": "Thu, 24 Oct 2024 09:14:07 GMT",
    "update_date": "Thu, 24 Oct 2024 09:14:07 GMT"
  }
}
```

### 删除数据集

```
DELETE /api/v1/datasets
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "ids": ["527fa74891e811ef9c650242ac120006", "527fa74891e811ef9c650242ac120007"]
}
```

**响应**:

```json
{
  "code": 0
}
```

### 更新数据集

```
PUT /api/v1/datasets/{dataset_id}
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "name": "更新后的数据集名称",
  "embedding_model": "BAAI/bge-zh-v1.5",
  "chunk_method": "naive"
}
```

**响应**:

```json
{
  "code": 0
}
```

### 列出数据集

```
GET /api/v1/datasets?page={page}&page_size={page_size}&orderby={orderby}&desc={desc}&name={dataset_name}&id={dataset_id}
```

**请求头**:

- 'Authorization: Bearer <YOUR_API_KEY>'

**请求参数**:

- page: 页码，默认为1
- page_size: 每页数量，默认为30
- orderby: 排序字段，可选值：create_time(默认)，update_time
- desc: 是否降序排序，默认为true
- name: 数据集名称
- id: 数据集ID

**响应**:

```json
{
  "code": 0,
  "data": [
    {
      "id": "527fa74891e811ef9c650242ac120006",
      "name": "测试数据集",
      "avatar": null,
      "description": null,
      "chunk_count": 0,
      "chunk_method": "naive",
      "document_count": 0,
      "embedding_model": "BAAI/bge-large-zh-v1.5",
      "language": "English",
      "parser_config": {
        "chunk_token_num": 128,
        "delimiter": "\\n",
        "html4excel": false,
        "layout_recognize": true,
        "raptor": {
          "use_raptor": false
        }
      },
      "permission": "me",
      "similarity_threshold": 0.2,
      "status": "1",
      "tenant_id": "69736c5e723611efb51b0242ac120007",
      "token_num": 0,
      "vector_similarity_weight": 0.3,
      "created_by": "69736c5e723611efb51b0242ac120007",
      "create_time": 1729761247434,
      "update_time": 1729761247434,
      "create_date": "Thu, 24 Oct 2024 09:14:07 GMT",
      "update_date": "Thu, 24 Oct 2024 09:14:07 GMT"
    }
  ]
}
```

## 文档管理

### 上传文档

```
POST /api/v1/datasets/{dataset_id}/documents
```

**请求头**:

- 'Content-Type: multipart/form-data'
- 'Authorization: Bearer <YOUR_API_KEY>'

**表单数据**:

- file: 要上传的文件（可多个）

**响应**:

```json
{
  "code": 0,
  "data": [
    {
      "id": "b330ec2e91ec11efbc510242ac120004",
      "name": "1.txt",
      "location": "1.txt",
      "size": 17966,
      "type": "doc",
      "thumbnail": "",
      "run": "UNSTART",
      "chunk_method": "naive",
      "parser_config": {
        "chunk_token_num": 128,
        "delimiter": "\\n",
        "html4excel": false,
        "layout_recognize": true,
        "raptor": {
          "use_raptor": false
        }
      },
      "dataset_id": "527fa74891e811ef9c650242ac120006",
      "created_by": "69736c5e723611efb51b0242ac120007"
    }
  ]
}
```

### 更新文档

```
PUT /api/v1/datasets/{dataset_id}/documents/{document_id}
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "name": "新文档名称.txt",
  "chunk_method": "manual",
  "parser_config": {
    "chunk_token_count": 128
  }
}
```

**响应**:

```json
{
  "code": 0
}
```

### 下载文档

```
GET /api/v1/datasets/{dataset_id}/documents/{document_id}
```

**请求头**:

- 'Authorization: Bearer <YOUR_API_KEY>'

**响应**: 文件内容

### 列出文档

```
GET /api/v1/datasets/{dataset_id}/documents?page={page}&page_size={page_size}&orderby={orderby}&desc={desc}&keywords={keywords}&id={document_id}&name={document_name}
```

**请求头**:

- 'Authorization: Bearer <YOUR_API_KEY>'

**请求参数**:

- page: 页码，默认为1
- page_size: 每页数量，默认为30
- orderby: 排序字段，可选值：create_time(默认)，update_time
- desc: 是否降序排序，默认为true
- keywords: 关键词
- id: 文档ID
- name: 文档名称

**响应**:

```json
{
  "code": 0,
  "data": {
    "docs": [
      {
        "id": "b330ec2e91ec11efbc510242ac120004",
        "name": "1.txt",
        "location": "1.txt",
        "size": 17966,
        "type": "doc",
        "thumbnail": "",
        "run": "UNSTART",
        "chunk_method": "naive",
        "parser_config": {
          "chunk_token_num": 128,
          "delimiter": "\\n",
          "html4excel": false,
          "layout_recognize": true,
          "raptor": {
            "use_raptor": false
          }
        },
        "dataset_id": "527fa74891e811ef9c650242ac120006",
        "created_by": "69736c5e723611efb51b0242ac120007",
        "chunk_count": 0,
        "token_count": 0,
        "process_begin_at": null,
        "process_duation": 0,
        "progress": 0,
        "progress_msg": "",
        "source_type": "local",
        "status": "1",
        "create_date": "2024-10-24T09:45:27",
        "update_date": "2024-10-24T09:45:27",
        "create_time": 1729763127646,
        "update_time": 1729763127646
      }
    ],
    "total": 1
  }
}
```

### 删除文档

```
DELETE /api/v1/datasets/{dataset_id}/documents
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "ids": ["b330ec2e91ec11efbc510242ac120004", "b330ec2e91ec11efbc510242ac120005"]
}
```

**响应**:

```json
{
  "code": 0
}
```

### 解析文档

```
POST /api/v1/datasets/{dataset_id}/chunks
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "document_ids": ["b330ec2e91ec11efbc510242ac120004", "b330ec2e91ec11efbc510242ac120005"]
}
```

**响应**:

```json
{
  "code": 0
}
```

### 停止解析文档

```
DELETE /api/v1/datasets/{dataset_id}/chunks
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "document_ids": ["b330ec2e91ec11efbc510242ac120004", "b330ec2e91ec11efbc510242ac120005"]
}
```

**响应**:

```json
{
  "code": 0
}
```

## 块管理

### 添加块

```
POST /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "content": "这是一个测试块的内容",
  "important_keywords": ["测试", "块"],
  "questions": ["这是什么?"]
}
```

**响应**:

```json
{
  "code": 0,
  "data": {
    "chunk": {
      "id": "12ccdc56e59837e5",
      "content": "这是一个测试块的内容",
      "document_id": "b330ec2e91ec11efbc510242ac120004",
      "dataset_id": "527fa74891e811ef9c650242ac120006",
      "important_keywords": ["测试", "块"],
      "questions": ["这是什么?"],
      "create_time": "2024-10-24 10:59:55",
      "create_timestamp": 1729767595.969164
    }
  }
}
```

### 列出块

```
GET /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks?keywords={keywords}&page={page}&page_size={page_size}&id={chunk_id}
```

**请求头**:

- 'Authorization: Bearer <YOUR_API_KEY>'

**请求参数**:

- keywords: 关键词
- page: 页码，默认为1
- page_size: 每页数量，默认为1024
- id: 块ID

**响应**:

```json
{
  "code": 0,
  "data": {
    "chunks": [
      {
        "id": "b48c170e90f70af998485c1065490726",
        "content": "这是一个测试块的内容",
        "docnm_kwd": "1.txt",
        "document_id": "b330ec2e91ec11efbc510242ac120004",
        "image_id": "",
        "important_keywords": "测试,块",
        "positions": [""],
        "available": true
      }
    ],
    "doc": {
      "chunk_count": 1,
      "chunk_method": "naive",
      "create_date": "Thu, 24 Oct 2024 09:45:27 GMT",
      "create_time": 1729763127646,
      "created_by": "69736c5e723611efb51b0242ac120007",
      "dataset_id": "527fa74891e811ef9c650242ac120006",
      "id": "b330ec2e91ec11efbc510242ac120004",
      "location": "1.txt",
      "name": "1.txt",
      "parser_config": {
        "chunk_token_num": 128,
        "delimiter": "\\n",
        "html4excel": false,
        "layout_recognize": true,
        "raptor": {
          "use_raptor": false
        }
      },
      "process_begin_at": "Thu, 24 Oct 2024 09:56:44 GMT",
      "process_duation": 0.54213,
      "progress": 0.0,
      "progress_msg": "Task dispatched...",
      "run": "2",
      "size": 17966,
      "source_type": "local",
      "status": "1",
      "thumbnail": "",
      "token_count": 8,
      "type": "doc",
      "update_date": "Thu, 24 Oct 2024 11:03:15 GMT",
      "update_time": 1729767795721
    },
    "total": 1
  }
}
```

### 删除块

```
DELETE /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "chunk_ids": ["b48c170e90f70af998485c1065490726", "b48c170e90f70af998485c1065490727"]
}
```

**响应**:

```json
{
  "code": 0
}
```

### 更新块

```
PUT /api/v1/datasets/{dataset_id}/documents/{document_id}/chunks/{chunk_id}
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "content": "更新后的块内容",
  "important_keywords": ["更新", "块"],
  "available": true
}
```

**响应**:

```json
{
  "code": 0
}
```

## 检索

### 检索块

```
POST /api/v1/retrieval
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "question": "什么是RAGFlow?",
  "dataset_ids": ["527fa74891e811ef9c650242ac120006"],
  "page": 1,
  "page_size": 10,
  "similarity_threshold": 0.2,
  "vector_similarity_weight": 0.3,
  "top_k": 1024,
  "keyword": false,
  "highlight": true
}
```

**响应**:

```json
{
  "code": 0,
  "data": {
    "chunks": [
      {
        "id": "b48c170e90f70af998485c1065490726",
        "content": "这是一个测试块的内容",
        "content_ltks": "这是一个测试块的内容",
        "document_id": "b330ec2e91ec11efbc510242ac120004",
        "document_keyword": "1.txt",
        "highlight": "这是一个<em>测试</em>块的内容",
        "image_id": "",
        "important_keywords": ["测试", "块"],
        "kb_id": "527fa74891e811ef9c650242ac120006",
        "positions": [""],
        "similarity": 0.8669436601210759,
        "term_similarity": 0.9,
        "vector_similarity": 0.8439122004035864
      }
    ],
    "doc_aggs": [
      {
        "doc_id": "b330ec2e91ec11efbc510242ac120004",
        "doc_name": "1.txt",
        "count": 1
      }
    ],
    "total": 1
  }
}
```

## 聊天助手管理

### 创建聊天助手

```
POST /api/v1/chats
```

**请求头**:

- 'Content-Type: application/json'
- 'Authorization: Bearer <YOUR_API_KEY>'

**请求体**:

```json
{
  "name": "测试助手",
  "avatar": "Base64编码的头像",
  "dataset_ids": ["527fa74891e811ef9c650242ac120006"],
  "llm": {
    "model_name": "qwen-plus@Tongyi-Qianwen",
    "temperature": 0.1,
    "top_p": 0.3,
    "presence_penalty": 0.4,
    "frequency_penalty": 0.7
  },
  "prompt": {
    "similarity_threshold": 0.2,
    "keywords_similarity_weight": 0.3,
    "top_n": 6,
    "variables": [{"key": "knowledge", "optional": false}],
    "rerank_model": "",
    "empty_response": "抱歉！知识库中没有找到相关内容！",
    "opener": "您好！我是您的助手，有什么可以帮您？",
    "prompt": "你是一个智能助手。请总结知识库内容以回答问题。请列出知识库中的数据并详细回答。当所有知识库内容与问题无关时，你的回答必须包含「知识库中找不到你要找的答案！」这句话。回答需要考虑聊天历史。\n"
  }
}
```

**响应**:

```json
{
  "code": 0,
  "data": {
    "id": "b1f2f15691f911ef81180242ac120003",
    "name": "测试助手",
    "avatar": "",
    "dataset_ids": ["527fa74891e811ef9c650242ac120006"],
    "description": "A helpful Assistant",
    "do_refer": "1",
    "language": "English",
    "llm": {
      "model_name": "qwen-plus@Tongyi-Qianwen",
      "temperature": 0.1,
      "top_p": 0.3,
      "presence_penalty": 0.4,
      "frequency_penalty": 0.7
    },
    "prompt": {
      "similarity_threshold": 0.2,
      "keywords_similarity_weight": 0.3,
      "top_n": 6,
      "variables": [{"key": "knowledge", "optional": false}],
      "rerank_model": "",
      "empty_response": "抱歉！知识库中没有找到相关内容！",
      "opener": "您好！我是您的助手，有什么可以帮您？",
      "prompt": "你是一个智能助手。请总结知识库内容以回答问题。请列出知识库中的数据并详细回答。当所有知识库内容与问题无关时，你的回答必须包含「知识库中找不到你要找的答案！」这句话。回答需要考虑聊天历史。\n"
    },
    "prompt_type": "simple",
    "status": "1",
    "tenant_id": "69736c5e723611efb51b0242ac120007",
    "top_k": 1024,
    "create_date": "Thu, 24 Oct 2024 11:18:29 GMT",
    "update_date": "Thu, 24 Oct 2024 11:18:29 GMT",
    "create_time": 1729768709023,
    "update_time": 1729768709023
  }
}
```

### 更多API省略

查看完整API文档请参考RAGFlow官方文档或系统内提供的Swagger UI文档页面。
