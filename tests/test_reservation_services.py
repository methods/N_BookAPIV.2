""" Unit tests for reservation services """
import uuid
import copy
from datetime import datetime, timezone
from unittest.mock import MagicMock
from bson.objectid import ObjectId
import pytest
from pymongo.errors import ConnectionFailure
from database import reservation_services
from database.reservation_services import BookNotAvailableForReservationError, ReservationNotFoundError
from app import app

def test_create_reservation_for_book(mocker):
    """
    GIVEN a valid book_id and reservation data
    WHEN create_reservation_for_book is called
    AND the parent book is found in the database (mocked)
    THEN it should call insert_one on the reservations collection with a correctly
    structured document and return the processed document.
    """
    # Arrange
    # Mock external dependencies
    mock_find_book = mocker.patch('database.reservation_services.mongo_helper.find_one_book')
    mock_books_collection = MagicMock()
    mock_reservations_collection = MagicMock()
    mocker.patch(
        'database.reservation_services.get_reservations_collection',
        return_value=mock_reservations_collection
    )

    # Mock uuid.uuid4() in the reservation function
    fake_reservation_uuid = "a1b2c3d4-e5f6-7890-1234-567890abcdef"
    mocker.patch('database.reservation_services.uuid.uuid4', return_value=fake_reservation_uuid)

    # Fake the book_id and reservation data
    fake_book_id = uuid.uuid4()
    fake_user_doc = {
        '_id': ObjectId(),
        'email': 'john.doe@example.com',
        'given_name': 'John',
        'family_name': 'Doe',
        'roles': ['viewer']
    }

    # Mock the fake find_book result
    mock_find_book.return_value = {'id': fake_book_id, 'title': 'A Valid Book'}

    # Mock the return value from the fake reservations collection
    fake_new_reservation_id = uuid.uuid4()
    mock_reservations_collection.insert_one.return_value = MagicMock(
        inserted_id=fake_new_reservation_id
    )

    # Act
    # Call the create_reservation helper function
    new_reservation = reservation_services.create_reservation_for_book(
        fake_book_id,
        fake_user_doc,
        mock_books_collection
    )

    # Assert
    # Was the find_book function called to validate the book_id
    mock_find_book.assert_called_once_with(fake_book_id, mock_books_collection)

    # Was the reservations collection's insert_one method called?
    mock_reservations_collection.insert_one.assert_called_once()

    # Check the inserted document
    inserted_doc = mock_reservations_collection.insert_one.call_args[0][0]
    assert inserted_doc['book_id'] == fake_book_id
    assert inserted_doc['user_id'] == fake_user_doc['_id']
    assert inserted_doc['forenames'] == 'John'
    assert inserted_doc['surname'] == 'Doe'
    assert inserted_doc['state'] == 'reserved'
    assert inserted_doc['id'] == fake_reservation_uuid
    assert 'reservedAt' in inserted_doc

    # Check the returned object was correctly processed
    assert new_reservation['id'] == fake_reservation_uuid
    assert new_reservation['book_id'] == fake_book_id
    assert 'user_id' not in new_reservation
    assert 'reservedAt' in new_reservation

def test_create_reservation_for_non_existent_book_raises_error(mocker):
    """
    GIVEN an invalid book_id
    WHEN create_reservation_for_book is called
    AND the book service returns None
    THEN it should raise a BookNotAvailableForReservationError
    AND it should NOT attempt to create a reservation.
    """

    # ARRANGE
    # 1. Mock all external dependencies
    mock_find_book = mocker.patch('database.reservation_services.mongo_helper.find_one_book')
    mock_reservations_collection = MagicMock()
    mock_books_collection = MagicMock()
    mocker.patch(
        'database.reservation_services.get_reservations_collection',
        return_value=mock_reservations_collection
    )

    # 2. Configure the book service to simulate failure
    mock_find_book.return_value = None

    # 3. Set up input data
    non_existent_book_uuid = str(uuid.uuid4())
    fake_user_doc = {
        '_id': ObjectId(),
        'email': 'john.doe@example.com',
        'given_name': 'John',
        'family_name': 'Doe',
        'roles': ['viewer']
    }

    # ACT & ASSERT
    # Use pytest.raises to assert that our specific exception is thrown.
    with pytest.raises(BookNotAvailableForReservationError) as exc_info:
        reservation_services.create_reservation_for_book(
            non_existent_book_uuid,
            fake_user_doc,
            mock_books_collection
        )

    # Assert the exception message is helpful
    assert non_existent_book_uuid in str(exc_info.value)

    # Assert that no reservation was created in the failure case.
    mock_reservations_collection.insert_one.assert_not_called()

