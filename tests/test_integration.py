# pylint: disable=missing-docstring
import os
import uuid
from bson.objectid import ObjectId
import pytest
from pymongo import MongoClient
from database import user_services
from app import app

# pylint: disable=R0801
@pytest.fixture(name="client")
def client_fixture():
    """Provides a test client for making requests to our Flask app."""
    app.config['TESTING'] = True
    app.config['MONGO_URI'] = 'mongodb://localhost:27017/'
    app.config['DB_NAME'] = 'test_database'
    app.config['COLLECTION_NAME'] = 'test_books'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', "a-secure-key-for-testing-only")
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

@pytest.fixture(name="mongo_client")
def mongo_client_fixture():
    """Provides a raw MongoDB client for direct DB access in tests."""
    # Connect to mongoDB running locally in docker
    client = MongoClient("mongodb://localhost:27017/")
    # Yield the client to the test function
    yield client
    # Clean up the mongoDB after the test
    client.drop_database("test_database")

@pytest.fixture(name="user_factory")
def test_user_factory():
    """
    A factory fixture that returns a function for creating users.
    This allows tests to create multiple, distinct users.
    """

    def _create_user(role='viewer', name='Test User'):
        """The actual factory function."""
        profile = {
            # Use the name to make the 'sub' and 'email' unique for each user
            'sub': f"google-id-{name.replace(' ', '-').lower()}",
            'email': f"{name.replace(' ', '.').lower()}@example.com",
            'name': name
        }
        # Add the special 'test_role' if we want to create an admin
        if role == 'admin':
            profile['test_role'] = 'admin'

        # Use the service layer to create the user in the test database
        user_doc = user_services.get_or_create_user_from_oidc(profile)
        return user_doc

    # The fixture returns the inner function
    return _create_user

@pytest.fixture(name="authenticated_client")
def authenticated_client_for_testing(client):
    """
    A factory fixture that returns a function to create an authenticated
    client for a given user document.
    """

    def _create_authenticated_client(user_doc):
        """Logs in the given user."""
        with client.session_transaction() as sess:
            sess['user_id'] = str(user_doc['_id'])
        return client  # Return the now-authenticated client

    return _create_authenticated_client


@pytest.fixture(name="logout_client")
def logged_out_client(client):
    """
    Provides a test client that has a session with user_id set to None,
    simulating a logged-out user or a new visitor.
    """
    # Open a session transaction. This is crucial because it ensures
    # the client is interacting with the session machinery.
    def _create_logged_out_client(user_doc):
        """Logs in the given user."""
        with client.session_transaction() as sess:
            sess['user_id'] = str(user_doc['_id'])
            sess['user_id'] = None
        return client  # Return the now-authenticated client

    return _create_logged_out_client

@pytest.fixture(name="reservation_setup")
def reservation_scenario(user_factory, authenticated_client):
    """
    Sets up a complete scenario for reservation tests and returns the
    key components in a dictionary.
    """
    # 1. Create the user personas and clients
    owner_user = user_factory(role='viewer', name='Scenario Owner')
    admin_user = user_factory(role='admin', name='Scenario Admin')
    owner_client = authenticated_client(owner_user)
    test_admin_client = authenticated_client(admin_user)

    # 2. Use the admin to create the book
    book_res = test_admin_client.post("/books", json=book_payloads[0])
    assert book_res.status_code == 201
    created_book = book_res.get_json()

    # 3. Use the owner to create the reservation
    res_res = owner_client.post(f"/books/{created_book['id']}/reservations")
    assert res_res.status_code == 201
    created_reservation = res_res.get_json()

    # 4. Bundle everything into a simple dictionary and return it.
    return {
        "test_admin_client": test_admin_client,
        "owner_client": owner_client,
        "owner_user": owner_user,
        "book": created_book,
        "reservation": created_reservation
    }

# Define multiple book payloads for testing
book_payloads = [
    {
        "title": "The Midnight Library",
        "synopsis": "A novel about all the choices that go into a life well lived.",
        "author": "Matt Haig"
    },
    {
        "title": "Educated",
        "synopsis": "A memoir about a woman who leaves her survivalist family "
                    "and goes on to earn a PhD from Cambridge University.",
        "author": "Tara Westover"
    },
    {
        "title": "Becoming",
        "synopsis": "An autobiography by the former First Lady "
                    "of the United States, Michelle Obama.",
        "author": "Michelle Obama"
    },
    {
        "title": "The Silent Patient",
        "synopsis": "A psychological thriller about a woman who shoots "
                    "her husband and then never speaks again.",
        "author": "Alex Michaelides"
    }
]

def test_post_route_inserts_to_mongodb(mongo_client, admin_client):
    # # Set up the test DB and collection
    db = mongo_client['test_database']
    collection = db['test_books']

    # Act: send the POST request:
    response = admin_client.post(
        "/books", 
        json=book_payloads[0]
    )

    # Assert:
    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"
    response_data = response.get_json()
    assert response_data["title"] == "The Midnight Library"
    assert response_data["author"] == "Matt Haig"

    # Assert database state directly:
    saved_book = collection.find_one({"title": "The Midnight Library"})
    assert saved_book is not None
    assert saved_book["author"] == "Matt Haig"

