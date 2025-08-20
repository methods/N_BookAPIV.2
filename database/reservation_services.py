""" Contains all helper functions for the reservations collection"""
from datetime import datetime, timezone
import uuid
import copy
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import ConnectionFailure
from . import mongo_helper

class BookNotAvailableForReservationError(Exception):
    """
    Exception raised when a reservation has not been available for book
    """

class ReservationNotFoundError(Exception):
    """
    Exception raised when a reservation cannot be found in the database
    """

def _process_reservation_for_api(reservation_doc):
    """
    A private helper to consistently format a reservation document for API output.
    Converts ObjectIds and datetimes to strings and removes internal fields.
    """
    if not reservation_doc:
        return None

    doc_copy = reservation_doc.copy()

    doc_copy.pop('_id', None)
    doc_copy['user_id'] = str(doc_copy['user_id'])

    if 'reservedAt' in doc_copy and hasattr(doc_copy['reservedAt'], 'isoformat'):
        doc_copy['reservedAt'] = doc_copy['reservedAt'].isoformat()
    if 'cancelledAt' in doc_copy and hasattr(doc_copy['cancelledAt'], 'isoformat'):
        doc_copy['cancelledAt'] = doc_copy['cancelledAt'].isoformat()

    return doc_copy

def get_reservations_collection():
    """
    Connect to the database and return the reservations collection
    """
    from app import app # pylint: disable=import-outside-toplevel
    try:
        client = MongoClient(app.config['MONGO_URI'], serverSelectionTimeoutMS=5000)
        db = client[app.config['DB_NAME']]
        reservations_collection = db.reservations
        return reservations_collection
    except ConnectionFailure as e:
        # Handle the connection error and return error information
        raise ConnectionFailure(f'Could not connect to MongoDB: {str(e)}') from e

def create_reservation_for_book(book_id, user: dict, books_collection):
    """
    Creates a reservation record for a book
    """
    # Check that the book to be reserved is in the collection and not deleted
    book_to_reserve = mongo_helper.find_one_book(book_id, books_collection)
    if book_to_reserve is None:
        raise BookNotAvailableForReservationError(
            f"Book with ID {book_id} is not available for reservation."
        )

    # Parse user data for the new reservation
    forename = user.get('given_name')
    surname = user.get('family_name')
    # Some users may have only a 'name' field
    if not forename and user.get('name'):
        name_parts = user['name'].split(' ', 1)
        forename = name_parts[0]
        surname = name_parts[1] if len(name_parts) > 1 else ''
    # Some users may only have an email
    if not forename and not surname:
        forename = user.get('email', 'Unknown User') # Fallback if even email is missing
        surname = '(No name provided)'

    # Prepare the collection to be modified
    reservations_collection = get_reservations_collection()
    new_reservation_doc = {
        'id': str(uuid.uuid4()),
        'book_id': book_id, # Store the ObjectId to link to the book
        'user_id': user['_id'],
        'forenames': forename,
        'surname': surname,
        'state': 'reserved', # Correctly set the default state
        'reservedAt': datetime.now(timezone.utc)
    }

    # Add the new reservation to the collection
    result = reservations_collection.insert_one(new_reservation_doc)
    created_reservation = copy.deepcopy(new_reservation_doc)
    created_reservation['_id'] = result.inserted_id
    created_reservation.pop('_id', None)
    created_reservation.pop('user_id', None)
    created_reservation['reservedAt'] = created_reservation['reservedAt'].isoformat()
    return created_reservation

def find_reservation_by_id(reservation_id):
    """
    Find a reservation record by its 'id' field which is uuid.
    """
    # Prepare the collection to be searched
    reservations_collection = get_reservations_collection()

    # Search the collection using the given reservation_id
    result = reservations_collection.find_one({'id': reservation_id})
    if result is None:
        raise ReservationNotFoundError(
            f"Reservation with ID {reservation_id} cannot be found in the database."
        )
    # Prepare the returned reservation document for output and return it
    return _process_reservation_for_api(result)

def cancel_reservation_by_id(reservation_id):
    """
    Find a reservation record by its 'id' field and update it as 'cancelled'.
    """
    # Prepare the collection for the operation
    reservations_collection = get_reservations_collection()
    # Check the reservation is active
    query_filter = {
        'id': reservation_id,
        'state': 'reserved'
    }
    # Prepare the changes to the document
    update_doc = {
        '$set': {
            'state': 'cancelled',
            'cancelledAt': datetime.now(timezone.utc)
        }
    }
    # Find and update the document
    # Use find_one_and_update to get the updated document back in one go
    updated_doc = reservations_collection.find_one_and_update(
        query_filter,
        update_doc,
        return_document=ReturnDocument.AFTER
    )
    # Process and return the updated_doc or raise an error if it's None
    if not updated_doc:
        raise ReservationNotFoundError(
            f"Reservation with ID {reservation_id} cannot be found in the database."
        )
    return _process_reservation_for_api(updated_doc)

def find_all_reservations(current_user: dict, filters: dict = None):
    """
    Finds a list of reservations based on the user's role and provided filters.
    - Regular users can only see their own reservations.
    - Admins can see all reservations and can filter by user_id.
    """
    # Prepare the collection for the operation
    reservations_collection = get_reservations_collection()

    # Build the query for the collection
    query = {}

    # Check if the user is an admin
    is_admin = 'admin' in current_user.get('roles', [])

    # If the user is an admin, import any user_id filters they've asked for
    if is_admin:
        if filters and 'user_id' in filters:
            query['user_id'] = filters['user_id']
    else:
        # If the user is not an admin, use their user_id to filter
        query['user_id'] = current_user['_id']

    # Execute the query
    cursor = reservations_collection.find(query)

    # Convert the cursor to a list of raw documents.
    raw_reservations = list(cursor)

    # Process the raw documents in the list
    processed_reservations = [
        _process_reservation_for_api(doc) for doc in raw_reservations
    ]

    # Return the final, clean list.
    return processed_reservations
