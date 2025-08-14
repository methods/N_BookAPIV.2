"""Flask application module for managing a collection of books."""
# pylint: disable=cyclic-import
import uuid
import copy
import os
from urllib.parse import urljoin
from dotenv import load_dotenv
from flask import Flask, request, jsonify, g
from werkzeug.exceptions import NotFound
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from database.mongo_helper import (
    insert_book_to_mongo,
    find_all_books,
    find_one_book,
    delete_book_by_id,
    update_book_by_id
)
from database import reservation_services
from auth.services import init_oauth
from auth.views import auth_bp # Imports the blueprint object from the auth module
from auth.decorators import login_required, roles_required, reservation_owner_or_admin_required

app = Flask(__name__)

# Use app.config to set config connection details
load_dotenv()
app.config['MONGO_URI'] = os.getenv('MONGO_CONNECTION')
app.config['DB_NAME'] = os.getenv('PROJECT_DATABASE')
app.config['COLLECTION_NAME'] = os.getenv('PROJECT_COLLECTION')
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')

# Call the function to initialise the OAuth Client
init_oauth(app)
# Register the auth blueprint with the main app, applying a URL prefix
app.register_blueprint(auth_bp, url_prefix='/auth')

def get_book_collection():
    """Initialize the mongoDB connection"""
    try:
        client = MongoClient(app.config['MONGO_URI'], serverSelectionTimeoutMS=5000)
        # Check the status of the server, will fail if server is down
        # client.admin.command('ismaster')
        db = client[app.config['DB_NAME']]
        books_collection = db[app.config['COLLECTION_NAME']]
        return books_collection
    except ConnectionFailure as e:
        # Handle the connection error and return error information
        raise ConnectionFailure(f'Could not connect to MongoDB: {str(e)}') from e

def append_hostname(book, host):
    """Helper function to append the hostname to the links in a book object."""
    if "links" in book:
        book["links"] = {
            key: urljoin(host, path)
            for key, path in book["links"].items()
        }
    return book


# ----------- POST section ------------------
@app.route("/books", methods=["POST"])
@login_required
@roles_required('admin', 'editor')
def add_book():
    """Function to add a new book to the collection."""
    # check if request is json
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415

    new_book = request.json
    if not isinstance(new_book, dict):
        return jsonify({"error": "JSON payload must be a dictionary"}), 400

    # create UUID and add it to the new_book object
    new_book_id = str(uuid.uuid4())
    new_book["id"] = new_book_id

    # validation
    required_fields = ["title", "synopsis", "author"]
    missing_fields = [field for field in required_fields if field not in new_book]
    if missing_fields:
        return {"error": f"Missing required fields: {', '.join(missing_fields)}"}, 400

    new_book['links'] = {
        "self": f"/books/{new_book_id}",
        "reservations": f"/books/{new_book_id}/reservations",
        "reviews": f"/books/{new_book_id}/reviews"
    }

    # Map field names to their expected types
    field_types = {
        "id": str,
        "title": str,
        "synopsis": str,
        "author": str,
        "links": dict
    }

    for field, expected_type in field_types.items():
        if not isinstance(new_book[field], expected_type):
            return {"error": f"Field {field} is not of type {expected_type}"}, 400

    # use helper function
    books_collection = get_book_collection()
    # check if mongoDB connected??
    insert_book_to_mongo(new_book, books_collection)

    # Get the host from the request headers
    host = request.host_url
    # Send the host and new book_id to the helper function to generate links
    book_for_response = append_hostname(new_book, host)
    # Remove MOngoDB's ObjectID value
    book_for_response.pop('_id', None)

    return jsonify(book_for_response), 201

@app.route('/books/<book_id>/reservations', methods=['POST'])
@login_required
def add_reservation(book_id):
    """ Function to add a new reservation to the reservations collection. """
    # Get the user data from Flask.g object
    current_user = g.user
    books_collection = get_book_collection()
    # Call the reservation service
    try:
        new_reservation = reservation_services.create_reservation_for_book(
            book_id,
            current_user,
            books_collection
        )

        return jsonify(new_reservation), 201

    except reservation_services.BookNotAvailableForReservationError as e:
        return jsonify({"error": str(e)}), 404

