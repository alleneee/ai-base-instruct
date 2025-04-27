#!/usr/bin/env python
"""
更新Celery导入路径的脚本

此脚本帮助将现有代码中的Celery导入路径更新为统一的导入路径。
"""
import os
import re
import argparse
from pathlib import Path

# 定义需要替换的导入路径
IMPORT_REPLACEMENTS = [
    # 旧的导入路径 -> 新的导入路径
    (r'from\s+enterprise_kb\.core\.celery\s+import\s+celery_app', 'from enterprise_kb.core.unified_celery import celery_app'),
    (r'from\s+enterprise_kb\.core\.celery_app\s+import\s+app', 'from enterprise_kb.core.unified_celery import celery_app as app'),
    (r'from\s+enterprise_kb\.core\.celery_app\s+import\s+app\s+as\s+celery_app', 'from enterprise_kb.core.unified_celery import celery_app'),
    (r'from\s+enterprise_kb\.core\.celery\.app\s+import\s+celery_app', 'from enterprise_kb.core.unified_celery import celery_app'),
    (r'from\s+enterprise_kb\.core\.celery\s+import\s+BaseTask', 'from enterprise_kb.core.unified_celery import BaseTask'),
    (r'from\s+enterprise_kb\.core\.celery_app\s+import\s+BaseTask', 'from enterprise_kb.core.unified_celery import BaseTask'),
    (r'from\s+enterprise_kb\.core\.celery\.app\s+import\s+BaseTask', 'from enterprise_kb.core.unified_celery import BaseTask'),
    (r'from\s+enterprise_kb\.core\.celery\s+import\s+get_task_info', 'from enterprise_kb.core.unified_celery import get_task_info'),
    (r'from\s+enterprise_kb\.core\.celery_app\s+import\s+get_task_info', 'from enterprise_kb.core.unified_celery import get_task_info'),
    (r'from\s+enterprise_kb\.core\.celery\.app\s+import\s+get_task_info', 'from enterprise_kb.core.unified_celery import get_task_info'),
    (r'import\s+enterprise_kb\.core\.celery', 'import enterprise_kb.core.unified_celery'),
    (r'import\s+enterprise_kb\.core\.celery_app', 'import enterprise_kb.core.unified_celery'),
    (r'import\s+enterprise_kb\.core\.celery\.app', 'import enterprise_kb.core.unified_celery'),
    # 添加更多的导入模式
    (r'from\s+enterprise_kb\.core\.celery\s+import', 'from enterprise_kb.core.unified_celery import'),
    (r'from\s+enterprise_kb\.core\.celery_app\s+import', 'from enterprise_kb.core.unified_celery import'),
    (r'from\s+enterprise_kb\.core\.celery\.app\s+import', 'from enterprise_kb.core.unified_celery import'),
]

# 定义需要替换的装饰器
DECORATOR_REPLACEMENTS = [
    # 旧的装饰器 -> 新的装饰器
    (r'@app\.task', '@celery_app.task'),
    (r'@shared_task', '@celery_app.task'),
    # 添加更多的装饰器模式
    (r'@app\.task\(', '@celery_app.task('),
    (r'@shared_task\(', '@celery_app.task('),
]

def update_file(file_path, dry_run=False):
    """更新单个文件中的导入路径和装饰器

    Args:
        file_path: 文件路径
        dry_run: 是否只打印而不实际修改

    Returns:
        是否进行了修改
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # 替换导入路径
    for old_import, new_import in IMPORT_REPLACEMENTS:
        content = re.sub(old_import, new_import, content)

    # 替换装饰器
    for old_decorator, new_decorator in DECORATOR_REPLACEMENTS:
        content = re.sub(old_decorator, new_decorator, content)

    # 检查是否有变化
    if content != original_content:
        if dry_run:
            print(f"将更新文件: {file_path}")
            return True
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"已更新文件: {file_path}")
            return True

    return False

def scan_directory(directory, extensions=None, dry_run=False):
    """扫描目录中的所有Python文件，更新导入路径

    Args:
        directory: 目录路径
        extensions: 文件扩展名列表，默认为['.py']
        dry_run: 是否只打印而不实际修改

    Returns:
        更新的文件数量
    """
    if extensions is None:
        extensions = ['.py']

    updated_count = 0

    for root, _, files in os.walk(directory):
        for file in files:
            if any(file.endswith(ext) for ext in extensions):
                file_path = os.path.join(root, file)
                if update_file(file_path, dry_run):
                    updated_count += 1

    return updated_count

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='更新Celery导入路径')
    parser.add_argument('--directory', '-d', default='.', help='要扫描的目录')
    parser.add_argument('--extensions', '-e', nargs='+', default=['.py'], help='要处理的文件扩展名')
    parser.add_argument('--dry-run', '-n', action='store_true', help='只打印将要更新的文件，不实际修改')

    args = parser.parse_args()

    print(f"开始扫描目录: {args.directory}")
    print(f"处理文件类型: {', '.join(args.extensions)}")

    if args.dry_run:
        print("干运行模式: 不会实际修改文件")

    updated_count = scan_directory(args.directory, args.extensions, args.dry_run)

    print(f"扫描完成，{'将' if args.dry_run else '已'}更新 {updated_count} 个文件")

if __name__ == "__main__":
    main()