def test_get_all_books_gets_from_mongodb(admin_client):

    # Arrange
    # POST several books to the test database
    for book_payload in book_payloads:
        response = admin_client.post(
            "/books",
            json=book_payload
        )

    # Act: GET all books
    response = admin_client.get("/books")

    # Assert: Check the response
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    response_data = response.get_json()
    assert isinstance(response_data, dict)
    assert 'total_count' in response_data
    assert 'items' in response_data
    # Assert: Check the total count of books
    assert response_data['total_count'] == len(book_payloads)

    # Assert: Check the title of one of the inserted books
    book_titles = [book['title'] for book in response_data['items']]
    assert "The Midnight Library" in book_titles

def test_update_soft_deleted_book_returns_404(mongo_client, admin_client):
    """
    GIVEN a book exists in the DB but is marked as 'deleted'
    WHEN a PUT request is made to update it
    THEN the API should return a 404 Not Found and the book should NOT be updated.
    """
    db = mongo_client['test_database']
    collection = db['test_books']
    # Arrange
    # Insert a soft-deleted book into the test database.
    soft_deleted_book = {
            "author": "A Deleted Author",
            "id": "550e8400-e29b-41d4-a716-446655440004",
            "links": {
            "reservations":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reservations",
            "reviews":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reviews",
            "self":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004"
            },
            "synopsis": "A book that was deleted.",
            "title": "The Deleted Book",
            "state": "deleted"
      }
    result = collection.insert_one(soft_deleted_book)
    book_id = str(result.inserted_id)

    update_payload = {
        'title': 'Resurrected book',
        'synopsis': 'Trying to resurrect this book',
        'author': 'Book Resurrector'
    }

    # Act
    response = admin_client.put(f"/books/{book_id}", json=update_payload)

    # Assert the API correctly reports that the resource was not found.
    assert response.status_code == 404

    # Assert that the database state was NOT changed.

    book_in_db = collection.find_one({'_id': ObjectId(book_id)})
    assert book_in_db['title'] == 'The Deleted Book'  # The title was NOT updated
    assert book_in_db['state'] == 'deleted'


