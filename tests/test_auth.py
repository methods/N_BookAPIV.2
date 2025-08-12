# pylint: disable=missing-docstring
import os
import uuid
from unittest.mock import MagicMock
from bson.objectid import ObjectId
from flask import redirect, g, session, jsonify
import pytest
from werkzeug.exceptions import InternalServerError, NotFound, Forbidden
from auth.decorators import login_required, roles_required, reservation_owner_or_admin_required
import auth.services as auth_services
from auth.services import AuthServiceError
from app import app

@pytest.fixture(name="_client")
def client_fixture():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', "a-secure-key-for-testing-only")
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
        'client_kwargs': {'scope': 'openid email profile'}
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
    mock_user_service_call = mocker.patch(
        'auth.services.user_services.get_or_create_user_from_oidc'
    )

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


def test_oauth_authorize_raises_error_if_no_profile_in_token(mocker):
    """
    If Authlib returns a token with no 'userinfo'
    when oauth_authorize is called, it should raise a custom AuthServiceError.
    """
    # Arrange
    # 1. Mock the Authlib call.
    mock_authlib_call = mocker.patch('auth.services.oauth.google.authorize_access_token')

    # 2. Configure the mock to return a dictionary that is MISSING the 'userinfo' key.
    #    This simulates the exact failure condition we want to test.
    mock_authlib_call.return_value = {'access_token': 'some_token', 'other_stuff': '...'}

    # Act & ASSERT
    # Use pytest.raises to assert that our specific exception is raised.
    with pytest.raises(AuthServiceError, match="Could not retrieve user profile"):
        auth_services.oauth_authorize()

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
            return jsonify(message="You should not see this!")

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

def test_login_required_with_invalid_user_id_clears_session_and_redirects(mocker, _client):
    """
    If a user has an invalid user_id, when they access a protected route,
    session should be cleared + they should be redirected to the login page.
    """
    # Arrange
    # Mock the database service to fail the user lookup
    mock_find_user = mocker.patch('auth.decorators.user_services.find_user_by_id')
    mock_find_user.return_value = None
    # Mock invalid user_id to be passed
    invalid_user_id = str(ObjectId())

    with app.test_request_context('/protected-route'):
        # Manually set the session
        session['user_id'] = str(invalid_user_id)
        # Define the decorated fake view
        @login_required
        def fake_protected_view():
            return jsonify(message="This should never be returned.")

        # Act
        response = fake_protected_view()

        # Assert
        # 1. Was the database queried with the correct ID from the session?
        mock_find_user.assert_called_once_with(str(invalid_user_id))

        # 2. Was the user redirected appropriately?
        assert response.status_code == 302
        assert 'http://localhost:5000/auth/login' in response.location

        # 3. After the redirect, the session should be empty.
        assert 'user_id' not in session

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

def test_reservation_owner_or_admin_decorator_allows_owner_unit(mocker, _client):
    """
    UNIT TEST:
    GIVEN a user who is the owner of a reservation (and not an admin)
    WHEN a view protected by the decorator is called
    THEN it should fetch the reservation, attach it to g.reservation,
    and allow the view function to execute.
    """
    # NOTE - Test written by AI from docstring
    # ARRANGE
    # 1. Define the fake data. The key is that the user's public 'id'
    #    matches the 'user_id' in the reservation document.
    fake_user_public_id = "user-uuid-123"
    fake_user_doc = {
        '_id': ObjectId(),
        'id': fake_user_public_id,
        'email': 'owner@test.com',
        'roles': ['viewer'] # This user is NOT an admin
    }

    fake_reservation_id = str(uuid.uuid4())
    fake_reservation_doc = {
        '_id': ObjectId(),
        'id': fake_reservation_id,
        'user_id': fake_user_public_id, # Link to the owner
        'book_id': str(uuid.uuid4())
    }

    # 2. Mock the dependency of the decorator, which is the service function
    #    that fetches the reservation.
    mock_find_reservation = mocker.patch(
        'auth.decorators.reservation_services.find_reservation_by_id'
    )
    mock_find_reservation.return_value = fake_reservation_doc

    # 3. Create a test request context. This is what allows us to use 'g'.
    with app.test_request_context(f"/reservations/{fake_reservation_id}"):
        # 4. Manually set g.user. We are simulating the state AFTER
        #    @login_required has successfully run.
        g.user = fake_user_doc

        # 5. Define a fake view function and apply our decorator to it.
        @reservation_owner_or_admin_required
        def fake_protected_view(reservation_id):
            # This is the code that will run if the decorator allows access.
            # We can use it to prove that g.reservation was set correctly.
            return f"Success for reservation {g.reservation['id']}"

        # ACT
        # Call the decorated function directly.
        response = fake_protected_view(reservation_id=fake_reservation_id)

    # ASSERT
    # 1. Was the database service called to fetch the reservation?
    mock_find_reservation.assert_called_once_with(fake_reservation_id)

    # 2. Did the view execute successfully and return the expected success message?
    assert response == f"Success for reservation {fake_reservation_id}"


