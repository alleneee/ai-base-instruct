from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from pydantic import BaseModel, Field


class LLMSettings(BaseModel):
    """LLM设置模型"""
    model_name: Optional[str] = Field(None, description="聊天模型名称")
    temperature: Optional[float] = Field(0.1, description="模型预测的随机性")
    top_p: Optional[float] = Field(0.3, description="核心采样阈值")
    presence_penalty: Optional[float] = Field(0.4, description="降低模型重复信息的倾向")
    frequency_penalty: Optional[float] = Field(0.7, description="降低模型重复词汇的倾向")


class PromptVariable(BaseModel):
    """提示变量模型"""
    key: str = Field(..., description="变量键")
    optional: bool = Field(False, description="是否可选")


class PromptSettings(BaseModel):
    """提示设置模型"""
    similarity_threshold: Optional[float] = Field(0.2, description="相似度阈值")
    keywords_similarity_weight: Optional[float] = Field(0.3, description="关键词相似度权重")
    top_n: Optional[int] = Field(6, description="返回给LLM的顶部块数量")
    variables: Optional[List[PromptVariable]] = Field([{"key": "knowledge", "optional": False}], description="变量列表")
    rerank_model: Optional[str] = Field("", description="重排序模型")
    empty_response: Optional[str] = Field("Sorry! No relevant content was found in the knowledge base!", description="无检索结果时的响应")
    opener: Optional[str] = Field("Hi! I'm your assistant, what can I do for you?", description="开场白")
    prompt: Optional[str] = Field("You are an intelligent assistant. Please summarize the content of the knowledge base to answer the question. Please list the data in the knowledge base and answer in detail. When all knowledge base content is irrelevant to the question, your answer must include the sentence \"The answer you are looking for is not found in the knowledge base!\" Answers need to consider chat history.\n", description="提示内容")


class ChatCreate(BaseModel):
    """创建聊天助手请求模型"""
    name: str = Field(..., description="聊天助手名称")
    avatar: Optional[str] = Field(None, description="头像Base64编码")
    dataset_ids: Optional[List[str]] = Field([], description="关联的数据集ID列表")
    llm: Optional[LLMSettings] = Field(None, description="LLM设置")
    prompt: Optional[PromptSettings] = Field(None, description="提示设置")


class ChatUpdate(BaseModel):
    """更新聊天助手请求模型"""
    name: Optional[str] = Field(None, description="聊天助手名称")
    avatar: Optional[str] = Field(None, description="头像Base64编码")
    dataset_ids: Optional[List[str]] = Field(None, description="关联的数据集ID列表")
    llm: Optional[LLMSettings] = Field(None, description="LLM设置")
    prompt: Optional[PromptSettings] = Field(None, description="提示设置")


class ChatDeleteRequest(BaseModel):
    """删除聊天助手请求模型"""
    ids: List[str] = Field(..., description="要删除的聊天助手ID列表")


class Chat(BaseModel):
    """聊天助手模型"""
    id: str = Field(..., description="聊天助手ID")
    name: str = Field(..., description="聊天助手名称")
    avatar: Optional[str] = Field("", description="头像")
    dataset_ids: List[str] = Field(..., description="关联的数据集ID列表")
    description: str = Field("A helpful Assistant", description="描述")
    do_refer: str = Field("1", description="是否引用")
    language: str = Field("English", description="语言")
    llm: LLMSettings = Field(..., description="LLM设置")
    prompt: PromptSettings = Field(..., description="提示设置")
    prompt_type: str = Field("simple", description="提示类型")
    status: str = Field("1", description="状态")
    tenant_id: str = Field(..., description="租户ID")
    top_k: int = Field(1024, description="顶部K值")
    create_date: datetime = Field(..., description="创建日期")
    update_date: datetime = Field(..., description="更新日期")
    create_time: int = Field(..., description="创建时间戳")
    update_time: int = Field(..., description="更新时间戳")


