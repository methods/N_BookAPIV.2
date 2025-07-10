# pylint: disable=missing-docstring
from unittest.mock import MagicMock
import pytest
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
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

def test_get_or_create_user_with_new_user(mocker):
    """
    When get_or_create_user_from_oidc is called and no user is found in the collection,
    it should create a new user and return it.
    """
    # Mock the database connection
    mock_get_collection = mocker.patch('database.user_services.get_users_collection')
    # Mock the collection object to be returned
    mock_users_collection = MagicMock()
    mock_get_collection.return_value = mock_users_collection

    # Configure find_one to return None, simulating a new user
    mock_users_collection.find_one.return_value = None

    # Mock insert_one to simulate the DB assigning an _id and returning it
    fake_new_id = ObjectId()
    mock_users_collection.insert_one.return_value = MagicMock(inserted_id=fake_new_id)

    # Create a fake profile that will be used for the database query
    fake_profile = {
        'sub': 'google-id-new-user',
        'email': 'new.user@example.com',
        'name': 'New User',
        'email_verified': True
    }

    # Act
    returned_user = user_services.get_or_create_user_from_oidc(fake_profile)

    # Assert
    mock_users_collection.find_one.assert_called_once_with({'google_id': 'google-id-new-user'})

    # Check that insert_one was called once with the correct document
    mock_users_collection.insert_one.assert_called_once()
    inserted_doc = mock_users_collection.insert_one.call_args[0][0]
    assert inserted_doc['google_id'] == 'google-id-new-user'
    assert inserted_doc['roles'] == ['viewer']

    # Check the function returns the correct dictionary with the _id field added
    assert returned_user is not None
    assert returned_user['google_id'] == 'google-id-new-user'
    assert returned_user['_id'] == fake_new_id
    assert returned_user['roles'] == ['viewer']

def test_find_user_by_id(mocker):
    """
    Given a user_id, when find_user_by_id is called, it should return the correct document.
    """
    # Arrange
    # Mock the database connection
    mock_get_collection = mocker.patch('database.user_services.get_users_collection')
    mock_users_collection = MagicMock()
    mock_get_collection.return_value = mock_users_collection

    test_id = ObjectId()
    expected_user_doc = {'_id': test_id, 'email': 'test@test.com'}

    # Tell the mocked collection to return the user document when queried
    mock_users_collection.find_one.return_value = expected_user_doc

    # Act
    result = user_services.find_user_by_id(str(test_id))

    # Assert
    # 1. Was find_one called with the correct query?
    # The string ID must be converted to an ObjectID as this is the shape mongoDB expects
    mock_users_collection.find_one.assert_called_once_with({'_id': test_id})

    # 2. Did the function return the correct document?
    assert result == expected_user_doc

def test_find_user_by_id_with_invalid_id_string():
    """
    If find_user_by_id is called with an invalid id, it should
    catch the InvalidID exception and return None.
    """
    # Arrange
    # A string that is not a valid 24-character hex string
    invalid_id_string = "not-a-valid-mongo-id"

    # Act
    result = user_services.find_user_by_id(invalid_id_string)

    # Assert
    assert result is None
