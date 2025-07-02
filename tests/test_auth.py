# pylint: disable=missing-docstring
from unittest.mock import MagicMock
from bson.objectid import ObjectId
from flask import redirect
import pytest
import auth.services as auth_services
from app import app

@pytest.fixture(name="_client")
def client_fixture():
    app.config['TESTING'] = True
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