class ChatResponse(BaseModel):
    """聊天助手响应模型"""
    code: int = Field(0, description="状态码")
    data: Chat = Field(..., description="聊天助手数据")


class ChatListResponse(BaseModel):
    """聊天助手列表响应模型"""
    code: int = Field(0, description="状态码")
    data: List[Chat] = Field(..., description="聊天助手列表")


class Message(BaseModel):
    """消息模型"""
    role: str = Field(..., description="角色")
    content: str = Field(..., description="内容")


class Session(BaseModel):
    """会话模型"""
    id: str = Field(..., description="会话ID")
    chat_id: str = Field(..., description="聊天助手ID")
    name: str = Field(..., description="会话名称")
    messages: List[Message] = Field(..., description="消息列表")
    create_date: datetime = Field(..., description="创建日期")
    update_date: datetime = Field(..., description="更新日期")
    create_time: int = Field(..., description="创建时间戳")
    update_time: int = Field(..., description="更新时间戳")


class SessionCreate(BaseModel):
    """创建会话请求模型"""
    name: str = Field(..., description="会话名称")
    user_id: Optional[str] = Field(None, description="用户ID")


class SessionUpdate(BaseModel):
    """更新会话请求模型"""
    name: str = Field(..., description="会话名称")
    user_id: Optional[str] = Field(None, description="用户ID")


class SessionDeleteRequest(BaseModel):
    """删除会话请求模型"""
    ids: List[str] = Field(..., description="要删除的会话ID列表")


class SessionListResponse(BaseModel):
    """会话列表响应模型"""
    code: int = Field(0, description="状态码")
    data: List[Session] = Field(..., description="会话列表")


class SessionResponse(BaseModel):
    """会话响应模型"""
    code: int = Field(0, description="状态码")
    data: Session = Field(..., description="会话数据")


class ChatCompletionRequest(BaseModel):
    """聊天完成请求模型"""
    question: Optional[str] = Field(None, description="问题")
    stream: Optional[bool] = Field(True, description="是否流式输出")
    session_id: Optional[str] = Field(None, description="会话ID")
    user_id: Optional[str] = Field(None, description="用户ID")


class ChunkReference(BaseModel):
    """块引用模型"""
    id: str = Field(..., description="块ID")
    content: str = Field(..., description="块内容")
    document_id: str = Field(..., description="文档ID")
    document_name: str = Field(..., description="文档名称")
    dataset_id: str = Field(..., description="数据集ID")
    image_id: str = Field("", description="图片ID")
    similarity: float = Field(..., description="相似度")
    vector_similarity: float = Field(..., description="向量相似度")
    term_similarity: float = Field(..., description="术语相似度")
    positions: List[str] = Field(..., description="位置")


class ReferenceData(BaseModel):
    """引用数据模型"""
    total: int = Field(..., description="总数")
    chunks: List[ChunkReference] = Field(..., description="块引用列表")
    doc_aggs: List[DocumentAggregation] = Field(..., description="文档聚合")


class ChatCompletionStreamData(BaseModel):
    """聊天完成流式数据模型"""
    answer: str = Field(..., description="回答")
    reference: Union[ReferenceData, Dict[str, Any]] = Field({}, description="引用数据")
    audio_binary: Optional[Any] = Field(None, description="音频二进制数据")
    id: Optional[str] = Field(None, description="ID")
    session_id: str = Field(..., description="会话ID")
    prompt: Optional[str] = Field(None, description="提示")


class ChatCompletionStreamResponse(BaseModel):
    """聊天完成流式响应模型"""
    code: int = Field(0, description="状态码")
    message: str = Field("", description="消息")
    data: Union[ChatCompletionStreamData, bool] = Field(..., description="数据")


class RelatedQuestionsRequest(BaseModel):
    """相关问题请求模型"""
    question: str = Field(..., description="问题")


class RelatedQuestionsResponse(BaseModel):
    """相关问题响应模型"""
    code: int = Field(0, description="状态码")
    data: List[str] = Field(..., description="相关问题列表")
    message: str = Field("success", description="消息") 