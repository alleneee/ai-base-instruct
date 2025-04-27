#!/bin/bash
# 启动Celery worker和beat的脚本

# 设置环境变量
export PYTHONPATH=$(pwd)

# 定义颜色
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 显示帮助信息
show_help() {
    echo -e "${GREEN}Celery启动脚本${NC}"
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  worker        启动Celery worker"
    echo "  beat          启动Celery beat"
    echo "  flower        启动Flower监控"
    echo "  all           启动所有服务"
    echo "  stop          停止所有服务"
    echo "  status        查看服务状态"
    echo "  help          显示帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 worker     # 启动Celery worker"
    echo "  $0 all        # 启动所有服务"
    echo "  $0 stop       # 停止所有服务"
}

# 启动Celery worker
start_worker() {
    echo -e "${GREEN}启动Celery worker...${NC}"
    celery -A enterprise_kb.core.unified_celery worker \
        -Q default,document_processing,document_splitting,document_segment,document_merging,index,priority \
        -l info \
        --logfile=logs/celery_worker.log \
        --detach
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Celery worker启动成功${NC}"
    else
        echo -e "${RED}Celery worker启动失败${NC}"
    fi
}

# 启动Celery beat
start_beat() {
    echo -e "${GREEN}启动Celery beat...${NC}"
    celery -A enterprise_kb.core.unified_celery beat \
        -l info \
        --logfile=logs/celery_beat.log \
        --detach
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Celery beat启动成功${NC}"
    else
        echo -e "${RED}Celery beat启动失败${NC}"
    fi
}

# 启动Flower监控
start_flower() {
    echo -e "${GREEN}启动Flower监控...${NC}"
    celery -A enterprise_kb.core.unified_celery flower \
        --port=5555 \
        --logfile=logs/celery_flower.log \
        --detach
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}Flower监控启动成功，访问 http://localhost:5555 查看${NC}"
    else
        echo -e "${RED}Flower监控启动失败${NC}"
    fi
}

# 停止所有服务
stop_all() {
    echo -e "${YELLOW}停止所有Celery服务...${NC}"
    pkill -f "celery worker" || true
    pkill -f "celery beat" || true
    pkill -f "celery flower" || true
    echo -e "${GREEN}所有Celery服务已停止${NC}"
}

# 查看服务状态
check_status() {
    echo -e "${GREEN}Celery服务状态:${NC}"
    
    # 检查worker
    if pgrep -f "celery worker" > /dev/null; then
        echo -e "${GREEN}Celery worker正在运行${NC}"
    else
        echo -e "${RED}Celery worker未运行${NC}"
    fi
    
    # 检查beat
    if pgrep -f "celery beat" > /dev/null; then
        echo -e "${GREEN}Celery beat正在运行${NC}"
    else
        echo -e "${RED}Celery beat未运行${NC}"
    fi
    
    # 检查flower
    if pgrep -f "celery flower" > /dev/null; then
        echo -e "${GREEN}Flower监控正在运行，访问 http://localhost:5555 查看${NC}"
    else
        echo -e "${RED}Flower监控未运行${NC}"
    fi
}

# 确保日志目录存在
mkdir -p logs

# 根据参数执行相应操作
case "$1" in
    worker)
        start_worker
        ;;
    beat)
        start_beat
        ;;
    flower)
        start_flower
        ;;
    all)
        stop_all
        start_worker
        start_beat
        start_flower
        ;;
    stop)
        stop_all
        ;;
    status)
        check_status
        ;;
    help|*)
        show_help
        ;;
esac