def test_get_reservations_collection_on_success(mocker, monkeypatch):
    """
    UNIT TEST:
    GIVEN a successful connection to MongoDB
    WHEN get_reservations_collection is called
    THEN it should use the app config to return the correct collection object.
    """
    # ARRANGE
    # 1. Use monkeypatch to temporarily set the config values on the REAL app object.
    monkeypatch.setitem(app.config, 'MONGO_URI', 'mongodb://fake-host:27017/')
    monkeypatch.setitem(app.config, 'DB_NAME', 'fake_db_name')

    # 2. Mock the entire MongoClient class.
    mock_client_instance = MagicMock()
    mock_mongo_client_class = mocker.patch('database.reservation_services.MongoClient')
    mock_mongo_client_class.return_value = mock_client_instance

    # 3. Create a fake database object and a fake collection object.
    mock_db_object = MagicMock()
    expected_collection_object = MagicMock()

    # 4. Configure the mock client to return the fake DB when accessed by key.
    mock_client_instance.__getitem__.return_value = mock_db_object
    # 5. Configure the fake DB to return the fake collection when 'reservations' is accessed.
    mock_db_object.reservations = expected_collection_object

    # ACT
    actual_collection = reservation_services.get_reservations_collection()

    # ASSERT
    # 1. Was MongoClient called with the correct URI from our fake app config?
    mock_mongo_client_class.assert_called_once_with(
        'mongodb://fake-host:27017/',
        serverSelectionTimeoutMS=5000
    )

    # 2. Was the database selected using the correct name from our fake app config?
    mock_client_instance.__getitem__.assert_called_once_with('fake_db_name')

    # 3. Did the function return the specific collection object we expected?
    assert actual_collection == expected_collection_object


def test_get_reservations_collection_on_failure(mocker, monkeypatch):
    """
    UNIT TEST:
    GIVEN the MongoDB connection fails
    WHEN get_reservations_collection is called
    THEN it should raise a ConnectionFailure exception.
    """
    # ARRANGE
    # 1. Use monkeypatch to temporarily set the config values on the REAL app object.
    monkeypatch.setitem(app.config, 'MONGO_URI', 'mongodb://fake-host:27017/')
    monkeypatch.setitem(app.config, 'DB_NAME', 'fake_db_name')

    # 2. Mock the MongoClient class to *raise an exception* when it's initialized.
    #    We use 'side_effect' for this.
    mock_mongo_client_class = mocker.patch('database.reservation_services.MongoClient')
    mock_mongo_client_class.side_effect = ConnectionFailure("Could not connect to server.")

    # ACT & ASSERT
    # Use pytest.raises to assert that the expected exception was thrown.
    with pytest.raises(ConnectionFailure) as exc_info:
        reservation_services.get_reservations_collection()

    # (Optional but good) Check that your custom error message is in the exception.
    assert "Could not connect to MongoDB" in str(exc_info.value)

    # We can also assert that an attempt was made to connect.
    mock_mongo_client_class.assert_called_once()

# NOTE - fully AI generated test
@pytest.mark.parametrize("user_doc_input, expected_forename, expected_surname", [
    # Test Case 1: The ideal user with given_name and family_name
    (
            {
                '_id': ObjectId(),
                'email': 'test1@test.com',
                'given_name': 'John',
                'family_name': 'Doe'
            },
            "John",
            "Doe"
    ),
    # Test Case 2: User with only a 'name' field
    (
            {'_id': ObjectId(), 'email': 'test2@test.com', 'name': 'Jane Smith'},
            "Jane",
            "Smith"
    ),
    # Test Case 3: User with only an 'email' field
    (
            {'_id': ObjectId(), 'email': 'test3@test.com'},
            "test3@test.com",
            "(No name provided)"
    ),
    # Test Case 4: Edge case of a single 'name'
    (
            {'_id': ObjectId(), 'email': 'test4@test.com', 'name': 'Cher'},
            "Cher",
            ""
    ),
    # Test Case 5: A completely empty user object (ultimate fallback)
    (
            {'_id': ObjectId()},
            "Unknown User",
            "(No name provided)"
    )
])
def test_create_reservation_parses_various_user_name_formats(
        mocker, user_doc_input, expected_forename, expected_surname
):
    """
    UNIT TEST:
    Verifies that the reservation creation logic correctly parses the user's name
    from various possible formats in the user document.
    """
    # ARRANGE
    # Mock all dependencies to isolate the name-parsing logic
    mocker.patch(
        'database.reservation_services.mongo_helper.find_one_book',
        return_value={'id': 'some-book-id'}
    )
    mock_reservations_collection = MagicMock()
    mocker.patch(
        'database.reservation_services.get_reservations_collection',
        return_value=mock_reservations_collection
    )
    mocker.patch('database.reservation_services.uuid.uuid4')
    mocker.patch('database.reservation_services.datetime')
    mock_reservations_collection.insert_one.return_value = MagicMock(inserted_id=ObjectId())

    # ACT
    # Call the function with the parameterized user document
    reservation_services.create_reservation_for_book(
        "some-book-id",
        user_doc_input,
        MagicMock()  # mock books_collection
    )

    # ASSERT
    # Check that insert_one was called.
    mock_reservations_collection.insert_one.assert_called_once()

    # Capture the document that was passed to insert_one.
    inserted_doc = mock_reservations_collection.insert_one.call_args[0][0]

    # Assert that the name was parsed correctly for this test case.
    assert inserted_doc['forenames'] == expected_forename
    assert inserted_doc['surname'] == expected_surname


