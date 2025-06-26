# pylint: disable=missing-docstring
from unittest.mock import MagicMock
import pytest
import auth.services as auth_services
from app import app

@pytest.fixture(name="client")
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

def test_login_service_function_calls_authlib_redirect(mocker, client):
    """ When login service function is called, it should call Authlib's authorise redirect"""
    # Mock the dependency of the service function, which is the Authlib client
    mock_service_redirect = mocker.patch('auth.services.oauth.google.authorize_redirect')
    # mock_service_redirect mocks the Authlib function.
    # Authlib would here generate a long secure URL which is sent to the client
    # This URL is sent to the client with 302 causing it to be automatically redirected
    from flask import redirect
    expected_redirect_url = redirect('http://localhost:5000/oauth/authorized')
    mock_service_redirect.return_value = expected_redirect_url
    expected_callback_uri = 'http://localhost:5000/auth/callback'

    # Call the login function
    response = auth_services.login(app)

    # Assert
    mock_service_redirect.assert_called_once_with(expected_callback_uri)
    assert response.status_code == 302
    assert response.location == expected_redirect_url
