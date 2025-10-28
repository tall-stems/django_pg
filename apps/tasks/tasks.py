"""
Simple Celery tasks for the Notes app.

This module contains basic async tasks for creating and managing notes.
Perfect for learning Celery fundamentals and building upon.
"""

import logging
from typing import Dict, Any
from celery import shared_task
from django.contrib.auth.models import User
from notes.models import Note

logger = logging.getLogger(__name__)


@shared_task
def create_note_task(user_id: int, title: str, text: str = "", completed: bool = False) -> Dict[str, Any]:
    """
    Create a note for a user asynchronously.

    This is useful for:
    - Scheduled note creation
    - Bulk note operations
    - Offloading note creation from web requests

    Args:
        user_id: The ID of the user who owns the note
        title: The title of the note
        text: The body text of the note (optional)
        completed: Whether the note is completed (default: False)

    Returns:
        Dict with task results containing note ID and success status

    Example:
        # Call synchronously (for testing)
        result = create_note_task(user_id=1, title="My Note", text="Note body")

        # Call asynchronously (queued to Celery)
        task = create_note_task.delay(user_id=1, title="My Note", text="Note body")
        result = task.get()  # Wait for result
    """
    try:
        # Fetch the user
        user = User.objects.get(id=user_id)

        # Create the note
        note = Note.objects.create(
            user=user,
            title=title,
            text=text,
            completed=completed
        )

        logger.info(f"Created note {note.id} for user {user.username}: '{title}'")

        return {
            'success': True,
            'note_id': note.id,
            'user_id': user_id,
            'title': title,
            'message': f'Note "{title}" created successfully'
        }

    except User.DoesNotExist:
        error_msg = f'User with ID {user_id} does not exist'
        logger.error(f"Failed to create note: {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"Failed to create note for user {user_id}: {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }


@shared_task
def delete_completed_notes(user_id: int = None) -> Dict[str, Any]:
    """
    Delete all completed notes for a user (or all users if user_id is None).

    This demonstrates bulk operations with Celery.

    Args:
        user_id: Optional user ID. If None, deletes for all users.

    Returns:
        Dict with count of deleted notes

    Example:
        # Delete for specific user
        delete_completed_notes.delay(user_id=1)

        # Delete for all users (be careful!)
        delete_completed_notes.delay()
    """
    try:
        # Build query
        if user_id:
            user = User.objects.get(id=user_id)
            notes = Note.objects.filter(user=user, completed=True)
            log_msg = f"user {user.username}"
        else:
            notes = Note.objects.filter(completed=True)
            log_msg = "all users"

        # Count before deletion
        count = notes.count()

        # Delete notes
        notes.delete()

        logger.info(f"Deleted {count} completed notes for {log_msg}")

        return {
            'success': True,
            'deleted_count': count,
            'message': f'Deleted {count} completed notes'
        }

    except User.DoesNotExist:
        error_msg = f'User with ID {user_id} does not exist'
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg
        }

    except Exception as exc:
        error_msg = str(exc)
        logger.error(f"Failed to delete completed notes: {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }
