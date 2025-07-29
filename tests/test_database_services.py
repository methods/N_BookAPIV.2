# pylint: disable=missing-docstring
import uuid
from unittest.mock import MagicMock
from copy import deepcopy
import pytest
from pymongo import ReturnDocument
from pymongo.errors import ConnectionFailure
from bson.objectid import ObjectId
from database.mongo_helper import (
    insert_book_to_mongo,
    find_all_books,
    find_one_book,
    delete_book_by_id,
    update_book_by_id
)
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

def test_find_all_books():
    """
    WHEN find_all_books is called
    THEN it should call find(), convert the cursor to a list, and stringify the IDs.
    """
    # Arrange
    # Mock the books collection
    mock_books_collection = MagicMock()
    # Test data
    fake_book_id_1 = ObjectId()
    fake_book_id_2 = ObjectId()
    mock_db_data = [
        {'_id': fake_book_id_1, 'title': 'Book One'},
        {'_id': fake_book_id_2, 'title': 'Book Two'}
    ]
    # Configure the mock collection's find() method to return our fake data
    #    (A list is a valid iterable, so it works as a fake cursor for the test)
    mock_books_collection.find.return_value = mock_db_data

    # Act
    books_list_result, total_count_result = find_all_books(mock_books_collection)

    # Assert
    # Find called correctly?
    mock_books_collection.find.assert_called_once_with({})

    # Did the function return a list of the correct length and are the test books present?
    assert isinstance(books_list_result, list)
    assert len(books_list_result) == 2
    assert books_list_result[0]['_id'] == str(fake_book_id_1)
    assert books_list_result[1]['title'] == 'Book Two'

    # Is the total_count present and correct?
    assert isinstance(total_count_result, int)
    assert total_count_result == 2

def test_find_one_book():
    """
    GIVEN a mocked find_one that behaves conditionally
    WHEN find_book_by_id is called with a matching ID, it should return the document.
    WHEN called with a non-matching ID, it should return None.
    """
    # Arrange
    # Mock the books collection
    mock_books_collection = MagicMock()

    # Define our "fake database" state and the specific IDs we will test

    correct_id = str(uuid.uuid4())
    wrong_id = str(uuid.uuid4())
    fake_book_in_db = {
        'id': correct_id,
        'title': 'The Correct Book',
        'author': 'Jane Doe'
    }

    def find_one_side_effect(query):

        # Check if the query matches what we expect for the correct book
        if query == {'id': correct_id, 'state': {'$ne': 'deleted'}}:
            # If the query is correct, return the document
            return fake_book_in_db
        return None

    # Assign the custom function to the mock's side effect attribute
    mock_books_collection.find_one.side_effect = find_one_side_effect

    # Act and assert for the correct_id
    result_success = find_one_book(correct_id, mock_books_collection)

    # Assert that it returned the full document, with the ID correctly stringified
    assert result_success is not None
    assert result_success['title'] == 'The Correct Book'
    assert result_success['id'] == correct_id

    # Act and assert for the wrong_id
    result_failure = find_one_book(wrong_id, mock_books_collection)

    # Assert that it correctly returned None
    assert result_failure is None

    # We can also check the total calls to our mock
    assert mock_books_collection.find_one.call_count == 2

