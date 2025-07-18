"""Module containing pymongo helper functions."""

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
    pass
