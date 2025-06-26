# pylint: disable=missing-docstring
from unittest.mock import MagicMock
import pytest
import auth.services as auth_services


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
