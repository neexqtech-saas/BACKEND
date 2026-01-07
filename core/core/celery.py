"""
Celery Configuration
"""

import os

# Set the default Django settings module for the 'celery' program.
# This MUST be set before importing Django or Celery
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Import Celery AFTER setting the environment variable
from celery import Celery

app = Celery('core')

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
# Explicitly include 'core.tasks' since 'core' is the project directory, not an app
app.autodiscover_tasks(packages=['core'])


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')

