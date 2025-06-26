""" Module to initialize the OAuth client and handle core OAuth functions """

import os
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth

## --MODULE LEVEL GLOBALS --
oauth = OAuth()
load_dotenv()
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')
APP_SECRET_KEY = os.getenv('SECRET_KEY')


def init_oauth(app):
    """Initialize the OAuth client, attach it to the Flask app"""
    oauth.init_app(app)
    oauth.register(
        name='google',
        client_id=GOOGLE_CLIENT_ID,
        client_secret=GOOGLE_CLIENT_SECRET,
        server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
        client_kwargs={'scope': 'openid email'}
    )

def login():
    """Login to Google OAuth"""
    redirect_uri = 'http://localhost:5000/auth/callback'
    return oauth.google.authorize_redirect(redirect_uri)
