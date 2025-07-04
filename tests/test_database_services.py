# pylint: disable=missing-docstring
import pytest
from pymongo.errors import ConnectionFailure
from unittest.mock import MagicMock
from database.mongo_helper import insert_book_to_mongo
from database import user_services



def test_insert_book_to_mongo():
    # Setup the mock
    mock_result = MagicMock()
    mock_result.inserted_id = '12345'
    mock_result.acknowledged = True
    # Create a mock for books_collection
    mock_books_collection = MagicMock()
    mock_books_collection.insert_one.return_value = mock_result

    # Test data
    new_book = {
        "title": "The Great Gatsby",
        "author": "F. Scott Fitzgerald",
        "synopsis": "A story about the American Dream"
    }

    # Call the function
    result = insert_book_to_mongo(new_book, mock_books_collection)

    # Assertions
    mock_books_collection.insert_one.assert_called_once_with(new_book)
    assert result == '12345'

def test_get_or_create_user_with_existing_user(mocker):
    """
    If get_or_create_user_from_oidc is called with an existing user, it should
    call find_one and return the result without calling insert_one.
    """
    # Mock the database connection
    mock_get_collection = mocker.patch('database.user_services.get_users_collection')
    # Mock the collection object to be returned
    mock_users_collection = MagicMock()
    mock_get_collection.return_value = mock_users_collection

    # Setup mock data
    fake_profile = {"sub": "google-id-123"}
    existing_user_doc = {"email": "editor.user@example.com", "google_id": "google-id-123"}

    # Configure the fake collection object's methods
    mock_users_collection.find_one.return_value = existing_user_doc

    # Act
    result = user_services.get_or_create_user_from_oidc(fake_profile)

    # Assert
    mock_get_collection.assert_called_once_with()
    mock_users_collection.find_one.assert_called_once_with({'google_id': 'google-id-123'})
    assert result == existing_user_doc

def test_get_users_collection_success(mocker):
    """
    When get_users_collection is called, it should return the correct collection.
    """
    # Mock the app as it's imported in the function
    mock_app = MagicMock()
    mock_app.config = {
        'MONGO_URI': 'mongodb://fake-host:27017/',
        'DB_NAME': 'fake_db'
    }
    mocker.patch('app.app', mock_app)

    # Mock MongoClient
    mock_client_instance = MagicMock()
    mock_mongo_client_class = mocker.patch('database.user_services.MongoClient')
    mock_mongo_client_class.return_value = mock_client_instance

    # Create a fake collection object that will be returned
    expected_collection = MagicMock()
    mock_client_instance.__getitem__.return_value = {'users': expected_collection}

    # Act
    actual_collection = user_services.get_users_collection()

    # Assert
    # Was MongoClient called with the correct fake URI
    mock_mongo_client_class.assert_called_once_with(
        'mongodb://fake-host:27017/',
        serverSelectionTimeoutMS=5000
    )
    assert actual_collection == expected_collection

def test_get_users_collection_failure(mocker):
    """
    If the mongoDB connection fails, when the collection is called
    it should raise a ConnectionFailure.
    """
    # Mock the app as it's imported in the function
    mock_app = MagicMock()
    mock_app.config = {
        'MONGO_URI': 'mongodb://fake-host:27017/',
        'DB_NAME': 'fake_db'
    }
    mocker.patch('app.app', mock_app)

    # Mock the MongoClient class to *raise an exception* when it's called.
    mock_mongo_client_class = mocker.patch('database.user_services.MongoClient')
    mock_mongo_client_class.side_effect = ConnectionFailure("Could not connect")

    # Act & Assert
    # Use pytest.raises to assert that the expected exception was thrown.
    # The 'with' block will pass if a ConnectionFailure is raised inside it,
    # and fail otherwise.
    with pytest.raises(ConnectionFailure):
        user_services.get_users_collection()

    mock_mongo_client_class.assert_called_once()
