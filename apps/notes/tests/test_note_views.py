import pytest
from notes.models import Note
from .factories import UserFactory, NoteFactory

@pytest.fixture
def logged_user(client):
    user = UserFactory()
    client.login(username=user.username, password='password')
    return user

@pytest.mark.django_db
def test_list_endpoint_returns_user_notes(client, logged_user):
    note = NoteFactory(user=logged_user)
    second_note = NoteFactory(user=logged_user)

    response = client.get(path='/notes/')
    assert 200 == response.status_code
    assert 'notes/note_list.html' == response.templates[0].name
    content = str(response.content)
    assert note.title in content
    assert second_note.title in content
    assert 2 == len(response.context['notes'])

@pytest.mark.django_db
def test_list_endpoint_only_returns_notes_from_authenticated_user(client, logged_user):
    other_user = UserFactory()
    other_note = NoteFactory(user=other_user)

    note = NoteFactory(user=logged_user)

    response = client.get(path='/notes/')
    assert 200 == response.status_code
    content = str(response.content)
    assert 1 == len(response.context['notes'])
    assert other_note.title not in content

@pytest.mark.django_db
def test_create_endpoint_receives_form_data(client, logged_user):
    form_data = {'title': 'Test title', 'text': 'Test text'}

    response = client.post(path='/notes/create', data=form_data, follow=True)

    assert 200 == response.status_code
    assert 'notes/note_list.html' == response.templates[0].name
    assert 1 == logged_user.notes.count()
    assert 'Test title' == logged_user.notes.first().title
