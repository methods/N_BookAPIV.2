# pylint: disable=missing-docstring
import os
import uuid
from datetime import datetime, timezone
from unittest.mock import patch
from pymongo.errors import ServerSelectionTimeoutError
import pytest
from database.reservation_services import BookNotAvailableForReservationError
from app import app, get_book_collection

# Option 1: Rename the fixture to something unique (which I've used)
# Option 2: Use a linter plugin that understands pytest
# pylint: disable=R0801
@pytest.fixture(name="client")
def client_fixture():
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', "a-secure-key-for-testing-only")
    return app.test_client()

# This client fixture is logged in as a fake admin user
@pytest.fixture(name="admin_client")
def admin_client_fixture(client, mocker):
    # Create the fake admin user object
    fake_admin_id = str(uuid.uuid4())
    fake_admin_doc = {
        'id': fake_admin_id,
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
        sess['user_id'] = fake_admin_id

    # The 'client' object that was passed in now has the session cookie.
    yield client


@pytest.fixture(name="viewer_only_client")
def logged_in_client(client, mocker):
    """
    Provides a test client "logged in" as a specific user by mocking
    the user lookup in the @login_required decorator.
    """
    fake_user_id = str(uuid.uuid4())
    # 1. Define the fake user that will be placed in g.user
    fake_user_doc = {
        'id': fake_user_id,
        'email': 'testy.mctestface@example.com',
        'given_name': 'Testy',
        'family_name': 'McTestface',
        'roles': ['viewer']
    }

    # 2. Mock the find_user_by_id function that @login_required depends on
    mocker.patch(
        'auth.decorators.user_services.find_user_by_id',
        return_value=fake_user_doc
    )

    # 3. Set the session cookie on the client
    with client.session_transaction() as sess:
        sess['user_id'] = fake_user_id

    yield client

# Create a stub to mock the insert_book_to_mongo function to avoid inserting to real DB
@pytest.fixture(name="_insert_book_to_db")
def stub_insert_book():
    with patch("app.insert_book_to_mongo") as mock_insert_book:
        mock_insert_book.return_value.inserted_id = "12345"
        yield mock_insert_book

# Mock book database object

books_database = [
        {
            "id": "1",
            "title": "The Great Adventure",
            "synopsis": "A thrilling adventure through the jungles of South America.",
            "author": "Jane Doe",
            "links": {
                "self": "/books/1",
                "reservations": "/books/1/reservations",
                "reviews": "/books/1/reviews"
            },
            "state": "active"
        },
        {
            "id": "2",
            "title": "Mystery of the Old Manor",
            "synopsis": "A detective story set in an old manor with many secrets.",
            "author": "John Smith",
            "links": {
                "self": "/books/2",
                "reservations": "/books/2/reservations",
                "reviews": "/books/2/reviews"
            },
            "state": "active"
        },
        {
            "id": "3",
            "title": "The Science of Everything",
            "synopsis": "An in-depth look at the scientific principles that govern our world.",
            "author": "Alice Johnson",
            "links": {
                "self": "/books/3",
                "reservations": "/books/3/reservations",
                "reviews": "/books/3/reviews"
            },
            "state": "deleted"
        }
    ]

# ------------------- Tests for POST ---------------------------------------------

def test_add_book_creates_new_book(admin_client, _insert_book_to_db):

    test_book = {
        "title": "Test Book",
        "author": "AN Other",
        "synopsis": "Test Synopsis"
    }

    response = admin_client.post("/books", json = test_book)

    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"

    response_data = response.get_json()
    required_fields = ["id", "title", "synopsis", "author", "links"]
    # check that required fields are in the response data
    for field in required_fields:
        assert field in response_data, f"{field} not in response_data"

def test_add_book_sent_with_missing_required_fields(admin_client):
    test_book = {
        "author": "AN Other"
        # missing 'title' and 'synopsis'
    }
    response = admin_client.post("/books", json = test_book)

    assert response.status_code == 400
    response_data = response.get_json()
    assert 'error' in response_data
    assert "Missing required fields: title, synopsis" in response.get_json()["error"]


def test_add_book_sent_with_wrong_types(admin_client):
    test_book = {
        "title": 1234567,
        "author": "AN Other",
        "synopsis": "Test Synopsis"
    }

    response = admin_client.post("/books", json = test_book)

    assert response.status_code == 400
    response_data = response.get_json()
    assert 'error' in response_data
    assert "Field title is not of type <class 'str'>" in response.get_json()["error"]

def test_add_book_with_invalid_json_content(admin_client):

    # This should trigger a TypeError
    response = admin_client.post("/books", json ="This is not a JSON object")

    assert response.status_code == 400
    assert "JSON payload must be a dictionary" in response.get_json()["error"]

def test_add_book_check_request_header_is_json(admin_client):

    response = admin_client.post(
        "/books",
        data ="This is not a JSON object",
        headers = {"content-type": "text/plain"}
    )

    assert response.status_code == 415
    assert "Request must be JSON" in response.get_json()["error"]

def test_add_reservation_view_on_success(mocker, viewer_only_client):
    """
    GIVEN a logged-in user and a valid payload
    WHEN a POST request is made to create a reservation for a valid book
    THEN it should call the reservation service and return a 201 Created response.
    """
    # Arrange
    # Mock data for the book and reservation data
    fake_book_uuid = "a1b2c3d4-e5f6-7890-1234-567890abcdef"

    # This is the fake, processed document we expect our service to return.
    fake_created_reservation = {
        'id': str(uuid.uuid4()),
        'book_id': fake_book_uuid,
        'forenames': 'Testy',
        'surname': 'McTestface',
        'state': 'reserved',
        'reservedAt': datetime.now(timezone.utc).isoformat()
    }

    # Mock the service function that the view depends on.
    mock_create_reservation = mocker.patch(
        'app.reservation_services.create_reservation_for_book'  # Adjust path as needed
    )
    mock_create_reservation.return_value = fake_created_reservation

    # Act
    # Use your authenticated client to make the request. A 'viewer' is fine.
    response = viewer_only_client.post(
        f'/books/{fake_book_uuid}/reservations',
        json={}
    )

    # Assert
    # Was the service called with the correct arguments from the URL and payload?
    mock_create_reservation.assert_called_once()

    # Examine the arguments passed to the service function
    call_args = mock_create_reservation.call_args[0]
    passed_book_uuid = call_args[0]
    passed_user_object = call_args[1]
    passed_collection_object = call_args[2]

    assert passed_book_uuid == fake_book_uuid
    # Verify that the user object passed was the one from our logged-in session.
    assert passed_user_object['email'] == 'testy.mctestface@example.com'
    assert passed_user_object['given_name'] == 'Testy'
    # Verify the collection was passed (as per your current design).
    assert passed_collection_object is not None

    # 3. Check the HTTP response.
    assert response.status_code == 201
    response_data = response.get_json()
    assert response_data['forenames'] == 'Testy'
    assert response_data['id'] == fake_created_reservation['id']

def test_add_reservation_view_for_invalid_book_returns_404(mocker, viewer_only_client):
    """
    GIVEN a logged-in user
    WHEN they try to create a reservation for a book that is invalid or deleted
    AND the reservation service raises a BookNotAvailableForReservationError
    THEN the view should catch the exception and return a 404 Not Found.
    """
    # Note - fully AI generated test
    # ARRANGE
    # 1. An ID for a book that we'll pretend doesn't exist or is deleted.
    non_existent_book_uuid = "a1b2c3d4-e5f6-7890-ffffffffffff"

    # 2. Mock the service function to simulate the failure.
    #    Instead of returning a value, use 'side_effect' to make it raise our custom exception.
    error_message = f"Book with ID {non_existent_book_uuid} is not available for reservation."
    mock_create_reservation = mocker.patch(
        'app.reservation_services.create_reservation_for_book'  # Adjust path as needed
    )
    mock_create_reservation.side_effect = BookNotAvailableForReservationError(error_message)

    # ACT
    # Make the request using an authenticated client. The payload doesn't matter
    # for this test, as the service will fail before it's used.
    response = viewer_only_client.post(
        f'/books/{non_existent_book_uuid}/reservations',
        json={}  # An empty JSON body is fine since our service is mocked to fail
    )

    # ASSERT
    # 1. Was our service function called? This confirms the view logic was triggered.
    mock_create_reservation.assert_called_once()

    # 2. Did the view correctly translate the exception into a 404 Not Found?
    assert response.status_code == 404
    assert response.content_type == "application/json"

    # 3. Did the response body contain the helpful error message from the exception?
    response_data = response.get_json()
    assert "error" in response_data
    assert response_data["error"] == error_message

# ------------------------ Tests for GET --------------------------------------------
def test_get_all_books_returns_all_books(client):
    response = client.get("/books")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    response_data = response.get_json()
    assert isinstance(response_data, dict)
    assert 'total_count' in response_data
    assert 'items' in response_data

def test_get_all_returns_correctly_when_list_is_empty(mocker, client):
    """
    Given an empty list, when get_all is called it
    should return 200 OK with the correct empty list and count structure.
    """
    # Arrange
    # Mock the service function in app.py that get_all depends on
    mock_get_books = mocker.patch('app.find_all_books')
    mock_get_books.return_value = ([], 0)

    #Act
    response = client.get("/books")

    # Assert
    assert response.status_code == 200
    assert response.content_type == "application/json"

    response_data = response.get_json()
    assert response_data == {
        "total_count": 0,
        "offset": 0,
        "limit": 20,
        "items": []
    }
    mock_get_books.assert_called_once()

def test_get_all_books_returns_500_if_service_returns_none(mocker, client):
    # Arrange
    # Mock the service function in app.py that get_all depends on
    mock_get_books = mocker.patch('app.find_all_books')
    mock_get_books.return_value = None

    response = client.get("/books")
    assert response.status_code == 500
    assert response.content_type == "application/json"
    response_data = response.get_json()
    assert "error" in response_data
    assert response_data["error"] == "An internal server error occurred."

def test_missing_fields_in_book_object_returned_by_database(mocker, client):
    # Arrange
    # Mock the service function in app.py that get_all depends on
    mock_get_books = mocker.patch('app.find_all_books')
    mock_get_books.return_value = ([
            {
                "id": "1",
                "title": "The Great Adventure",
                "synopsis": "A thrilling adventure through the jungles of South America.",
                "author": "Jane Doe",
                "links": {
                    "self": "/books/1",
                    "reservations": "/books/1/reservations",
                    "reviews": "/books/1/reviews"
                },
                "state": "active"
            },
            {
                "id": "2",
                "title": "Mystery of the Old Manor",
                "links": {
                    "self": "/books/2",
                    "reservations": "/books/2/reservations",
                    "reviews": "/books/2/reviews"
                },
                "state": "active"
            }
                                   ], 0)

    response = client.get("/books")
    assert response.status_code == 500
    assert "Missing fields" in response.get_json()["error"]

 #-------- Tests for filter GET /books by delete ----------------
def test_get_books_excludes_deleted_books_and_omits_state_field(mocker, client):
    # Arrange
    # Mock the service function in app.py that get_all depends on
    mock_get_books = mocker.patch('app.find_all_books')
    mock_get_books.return_value = ([
        {
            "id": "2",
            "title": "Mystery of the Old Manor",
            "synopsis": "A detective story set in an old manor with many secrets.",
            "author": "John Smith",
            "links": {
                "self": "/books/2",
                "reservations": "/books/2/reservations",
                "reviews": "/books/2/reviews"
            },
            "state": "active"
        },
        {
            "id": "3",
            "title": "The Science of Everything",
            "synopsis": "An in-depth look at the scientific principles that govern our world.",
            "author": "Alice Johnson",
            "links": {
                "self": "/books/3",
                "reservations": "/books/3/reservations",
                "reviews": "/books/3/reviews"
            }
        }
                                    ], 0)

    response = client.get("/books")
    assert response.status_code == 200

    data = response.get_json()
    assert "items" in data
    books = data["items"]

    # Check right object is returned
    assert len(books) == 2
    for book in books:
        assert "state" not in book
    assert books[0].get("id") == '2'
    assert books[1].get("title") == "The Science of Everything"

 #-------- Tests for GET a single resource ----------------

def test_get_book_returns_specified_book(mocker, client):
    # Arrange
    # Mock the service function in app.py that get_book depends on
    mock_get_book = mocker.patch('app.find_one_book')
    mock_get_book.return_value = {
            "_id": "6855632dd4e66f0d8b052770",
            "author": "J.D. Salinger",
            "id": "550e8400-e29b-41d4-a716-446655440004",
            "links": {
            "reservations":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reservations",
            "reviews":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reviews",
            "self":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004"
            },
            "synopsis": "A story about teenage rebellion and alienation.",
            "title": "The Catcher in the Rye",
            "state": "active"
      }


    # Test GET request using the book ID
    response = client.get("/books/6855632dd4e66f0d8b052770")

    assert response.status_code == 200
    assert response.content_type == "application/json"
    returned_book = response.get_json()
    assert returned_book["_id"] == "6855632dd4e66f0d8b052770"
    assert returned_book["title"] == "The Catcher in the Rye"
    assert "state" not in returned_book

def test_get_book_not_found_returns_404(client):
    # Test GET request using invalid book ID
    response = client.get("/books/12341234")
    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert "Book not found" in response.get_json()["error"]

def test_invalid_urls_return_404(client):
    # Test invalid URL
    response = client.get("/books/")
    assert response.status_code == 404
    assert response.content_type == "application/json"
    response_data = response.get_json()
    # Assert that the values are correct for a 404.
    assert "code" in response_data
    assert "name" in response_data
    assert "description" in response_data
    assert response_data["code"] == 404
    assert response_data["name"] == "Not Found"

def test_get_book_returns_404_if_state_equals_deleted(mocker, client):
    # Mock the service function in app.py that get_book depends on
    mock_get_book = mocker.patch('app.find_one_book')
    mock_get_book.return_value = {
            "_id": "6855632dd4e66f0d8b052770",
            "author": "J.D. Salinger",
            "id": "550e8400-e29b-41d4-a716-446655440004",
            "links": {
            "reservations":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reservations",
            "reviews":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reviews",
            "self":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004"
            },
            "synopsis": "A story about teenage rebellion and alienation.",
            "title": "The Catcher in the Rye",
            "state": "deleted"
      }
    # Test GET request using the book ID
    response = client.get("/books/6855632dd4e66f0d8b052770")

    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert "Book not found" in response.get_json()["error"]

# ------------------------ Tests for DELETE --------------------------------------------

def test_book_is_soft_deleted_on_delete_request(mocker, admin_client):
    # Mock the service function in app.py that delete_book depends on
    mock_delete_book = mocker.patch('app.delete_book_by_id')
    mock_delete_book.return_value = {
            "_id": "6855632dd4e66f0d8b052770",
            "author": "J.D. Salinger",
            "id": "550e8400-e29b-41d4-a716-446655440004",
            "links": {
            "reservations":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reservations",
            "reviews":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reviews",
            "self":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004"
            },
            "synopsis": "A story about teenage rebellion and alienation.",
            "title": "The Catcher in the Rye",
            "state": "deleted"
      }

    # Send DELETE request
    book_id = '6855632dd4e66f0d8b052770'
    response = admin_client.delete(f"/books/{book_id}")

    assert response.status_code == 204
    assert response.data == b''

def test_delete_book_as_anon_user_is_blocked(client):
    book_id ="1234567"
    response = client.delete(f"/books/{book_id}")
    assert response.status_code == 302
    assert 'http://localhost:5000/auth/login' in response.location

def test_delete_invalid_book_id(admin_client):
    response = admin_client.delete("/books/12341234")
    assert response.status_code == 404
    assert response.content_type == "application/json"
    assert "Book not found" in response.get_json()["error"]

# ------------------------ Tests for PUT --------------------------------------------

def test_update_book_request_returns_correct_status_and_content_type(mocker, admin_client):
    # Arrange
    # Set a book_id to be supplied by the client request
    book_id_to_update = "6855632dd4e66f0d8b052770"
    # Mock the service function in app.py that update_book depends on
    mock_update_book_service = mocker.patch('app.update_book_by_id')
    mock_update_book_service.return_value = {
        '_id': book_id_to_update,
        'title': 'The New Title',
        'author': 'New Author',
        'synopsis': 'A new synopsis.',
        "links": {
            "self": "/books/550e8400-e29b-41d4-a716-446655440001",
            "reservations": "/books/550e8400-e29b-41d4-a716-446655440001/reservations",
            "reviews": "/books/550e8400-e29b-41d4-a716-446655440001/reviews"
        },
        'state': 'active'
      }

    # Fake JSON payload to be supplied by the client request
    update_payload = {
        'title': 'The New Title',
        'author': 'New Author',
        'synopsis': 'A new synopsis.'
    }

    # Act
    response = admin_client.put(
        f"/books/{book_id_to_update}",
        json=update_payload
    )

    # Assert
    mock_update_book_service.assert_called_once()
    assert response.status_code == 200
    response_data = response.get_json()
    assert response_data['title'] == 'The New Title'
    assert response_data['_id'] == book_id_to_update
    assert response_data['author'] == 'New Author'
    assert response_data['synopsis'] == 'A new synopsis.'
    assert "links" in response_data
    assert 'state' not in response_data

def test_update_book_sent_with_invalid_book_id(mocker, admin_client):
    # Mock the service function in app.py that update_book depends on
    mock_update_book_service = mocker.patch('app.update_book_by_id')
    mock_update_book_service.return_value = None
    test_book = {
        "title": "Some title",
        "author": "Some author",
        "synopsis": "Some synopsis"
    }
    response = admin_client.put("/books/999", json =test_book)
    assert response.status_code == 404
    assert "Book not found" in response.get_json()["error"]

def test_update_book_check_request_header_is_json(admin_client):

    response = admin_client.put(
        "/books/1",
        data ="This is not a JSON object",
        headers = {"content-type": "text/plain"}
    )

    assert response.status_code == 415
    assert "Request must be JSON" in response.get_json()["error"]

def test_update_book_with_invalid_json_content(admin_client):

    # This should trigger a TypeError
    response = admin_client.put("/books/1", json ="This is not a JSON object")

    assert response.status_code == 400
    assert "JSON payload must be a dictionary" in response.get_json()["error"]

def test_update_book_sent_with_missing_required_fields(admin_client):
    test_book = {
        "author": "AN Other"
        # missing 'title' and 'synopsis'
    }
    response = admin_client.put("/books/1", json = test_book)

    assert response.status_code == 400
    response_data = response.get_json()
    assert 'error' in response_data
    assert "Missing required fields: title, synopsis" in response.get_json()["error"]

# ------------------------ Tests for HELPER FUNCTIONS -------------------------------------

def test_append_host_to_links_in_post(admin_client, _insert_book_to_db):
    # 1. Make a POST request
    test_book = {
        "title": "Append Test Book",
        "author": "AN Other II",
        "synopsis": "Test Synopsis"
    }

    response = admin_client.post("/books", json = test_book)

    assert response.status_code == 201
    assert response.headers["content-type"] == "application/json"

    # 2. Get the response data
    response_data = response.get_json()
    new_book_id = response_data.get("id")
    links = response_data.get("links")

    assert new_book_id is not None, "Response JSON must contain an 'id'"
    assert links is not None, "Response JSON must contain a 'links' object"

    # 3. Assert the hostname in the generated links
    print(f"\n[TEST INFO] Links returned from API: {links}")
    self_link = links.get("self")
    assert self_link is not None, "'links' object must contain a 'self' link"
    # Check that the hostname from the simulated request ('localhost') was correctly prepended.
    expected_link_start = "http://localhost"
    assert self_link.startswith(expected_link_start), \
        f"Link should start with the test server's hostname '{expected_link_start}'"
    # Also check that the path is correct
    expected_path = f"/books/{new_book_id}"
    assert self_link.endswith(expected_path), \
        f"Link should end with the resource path '{expected_path}'"

def test_append_host_to_links_in_get(client):
    response = client.get("/books")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    # Get the response data
    response_data = response.get_json()
    assert isinstance(response_data, dict)
    assert 'total_count' in response_data
    assert 'items' in response_data

    # response_data["items"]["links"]["self"]
    for book in response_data["items"]:
        new_book_id = book.get("id")
        assert book["links"]["self"].startswith("http://localhost")
        assert book["links"]["reservations"].startswith("http://localhost")
        assert book["links"]["reviews"].startswith("http://localhost")
        assert book["links"]["self"].endswith(f"books/{new_book_id}")

def test_append_host_to_links_in_get_book(mocker, client):

    # Mock the service function in app.py that get_book depends on
    mock_get_book = mocker.patch('app.find_one_book')
    mock_get_book.return_value = {
            "_id": "6855632dd4e66f0d8b052770",
            "author": "J.D. Salinger",
            "id": "550e8400-e29b-41d4-a716-446655440004",
            "links": {
            "reservations":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reservations",
            "reviews":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004/reviews",
            "self":
                "http://127.0.0.1:5000/books/550e8400-e29b-41d4-a716-446655440004"
            },
            "synopsis": "A story about teenage rebellion and alienation.",
            "title": "The Catcher in the Rye",
            "state": "active"
      }


    # Test GET request using the book ID
    response = client.get("/books/6855632dd4e66f0d8b052770")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    # Get the response data, the ID and links
    response_data = response.get_json()
    book_id = response_data.get("id")
    links = response_data.get("links")

    assert book_id is not None, "Response JSON must contain an 'id'"
    assert links is not None, "Response JSON must contain a 'links' object"

    self_link = links.get("self")
    assert self_link is not None, "'links' object must contain a 'self' link"

    expected_link_start = "http://127.0.0.1:5000"
    assert self_link.startswith(expected_link_start), \
        f"Link should start with the test server's hostname '{expected_link_start}'"

    expected_path = f"/books/{book_id}"
    assert self_link.endswith(expected_path), \
        f"Link should end with the resource path '{expected_path}'"

def test_append_host_to_links_in_put(mocker, admin_client):

    # Arrange
    # Set a book_id to be supplied by the client request
    book_id_to_update = "6855632dd4e66f0d8b052770"
    # Mock the service function in app.py that update_book depends on
    mock_update_book_service = mocker.patch('app.update_book_by_id')
    mock_update_book_service.return_value = {
        '_id': book_id_to_update,
        'title': 'The New Title',
        'author': 'New Author',
        'synopsis': 'A new synopsis.',
        "links": {
            "self": "/books/6855632dd4e66f0d8b052770",
            "reservations": "/books/6855632dd4e66f0d8b052770/reservations",
            "reviews": "/books/6855632dd4e66f0d8b052770/reviews"
        },
        'state': 'active'
      }

    # Fake JSON payload to be supplied by the client request
    update_payload = {
        'title': 'The New Title',
        'author': 'New Author',
        'synopsis': 'A new synopsis.'
    }

    # Act
    response = admin_client.put(
        f"/books/{book_id_to_update}",
        json=update_payload
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    # Get the response data, the ID and links
    response_data = response.get_json()
    book_id = response_data.get("_id")
    links = response_data.get("links")

    assert book_id is not None, "Response JSON must contain an 'id'"
    assert links is not None, "Response JSON must contain a 'links' object"

    self_link = links.get("self")
    assert self_link is not None, "'links' object must contain a 'self' link"

    expected_link_start = "http://localhost"
    assert self_link.startswith(expected_link_start), \
        f"Link should start with the test server's hostname '{expected_link_start}'"

    expected_path = f"/books/{book_id}"
    assert self_link.endswith(expected_path), \
        f"Link should end with the resource path '{expected_path}'"

def test_get_book_collection_handles_connection_failure():
    with patch("app.MongoClient") as mock_client:
        # Set the side effect to raise a ServerSelectionTimeoutError
        mock_client.side_effect = ServerSelectionTimeoutError("Mock Connection Timeout")

        with pytest.raises(Exception) as exc_info:
            get_book_collection()

        assert "Could not connect to MongoDB: Mock Connection Timeout" in str(exc_info.value)