def test_delete_book_by_id_soft_deletes_book():
    """
    GIVEN a MongoDB ObjectId that should be deleted
    WHEN delete_book_by_id is called with it
    THEN it should update the book's state field to 'deleted'
    and return the updated book document.
    """
    # Arrange
    # Mock the books collection
    mock_books_collection = MagicMock()

    # Set up sample _id's for testing
    correct_id = str(uuid.uuid4())
    wrong_id = str(uuid.uuid4())

    # And set up a fake book document to be returned
    fake_book_in_db = {
        '_id': ObjectId(),
        'id': correct_id,
        'title': 'The Correct Book',
        'author': 'Jane Doe',
        'state': 'active'
    }

    # Define the "side effect" function for find_one_and_update
    def find_one_and_update_side_effect(filter_query, update_doc, return_document):
        # Check if the ID in the filter matches the one we expect to find.
        if filter_query == {'id': correct_id}:
            # Simulate the update operation
            changes = update_doc.get('$set', {})

            # Create a copy of the original document to modify
            updated_doc = deepcopy(fake_book_in_db)

            # Apply the changes from the update document
            updated_doc.update(changes)

            # Respect the return_document option, just like the real DB
            if return_document == ReturnDocument.AFTER:
                return updated_doc
            # If return_document is not specified correctly, return the unmodified document
            return fake_book_in_db
        # If a wrong or invalid ID is sent, return None
        return None

    # Assign the side_effect to the mock
    mock_books_collection.find_one_and_update.side_effect = find_one_and_update_side_effect

    # Act and assert for the correct_id and update_doc
    result_success = delete_book_by_id(correct_id, mock_books_collection)

    # Assert that update_one was called with the correct filter and update document.
    mock_books_collection.find_one_and_update.assert_called_with(
        {'id': correct_id},
        {'$set': {'state': 'deleted'}},
        return_document=ReturnDocument.AFTER
    )
    assert result_success is not None
    assert result_success['state'] == 'deleted'
    assert result_success['id'] == correct_id # Also check the ID was stringified
    assert result_success['title'] == 'The Correct Book'

    # Act and assert for the wrong_id
    result_not_found = delete_book_by_id(wrong_id, mock_books_collection)
    assert result_not_found is None

def test_update_book_by_id_updates_db_and_returns_updated_book():
    """
    WHEN update_book_by_id is called with the correct _id and formatted JSON
    THEN it should set the book's fields to their new values
    and return the updated book document.
    """
    # Arrange
    # Mock the books collection
    mock_books_collection = MagicMock()

    # Set up sample _id's for testing
    correct_id = ObjectId()
    wrong_id = ObjectId()
    invalid_id = "not-a-valid-mongo-id"

    # And set up a fake book document to be updated
    fake_book_in_db = {
        '_id': correct_id,
        'title': 'The Old Book',
        'author': 'Old Author',
        'synopsis': 'An old synopsis of an old book',
    }
    # And the fake new data to update it with
    fake_new_book_data = {
        'title': 'The New Book',
        'author': 'New Author',
        'synopsis': 'A new synopsis of an new book',
    }

    # Define the "side effect" function for find_one_and_update
    def find_one_and_update_side_effect(filter_query, update_doc, return_document):
        # Check if the ID in the filter matches the one we expect to find.
        if filter_query == {'_id': correct_id, 'state': {'$ne': 'deleted'}}:
            # Simulate the update operation
            changes = update_doc.get('$set', {})

            # Create a copy of the original document to modify
            updated_doc = deepcopy(fake_book_in_db)

            # Apply the changes from the update document
            updated_doc.update(changes)

            # Respect the return_document option, just like the real DB
            if return_document == ReturnDocument.AFTER:
                return updated_doc
            # If return_document is not specified correctly, return the unmodified document
            return fake_book_in_db
        # If a wrong or invalid ID is sent, return None
        return None

    # Assign the side_effect to the mock
    mock_books_collection.find_one_and_update.side_effect = find_one_and_update_side_effect

    # Act and assert for the correct_id and update_doc
    result_success = update_book_by_id(str(correct_id), fake_new_book_data, mock_books_collection)

    # Assert that update_one was called with the correct filter and update document.
    mock_books_collection.find_one_and_update.assert_called_with(
        {'_id': correct_id, 'state': {'$ne': 'deleted'}},
        {'$set': fake_new_book_data},
        return_document=ReturnDocument.AFTER
    )
    assert result_success is not None
    assert result_success['_id'] == str(correct_id) # Also check the ID was stringified
    assert result_success['title'] == 'The New Book'

    # Act and assert for a 'wrong' (but valid) ID
    result_wrong_id = update_book_by_id(str(wrong_id), fake_new_book_data, mock_books_collection)
    assert result_wrong_id is None

    # Act and assert for a malformed ID string
    result_invalid_id = update_book_by_id(
        str(invalid_id),
        fake_new_book_data,
        mock_books_collection
    )
    assert result_invalid_id is None

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
