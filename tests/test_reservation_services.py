""" Unit tests for reservation services """
import uuid
from unittest.mock import MagicMock
import pytest
from database import reservation_services
from database.reservation_services import BookNotAvailableForReservationError

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
    reservation_payload = {'forenames': 'John', 'surname': 'Doe'}

    # Mock the fake find_book result
    mock_find_book.return_value = {'id': fake_book_id, 'title': 'A Valid Book'}

    # Mock the return value from the fake reservations collection
    fake_new_reservation_id = uuid.uuid4()
    mock_reservations_collection.insert_one.return_value = MagicMock(inserted_id=fake_new_reservation_id)

    # Act
    # Call the create_reservation helper function
    new_reservation = reservation_services.create_reservation_for_book(
        str(fake_book_id),
        reservation_payload,
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
    assert inserted_doc['forenames'] == 'John'
    assert inserted_doc['state'] == 'reserved'
    assert inserted_doc['id'] == fake_reservation_uuid
    assert 'reservedAt' in inserted_doc

    # Check the returned object was correctly processed
    assert new_reservation['id'] == fake_reservation_uuid
    assert new_reservation['book_id'] == fake_book_id
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
    reservation_payload = {'forenames': 'John', 'surname': 'Doe'}

    # ACT & ASSERT
    # Use pytest.raises to assert that our specific exception is thrown.
    with pytest.raises(BookNotAvailableForReservationError) as exc_info:
        reservation_services.create_reservation_for_book(
            non_existent_book_uuid,
            reservation_payload,
            mock_books_collection
        )

    # Assert the exception message is helpful
    assert non_existent_book_uuid in str(exc_info.value)

    # Assert that no reservation was created in the failure case.
    mock_reservations_collection.insert_one.assert_not_called()
