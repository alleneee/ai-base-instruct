from celery.schedules import crontab

# 定义周期性任务
beat_schedule = {
    'cleanup-temp-files-weekly': {
        'task': 'cleanup_temp_files',
        'schedule': crontab(day_of_week='sunday', hour=2, minute=0),
        'args': (7,),
    },
    'backup-database-daily': {
        'task': 'backup_database',
        'schedule': crontab(hour=1, minute=0),
        'args': (None,),
    },
    'optimize-index-weekly': {
        'task': 'optimize_index',
        'schedule': crontab(day_of_week='saturday', hour=3, minute=0),
    },
} 