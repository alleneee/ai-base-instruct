flowchart TB
    %% 定义子图/分组
    subgraph AppLayer["应用层"]
        BusinessApp["业务应用"]
        AdminConsole["管理控制台"]
    end

    subgraph AbstractLayer["抽象LLM平台(中间层)"]
        APIGateway["统一API网关"]
        ModelRouter["模型路由服务"]
        RAGEngine["RAG编排引擎"]
        ContextManager["上下文管理器"]
        PromptManager["提示词管理"]
        SecurityMonitoring["安全与监控"]
    end

    subgraph KnowledgeLayer["自建知识库平台"]
        DocProcessor["文档处理管道"]
        Vectorization["向量化服务"]
        VectorDB[(向量数据库)]
        SearchEngine["检索引擎"]
        KnowledgeMCP["知识库MCP服务"]
        KnowledgeAPI["知识库管理API"]
    end

    subgraph BailianLayer["阿里云百炼平台"]
        LLMService["大模型服务"]
        AgentOrchestration["智能体编排"]
        MCPService["MCP服务"]
        InfraManagement["基础设施管理"]
    end

    %% 定义层级之间的关系
    AppLayer --> AbstractLayer
    AbstractLayer --> KnowledgeLayer
    AbstractLayer --> BailianLayer

    %% 定义主数据流 (蓝色)
    BusinessApp -->|1.用户请求| APIGateway
    APIGateway -->|2.请求路由| ModelRouter
    ModelRouter -->|3.需要知识增强| RAGEngine
    RAGEngine -->|4.知识检索| SearchEngine
    SearchEngine -->|5.向量检索| VectorDB
    SearchEngine -->|6.检索结果| RAGEngine
    RAGEngine -->|7.增强后提示词| LLMService
    LLMService -->|8.模型响应| RAGEngine
    RAGEngine -->|9.更新上下文| ContextManager
    RAGEngine -->|10.最终响应| APIGateway
    APIGateway -->|11.返回用户| BusinessApp

    %% 知识库管理流程 (绿色)
    AdminConsole -->|知识库管理| KnowledgeAPI
    KnowledgeAPI -->|文档导入| DocProcessor
    DocProcessor -->|文档处理| Vectorization
    Vectorization -->|向量存储| VectorDB

    %% 提示词管理 (紫色)
    PromptManager -->|提供提示词模板| RAGEngine

    %% MCP集成 (红色)
    KnowledgeMCP -->|注册为MCP工具| MCPService
    AgentOrchestration -->|工具调用| KnowledgeMCP

    %% 安全监控 (灰色虚线)
    SecurityMonitoring -.->|监控API调用| APIGateway
    SecurityMonitoring -.->|监控RAG流程| RAGEngine
    SecurityMonitoring -.->|监控知识库访问| KnowledgeMCP
    SecurityMonitoring -.->|监控模型调用| LLMService

    %% 添加说明/注释
    classDef applicationStyle fill:#FFD700,stroke:#333,stroke-width:1px
    classDef abstractionStyle fill:#3CB371,stroke:#333,stroke-width:1px
    classDef knowledgeStyle fill:#1E90FF,stroke:#333,stroke-width:1px
    classDef bailianStyle fill:#FA8072,stroke:#333,stroke-width:1px

    class BusinessApp,AdminConsole applicationStyle
    class APIGateway,ModelRouter,RAGEngine,ContextManager,PromptManager,SecurityMonitoring abstractionStyle
    class DocProcessor,Vectorization,VectorDB,SearchEngine,KnowledgeMCP,KnowledgeAPI knowledgeStyle
    class LLMService,AgentOrchestration,MCPService,InfraManagement bailianStyle