def test_reservation_decorator_aborts_500_if_kwarg_is_missing(_client):
    """
    UNIT TEST:
    GIVEN a route that is missing the 'reservation_id' variable
    WHEN the decorator is called
    THEN it should abort with a 500 Internal Server Error.
    """
    with app.test_request_context('/some_other_route'):
        # ARRANGE
        # The decorator should fail before it ever calls a service
        @reservation_owner_or_admin_required
        def bad_view():
            pass

        # ACT & ASSERT
        # Assert that calling the view with NO keyword arguments
        # raises the correct exception.
        with pytest.raises(InternalServerError) as exc_info:
            bad_view()

        # Check the error message for clarity
        assert "couldn't find reservation ID in URL" in str(exc_info.value)


def test_reservation_decorator_aborts_404_if_resource_not_found(mocker, _client):
    """
    UNIT TEST:
    GIVEN a reservation ID that does not exist
    WHEN the decorator is called
    THEN it should abort with a 404 Not Found error.
    """
    # ARRANGE
    # Mock the service dependency to simulate "not found"
    mock_find_reservation = mocker.patch(
        'auth.decorators.reservation_services.find_reservation_by_id'
    )
    mock_find_reservation.return_value = None

    non_existent_uuid = "non-existent-uuid-123"

    with app.test_request_context(f"/reservations/{non_existent_uuid}"):
        # We still need a valid g.user for the decorator to run past the login check
        g.user = {'roles': ['viewer'], 'id': 'some-user-id'}

        @reservation_owner_or_admin_required
        def fake_view(reservation_id):
            pass

        # ACT & ASSERT
        with pytest.raises(NotFound):  # werkzeug.exceptions.NotFound is the 404 error
            fake_view(reservation_id=non_existent_uuid)

    # Verify the service was called correctly before the abort
    mock_find_reservation.assert_called_once_with(non_existent_uuid)

def test_reservation_decorator_aborts_403_for_unauthorized_user(mocker, _client):
    """
    UNIT TEST:
    GIVEN a user who is neither the owner nor an admin
    WHEN the decorator is called
    THEN it should abort with a 403 Forbidden error.
    """
    # ARRANGE
    # 1. This user is NOT an admin.
    unauthorized_user = {'id': 'user-id-123', 'roles': ['viewer']}

    # 2. This reservation is owned by SOMEONE ELSE.
    reservation_owned_by_other = {
        'id': 'res-uuid-abc',
        'user_id': 'a-different-user-id-456'
    }

    # 3. Mock the service to return the reservation.
    mock_find_reservation = mocker.patch(
        'auth.decorators.reservation_services.find_reservation_by_id'
    )
    mock_find_reservation.return_value = reservation_owned_by_other

    with app.test_request_context("/reservations/res-uuid-abc"):
        g.user = unauthorized_user

        @reservation_owner_or_admin_required
        def fake_view(reservation_id):
            pass

        # ACT & ASSERT
        with pytest.raises(Forbidden): # werkzeug.exceptions.Forbidden is the 403
            fake_view(reservation_id="res-uuid-abc")
