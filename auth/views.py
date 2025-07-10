"""
This module handles the user-facing endpoints for the authentication process,
including login initiation, the OAuth callback from the identity provider,
and logout.
"""
import logging
from flask import Blueprint, redirect, session
from authlib.integrations.base_client import OAuthError
from auth.decorators import login_required
from . import services

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
        # The oauth_authorize function should have exchanged
        # the single use code for a token with the user data
        # pylint: disable=assignment-from-none
        user = services.oauth_authorize()

        if user:
            # pylint: disable=unsubscriptable-object
            session['user_id'] = str(user['_id'])
            return redirect('http://localhost:5000/books')

        logging.warning("Authorization failed: user service did not return a user.")
        return redirect('http://localhost:5000/') # Or some other error page

    except OAuthError as e:
        # This case handles if Authlib throws an error (e.g., user clicked "deny")
        logging.error("OAuth error during callback: %s", e.description)
        return redirect('http://localhost:5000/')

@auth_bp.route('/logout')
@login_required
def logout():
    """Logs the current user out by clearing the session."""
    session.clear()
    return redirect('http://localhost:5000/')
