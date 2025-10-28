"""
Django management command to check Celery task status.

Usage:
    python manage.py check_task <task-id>
"""

from django.core.management.base import BaseCommand
from celery.result import AsyncResult
import json


class Command(BaseCommand):
    help = 'Check the status of a Celery task'

    def add_arguments(self, parser):
        parser.add_argument(
            'task_id',
            type=str,
            help='The task ID to check'
        )

    def handle(self, *args, **options):
        task_id = options['task_id']

        self.stdout.write(f'Checking task: {task_id}')
        self.stdout.write('')

        # Get task result
        result = AsyncResult(task_id)

        # Display status
        self.stdout.write(f'Status: {self.style.WARNING(result.state)}')

        # Show result if complete
        if result.ready():
            if result.successful():
                self.stdout.write(self.style.SUCCESS('✓ Task completed successfully'))
                self.stdout.write('')
                self.stdout.write('Result:')
                self.stdout.write(json.dumps(result.result, indent=2))
            else:
                self.stdout.write(self.style.ERROR('✗ Task failed'))
                self.stdout.write('')
                self.stdout.write(f'Error: {result.result}')
        else:
            self.stdout.write(self.style.WARNING('Task is still pending...'))
            self.stdout.write('')
            self.stdout.write('Run this command again in a few seconds.')
