from django.contrib.auth.models import User
import pytest

def test_home_endpoint_returns_home_index_template(client):
    response = client.get(path='/')
    assert 200 == response.status_code
    assert response.templates[0].name == 'home/index.html'

def test_signup_endpoint_shows_signup_form_for_unauthenticated_user(client):
    response = client.get(path='/signup')
    assert 200 == response.status_code
    assert response.templates[0].name == 'home/signup.html'

@pytest.mark.django_db
def test_signup_endpoint_redirects_to_home_for_authenticated_user(client):
    '''
        When a user is authenticated, the signup endpoint should redirect to the home page.
    '''

    user = User.objects.create_user('Tester', 'tester@test.com', 'test_password')
    client.login(username=user.username, password='test_password')

    response = client.get(path='/signup', follow=True)
    assert 200 == response.status_code
    assert response.templates[0].name == 'home/index.html'