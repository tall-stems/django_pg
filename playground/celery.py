"""
Celery configuration for the Django Stems Playground project.

This module sets up Celery with Redis as both broker and result backend.
It includes comprehensive configuration for development and production environments.
"""

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "playground.settings")

# Create the Celery application
app = Celery("playground")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """
    Debug task to test Celery configuration.
    Usage: debug_task.delay()
    """
    print(f'Request: {self.request!r}')