# ----------- GET section ------------------
@app.route("/books", methods=["GET"])
def get_all_books():
    """
    Retrieve all books from the database and
    return them in a JSON response
    including the total count.
    """
    # if not books:
    #     return jsonify({"error": "No books found"}), 404

    books_collection = get_book_collection()
    books_list_result, _total_count_result = find_all_books(books_collection)

    all_books = []
    # extract host from the request
    host = request.host_url

    for book in books_list_result:
        # check if the book has the "deleted" state
        if book.get("state")!="deleted":
            # if the book has a state other than "deleted" remove the state field before appending
            book_copy = copy.deepcopy(book)
            book_copy.pop("state", None)
            book_with_hostname = append_hostname(book_copy, host)
            all_books.append(book_with_hostname)

    # validation
    required_fields = ["id", "title", "synopsis", "author", "links"]
    missing_fields_info = []

    for book in all_books:
        missing_fields = [field for field in required_fields if field not in book]
        if missing_fields:
            missing_fields_info.append({
                "book": book,
                "missing_fields": missing_fields
            })

    if missing_fields_info:
        error_message = "Missing required fields:\n"
        for info in missing_fields_info:
            error_message += f"Missing fields: {', '.join(info['missing_fields'])} in {info['book']}. \n" # pylint: disable=line-too-long

        print(error_message)
        return jsonify({"error": error_message}), 500

    count_books = len(all_books)
    response_data = {
        "total_count" : count_books,
        "items" : all_books
    }

    return jsonify(response_data), 200

@app.route("/books/<string:book_id>", methods=["GET"])
def get_book(book_id):
    """
    Retrieve a specific book by its unique ID.
    """
    # extract host from the request
    host = request.host_url

    books_collection = get_book_collection()

    searched_book = find_one_book(book_id, books_collection)

    if not searched_book:
        return jsonify({"error": "Book not found"}), 404

    if searched_book.get("state")!="deleted":
        book_copy = copy.deepcopy(searched_book)
        book_copy.pop("state", None)
        return jsonify(append_hostname(book_copy, host)), 200
    return jsonify({"error": "Book not found"}), 404

@app.route("/books/<string:book_id>/reservations/<string:reservation_id>", methods=["GET"])
@login_required
@reservation_owner_or_admin_required
def get_reservation(book_id, reservation_id): # pylint: disable=unused-argument
    """
    Retrieve a specific reservation by its unique ID,
    if the reservation is owned by the current user,
    or if the current user is an admin.
    """
    reservation_to_return = g.reservation

    return jsonify(reservation_to_return), 200

# ----------- DELETE section ------------------
@app.route("/books/<string:book_id>", methods=["DELETE"])
@login_required
@roles_required('admin')
def delete_book(book_id):
    """
    Soft delete a book by setting its state to 'deleted' or return error if not found.
    """
    books_collection = get_book_collection()
    deleted_book = delete_book_by_id(book_id, books_collection)

    if deleted_book:
        # For debugging - may switch to logging later
        print(f"User '{g.user['email']}' deleted book '{deleted_book['title']}'")

        return "", 204
    return jsonify({"error": "Book not found"}), 404

# ----------- PUT section ------------------

@app.route("/books/<string:book_id>", methods=["PUT"])
@login_required
@roles_required('admin', 'editor')
def update_book(book_id):
    """
    Update a book by its unique ID using JSON from the request body.
    Returns a single dictionary with the updated book's details.
    """

    # check if request is json
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415

    # check request body is valid
    request_body = request.get_json()
    if not isinstance(request_body, dict):
        return jsonify({"error": "JSON payload must be a dictionary"}), 400
    print(request_body)
    # check request body contains required fields
    required_fields = ["title", "synopsis", "author"]
    missing_fields = [field for field in required_fields if field not in request_body]
    if missing_fields:
        return {"error": f"Missing required fields: {', '.join(missing_fields)}"}, 400

    host = request.host_url

    book_collection = get_book_collection()
    updated_book = update_book_by_id(book_id, request_body, book_collection)

    if updated_book:
        book_copy = copy.deepcopy(updated_book)
        book_copy.pop("state", None)
        return jsonify(append_hostname(book_copy, host)), 200
    return jsonify({"error": "Book not found"}), 404

@app.errorhandler(NotFound)
def handle_not_found(e):
    """Return a custom JSON response for 404 Not Found errors."""
    return jsonify({"error": str(e)}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    """Return a custom JSON response for any exception."""
    return jsonify({"error": str(e)}), 500
