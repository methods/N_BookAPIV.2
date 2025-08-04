""" Contains all helper functions for the reservations collection"""
from datetime import datetime, timezone
import uuid
from bson.objectid import ObjectId
from . import mongo_helper

class BookNotAvailableForReservationError(Exception):
    pass

def get_reservations_collection():
    pass

def create_reservation_for_book(book_id, reservation_data, books_collection):
    """
    Creates a reservation record for a book
    """
    book_to_reserve = mongo_helper.find_one_book(book_id, books_collection)
    print(book_to_reserve)
    return
