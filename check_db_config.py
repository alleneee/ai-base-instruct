#!/usr/bin/env python3
"""检查数据库配置脚本"""

from enterprise_kb.core.config.settings import settings

def main():
    """主函数"""
    print("======= 数据库配置检查 =======")
    print(f"DATABASE_URL: {settings.DATABASE_URL}")
    print(f"MYSQL_URL: {settings.MYSQL_URL}")
    
    # 检查是否使用MySQL连接字符串
    if "mysql" in settings.DATABASE_URL.lower():
        print("✅ 正在使用MySQL连接字符串")
    elif "postgresql" in settings.DATABASE_URL.lower():
        print("❌ 正在使用PostgreSQL连接字符串")
    else:
        print(f"⚠️ 使用其他类型的数据库: {settings.DATABASE_URL}")
    
    # 打印所有与数据库相关的设置
    print("\n======= 所有数据库相关设置 =======")
    for key, value in settings.__dict__.items():
        if "db" in key.lower() or "sql" in key.lower() or "database" in key.lower():
            print(f"{key}: {value}")

if __name__ == "__main__":
    main() 