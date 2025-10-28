"""
Django management command to test Celery tasks.

Usage:
    python manage.py test_celery
    python manage.py test_celery --task welcome --user-id 1
    python manage.py test_celery --task note --user-id 1 --note-title "Test Note"
    python manage.py test_celery --task report --user-id 1
    python manage.py test_celery --task progress
    python manage.py test_celery --task maintenance
    python manage.py test_celery --task media --args "test_image.jpg" 800 600
    python manage.py test_celery --task workflow --user-id 1
    python manage.py test_celery --task chain
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tasks.email import send_welcome_email, send_note_notification
from tasks.reports import generate_user_analytics_report, generate_activity_summary
from tasks.maintenance import health_check, calculate_user_stats
from tasks.advanced import long_running_task_with_progress, batch_user_operation, conditional_workflow
from tasks.media import resize_image, generate_thumbnails, optimize_image
from tasks.api_integration import fetch_external_user_data, sync_user_analytics_to_api, batch_fetch_user_data
from playground.celery import debug_task
import os


class Command(BaseCommand):
    help = 'Test Celery tasks and configuration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            choices=['debug', 'welcome', 'note', 'report', 'progress', 'maintenance', 'batch', 'media', 'workflow', 'chain', 'api', 'api-sync', 'api-batch'],
            default='debug',
            help='Type of task to test'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID for email tasks'
        )
        parser.add_argument(
            '--note-title',
            type=str,
            default='Test Note',
            help='Note title for note notification task'
        )
        parser.add_argument(
            '--media-args',
            nargs='*',
            help='Additional arguments for tasks (e.g., filename, dimensions)'
        )

    def handle(self, *args, **options):
        if options is None:
            options = {}
        task_type = options.get('task', 'debug')  # Use get() with default
        # task_type = options['task']
        # Log the task type being tested

        self.stdout.write(
            self.style.SUCCESS(f'Testing Celery task: {task_type}')
        )

        if task_type == 'debug':
            # Test basic Celery functionality
            result = debug_task.delay()
            self.stdout.write(f'Debug task submitted with ID: {result.id}')

        elif task_type == 'welcome':
            user_id = options.get('user_id')
            if not user_id:
                self.stdout.write(
                    self.style.ERROR('--user-id is required for welcome task')
                )
                return

            # Verify user exists
            try:
                user = User.objects.get(id=user_id)
                self.stdout.write(f'Sending welcome email to: {user.email}')

                result = send_welcome_email.delay(user_id)
                self.stdout.write(f'Welcome email task submitted with ID: {result.id}')

            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User with ID {user_id} does not exist')
                )

        elif task_type == 'note':
            user_id = options.get('user_id')
            note_title = options['note_title']

            if not user_id:
                self.stdout.write(
                    self.style.ERROR('--user-id is required for note task')
                )
                return

            # Verify user exists
            try:
                user = User.objects.get(id=user_id)
                self.stdout.write(
                    f'Sending note notification to: {user.email} for note: "{note_title}"'
                )

                result = send_note_notification.delay(
                    user_id=user_id,
                    note_title=note_title,
                    action='created'
                )
                self.stdout.write(f'Note notification task submitted with ID: {result.id}')

            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f'User with ID {user_id} does not exist')
                )

        elif task_type == 'report':
            user_id = options.get('user_id')

            if user_id:
                # Generate report for specific user
                try:
                    user = User.objects.get(id=user_id)
                    self.stdout.write(f'Generating analytics report for user: {user.username}')
                    result = generate_user_analytics_report.delay(user_id, 'pdf')
                    self.stdout.write(f'Analytics report task submitted with ID: {result.id}')
                except User.DoesNotExist:
                    self.stdout.write(
                        self.style.ERROR(f'User with ID {user_id} does not exist')
                    )
            else:
                # Generate activity summary
                self.stdout.write('Generating activity summary report...')
                result = generate_activity_summary.delay(30)
                self.stdout.write(f'Activity summary task submitted with ID: {result.id}')

        elif task_type == 'progress':
            # Test progress tracking
            self.stdout.write('Testing progress tracking with long-running task...')
            result = long_running_task_with_progress.delay(duration=10, steps=5)
            self.stdout.write(f'Progress task submitted with ID: {result.id}')
            self.stdout.write('Monitor progress at: http://localhost:8000/celery-progress/{}/'.format(result.id))

        elif task_type == 'maintenance':
            # Test maintenance tasks
            self.stdout.write('Running health check...')
            health_result = health_check.delay()
            self.stdout.write(f'Health check task submitted with ID: {health_result.id}')

            self.stdout.write('Calculating user statistics...')
            stats_result = calculate_user_stats.delay()
            self.stdout.write(f'User stats task submitted with ID: {stats_result.id}')

        elif task_type == 'batch':
            # Test batch operations
            user_ids = list(User.objects.values_list('id', flat=True))
            if user_ids:
                self.stdout.write(f'Running batch welcome email for {len(user_ids)} users...')
                result = batch_user_operation.delay(user_ids, 'welcome_email')
                self.stdout.write(f'Batch operation task submitted with ID: {result.id}')
                self.stdout.write('Monitor progress at: http://localhost:8000/celery-progress/{}/'.format(result.id))
            else:
                self.stdout.write(self.style.WARNING('No users found for batch operation'))

        elif task_type == 'media':
            # Test media processing tasks
            args = options.get('media-args', [])
            if not args:
                self.stdout.write(self.style.ERROR('Media tasks require arguments: --media-args filename [width] [height]'))
                return

            filename = args[0]
            filepath = os.path.join('media', 'uploads', filename)

            if not os.path.exists(filepath):
                self.stdout.write(self.style.ERROR(f'File not found: {filepath}'))
                return

            if len(args) >= 3:
                # Resize image
                width, height = int(args[1]), int(args[2])
                self.stdout.write(f'Resizing image {filename} to {width}x{height}...')
                result = resize_image.delay(filename, width, height)
                self.stdout.write(f'Image resize task submitted with ID: {result.id}')
            elif len(args) == 2 and args[1] == 'thumbnails':
                # Generate thumbnails
                self.stdout.write(f'Generating thumbnails for {filename}...')
                result = generate_thumbnails.delay(filename)
                self.stdout.write(f'Thumbnail generation task submitted with ID: {result.id}')
            else:
                # Optimize image
                self.stdout.write(f'Optimizing image {filename}...')
                result = optimize_image.delay(filename)
                self.stdout.write(f'Image optimization task submitted with ID: {result.id}')

        elif task_type == 'workflow':
            # Test conditional workflow
            user_id = options.get('user_id')
            if not user_id:
                self.stdout.write(self.style.ERROR('--user-id is required for workflow task'))
                return

            try:
                user = User.objects.get(id=user_id)
                self.stdout.write(f'Running conditional workflow for user: {user.username}')
                result = conditional_workflow.delay(user_id)
                self.stdout.write(f'Conditional workflow task submitted with ID: {result.id}')
                self.stdout.write('Monitor progress at: http://localhost:8000/celery-progress/{}/'.format(result.id))
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User with ID {user_id} does not exist'))

        elif task_type == 'chain':
            # Test task chaining
            self.stdout.write('Testing task chaining (progress -> email -> report)...')
            from celery import chain
            from tasks.advanced import create_task_chain

            user_ids = list(User.objects.values_list('id', flat=True)[:3])  # First 3 users
            if user_ids:
                result = create_task_chain.delay(user_ids)
                self.stdout.write(f'Task chain submitted with ID: {result.id}')
                self.stdout.write('This will run multiple tasks in sequence')
            else:
                self.stdout.write(self.style.WARNING('No users found for chain operation'))

        elif task_type == 'api':
            # Test external API integration
            user_id = options.get('user_id')
            if not user_id:
                self.stdout.write(self.style.ERROR('--user-id is required for api task'))
                return

            try:
                user = User.objects.get(id=user_id)
                self.stdout.write(f'Testing external API fetch for user: {user.username}')
                result = fetch_external_user_data.delay(user_id, include_metrics=True)
                self.stdout.write(f'API fetch task submitted with ID: {result.id}')
                self.stdout.write('This will demonstrate retry logic with exponential backoff')
                self.stdout.write('Check worker logs to see retry attempts and mock API responses')
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User with ID {user_id} does not exist'))

        elif task_type == 'api-sync':
            # Test API sync functionality
            user_id = options.get('user_id')
            if not user_id:
                self.stdout.write(self.style.ERROR('--user-id is required for api-sync task'))
                return

            try:
                user = User.objects.get(id=user_id)
                self.stdout.write(f'Testing analytics sync for user: {user.username}')

                # Create sample analytics data
                analytics_data = {
                    'records': [
                        {'event': 'login', 'timestamp': '2025-07-08T10:00:00Z'},
                        {'event': 'page_view', 'timestamp': '2025-07-08T10:05:00Z'},
                        {'event': 'button_click', 'timestamp': '2025-07-08T10:10:00Z'}
                    ]
                }

                result = sync_user_analytics_to_api.delay(user_id, analytics_data)
                self.stdout.write(f'Analytics sync task submitted with ID: {result.id}')
                self.stdout.write('This will test API sync with validation and retry logic')
            except User.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'User with ID {user_id} does not exist'))

        elif task_type == 'api-batch':
            # Test batch API operations
            user_ids = list(User.objects.values_list('id', flat=True)[:5])  # First 5 users
            if user_ids:
                self.stdout.write(f'Testing batch API fetch for {len(user_ids)} users...')
                result = batch_fetch_user_data.delay(user_ids, max_concurrent=2)
                self.stdout.write(f'Batch API task submitted with ID: {result.id}')
                self.stdout.write('This will launch individual API tasks asynchronously')
                self.stdout.write('Use the following command to check results:')
                self.stdout.write(f'python -c "from tasks.api_integration import check_batch_results; print(check_batch_results.delay(\'{result.id}\').get())"')
                self.stdout.write('Monitor progress at: http://localhost:8000/celery-progress/{}/'.format(result.id))
            else:
                self.stdout.write(self.style.WARNING('No users found for batch API operation'))

        self.stdout.write(
            self.style.SUCCESS('\nTo monitor task results:')
        )
        self.stdout.write('1. Check your terminal running the Celery worker')
        self.stdout.write('2. Check your email (or console output for development)')
        self.stdout.write('3. Use Django shell: python manage.py shell')
        self.stdout.write('   >>> from celery.result import AsyncResult')
        self.stdout.write('   >>> result = AsyncResult("task-id")')
        self.stdout.write('   >>> result.status')
        self.stdout.write('   >>> result.result')
        self.stdout.write('4. Check generated files in media/exports/ and media/reports/')
        self.stdout.write('5. For progress tasks, visit: http://localhost:8000/celery-progress/[task-id]/')
        self.stdout.write('Current task: http://localhost:8000/celery-progress/{}/'.format(result.id) if 'result' in locals() else 'No task result available')
