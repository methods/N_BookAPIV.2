""" Contains all helper functions for the reservations collection"""
from datetime import datetime, timezone
import uuid
import copy
from ssl import create_default_context

from bson.objectid import ObjectId
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from . import mongo_helper

class BookNotAvailableForReservationError(Exception):
    pass

def get_reservations_collection():
    """Connect to the database and return the reservations collection"""
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
    print(created_reservation)

    return created_reservation
