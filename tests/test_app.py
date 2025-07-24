# pylint: disable=missing-docstring
import os
from unittest.mock import patch
from bson.objectid import ObjectId
from pymongo.errors import ServerSelectionTimeoutError
import pytest
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

def test_500_response_is_json(admin_client):
    test_book = {
        "title": "Valid Title",
        "author": "AN Other",
        "synopsis": "Test Synopsis"
    }

    # Use patch to mock uuid module failing and throwing an exception
    with patch("uuid.uuid4", side_effect=Exception("An unexpected error occurred")):
        response = admin_client.post("/books", json = test_book)

        # Check the response code is 500
        assert response.status_code == 500

        assert response.content_type == "application/json"
        assert "An unexpected error occurred" in response.get_json()["error"]

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
    assert "error" in response.get_json()
    assert "cannot unpack non-iterable NoneType object" in response.get_json()["error"]

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
            "id": "1",
            "title": "The Great Adventure",
            "synopsis": "A thrilling adventure through the jungles of South America.",
            "author": "Jane Doe",
            "links": {
                "self": "/books/1",
                "reservations": "/books/1/reservations",
                "reviews": "/books/1/reviews"
            },
            "state": "deleted"
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
    assert "404 Not Found" in response.get_json()["error"]

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
    mock_delete_book = mocker.patch('database.mongo_helper.delete_book_by_id')
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

def test_book_database_is_initialized_for_delete_book_route(admin_client):
    with patch("app.books", None):
        response = admin_client.delete("/books/1")
        assert response.status_code == 500
        assert "Book collection not initialized" in response.get_json()["error"]

# ------------------------ Tests for PUT --------------------------------------------

def test_update_book_request_returns_correct_status_and_content_type(admin_client):
    with patch("app.books", books_database):

        test_book = {
            "title": "Test Book",
            "author": "AN Other",
            "synopsis": "Test Synopsis"
        }

        # send PUT request
        response = admin_client.put("/books/1", json=test_book)

        # Check response status code and content type
        assert response.status_code == 200
        assert response.content_type == "application/json"

def test_update_book_request_returns_required_fields(admin_client):
    with patch("app.books", books_database):
        test_book = {
            "title": "Test Book",
            "author": "AN Other",
            "synopsis": "Test Synopsis"
        }

        # Send PUT request
        response = admin_client.put("/books/1", json=test_book)
        response_data = response.get_json()

        # Check that required fields are in the response data
        required_fields = ["title", "synopsis", "author", "links"]
        for field in required_fields:
            assert field in response_data, f"{field} not in response_data"

def test_update_book_replaces_whole_object(admin_client):
    book_to_be_changed = {
        "id": "1",
        "title": "Original Title",
        "author": "Original Author",
        "synopsis": "Original Synopsis",
        "links": {
                "self": "link to be changed",
                "reservations": "link to be changed",
                "reviews": "link to be changed"
        }
    }
    # Patch the books list with just this book (no links)
    with patch("app.books", [book_to_be_changed]):
        updated_data = {
            "title": "Updated Title",
            "author": "Updated Author",
            "synopsis": "Updated Synopsis"
        }

        response = admin_client.put("/books/1", json=updated_data)
        assert response.status_code == 200

        data = response.get_json()
        assert "links" in data
        assert "/books/1" in data["links"]["self"]
        assert "/books/1/reservations" in data["links"]["reservations"]
        assert "/books/1/reviews" in data["links"]["reviews"]

        # Verify other fields were updated
        assert data["title"] == "Updated Title"
        assert data["author"] == "Updated Author"
        assert data["synopsis"] == "Updated Synopsis"

def test_update_book_sent_with_invalid_book_id(admin_client):
    with patch("app.books", books_database):
        test_book = {
            "title": "Some title",
            "author": "Some author",
            "synopsis": "Some synopsis"
        }
        response = admin_client.put("/books/999", json =test_book)
        assert response.status_code == 404
        assert "Book not found" in response.get_json()["error"]

def test_book_database_is_initialized_for_update_book_route(admin_client):
    with patch("app.books", None):
        test_book = {
            "title": "Test Book",
            "author": "AN Other",
            "synopsis": "Test Synopsis"
        }

        # Send PUT request
        response = admin_client.put("/books/1", json=test_book)
        assert response.status_code == 500
        assert "Book collection not initialized" in response.get_json()["error"]

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

def test_append_host_to_links_in_put(admin_client):

    test_book = {
        "title": "Test Book",
        "author": "AN Other",
        "synopsis": "Test Synopsis"
    }
    response = admin_client.put("/books/1", json = test_book)

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
