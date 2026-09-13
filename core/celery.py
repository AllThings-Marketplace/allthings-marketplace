import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
# Note: If your settings folder is not named 'core', change 'core.settings' to match.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

# Initialize the Celery app
app = Celery('core')

# Read configuration from Django settings, using a CELERY namespace
app.config_from_object('django.conf:settings', namespace='CELERY')

# Automatically discover tasks.py files in all installed apps (like marketplace)
app.autodiscover_tasks()