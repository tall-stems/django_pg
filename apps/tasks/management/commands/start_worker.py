"""
Django management command to start Celery worker.

Usage:
    python manage.py start_worker
    python manage.py start_worker --loglevel debug
    python manage.py start_worker --concurrency 4
"""

import subprocess
import sys
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Start Celery worker for development'

    def add_arguments(self, parser):
        parser.add_argument(
            '--loglevel',
            type=str,
            default='info',
            choices=['debug', 'info', 'warning', 'error', 'critical'],
            help='Logging level (default: info)'
        )
        parser.add_argument(
            '--concurrency',
            type=int,
            default=None,
            help='Number of worker processes (default: number of CPUs)'
        )
        parser.add_argument(
            '--queues',
            type=str,
            default='celery',
            help='Comma-separated list of queues to process (default: celery)'
        )

    def handle(self, *args, **options):
        loglevel = options['loglevel']
        concurrency = options['concurrency']
        queues = options['queues']

        self.stdout.write(self.style.SUCCESS('Starting Celery worker...'))
        self.stdout.write('')
        self.stdout.write(f'Log level: {loglevel}')
        if concurrency:
            self.stdout.write(f'Concurrency: {concurrency}')
        self.stdout.write(f'Queues: {queues}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('Press Ctrl+C to stop'))
        self.stdout.write('')

        # Build celery command
        cmd = ['celery', '-A', 'playground', 'worker', f'--loglevel={loglevel}']

        if concurrency:
            cmd.extend(['--concurrency', str(concurrency)])

        if queues != 'celery':
            cmd.extend(['-Q', queues])

        try:
            # Run celery worker
            subprocess.run(cmd)
        except KeyboardInterrupt:
            self.stdout.write('')
            self.stdout.write(self.style.SUCCESS('Worker stopped'))
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR('Celery not found. Is it installed?'))
            self.stdout.write('Install with: pip install celery')
            sys.exit(1)
