import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ai_assess.settings')
app = Celery('ai_assess')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()
