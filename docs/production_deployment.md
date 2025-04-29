# 企业知识库平台 - 生产环境部署指南

本文档提供了将企业知识库平台部署到生产环境的详细步骤和最佳实践。

## 系统要求

- Python 3.12+
- 足够的内存(建议至少4GB)
- 生产级Linux服务器(推荐使用Ubuntu 22.04 LTS或更高版本)

## 服务器架构

在生产环境中，我们使用以下架构:

```
客户端 → Nginx反向代理 → Gunicorn进程管理器 → Uvicorn工作进程 → FastAPI应用
```

这种架构提供了:

- 高性能HTTP服务(Nginx)
- 进程管理和负载均衡(Gunicorn)
- 异步ASGI处理(Uvicorn)
- 应用逻辑处理(FastAPI)

## 安装步骤

### 1. 设置服务器环境

```bash
# 安装基本依赖
sudo apt update
sudo apt install -y python3.12 python3.12-venv python3.12-dev nginx

# 创建应用目录
sudo mkdir -p /opt/enterprise_kb
sudo chown $USER:$USER /opt/enterprise_kb
```

### 2. 部署应用代码

```bash
# 克隆代码库
git clone https://github.com/your-repo/enterprise_kb.git /opt/enterprise_kb
cd /opt/enterprise_kb

# 创建并激活虚拟环境
python3.12 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

### 3. 配置环境变量

创建环境变量文件:

```bash
cp environment.env.example .env
```

编辑`.env`文件，设置所有必要的环境变量，包括:

- 数据库连接信息
- API密钥
- 应用设置
- 生产环境标志等

### 4. 配置Gunicorn和Uvicorn

本项目已包含Gunicorn配置文件和启动脚本:

- `enterprise_kb/scripts/gunicorn_conf.py` - Gunicorn配置文件
- `scripts/start_production.sh` - 生产环境启动脚本

您可以根据服务器的资源情况调整配置参数:

#### 关键配置参数

| 参数 | 环境变量 | 默认值 | 说明 |
|------|----------|--------|------|
| 每核心进程数 | WORKERS_PER_CORE | 1 | 每个CPU核心分配多少工作进程 |
| 最大进程数 | MAX_WORKERS | 0 (无限制) | 限制总进程数，防止内存过度使用 |
| 绑定地址 | HOST, PORT | 0.0.0.0:8000 | 服务监听地址和端口 |
| 日志级别 | LOG_LEVEL | info | 日志详细程度 |
| 请求超时 | TIMEOUT | 120 | 请求处理超时时间(秒) |

### 5. 设置Systemd服务

复制服务配置文件:

```bash
sudo cp scripts/enterprise_kb.service /etc/systemd/system/
```

编辑服务文件，更新项目路径和用户信息:

```bash
sudo nano /etc/systemd/system/enterprise_kb.service
```

启用并启动服务:

```bash
sudo systemctl daemon-reload
sudo systemctl enable enterprise_kb
sudo systemctl start enterprise_kb
```

检查服务状态:

```bash
sudo systemctl status enterprise_kb
```

### 6. 配置Nginx反向代理

创建Nginx配置文件:

```bash
sudo nano /etc/nginx/sites-available/enterprise_kb
```

添加以下配置:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_buffering off;
        proxy_redirect off;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # 为静态文件配置缓存和直接服务
    location /static {
        alias /opt/enterprise_kb/static;
        expires 1d;
    }
}
```

启用站点并重启Nginx:

```bash
sudo ln -s /etc/nginx/sites-available/enterprise_kb /etc/nginx/sites-enabled/
sudo systemctl restart nginx
```

## 性能优化

### 调整工作进程数

对于大多数应用，每个CPU核心1-2个工作进程是合理的。计算公式:

```
工作进程总数 = CPU核心数 × 每核心进程数
```

对于内存密集型应用，可能需要限制最大工作进程数以防止内存耗尽:

```
# 例如，在16GB内存的服务器上
export MAX_WORKERS=8
```

### 监控和日志

系统日志位于:

- 应用日志: `/opt/enterprise_kb/logs/`
- Systemd服务日志: `journalctl -u enterprise_kb`
- Nginx访问日志: `/var/log/nginx/access.log`
- Nginx错误日志: `/var/log/nginx/error.log`

建议设置日志轮转以防止日志文件过大:

```bash
sudo nano /etc/logrotate.d/enterprise_kb
```

添加类似配置:

```
/opt/enterprise_kb/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 www-data www-data
}
```

## 安全考虑

1. **HTTPS配置**: 生产环境应始终使用HTTPS

   ```bash
   # 使用Let's Encrypt获取免费SSL证书
   sudo apt install certbot python3-certbot-nginx
   sudo certbot --nginx -d your-domain.com
   ```

2. **防火墙设置**: 只开放必要端口

   ```bash
   sudo ufw allow ssh
   sudo ufw allow 'Nginx Full'
   sudo ufw enable
   ```

3. **定期更新**: 保持系统和依赖包的更新

   ```bash
   sudo apt update && sudo apt upgrade
   ```

## 故障排除

### 常见问题

1. **服务无法启动**
   - 检查日志: `journalctl -u enterprise_kb`
   - 验证环境变量设置
   - 确认Python依赖已正确安装

2. **请求超时**
   - 增加`TIMEOUT`环境变量值
   - 检查应用日志中的性能瓶颈

3. **内存使用过高**
   - 减少`MAX_WORKERS`
   - 检查内存泄漏
   - 考虑增加服务器内存

## 维护与运营

### 部署更新

```bash
# 停止服务
sudo systemctl stop enterprise_kb

# 更新代码
cd /opt/enterprise_kb
git pull

# 更新依赖
source .venv/bin/activate
pip install -r requirements.txt

# 执行数据库迁移
alembic upgrade head

# 重启服务
sudo systemctl start enterprise_kb
```

### 备份策略

定期备份重要数据:

- 数据库备份
- 向量库备份
- 环境配置文件

## 总结

遵循以上指南，您可以将企业知识库平台部署为高性能、可靠的生产服务。该架构使用Gunicorn管理Uvicorn工作进程，提供了稳定性和性能的平衡，同时保留了FastAPI的异步处理能力。
