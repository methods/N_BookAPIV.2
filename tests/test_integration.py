# pylint: disable=missing-docstring
import os
from bson.objectid import ObjectId
import pytest
from pymongo import MongoClient
from app import app

# pylint: disable=R0801
@pytest.fixture(name="client")
def client_fixture():
    """Provides a test client for making requests to our Flask app."""
    app.config['TESTING'] = True
    app.config['MONGO_URI'] = 'mongodb://localhost:27017/'
    app.config['DB_NAME'] = 'test_database'
    app.config['COLLECTION_NAME'] = 'test_books'
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
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