def test_find_reservation_by_id_success_unit(mocker):
    """
    UNIT TEST for find_reservation_by_id happy path.

    GIVEN a valid reservation ID (string UUID)
    WHEN the find_reservation_by_id service is called
    AND a matching document is found in the (mocked) database
    THEN it should call find_one with the correct query
    AND return a processed dictionary of the reservation.
    """
    # NOTE - This test generated by AI from docstring prompt
    # ARRANGE
    # 1. Mock the dependencies.
    mock_reservations_collection = MagicMock()
    mocker.patch(
        'database.reservation_services.get_reservations_collection',
        return_value=mock_reservations_collection
    )

    # 2. Define the test data.
    reservation_uuid_str = str(uuid.uuid4())
    fake_db_document = {
        '_id': ObjectId(),
        'id': reservation_uuid_str,
        'book_id': str(uuid.uuid4()),
        'user_id': str(ObjectId()),
        'state': 'reserved',
        'reservedAt': datetime.now(timezone.utc)
    }

    # 3. Configure the mock. Use deepcopy to ensure the test works with
    #    a copy of the data, just like the real function would.
    mock_reservations_collection.find_one.return_value = copy.deepcopy(fake_db_document)

    # ACT
    # Call the actual service function we are testing.
    result = reservation_services.find_reservation_by_id(reservation_uuid_str)

    # ASSERT
    # 1. Was the database queried correctly?
    mock_reservations_collection.find_one.assert_called_once_with(
        {'id': reservation_uuid_str}
    )

    # 2. Did the function return the correct, processed data?
    assert result is not None
    assert result['id'] == reservation_uuid_str
    assert result['book_id'] == fake_db_document['book_id']

    # Check that the internal _id was removed.
    assert '_id' not in result

    # Check that the datetime object was converted to an ISO string.
    assert isinstance(result['reservedAt'], str)
    assert result['reservedAt'] == fake_db_document['reservedAt'].isoformat()


def test_find_reservation_by_id_raises_error_when_not_found(mocker):
    """
    UNIT TEST for find_reservation_by_id failure path.

    GIVEN a reservation ID that does not exist in the database
    WHEN find_reservation_by_id is called
    THEN it should raise a ReservationNotFoundError.
    """
    # ARRANGE
    # 1. Mock the collection getter and the collection object.
    mock_get_collection = mocker.patch(
        'database.reservation_services.get_reservations_collection'
    )
    mock_reservations_collection = MagicMock()
    mock_get_collection.return_value = mock_reservations_collection

    # 2. This is the key step: Configure find_one to return None,
    #    simulating a document that is not found.
    mock_reservations_collection.find_one.return_value = None

    # 3. An ID to search for. The actual value doesn't matter since the mock will always return None.
    non_existent_uuid = str(uuid.uuid4())

    # ACT & ASSERT
    # Use pytest.raises as a context manager to assert that our
    # specific exception was raised during the function call.
    with pytest.raises(ReservationNotFoundError) as exc_info:
        reservation_services.find_reservation_by_id(non_existent_uuid)

    # (Optional but recommended) Assert that the exception message is helpful and contains the ID.
    assert non_existent_uuid in str(exc_info.value)
    assert "cannot be found" in str(exc_info.value)

    # We can also verify that the database was queried correctly before the exception was raised.
    mock_reservations_collection.find_one.assert_called_once_with({'id': non_existent_uuid})
