# pylint: disable=missing-docstring
# from unittest.mock import MagicMock
import os
import logging
from flask import redirect, session
from bson.objectid import ObjectId # This is imported so we can create a mongoDB-like ObjectId
import pytest
from authlib.integrations.base_client import OAuthError
import auth.services as auth_services
from app import app

@pytest.fixture(name="client")
def client_fixture():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    auth_services.init_oauth(app)
    return app.test_client()

# This client fixture is logged in as a fake admin user
@pytest.fixture(name="admin_client")
def admin_client_fixture(client, mocker):
    # Create the fake admin user object
    fake_admin_id = ObjectId()
    fake_admin_doc = {
        '_id': fake_admin_id,
        'email': 'admin@test.com',
        'roles': ['admin', 'viewer']
    }

    # Mock the function that the @login_required decorator calls
    mocker.patch(
        'auth.decorators.user_services.find_user_by_id',
        return_value=fake_admin_doc
    )

    # Use the client's session_transaction to set the cookie
    with client.session_transaction() as sess:
        sess['user_id'] = str(fake_admin_id)

    # The 'client' object that was passed in now has the session cookie.
    yield client

def test_auth_login_route_redirects_correctly(mocker, client):
    """ When the /auth/login route is called,
    it should call the oauth_login service function
    then send a 302 redirect to the appropriate page"""
    # Mock the oauth_login service function
    mock_service_login = mocker.patch('auth.services.oauth_login')
    # The auth_login function would normally return a Flask redirect object so we should mock that
    expected_redirect = redirect('https://google.com/auth?fake_params')
    mock_service_login.return_value = expected_redirect

    # Call the auth/login route
    response = client.get('/auth/login')

    # Assert
    assert mock_service_login.call_count == 1
    assert response.status_code == 302
    assert response.location == expected_redirect.location

def test_auth_callback_route_redirects_correctly_on_successful_login(mocker, client):
    """ When the /auth/callback route is called,
    it should call the oauth_authorize service function and expect
    a 302 redirect and that a session cookie is returned.
    """
    # Create a fake user document to mock the response from mongoDB *after*
    # the oauth_authorize function receives a token back from the oauth service.
    fake_user_id = ObjectId() # Creates a new ObjectId using mongoDB bson
    mock_user_document = {
        '_id': fake_user_id,
        'email': 'test.user@example.com',
        'roles': ['viewer']
    }
    # Establish the 'default' page for redirection after successful authorization
    expected_redirect_uri = 'http://localhost:5000/books'

    # Mock the oauth_authorize service function
    mock_service_authorize = mocker.patch('auth.services.oauth_authorize')
    # The mock function will return the mock user document
    mock_service_authorize.return_value = mock_user_document

    with client: # The 'with' block makes the client behave like a stateful browser;
        # the request context will then persist long enough for the assertions,
        # without 'with' this context is torn down as soon as client.get completes.
        # Call the auth/callback route
        response = client.get('/auth/callback')

        # Assert
        assert mock_service_authorize.call_count == 1
        assert 'user_id' in session
        assert session['user_id'] == str(fake_user_id)

    assert response.status_code == 302
    assert response.location == expected_redirect_uri


def test_callback_view_handles_service_returning_none(mocker, client, caplog):
    """
    GIVEN the authorize service returns None (e.g., DB issue)
    WHEN the /auth/callback route is hit
    THEN it should log a warning and redirect to the home/failure page.
    """
    # Arrange
    # Mock the service function to simulate the failure by returning None.
    mock_service_authorize = mocker.patch('auth.services.oauth_authorize')
    mock_service_authorize.return_value = None

    # Use the 'caplog' fixture to capture log messages.
    #    This allows us to assert that the correct warning was logged.
    caplog.set_level(logging.WARNING)

    # Act
    response = client.get('/auth/callback')

    # Assert
    # 1. Was the service function called?
    mock_service_authorize.assert_called_once()

    # 2. Was the user redirected to the correct failure page?
    assert response.status_code == 302
    assert response.location == 'http://localhost:5000/'

    # 3. Was the correct warning message logged?
    assert "Authorization failed: user service did not return a user." in caplog.text


def test_callback_view_handles_oauth_error(mocker, client, caplog):
    """
    GIVEN the authorize service raises an OAuthError (e.g., user denied access)
    WHEN the /auth/callback route is hit
    THEN it should log an error and redirect to the home/failure page.
    """
    # Arrange
    # Mock the service function to simulate failure by raising an exception.
    mock_service_authorize = mocker.patch('auth.services.oauth_authorize')
    mock_service_authorize.side_effect = OAuthError(description="User denied the request.")

    # Capture the log
    caplog.set_level(logging.ERROR)

    # Act
    response = client.get('/auth/callback')

    # Assert
    # 1. Was the service function called?
    mock_service_authorize.assert_called_once()

    # 2. Was the user redirected?
    assert response.status_code == 302
    assert response.location == 'http://localhost:5000/'

    # 3. Was the correct error message logged?
    assert "OAuth error during callback" in caplog.text
    assert "User denied the request." in caplog.text

def test_logout_route_clears_session_and_redirects(admin_client):
    """
        If an authenticated user makes a GET request to the /auth/logout route
        then their session should be cleared and they should be redirected.
        """
    # Arrange
    # The 'admin_client' fixture has already logged the user in by setting
    # a session cookie on the client. We can verify this as a pre-condition.
    with admin_client.session_transaction() as sess:
        assert 'user_id' in sess

    # Act
    # Make a GET request to the logout endpoint using the authenticated client.
    response = admin_client.get('/auth/logout')

    # Assert
    # 1. Assert that the user was redirected (e.g., to the homepage).
    assert response.status_code == 302
    assert response.location == 'http://localhost:5000/'

    # 2. Check if the session is now empty
    with admin_client.session_transaction() as sess:
        assert 'user_id' not in sess
        assert not sess
