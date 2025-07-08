""" Contains all mongoDB user service functions """
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from datetime import datetime, timezone

def get_users_collection():
    """Establishes a connection and returns the users collection."""
    from app import app
    try:
        # This creates a NEW client connection every time it's called.
        client = MongoClient(app.config['MONGO_URI'], serverSelectionTimeoutMS=5000)
        db = client[app.config['DB_NAME']]
        # Assuming your users collection is in the same DB.
        users_collection = db['users']
        return users_collection
    except ConnectionFailure as e:
        raise ConnectionFailure(f'Could not connect to MongoDB: {str(e)}') from e

def get_or_create_user_from_oidc(profile):
    """
    Finds a user by their OIDC profile or creates a new one.
    """
    users_collection = get_users_collection() # Call the local helper

    existing_user = users_collection.find_one({'google_id': profile['sub']})

    if existing_user:
        return existing_user
    else:
        # Prepare the new_user_doc
        new_user_doc = {
            'google_id': profile['sub'],
            'email': profile['email'],
            'name': profile.get('name'),
            'roles': ['viewer'], # Assign default role
            'createdAt': datetime.now(timezone.utc),
            'lastLogin': datetime.now(timezone.utc)
        }

        # Insert this into the database
        result = users_collection.insert_one(new_user_doc)

        # Explicitly assign the ['_id'] field from the inserted_id
        new_user_doc['_id'] = result.inserted_id
        return new_user_doc

def find_user_by_id(user_id):
    """
    Find a single user document by their mongoDB _id field.
    """
    users_collection = get_users_collection()
    return
