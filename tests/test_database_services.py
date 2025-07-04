# pylint: disable=missing-docstring
from unittest.mock import MagicMock
from database.mongo_helper import insert_book_to_mongo
from database import user_services

# @patch('mongo_helper.books_collection')
def test_insert_book_to_mongo():
    #Setup the mock
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
    mock_collection_object = MagicMock()
    mock_get_collection.return_value = mock_collection_object

    # Setup mock data
    fake_profile = {"sub": "google-id-123"}
    existing_user_doc = {"email": "editor.user@example.com", "google_id": "google-id-123"}

    # Configure the fake collection object's methods
    mock_collection_object.find_one.return_value = existing_user_doc

    # Act
    result = user_services.get_or_create_user_from_oidc(fake_profile)

    # Assert
    mock_get_collection.assert_called_once_with()
    mock_collection_object.find_one.assert_called_once_with({'google_id': 'google-id-123'})
    assert result == existing_user_doc
