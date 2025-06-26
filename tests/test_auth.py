# pylint: disable=missing-docstring
from unittest.mock import MagicMock
import pytest
import auth.services as auth_services
from app import app

@pytest.fixture(name="client")
def client_fixture():
    app.config['TESTING'] = True
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

def test_login_function_redirects_correctly(mocker, client):
    """ When login route is called, auth service should be called and return 302"""
    # Mock the login function to control its output
    mock_service_login = mocker.patch('auth.services.login')
    # The mock function should return a Flask redirect object
    from flask import redirect
    expected_redirect_url = redirect('http://localhost:5000/oauth/authorized')
    mock_service_login.return_value = expected_redirect_url

    # Call the login function
    response = client.get('/auth/login')

    # Assert
    mock_service_login.assert_called_once()
    assert response.status_code == 302
    assert response.location == expected_redirect_url
