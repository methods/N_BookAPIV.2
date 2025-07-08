# pylint: disable=missing-docstring
import os
from unittest.mock import MagicMock
from bson.objectid import ObjectId
from flask import redirect, g, session
from auth.decorators import login_required, roles_required
import pytest
import auth.services as auth_services
from app import app
from werkzeug.exceptions import Forbidden

@pytest.fixture(name="_client")
def client_fixture():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    auth_services.init_oauth(app)
    return app.test_client()


def test_init_oauth_calls_authlib_correctly(mocker):
    """ This test should test *our* code calls the library correctly """
    # Mock the Authlib functions that will be called by init_oauth
    mock_init_app = mocker.patch('auth.services.oauth.init_app')
    mock_register = mocker.patch('auth.services.oauth.register')

    # Mock the Flask app
    mock_app = MagicMock()

    # Define the expected values from the function call
    expected_call_args = {
        'name': 'google',
        'client_id': auth_services.GOOGLE_CLIENT_ID,
        'client_secret': auth_services.GOOGLE_CLIENT_SECRET,
        'server_metadata_url': 'https://accounts.google.com/.well-known/openid-configuration',
        'client_kwargs': {'scope': 'openid email'}
    }

    # Call the function
    auth_services.init_oauth(mock_app)

    # Assert outcomes
    mock_init_app.assert_called_once_with(mock_app)
    mock_register.assert_called_once_with(**expected_call_args)

def test_oauth_login_service_function_calls_authlib_redirect(mocker, _client):
    """ When login service function is called, it should call Authlib's authorise redirect"""
    # Mock the dependency of the service function, which is the Authlib client
    mock_service_redirect = mocker.patch('auth.services.oauth.google.authorize_redirect')
    # mock_service_redirect mocks the Authlib function.
    # Authlib would here generate a long secure URL which is sent to the client
    # This URL is sent to the client with 302 causing it to be automatically redirected
    expected_redirect_url = redirect('http://localhost:5000/oauth/authorized')
    mock_service_redirect.return_value = expected_redirect_url
    expected_callback_uri = 'http://localhost:5000/auth/callback'

    # Call the login function
    response = auth_services.oauth_login()

    # Assert
    mock_service_redirect.assert_called_once_with(expected_callback_uri)
    assert response.status_code == 302
    assert response == expected_redirect_url

def test_oauth_authorize_service_function_successfully_authorizes_user(mocker):
    """
    oauth_authorize should call the authlib function which handles the token exchange.
    It should then call the mongoDB function to retrieve the user's info,
    Then return the appropriate user document.
    """

    # Mock the authlib function being called
    mock_authlib_call = mocker.patch('auth.services.oauth.google.authorize_access_token')
    # Create a fake user profile to mock the google oauth response
    fake_google_profile = {
        'sub': 'google-id-12345',
        'email': 'test.user@example.com',
        'email_verified': True
    }
    # Tell the authlib mock function to return this contained in a dictionary
    mock_authlib_call.return_value = {'userinfo': fake_google_profile}

    # Mock the mongoDB function being called
    mock_user_service_call = mocker.patch('auth.services.user_services.get_or_create_user_from_oidc')

    # Create a fake user document to mock the database return
    expected_user_document = {
        '_id': ObjectId(),
        'email': 'test.user@example.com',
        'google_id': 'google-id-12345',
        'roles': ['viewer']
    }
    # Tell the mock mongoDB function to return the document
    mock_user_service_call.return_value = expected_user_document

    # Call the function
    user = auth_services.oauth_authorize()

    # Assert
    mock_authlib_call.assert_called_once()
    mock_user_service_call.assert_called_once_with(fake_google_profile)
    assert user == expected_user_document

def test_login_required_decorator_redirects_anon_user(_client):
    """
    If an anonymous user (no session) attempts to access a protected route,
    they should be redirected to the login page.
    """
    # Arrange
    with app.test_request_context('/protected-route'):
        # Define a fake view function that the decorator will wrap
        @login_required
        def fake_protected_view():
            return "You should not see this!"

        # Act
        # Call the decorated function
        response = fake_protected_view()

    # Assert
    # 1. Check for a 302 Redirect status code
    assert response.status_code == 302
    # 2. Check that the redirect location is the login page
    assert response.location == 'http://localhost:5000/auth/login'

def test_login_required_decorator_allows_authenticated_user(mocker, _client):
    """
    If a user is logged in correctly, when they access a protected route,
    user data should be loaded into flask.g.user and access allowed.
    """
    # Arrange
    # Mock the database service to look up a user
    mock_find_user = mocker.patch('auth.decorators.user_services.find_user_by_id')
    fake_user_id = ObjectId()
    fake_user_doc = {'_id': fake_user_id, 'email': 'test@test.com', 'roles': ['viewer']}
    mock_find_user.return_value = fake_user_doc

    with app.test_request_context('/protected-route'):
        # Manually set the session
        session['user_id'] = str(fake_user_id)
        # Define the decorated fake view
        @login_required
        def fake_protected_view():
            # This view can now safely access g.user
            return g.user['email']

        # Act
        response = fake_protected_view()

    # Assert
    # 1. Was the database queried with the correct ID from the session?
    mock_find_user.assert_called_once_with(str(fake_user_id))
    # 2. Did the view execute successfully?
    assert response == 'test@test.com'

def test_roles_required_denies_user_without_correct_role(_client):
    """
    If a user is logged in correctly, when they access a protected route
    but do not have the required role, a 403 Forbidden exception should be raised.
    """
    # Arrange
    with app.test_request_context('/admin-route'):
        g.user = {'roles': ['viewer']}

        @roles_required('admin')
        def fake_admin_view():
            return "You should not see this"

        # Act and Assert
        with pytest.raises(Forbidden):
            fake_admin_view()

def test_roles_required_allows_user_with_role(_client):
    """
    GIVEN a user with the required role is logged in
    WHEN they access a route protected by @roles_required
    THEN the view should execute.
    """
    with app.test_request_context('/admin-route'):
        # Arrange
        g.user = {'roles': ['viewer', 'admin']}

        @roles_required('admin')
        def fake_admin_view():
            return "Admin Access Granted"

        # Act
        response = fake_admin_view()

        # Assert
        assert response == "Admin Access Granted"
