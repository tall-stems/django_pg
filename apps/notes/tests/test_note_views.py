import pytest
from django.urls import reverse

from .factories import UserFactory, NoteFactory


@pytest.fixture
def logged_user(client):
    """Create a user and log them in for authenticated tests."""
    user = UserFactory()
    client.login(username=user.username, password="password")
    return user


@pytest.mark.django_db
def test_list_endpoint_returns_user_notes(client, logged_user):
    """Test that the notes list view displays all notes for the logged-in user."""
    note = NoteFactory(user=logged_user)
    second_note = NoteFactory(user=logged_user)

    response = client.get(reverse("notes:list"))
    assert response.status_code == 200
    assert response.templates[0].name == "notes/note_list.html"
    content = str(response.content)
    assert note.title in content
    assert second_note.title in content
    assert len(response.context["notes"]) == 2


@pytest.mark.django_db
def test_list_endpoint_only_returns_notes_from_authenticated_user(client, logged_user):
    """Test that users can only see their own notes, not notes from other users."""
    other_user = UserFactory()
    other_note = NoteFactory(user=other_user)
    note = NoteFactory(user=logged_user)

    response = client.get(reverse("notes:list"))
    assert response.status_code == 200
    content = str(response.content)
    assert len(response.context["notes"]) == 1
    assert note.title in content
    assert other_note.title not in content


@pytest.mark.django_db
def test_create_endpoint_receives_form_data(client, logged_user):
    """Test that a logged-in user can create a new note via form submission."""
    form_data = {"title": "Test title", "text": "Test text"}

    response = client.post(reverse("notes:create"), data=form_data, follow=True)

    assert response.status_code == 200
    assert response.templates[0].name == "notes/note_list.html"
    assert logged_user.notes.count() == 1
    created_note = logged_user.notes.first()
    assert created_note.title == "Test title"
    assert created_note.text == "Test text"
    assert created_note.user == logged_user


@pytest.mark.django_db
def test_notes_list_requires_authentication(client):
    """Test that the notes list redirects to login when user is not authenticated."""
    response = client.get(reverse("notes:list"))
    assert response.status_code == 302
    assert "/login" in response.url


@pytest.mark.django_db
def test_note_detail_view_shows_correct_note(client, logged_user):
    """Test that the note detail view displays the correct note for the owner."""
    note = NoteFactory(user=logged_user, title="My Specific Note")

    response = client.get(reverse("notes:detail", kwargs={"pk": note.pk}))
    assert response.status_code == 200
    assert response.templates[0].name == "notes/note_detail.html"
    content = str(response.content)
    assert note.title in content
    assert note.text in content


@pytest.mark.django_db
def test_user_cannot_view_other_users_note_detail(client, logged_user):
    """Test that users cannot access note details belonging to other users."""
    other_user = UserFactory()
    other_note = NoteFactory(user=other_user, title="Secret Note")

    response = client.get(reverse("notes:detail", kwargs={"pk": other_note.pk}))
    # Security is working correctly - should return 404 for notes not owned by user
    assert response.status_code == 404
