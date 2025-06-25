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
    # oauth.init_app(app)