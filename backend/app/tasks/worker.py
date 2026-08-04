from celery import Celery
from celery.schedules import crontab
from app.core.config import settings

celery_app = Celery(
    'ops_platform',
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        'app.tasks.broadband_tasks',
        'app.tasks.topology_tasks',
        'app.tasks.inspection_tasks',
        'app.tasks.config_backup_tasks',
        'app.tasks.command_tasks',
        'app.tasks.ipam_tasks',
        'app.tasks.probe_tasks',
    ],
)

celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='Asia/Shanghai',
    enable_utc=True,
    broker_connection_timeout=3,
    broker_connection_retry=False,
    broker_connection_max_retries=1,
    task_soft_time_limit=1800,
    task_time_limit=1900,
    result_expires=86400,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_routes={
        'app.tasks.broadband_tasks.*': {'queue': 'default'},
        'app.tasks.topology_tasks.*': {'queue': 'topology'},
        'app.tasks.inspection_tasks.*': {'queue': 'inspection'},
        'app.tasks.config_backup_tasks.*': {'queue': 'config_backup'},
        'app.tasks.command_tasks.*': {'queue': 'commands'},
        'app.tasks.ipam_tasks.*': {'queue': 'ipam'},
        'app.tasks.probe_tasks.*': {'queue': 'default'},
    },
    task_default_queue='default',
    beat_schedule={
        'check-broadband-renewals-daily': {
            'task': 'app.tasks.broadband_tasks.check_broadband_renewals',
            'schedule': crontab(hour=9, minute=0),
        },
        'run-inspection-scheduled': {
            'task': 'app.tasks.inspection_tasks.run_inspection_scheduled',
            'schedule': crontab(hour=9, minute=0),
        },
        'run-config-backup-scheduled': {
            'task': 'app.tasks.config_backup_tasks.run_config_backup_scheduled',
            'schedule': crontab(hour=2, minute=0),
        },
        'discover-ipam-subnets-periodic': {
            'task': 'app.tasks.ipam_tasks.discover_all_subnets',
            'schedule': crontab(minute=0, hour='*/4'),
        },
        'check-probe-task-timeout': {
            'task': 'app.tasks.probe_tasks.check_probe_task_timeout',
            'schedule': crontab(minute='*/5'),
        },
    },
)

worker = celery_app
