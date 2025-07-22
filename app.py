"""Flask application module for managing a collection of books."""
# pylint: disable=cyclic-import
import uuid
import copy
import os
from urllib.parse import urljoin
from dotenv import load_dotenv
from flask import Flask, request, jsonify
from werkzeug.exceptions import NotFound
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from database.mongo_helper import insert_book_to_mongo, find_all_books, find_one_book
from auth.services import init_oauth
from auth.views import auth_bp # Imports the blueprint object from the auth module
from auth.decorators import login_required, roles_required
from data import books

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
    print("book_for_response", book_for_response)
    # Remove MOngoDB's ObjectID value
    book_for_response.pop('_id', None)

    return jsonify(book_for_response), 201


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
    books_list_result, total_count_result = find_all_books(books_collection)

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

# ----------- DELETE section ------------------
@app.route("/books/<string:book_id>", methods=["DELETE"])
@login_required
@roles_required('admin')
def delete_book(book_id):
    """
    Soft delete a book by setting its state to 'deleted' or return error if not found.
    """
    if not books:
        return jsonify({"error": "Book collection not initialized"}), 500

    for book in books:
        if book.get("id") == book_id:
            book["state"] = "deleted"
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
    if not books:
        return jsonify({"error": "Book collection not initialized"}), 500

    # check if request is json
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 415

    # check request body is valid
    request_body = request.get_json()
    if not isinstance(request_body, dict):
        return jsonify({"error": "JSON payload must be a dictionary"}), 400

    # check request body contains required fields
    required_fields = ["title", "synopsis", "author"]
    missing_fields = [field for field in required_fields if field not in request_body]
    if missing_fields:
        return {"error": f"Missing required fields: {', '.join(missing_fields)}"}, 400

    host = request.host_url

    # now that we have a book object that is valid, loop through books
    for book in books:
        if book.get("id") == book_id:
            # update the book values to what is in the request
            book["title"] = request.json.get("title")
            book["synopsis"] = request.json.get("synopsis")
            book["author"] = request.json.get("author")

            # Add links exists as paths only
            book["links"] = {
                "self": f"/books/{book_id}",
                "reservations": f"/books/{book_id}/reservations",
                "reviews": f"/books/{book_id}/reviews"
            }
            # make a deepcopy of the modified book
            book_copy = copy.deepcopy(book)
            book_with_hostname = append_hostname(book_copy, host)
            return jsonify(book_with_hostname), 200

    return jsonify({"error": "Book not found"}), 404

@app.errorhandler(NotFound)
def handle_not_found(e):
    """Return a custom JSON response for 404 Not Found errors."""
    return jsonify({"error": str(e)}), 404

@app.errorhandler(Exception)
def handle_exception(e):
    """Return a custom JSON response for any exception."""
    return jsonify({"error": str(e)}), 500
