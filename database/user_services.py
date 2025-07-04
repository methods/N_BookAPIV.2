""" Contains all mongoDB user service functions """
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

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
        return None
