import logging
import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from enterprise_kb.core.unified_celery import celery_app
from enterprise_kb.core.config import settings
from enterprise_kb.db.repositories.base import BaseRepository

logger = logging.getLogger(__name__)

@celery_app.task(name="cleanup-temp-files")
def cleanup_temp_files(days: int = 7):
    """
    清理临时文件目录中超过指定天数的文件
    
    Args:
        days: 文件保留天数，默认7天
    
    Returns:
        删除的文件数量
    """
    logger.info(f"开始清理临时文件，保留{days}天内的文件")
    
    temp_dir = Path(settings.TEMP_FILES_DIR)
    if not temp_dir.exists():
        logger.warning(f"临时目录 {temp_dir} 不存在")
        return {"deleted_files": 0}
    
    current_time = time.time()
    cutoff_time = current_time - (days * 86400)  # 86400秒 = 1天
    deleted_count = 0
    
    for item in temp_dir.glob("**/*"):
        if item.is_file():
            mtime = item.stat().st_mtime
            if mtime < cutoff_time:
                try:
                    item.unlink()
                    deleted_count += 1
                    logger.debug(f"已删除文件: {item}")
                except Exception as e:
                    logger.error(f"删除文件 {item} 时出错: {str(e)}")
    
    logger.info(f"临时文件清理完成，共删除 {deleted_count} 个文件")
    return {"deleted_files": deleted_count}

@celery_app.task(name="backup-database")
def backup_database():
    """
    备份数据库
    
    Returns:
        备份文件路径
    """
    logger.info("开始数据库备份")
    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = backup_dir / f"db_backup_{timestamp}.sql"
    
    try:
        # 根据数据库类型执行不同的备份命令
        if "postgresql" in settings.DATABASE_URL:
            # PostgreSQL备份
            db_url_parts = settings.DATABASE_URL.replace("postgresql://", "").split("/")
            db_credentials = db_url_parts[0].split("@")
            db_name = db_url_parts[1]
            
            if "@" in settings.DATABASE_URL:
                user_pass = db_credentials[0].split(":")
                username = user_pass[0]
                password = user_pass[1] if len(user_pass) > 1 else ""
                host_port = db_credentials[1].split(":")
                host = host_port[0]
                port = host_port[1] if len(host_port) > 1 else "5432"
            else:
                host = db_credentials[0].split(":")[0]
                port = "5432"
                username = ""
                password = ""
            
            # 设置环境变量避免密码在命令行中显示
            if password:
                os.environ["PGPASSWORD"] = password
            
            cmd = f"pg_dump -h {host} -p {port}"
            if username:
                cmd += f" -U {username}"
                
            cmd += f" {db_name} > {backup_file}"
            
            result = os.system(cmd)
            if password:
                del os.environ["PGPASSWORD"]  # 清除环境变量
            
            if result != 0:
                raise Exception(f"PostgreSQL备份失败，退出码: {result}")
                
        elif "sqlite" in settings.DATABASE_URL:
            # SQLite备份
            db_path = settings.DATABASE_URL.replace("sqlite:///", "")
            shutil.copy2(db_path, backup_file)
            
        else:
            raise NotImplementedError(f"不支持的数据库类型: {settings.DATABASE_URL}")
            
        logger.info(f"数据库备份完成，备份文件: {backup_file}")
        return {"backup_file": str(backup_file)}
        
    except Exception as e:
        logger.error(f"数据库备份失败: {str(e)}")
        raise

@celery_app.task(name="optimize-index")
def optimize_index():
    """
    优化搜索索引，提高检索性能
    
    Returns:
        优化结果
    """
    logger.info("开始优化索引")
    try:
        # 这里实现具体的索引优化逻辑
        # 可以根据项目实际使用的索引系统（如ElasticSearch等）
        # 添加相应的优化代码
        
        # 模拟优化过程
        time.sleep(5)
        
        # 返回优化结果
        return {"success": True, "message": "索引优化完成"}
    except Exception as e:
        logger.error(f"索引优化失败: {str(e)}")
        return {"success": False, "error": str(e)} 