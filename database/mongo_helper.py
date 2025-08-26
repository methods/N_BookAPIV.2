"""Module containing pymongo helper functions."""
from pymongo import ReturnDocument

def insert_book_to_mongo(new_book, books_collection):
    """Add a new book to the MongoDB collection."""
    result = books_collection.insert_one(new_book)
    if result.acknowledged:
        print("New book was successfully inserted.")
    return str(result.inserted_id)

def find_all_books(books_collection, offset: int, limit: int):
    """
    Returns a list of all books in the collection.
    """
    # Set the query filter to filter out deleted books
    query_filter = {'state': {'$ne': 'deleted'}}

    # Get the total count of documents for pagination metadata
    total_count = books_collection.count_documents(query_filter)

    # Use find({}) to get a mongoDB Cursor object for all books
    #   AND apply offset() and limit() sequentially
    books_cursor = books_collection.find(query_filter).skip(offset).limit(limit)

    # Use list() to iterate through the collection using the Cursor
    books_list = list(books_cursor)

    # Convert all the BSON _id to strings so the list can be JSON serialized
    for book in books_list:
        book.pop('_id', None)

    # Return the list and the count
    return books_list, total_count

def find_one_book(book_id: str, books_collection):
    """
    Returns a book specified by _id from the MongoDB collection.
    """

    # Convert the string ID to a BSON ObjectId

    # Use mongoDB built in find_one method

    query_filter = {
        'id': book_id,
        'state': {'$ne': 'deleted'}
    }

    book = books_collection.find_one(query_filter)

    if book:
        # Process the document appropriately
        book.pop('_id', None)
        return book
    return None

def delete_book_by_id(book_id: str, books_collection):
    """
    Soft deletes a book specified by _id from the MongoDB collection
    and returns the updated document if it exists or None otherwise.
    """

    # Use find_one_and_update to perform the soft delete
    updated_book = books_collection.find_one_and_update(
        {'id': book_id},
        {'$set': {'state': 'deleted'}},
        # This option tells MongoDB to return the document AFTER the update
        return_document=ReturnDocument.AFTER
    )

    # Process the _id for JSON serialization before returning
    if updated_book:
        updated_book.pop('_id', None)
        return updated_book
    return None

def update_book_by_id(book_id: str, new_book_data: dict, books_collection):
    """
    Updates a book specified by _id from the MongoDB collection
    and returns the updated document if it exists or None otherwise.
    """

    # obj_id = ObjectId(book_id)

    # Filter for deleted books
    query_filter = {
        'id': book_id,
        'state': {'$ne': 'deleted'}
    }

    # Use find_one_and_update to perform the update
    updated_book = books_collection.find_one_and_update(
        query_filter,
        {'$set': new_book_data},
        # This option tells MongoDB to return the document AFTER the update
        return_document=ReturnDocument.AFTER
    )

    # Remove the mongoDB _id field
    if updated_book:
        updated_book.pop('_id', None)
        return updated_book
    return None
