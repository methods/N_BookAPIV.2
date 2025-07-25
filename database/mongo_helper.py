"""Module containing pymongo helper functions."""
from bson.objectid import ObjectId, InvalidId
from pymongo import ReturnDocument

def insert_book_to_mongo(new_book, books_collection):
    """Add a new book to the MongoDB collection."""
    result = books_collection.insert_one(new_book)
    if result.acknowledged:
        print("New book was successfully inserted.")
    return str(result.inserted_id)

def find_all_books(books_collection):
    """
    Returns a list of all books in the collection.
    """
    # Use find({}) to get a mongoDB Cursor object for all books
    books_cursor = books_collection.find({})

    # Use list() to iterate through the collection using the Cursor
    books_list = list(books_cursor)

    # Count the items in the list
    total_count = len(books_list)

    # Convert all the BSON _id to strings so the list can be JSON serialized
    for book in books_list:
        book['_id'] = str(book['_id'])

    # Return the list and the count
    return books_list, total_count

def find_one_book(book_id: str, books_collection):
    """
    Returns a book specified by _id from the MongoDB collection.
    """
    try:
        # Convert the string ID to a BSON ObjectId
        obj_id = ObjectId(book_id)

        # Use mongoDB built in find_one method
        book = books_collection.find_one({'_id': obj_id})

        if book:
            # Process the document appropriately
            book['_id'] = str(book['_id'])

        return book
    except InvalidId:
        return None

def delete_book_by_id(book_id: str, books_collection):
    """
    Soft deletes a book specified by _id from the MongoDB collection
    and returns the updated document if it exists or None otherwise.
    """
    try:
        obj_id = ObjectId(book_id)
        # Use find_one_and_update to perform the soft delete
        updated_book = books_collection.find_one_and_update(
            {'_id': obj_id},
            {'$set': {'state': 'deleted'}},
            # This option tells MongoDB to return the document AFTER the update
            return_document=ReturnDocument.AFTER
        )

        # Process the _id for JSON serialization before returning
        if updated_book:
            updated_book['_id'] = str(updated_book['_id'])

        return updated_book
    except InvalidId:
        return None

def update_book_by_id(book_id: str, new_book_data: dict, books_collection):
    """
    Updates a book specified by _id from the MongoDB collection
    and returns the updated document if it exists or None otherwise.
    """
    try:
        obj_id = ObjectId(book_id)
        # Use find_one_and_update to perform the update
        updated_book = books_collection.find_one_and_update(
            {'_id': obj_id},
            {'$set': new_book_data},
            # This option tells MongoDB to return the document AFTER the update
            return_document=ReturnDocument.AFTER
        )

        # Process the _id for JSON serialization before returning
        if updated_book:
            updated_book['_id'] = str(updated_book['_id'])

        return updated_book
    except InvalidId:
        return None
