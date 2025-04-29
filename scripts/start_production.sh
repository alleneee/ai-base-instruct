#!/bin/bash
# 生产环境启动脚本
# 使用Gunicorn和Uvicorn Worker启动FastAPI应用

# 确保脚本在出错时立即退出
set -e

# 定义颜色和格式
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# 显示标题
echo -e "${GREEN}${BOLD}===========================================${NC}"
echo -e "${GREEN}${BOLD}   企业知识库平台 - 生产环境启动脚本   ${NC}"
echo -e "${GREEN}${BOLD}===========================================${NC}"

# 默认配置
DEFAULT_WORKERS_PER_CORE=1
DEFAULT_MAX_WORKERS=0  # 0表示无限制，根据核心数计算
DEFAULT_HOST="0.0.0.0"
DEFAULT_PORT=8000
DEFAULT_LOG_LEVEL="info"
DEFAULT_TIMEOUT=120

# 读取环境变量或使用默认值
WORKERS_PER_CORE=${WORKERS_PER_CORE:-$DEFAULT_WORKERS_PER_CORE}
MAX_WORKERS=${MAX_WORKERS:-$DEFAULT_MAX_WORKERS}
HOST=${HOST:-$DEFAULT_HOST}
PORT=${PORT:-$DEFAULT_PORT}
LOG_LEVEL=${LOG_LEVEL:-$DEFAULT_LOG_LEVEL}
TIMEOUT=${TIMEOUT:-$DEFAULT_TIMEOUT}
CONFIG_PATH="enterprise_kb/scripts/gunicorn_conf.py"

# 显示配置信息
echo -e "${YELLOW}启动配置:${NC}"
echo -e "  每核心工作进程数: ${BOLD}$WORKERS_PER_CORE${NC}"
echo -e "  最大工作进程数: ${BOLD}$MAX_WORKERS${NC}"
echo -e "  监听地址: ${BOLD}$HOST:$PORT${NC}"
echo -e "  日志级别: ${BOLD}$LOG_LEVEL${NC}"
echo -e "  请求超时: ${BOLD}${TIMEOUT}秒${NC}"
echo -e "  配置文件: ${BOLD}$CONFIG_PATH${NC}"
echo

# 检查Python环境
if [ -d ".venv" ]; then
  echo -e "${GREEN}使用虚拟环境 .venv${NC}"
  source .venv/bin/activate
fi

# 验证必要的包已安装
echo -e "${YELLOW}验证必要的包...${NC}"
python -c "import gunicorn" || { echo -e "${RED}错误: gunicorn未安装. 请运行 'pip install gunicorn'${NC}"; exit 1; }
python -c "import uvicorn" || { echo -e "${RED}错误: uvicorn未安装. 请运行 'pip install uvicorn'${NC}"; exit 1; }

# 设置环境变量
export WORKERS_PER_CORE=$WORKERS_PER_CORE
export MAX_WORKERS=$MAX_WORKERS
export BIND="${HOST}:${PORT}"
export LOG_LEVEL=$LOG_LEVEL
export TIMEOUT=$TIMEOUT

# 确保日志目录存在
mkdir -p logs

# 设置访问日志和错误日志
export ACCESS_LOG="logs/access.log"
export ERROR_LOG="logs/error.log"

echo -e "${GREEN}正在启动服务...${NC}"
echo

# 使用Gunicorn启动应用
exec gunicorn enterprise_kb.main:app \
  --config=$CONFIG_PATH \
  --bind=$BIND \
  --log-level=$LOG_LEVEL 