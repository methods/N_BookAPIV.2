# pylint: disable=missing-docstring
# from unittest.mock import MagicMock
from flask import redirect
import pytest
import auth.services as auth_services
from app import app

@pytest.fixture(name="client")
def client_fixture():
    app.config['TESTING'] = True
    auth_services.init_oauth(app)
    return app.test_client()

def test_auth_login_route_redirects_correctly(mocker, client):
    """ When the /auth/login route is called,
    it should call the auth_login service function
    then send a 302 redirect to the appropriate page"""
    # Mock the oauth_login service function
    mock_service_login = mocker.patch('auth.services.oauth_login')
    # The auth_login function would normally return a Flask redirect object so we should mock that
    expected_redirect = redirect('https://google.com/auth?fake_params')
    mock_service_login.return_value = expected_redirect

    # Call the auth.login route
    response = client.get('/auth/login')

    # Assert
    assert mock_service_login.call_count == 1
    assert response.status_code == 302
    assert response.location == expected_redirect.location
