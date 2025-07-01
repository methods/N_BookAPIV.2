"""
This module handles the user-facing endpoints for the authentication process,
including login initiation, the OAuth callback from the identity provider,
and logout.
"""
from flask import Blueprint, redirect, session
from . import services
import logging

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    """Login to Google OAuth"""
    # This route should simply call the relevant service function
    return services.oauth_login()

@auth_bp.route('/callback')
def callback():
    """Handles the callback from the OAuth service provider."""
    # The Oauth service sends back a single use code in the URL query params;
    # This is globally available via flask.request.args and therefore does not need to be passed
    try:
        # The oauth_authorize function should have exchanged the single use code for a token with the user data
        user = services.oauth_authorize()

        if user:
            session['user_id'] = str(user['_id'])
            return redirect('http://localhost:5000/books')

    except Exception as e:
        # This case handles if Authlib throws an error (e.g., user clicked "deny")
        logging.error(f"An exception occurred during OAuth callback: {e}")
        return redirect('http://localhost:5000/')
    return
