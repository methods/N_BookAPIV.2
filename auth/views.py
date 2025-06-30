"""
This module handles the user-facing endpoints for the authentication process,
including login initiation, the OAuth callback from the identity provider,
and logout.
"""
from flask import Blueprint
from . import services

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login')
def login():
    """Login to Google OAuth"""
    return services.oauth_login()

def callback():
    """Callback login from OAuth"""
    return
