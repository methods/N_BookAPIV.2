""" Module to initialize the OAuth client and handle core OAuth functions """

import os
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
from database import user_services

## --MODULE LEVEL GLOBALS --
oauth = OAuth()
load_dotenv()
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
APP_SECRET_KEY = os.getenv('SECRET_KEY')

# Custom exception for this module
class AuthServiceError(Exception):
    """Custom exception for authentication service failures."""

def init_oauth(app):
    """Initialize the OAuth client, attach it to the Flask app"""
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        # This URL is for Google's OpenID Connect - it stores all the information for their OAuth
        # connection, with which Authlib automatically configures itself.
        client_kwargs={'scope': 'openid email profile'}
    )

def oauth_login():
    """Login to Google OAuth"""
    redirect_uri = 'http://localhost:5000/auth/callback'
    return oauth.google.authorize_redirect(redirect_uri)

def oauth_authorize():
    """
    Handles the OAuth token exchange and retrieves or creates a user.
    """
    # Call Authlib to handle the entire secure token exchange.
    token = oauth.google.authorize_access_token()
    # Authlib handles parsing of the token, get the 'userinfo' dictionary from it
    profile = token.get('userinfo')
    if not profile:
        raise AuthServiceError("Could not retrieve user profile from OAuth token.")

    # Call the mongoDB get or create user function passing the userinfo dictionary
    user_document = user_services.get_or_create_user_from_oidc(profile)

    return user_document
