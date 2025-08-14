# pylint: disable=missing-docstring
import os
from bson.objectid import ObjectId
import pytest
from pymongo import MongoClient
from database import user_services, reservation_services
from app import app, get_book_collection

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

# @pytest.fixture(name="admin_user")
# def make_admin_user(mongo_client):
#     """Creates a real admin user in the test database and returns the document."""
#     # 1. Define the OIDC profile for the user we want to create.
#     admin_profile = {
#         'sub': 'google-admin-id-for-test',
#         'email': 'admin@test.com',
#         'name': 'Test Admin',
#         'test_role': 'admin'
#     }
#     admin_doc = user_services.get_or_create_user_from_oidc(admin_profile)
#
#     return admin_doc
#
#
# @pytest.fixture(name="admin_client_integration")
# def create_admin_client_integration(client, admin_user):
#     """
#     An authenticated client for INTEGRATION tests.
#     It logs in as a REAL user from the test database.
#     It does NOT mock the database.
#     """
#
#     with client.session_transaction() as sess:
#         # Set the session with the user's REAL MongoDB _id
#         sess['user_id'] = str(admin_user['_id'])
#
#     yield client

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

    # Arrange: Test book object
    new_book_payload = {
        "title": "The Midnight Library",
        "synopsis": "A novel about all the choices that go into a life well lived.",
        "author": "Matt Haig"
    }

    # Act: send the POST request:
    response = admin_client.post(
        "/books", 
        json=new_book_payload
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


def test_get_reservation_succeeds_for_admin(authenticated_client, user_factory):
    """
    INTEGRATION TEST for GET /books/{id}/reservations/{id} as an admin.

    GIVEN a logged-in admin user and an existing reservation owned by ANOTHER user
    WHEN a GET request is made to the reservation's specific URL
    THEN the decorators should grant access and the view should return a 200 OK
    with the correct reservation data.
    """
    # Arrange
    # 1. Create the two users we need using the factory.
    owner_user = user_factory(role='viewer', name='Owner User')
    admin_user = user_factory(role='admin', name='Admin User')
    # 2. Create a client that is logged in as the ADMIN.
    test_client = authenticated_client(admin_user)

    # Add the book to be reserved into the database
    new_book_payload = {
        "title": "The Midnight Library",
        "synopsis": "A novel about all the choices that go into a life well lived.",
        "author": "Matt Haig"
    }

    # Act: send the POST request:
    response = test_client.post(
        "/books",
        json=new_book_payload
    )
    # Check the response
    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"
    result = response.get_json()
    book_id = str(result.get('id'))

    # Arrange
    # Get the user_doc for the owner of the reservation to be created
    user_doc = owner_user

    # Call the books_collection to pass to the reservation function
    books_collection = get_book_collection()

    # Pass the book_id, user: dict and books_collection to the reservation function
    # We can't use the real route as the logged-in user is an admin, not the owner in this case
    res_result = reservation_services.create_reservation_for_book(
        book_id,
        user_doc,
        books_collection
    )
    reservation_id = res_result.get('id')

    # ACT
    response = test_client.get(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # ASSERT
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == reservation_id

def test_get_reservation_succeeds_for_owner_not_admin(authenticated_client, user_factory):
    """
     INTEGRATION TEST for GET /books/{id}/reservations/{id} as a user who owns the reservation.

    GIVEN a logged-in user and an existing reservation owned by that user
    WHEN a GET request is made to the reservation's specific URL
    THEN the decorators should grant access and the view should return a 200 OK
    with the correct reservation data.
    """
    # Arrange
    # Create the owner user and log them in
    owner_user = user_factory(role='viewer', name='Owner User')
    owner_client = authenticated_client(owner_user)

    # And create an admin user to add the book to the database...
    admin_user = user_factory(role='admin', name='Admin User')
    test_admin_client = authenticated_client(admin_user)
    # Add the book to be reserved into the database
    new_book_payload = {
        "title": "Becoming",
        "synopsis": "An autobiography by the former First Lady "
                    "of the United States, Michelle Obama.",
        "author": "Michelle Obama"
    }

    # ...using the actual route
    response = test_admin_client.post(
        "/books",
        json=new_book_payload
    )
    # Check the book was added correctly and get the book_id created
    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"
    result = response.get_json()
    book_id = str(result.get('id'))

    # Create the reservation - using the real route as the non-admin owner
    res_response = owner_client.post(
        f"/books/{book_id}/reservations"
    )
    # Check the reservation was added and get the reservation_id
    assert res_response.status_code == 201
    res_data = res_response.get_json()
    reservation_id = res_data.get('id')

    # Act - attempt to access the reservation logged in as the owner
    response = owner_client.get(
        f"/books/{book_id}/reservations/{reservation_id}"
    )

    # Assert - was the reservation correctly accessed?
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['id'] == reservation_id

def test_get_reservation_fails_for_user_not_admin_or_owner(authenticated_client, user_factory):
    """
     INTEGRATION TEST for GET /books/{id}/reservations/{id} as a user
     who does not own the reservation.

    GIVEN a logged-in user and an existing reservation owned a different user
    WHEN a GET request is made to the reservation's specific URL
    THEN the decorators should deny access and the view should return a 200 OK
    with the correct reservation data.
    """
    # Arrange
    # Create an admin user to add the book to the database and create a reservation
    admin_user = user_factory(role='admin', name='Admin User')
    test_admin_client = authenticated_client(admin_user)

    response = test_admin_client.post(
        "/books",
        json=book_payloads[1]
    )
    # Check the book was added correctly and get the book_id created
    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"
    result = response.get_json()
    book_id = str(result.get('id'))

    # Create a reservation using the logged in admin user
    res_response = test_admin_client.post(
        f"/books/{book_id}/reservations"
    )
    # Check the reservation was added and get the reservation_id
    assert res_response.status_code == 201
    res_data = res_response.get_json()
    reservation_id = res_data.get('id')

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