def test_get_reservation_succeeds_for_admin(reservation_setup):
    """
    INTEGRATION TEST for GET /books/{id}/reservations/{id} as an admin.

    GIVEN a logged-in admin user and an existing reservation owned by ANOTHER user
    WHEN a GET request is made to the reservation's specific URL
    THEN the decorators should grant access and the view should return a 200 OK
    with the correct reservation data.
    """
    # Arrange - the test database and documents are set up in the fixture
    test_admin_client = reservation_setup["test_admin_client"]
    book_id = reservation_setup["book"]["id"]
    reservation_id = reservation_setup["reservation"]["id"]

    # ACT
    response = test_admin_client.get(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # ASSERT
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == reservation_id

def test_get_reservation_succeeds_for_owner_not_admin(reservation_setup):
    """
     INTEGRATION TEST for GET /books/{id}/reservations/{id} as a user who owns the reservation.

    GIVEN a logged-in user and an existing reservation owned by that user
    WHEN a GET request is made to the reservation's specific URL
    THEN the decorators should grant access and the view should return a 200 OK
    with the correct reservation data.
    """
    # Arrange - the test database and documents are set up in the fixture
    owner_client = reservation_setup["owner_client"]
    book_id = reservation_setup["book"]["id"]
    reservation_id = reservation_setup["reservation"]["id"]

    # Act - attempt to access the reservation logged in as the owner
    response = owner_client.get(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # Assert - was the reservation correctly accessed?
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == reservation_id

def test_get_reservation_fails_for_user_not_admin_or_owner(
        authenticated_client,
        user_factory,
        reservation_setup
):
    """
     INTEGRATION TEST for GET /books/{id}/reservations/{id} as a user
     who does not own the reservation.

    GIVEN a logged-in user and an existing reservation owned a different user
    WHEN a GET request is made to the reservation's specific URL
    THEN the decorators should deny access and the view should return 403 Forbidden
    """
    # Arrange - the test database and documents are set up in the fixture
    book_id = reservation_setup["book"]["id"]
    reservation_id = reservation_setup["reservation"]["id"]

    # Create a non-admin user who does not own the reservation
    non_owner_user = user_factory(role='viewer', name='Non-Owner User')
    non_owner_client = authenticated_client(non_owner_user)

    # Act - attempt to access the reservation logged in as the non_owner
    response = non_owner_client.get(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # Assert - was the reservation view denied?
    assert response.status_code == 403
    assert response.content_type == "application/json"
    response_data = response.get_json()
    assert response_data["code"] == 403
    assert response_data["name"] == "Forbidden"
    assert "don't have the permission" in response_data["description"]

def test_get_reservation_with_anonymous_user_redirects_to_login(
        reservation_setup,
        user_factory,
        logout_client
):
    """
    GIVEN no logged-in user
    WHEN a GET request is made to the reservation's specific URL
    THEN the login_required decorator should deny access
    AND the view should return a 302 redirect to the login page.
    """
    # Arrange - the test database and documents are set up in the fixture
    book_id = reservation_setup["book"]["id"]
    reservation_id = reservation_setup["reservation"]["id"]

    # Create a session with a logged out user
    invisible_user = user_factory(role='viewer', name='Invisible User')
    anon_client = logout_client(invisible_user)
    # Act
    # Attempt to access the reservation GET endpoint while not logged in
    response = anon_client.get(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # Assert
    # Was the attempt redirected?
    assert response.status_code == 302
    assert 'http://localhost:5000/auth/login' in response.location

def test_get_reservation_with_non_existent_id_returns_404(reservation_setup):
    """
    GIVEN a logged-in admin user and a correct book_id
    AND a reservation UUID that is valid in format but does not exist in the database
    WHEN a GET request is made to the reservation's specific URL
    THEN the application should return a 404 Not Found response.
    """
    # Arrange - the test database and documents are set up in the fixture
    test_admin_client = reservation_setup["test_admin_client"]
    book_id = reservation_setup["book"]["id"]
    reservation_id = reservation_setup["reservation"]["id"]

    # Create a correctly formatted uuid and check it DOESN'T match the real one
    wrong_res_id = str(uuid.uuid4())
    assert wrong_res_id != reservation_id

    # Act
    # Attempt to access the reservation endpoint with the wrong_res_id
    response = test_admin_client.get(
        f"/books/{book_id}/reservations/{wrong_res_id}"
    )

    # Assert
    assert response.status_code == 404
    assert response.headers["content-type"] == "application/json"
    result = response.get_json()
    assert "not found" in result.get("description")

def test_delete_reservation_succeeds_for_owner_not_admin(reservation_setup):
    """
     INTEGRATION TEST for DELETE /books/{id}/reservations/{id} as a user who owns the reservation.

    GIVEN a logged-in user and an existing reservation owned by that user
    WHEN a DELETE request is made to the reservation's specific URL
    THEN the decorators should grant access and the view should return a 200 OK
    with the cancelled reservation data.
    """
    # Arrange - the test database and documents are set up in the fixture
    owner_client = reservation_setup["owner_client"]
    book_id = reservation_setup["book"]["id"]
    reservation_id = reservation_setup["reservation"]["id"]

    # Act - attempt to access the reservation logged in as the owner
    response = owner_client.delete(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # Assert - was the reservation correctly accessed?
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == reservation_id
    assert response_data['state'] == 'cancelled'

def test_delete_reservation_succeeds_for_admin_not_owner(reservation_setup):
    """
    INTEGRATION TEST for DELETE /books/{id}/reservations/{id} as an admin.

    GIVEN a logged-in admin user and an existing reservation owned by ANOTHER user
    WHEN a DELETE request is made to the reservation's specific URL
    THEN the decorators should grant access and the view should return a 200 OK
    with the cancelled reservation data.
    """
    # Arrange - the test database and documents are set up in the fixture
    test_admin_client = reservation_setup["test_admin_client"]
    book_id = reservation_setup["book"]["id"]
    reservation_id = reservation_setup["reservation"]["id"]

    # Act - attempt to access the reservation logged in as the admin
    response = test_admin_client.delete(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # Assert
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == reservation_id
    assert response_data['state'] == 'cancelled'

def test_delete_reservation_fails_for_user_not_admin_or_owner(
        authenticated_client,
        user_factory,
        reservation_setup
):
    """
     INTEGRATION TEST for DELETE /books/{id}/reservations/{id} as a user
     who does not own the reservation.

    GIVEN a logged-in user and an existing reservation owned by a different user
    WHEN a DELETE request is made to the reservation's specific URL
    THEN the decorators should deny access and the view should return a 403 Forbidden
    """
    # Arrange - the test database and documents are set up in the fixture
    book_id = reservation_setup["book"]["id"]
    reservation_id = reservation_setup["reservation"]["id"]

    # Create a non-admin user who does not own the reservation
    non_owner_user = user_factory(role='viewer', name='Non-Owner User')
    non_owner_client = authenticated_client(non_owner_user)

    # Act - attempt to access the reservation logged in as the non_owner
    response = non_owner_client.delete(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # Assert - was the reservation view denied?
    assert response.status_code == 403
    assert response.content_type == "application/json"
    response_data = response.get_json()
    assert response_data["code"] == 403
    assert response_data["name"] == "Forbidden"
    assert "don't have the permission" in response_data["description"]

def test_delete_reservation_as_anonymous_user_redirects_to_login(client):
    """
    INTEGRATION SANITY CHECK:
    Verifies that the @login_required decorator is active on the DELETE endpoint.
    """
    # Arrange - uuid's not needed as should not reach owner_or_admin decorator
    book_uuid = "some-book-uuid"
    reservation_uuid = "some-reservation-uuid"

    # Act
    response = client.delete(f"/books/{book_uuid}/reservations/{reservation_uuid}")

    # Assert
    assert response.status_code == 302
    assert "http://localhost:5000/auth/login" in response.location
