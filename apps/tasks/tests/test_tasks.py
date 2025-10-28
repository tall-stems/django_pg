"""
Tests for Celery tasks.

Run with: pytest apps/tasks/test_tasks.py -v
"""

import pytest
from django.contrib.auth.models import User
from notes.models import Note
from tasks.tasks import create_note_task, delete_completed_notes


@pytest.mark.django_db
class TestCreateNoteTask:
    """Tests for the create_note_task."""

    def test_create_note_success(self):
        """Test successful note creation."""
        # Create a user
        user = User.objects.create_user(username='testuser', email='test@example.com')

        # Call the task synchronously (not async for testing)
        result = create_note_task(
            user_id=user.id,
            title='Test Note',
            text='This is a test note'
        )

        # Verify result
        assert result['success'] is True
        assert result['title'] == 'Test Note'
        assert 'note_id' in result

        # Verify note was created in database
        note = Note.objects.get(id=result['note_id'])
        assert note.title == 'Test Note'
        assert note.text == 'This is a test note'
        assert note.user == user
        assert note.completed is False

    def test_create_completed_note(self):
        """Test creating a note that's already completed."""
        user = User.objects.create_user(username='testuser2')

        result = create_note_task(
            user_id=user.id,
            title='Completed Note',
            text='Already done',
            completed=True
        )

        assert result['success'] is True
        note = Note.objects.get(id=result['note_id'])
        assert note.completed is True

    def test_create_note_nonexistent_user(self):
        """Test note creation fails gracefully for nonexistent user."""
        result = create_note_task(
            user_id=99999,
            title='This will fail'
        )

        assert result['success'] is False
        assert 'does not exist' in result['error']

        # Verify no note was created
        assert Note.objects.count() == 0

    def test_create_note_minimal_fields(self):
        """Test creating a note with only required fields."""
        user = User.objects.create_user(username='minimal')

        result = create_note_task(user_id=user.id, title='Minimal')

        assert result['success'] is True
        note = Note.objects.get(id=result['note_id'])
        assert note.title == 'Minimal'
        assert note.text == ''  # Default empty text


@pytest.mark.django_db
class TestDeleteCompletedNotesTask:
    """Tests for the delete_completed_notes task."""

    def test_delete_completed_notes_for_user(self):
        """Test deleting completed notes for a specific user."""
        user = User.objects.create_user(username='testuser')

        # Create some notes
        Note.objects.create(user=user, title='Todo 1', completed=False)
        Note.objects.create(user=user, title='Done 1', completed=True)
        Note.objects.create(user=user, title='Done 2', completed=True)

        # Delete completed notes
        result = delete_completed_notes(user_id=user.id)

        assert result['success'] is True
        assert result['deleted_count'] == 2

        # Verify only incomplete note remains
        assert Note.objects.count() == 1
        assert Note.objects.filter(completed=False).count() == 1

    def test_delete_completed_notes_all_users(self):
        """Test deleting completed notes for all users."""
        user1 = User.objects.create_user(username='user1')
        user2 = User.objects.create_user(username='user2')

        # Create notes for both users
        Note.objects.create(user=user1, title='User1 Todo', completed=False)
        Note.objects.create(user=user1, title='User1 Done', completed=True)
        Note.objects.create(user=user2, title='User2 Todo', completed=False)
        Note.objects.create(user=user2, title='User2 Done', completed=True)

        # Delete all completed notes
        result = delete_completed_notes()

        assert result['success'] is True
        assert result['deleted_count'] == 2

        # Verify only incomplete notes remain
        assert Note.objects.count() == 2
        assert Note.objects.filter(completed=False).count() == 2

    def test_delete_when_no_completed_notes(self):
        """Test deletion when there are no completed notes."""
        user = User.objects.create_user(username='testuser')
        Note.objects.create(user=user, title='Todo', completed=False)

        result = delete_completed_notes(user_id=user.id)

        assert result['success'] is True
        assert result['deleted_count'] == 0

        # Original note still exists
        assert Note.objects.count() == 1

    def test_delete_nonexistent_user(self):
        """Test deletion fails gracefully for nonexistent user."""
        result = delete_completed_notes(user_id=99999)

        assert result['success'] is False
        assert 'does not exist' in result['error']
