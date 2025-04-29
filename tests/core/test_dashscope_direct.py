import os
import logging
from dotenv import load_dotenv
from llama_index.core import Settings as LlamaSettings
from llama_index.embeddings.dashscope import DashScopeEmbedding
from llama_index.llms.dashscope import DashScope
from llama_index.core.llms import ChatMessage, MessageRole

# 配置基本日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 加载环境变量
load_dotenv(verbose=True)
logger.info("环境变量已加载")

# 获取DashScope API密钥
api_key = os.getenv("DASHSCOPE_API_KEY")
if not api_key:
    logger.error("未找到DASHSCOPE_API_KEY环境变量")
    exit(1)

logger.info("API密钥获取成功")

def test_dashscope_embedding():
    """测试DashScope嵌入功能"""
    try:
        # 初始化DashScope嵌入模型
        embed_model = DashScopeEmbedding(
            model_name="text-embedding-v2",
            api_key=api_key
        )
        
        # 生成嵌入
        test_text = "这是一个用于测试嵌入的文本。"
        embedding = embed_model.get_text_embedding(test_text)
        
        # 检查结果
        logger.info(f"成功生成嵌入向量，维度: {len(embedding)}")
        logger.info(f"嵌入向量前5个元素: {embedding[:5]}")
        
        return True
    except Exception as e:
        logger.error(f"生成嵌入时出错: {str(e)}")
        return False

def test_dashscope_llm():
    """测试DashScope LLM功能"""
    try:
        # 初始化DashScope LLM模型
        llm = DashScope(
            model_name="qwen-max",
            api_key=api_key
        )
        
        # 创建消息
        messages = [ChatMessage(role=MessageRole.USER, content="你好，请介绍一下自己。")]
        
        # 进行聊天
        logger.info("开始聊天请求...")
        response = llm.chat(messages)
        
        # 检查结果
        logger.info(f"成功获取聊天回复: {response.message.content[:100]}...")
        
        return True
    except Exception as e:
        logger.error(f"聊天请求时出错: {str(e)}")
        return False

def main():
    """主函数"""
    logger.info("=== 开始DashScope功能测试 ===")
    
    # 测试嵌入
    logger.info("测试1: DashScope嵌入")
    embed_result = test_dashscope_embedding()
    logger.info(f"嵌入测试结果: {'成功' if embed_result else '失败'}")
    
    # 测试LLM
    logger.info("\n测试2: DashScope LLM")
    llm_result = test_dashscope_llm()
    logger.info(f"LLM测试结果: {'成功' if llm_result else '失败'}")
    
    # 总结
    logger.info("\n=== 测试总结 ===")
    if embed_result and llm_result:
        logger.info("所有测试通过！DashScope配置成功。")
    else:
        logger.error("测试失败。请检查API密钥和网络连接。")

if __name__ == "__main__":
    main() 