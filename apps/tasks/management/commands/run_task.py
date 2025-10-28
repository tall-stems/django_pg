"""
Django management command to test Celery tasks.

Usage:
    python manage.py run_task                          # Show help
    python manage.py run_task --user-id 1              # Create note async
    python manage.py run_task --user-id 1 --sync       # Create note synchronously
    python manage.py run_task --delete --user-id 1     # Delete completed notes
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from notes.models import Note
from tasks.tasks import create_note_task, delete_completed_notes


class Command(BaseCommand):
    help = 'Run Celery tasks for testing and demonstration'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID for the task'
        )
        parser.add_argument(
            '--title',
            type=str,
            default='Test Note from Celery',
            help='Note title (default: "Test Note from Celery")'
        )
        parser.add_argument(
            '--text',
            type=str,
            default='This note was created asynchronously using Celery',
            help='Note text'
        )
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Run task synchronously (immediately, not via queue)'
        )
        parser.add_argument(
            '--delete',
            action='store_true',
            help='Delete completed notes instead of creating'
        )

    def handle(self, *args, **options):
        user_id = options.get('user_id')

        # Show help if no user specified
        if not user_id:
            self.stdout.write(self.style.WARNING('Please specify --user-id'))
            self.stdout.write('')
            self.stdout.write('Examples:')
            self.stdout.write('  python manage.py run_task --user-id 1')
            self.stdout.write('  python manage.py run_task --user-id 1 --title "My Note" --text "Note body"')
            self.stdout.write('  python manage.py run_task --user-id 1 --sync')
            self.stdout.write('  python manage.py run_task --user-id 1 --delete')
            self.stdout.write('')
            self.stdout.write('Available users:')
            for user in User.objects.all()[:10]:
                note_count = Note.objects.filter(user=user).count()
                self.stdout.write(f'  ID {user.id}: {user.username} ({note_count} notes)')
            return

        # Verify user exists
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User with ID {user_id} does not exist'))
            return

        # Handle delete operation
        if options['delete']:
            self._handle_delete(user, options)
            return

        # Handle create note operation
        self._handle_create(user, options)

    def _handle_create(self, user, options):
        """Handle note creation task."""
        title = options['title']
        text = options['text']
        is_sync = options['sync']

        self.stdout.write(self.style.SUCCESS(f'Creating note for: {user.username} (ID: {user.id})'))
        self.stdout.write(f'Title: {title}')
        self.stdout.write(f'Mode: {"Synchronous" if is_sync else "Asynchronous (queued)"}')
        self.stdout.write('')

        if is_sync:
            # Run synchronously (immediately, bypasses queue)
            result = create_note_task(user.id, title, text)

            if result['success']:
                self.stdout.write(self.style.SUCCESS('✓ Note created!'))
                self.stdout.write(f'Note ID: {result["note_id"]}')

                # Show the note
                note = Note.objects.get(id=result['note_id'])
                self.stdout.write('')
                self.stdout.write('Created note:')
                self.stdout.write(f'  Title: {note.title}')
                self.stdout.write(f'  Text: {note.text}')
                self.stdout.write(f'  Completed: {note.completed}')
            else:
                self.stdout.write(self.style.ERROR(f'✗ Failed: {result["error"]}'))

        else:
            # Run asynchronously (via Celery queue)
            task = create_note_task.delay(user.id, title, text)

            self.stdout.write(self.style.SUCCESS('✓ Task queued!'))
            self.stdout.write(f'Task ID: {task.id}')
            self.stdout.write('')
            self.stdout.write('Check task status:')
            self.stdout.write(f'  python manage.py check_task {task.id}')
            self.stdout.write('')
            self.stdout.write('Or wait for result (blocks until complete):')
            self.stdout.write('  >>> from celery.result import AsyncResult')
            self.stdout.write(f'  >>> result = AsyncResult("{task.id}")')
            self.stdout.write('  >>> result.get(timeout=10)')
            self.stdout.write('')
            self.stdout.write('Make sure Celery worker is running:')
            self.stdout.write('  celery -A playground worker --loglevel=info')

    def _handle_delete(self, user, options):
        """Handle delete completed notes task."""
        is_sync = options['sync']

        # Count completed notes
        completed_count = Note.objects.filter(user=user, completed=True).count()

        self.stdout.write(self.style.WARNING(f'Deleting completed notes for: {user.username}'))
        self.stdout.write(f'Completed notes found: {completed_count}')
        self.stdout.write(f'Mode: {"Synchronous" if is_sync else "Asynchronous (queued)"}')
        self.stdout.write('')

        if is_sync:
            # Run synchronously
            result = delete_completed_notes(user.id)

            if result['success']:
                self.stdout.write(self.style.SUCCESS(f'✓ Deleted {result["deleted_count"]} notes'))
            else:
                self.stdout.write(self.style.ERROR(f'✗ Failed: {result["error"]}'))

        else:
            # Run asynchronously
            task = delete_completed_notes.delay(user.id)

            self.stdout.write(self.style.SUCCESS('✓ Task queued!'))
            self.stdout.write(f'Task ID: {task.id}')
