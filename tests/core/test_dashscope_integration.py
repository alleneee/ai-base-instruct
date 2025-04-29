import pytest
import os
import logging

# 配置基本日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入前手动加载环境变量
from dotenv import load_dotenv
logger.info("Loading .env file")
load_dotenv(verbose=True)

# 打印环境变量
embedding_provider = os.getenv('EMBEDDING_PROVIDER')
llm_provider = os.getenv('LLM_PROVIDER')
dashscope_api_key = os.getenv('DASHSCOPE_API_KEY')
logger.info(f"EMBEDDING_PROVIDER = {embedding_provider}")
logger.info(f"LLM_PROVIDER = {llm_provider}")
logger.info(f"DASHSCOPE_API_KEY exists = {bool(dashscope_api_key)}")

# 直接配置LlamaIndex
from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.llms.dashscope import DashScope as DashScopeLLM

# 手动配置LlamaSettings
logger.info("手动配置LlamaSettings")
if embedding_provider == "dashscope" and dashscope_api_key:
    embed_model_name = os.getenv('DASHSCOPE_EMBED_MODEL_NAME', 'text-embedding-v2')
    LlamaSettings.embed_model = DashScopeEmbedding(
        model_name=embed_model_name,
        api_key=dashscope_api_key
    )
    logger.info(f"已配置DashScope嵌入模型: {embed_model_name}")

if llm_provider == "dashscope" and dashscope_api_key:
    llm_model_name = os.getenv('DASHSCOPE_CHAT_MODEL_NAME', 'qwen-max')
    LlamaSettings.llm = DashScopeLLM(
        model_name=llm_model_name,
        api_key=dashscope_api_key
    )
    logger.info(f"已配置DashScope LLM模型: {llm_model_name}")

# --- 检查LlamaSettings ---
logger.info("检查 LlamaSettings 配置")
logger.info(f"LlamaSettings.embed_model type = {type(LlamaSettings.embed_model)}")
logger.info(f"LlamaSettings.llm type = {type(LlamaSettings.llm)}")

# --- 测试条件 ---
dashscope_configured = (
    embedding_provider == "dashscope" and
    llm_provider == "dashscope" and
    dashscope_api_key and
    isinstance(LlamaSettings.embed_model, DashScopeEmbedding) and
    isinstance(LlamaSettings.llm, DashScopeLLM)
)
logger.info(f"dashscope_configured = {dashscope_configured}")

# --- 创建测试环境配置 ---
# 我们不再尝试导入app_settings，而是直接从环境变量创建一个配置对象
class AppSettings:
    def __init__(self):
        self.EMBEDDING_PROVIDER = embedding_provider
        self.LLM_PROVIDER = llm_provider
        self.DASHSCOPE_API_KEY = dashscope_api_key
        self.DASHSCOPE_EMBED_MODEL_NAME = os.getenv('DASHSCOPE_EMBED_MODEL_NAME', 'text-embedding-v2')
        self.DASHSCOPE_CHAT_MODEL_NAME = os.getenv('DASHSCOPE_CHAT_MODEL_NAME', 'qwen-max')
        self.MILVUS_DIMENSION = 1536  # 假设维度是1536，可以从环境变量获取

app_settings = AppSettings()
logger.info("已创建测试用AppSettings对象")

# --- 测试用例 ---

@pytest.mark.skipif(not dashscope_configured, reason="DashScope provider not configured or API key missing in settings/env")
def test_dashscope_models_configured():
    """测试 LlamaIndex 全局设置是否正确配置了 DashScope 模型"""
    assert app_settings is not None, "Failed to load application settings"
    print(f"Testing with Embedding Provider: {app_settings.EMBEDDING_PROVIDER}")
    print(f"Testing with LLM Provider: {app_settings.LLM_PROVIDER}")
    print(f"Detected LlamaSettings.embed_model type: {type(LlamaSettings.embed_model)}")
    print(f"Detected LlamaSettings.llm type: {type(LlamaSettings.llm)}")

    assert isinstance(LlamaSettings.embed_model, DashScopeEmbedding), \
        f"Expected DashScopeEmbedding, but got {type(LlamaSettings.embed_model)}"
    assert isinstance(LlamaSettings.llm, DashScopeLLM), \
        f"Expected DashScope (imported as DashScopeLLM), but got {type(LlamaSettings.llm)}"
    
    assert hasattr(LlamaSettings.embed_model, 'model_name'), "DashScopeEmbedding should have model_name attribute"
    assert hasattr(LlamaSettings.llm, 'model_name'), "DashScopeLLM should have model_name attribute"
    
    assert LlamaSettings.embed_model.model_name == app_settings.DASHSCOPE_EMBED_MODEL_NAME
    assert LlamaSettings.llm.model_name == app_settings.DASHSCOPE_CHAT_MODEL_NAME

@pytest.mark.skipif(not dashscope_configured, reason="DashScope provider not configured or API key missing in settings/env")
def test_dashscope_embedding_generation():
    """测试使用配置的 DashScope Embedding 模型生成嵌入 (需要网络访问)"""
    test_text = "这是一个测试文本"
    try:
        embedding = LlamaSettings.embed_model.get_text_embedding(test_text)
        
        assert isinstance(embedding, list), "Embedding should be a list"
        assert len(embedding) > 0, "Embedding list should not be empty"
        assert all(isinstance(x, float) for x in embedding), "All elements in embedding should be floats"
        
        # 检查维度是否与配置匹配
        assert len(embedding) == app_settings.MILVUS_DIMENSION, \
            f"Embedding dimension mismatch: expected {app_settings.MILVUS_DIMENSION}, got {len(embedding)}"
            
        print(f"Successfully generated embedding of dimension {len(embedding)}")

    except Exception as e:
        pytest.fail(f"DashScope embedding generation failed: {e}")

@pytest.mark.skipif(not dashscope_configured, reason="DashScope provider not configured or API key missing in settings/env")
def test_dashscope_chat_completion():
    """测试使用配置的 DashScope LLM 模型进行简单对话 (需要网络访问)"""
    test_prompt = "你好，请介绍一下自己。"
    try:
        # 使用 complete 或 chat API
        # response = LlamaSettings.llm.complete(test_prompt) # For simple completion
        from llama_index.core.llms import ChatMessage, MessageRole
        messages = [ChatMessage(role=MessageRole.USER, content=test_prompt)]
        response = LlamaSettings.llm.chat(messages)

        assert response is not None, "LLM response should not be None"
        assert hasattr(response, 'message'), "LLM response should have a 'message' attribute"
        assert hasattr(response.message, 'content'), "LLM response message should have 'content'"
        assert isinstance(response.message.content, str), "LLM response content should be a string"
        assert len(response.message.content) > 0, "LLM response content should not be empty"

        print(f"Successfully received chat completion: {response.message.content[:50]}...")

    except Exception as e:
        pytest.fail(f"DashScope chat completion failed: {e}")

# 你可以添加更多测试，例如测试流式响应等 