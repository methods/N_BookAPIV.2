""" Contains all the authorization decorators to control database access """
from functools import wraps
from flask import session, redirect, g, abort
from database import user_services

def login_required(f):
    """
    A decorator to ensure that a user is logged in.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #
        user_id = session.get('user_id')
        if session.get('user_id') is None:
            return redirect('http://localhost:5000/auth/login')

        # Load the user from the database
        user = user_services.find_user_by_id(user_id)
        if user is None:
            session.clear()
            return redirect('http://localhost:5000/auth/login')

        # Store the user object on 'g' for this request
        g.user = user
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*required_roles):
    """
    A decorator to ensure a user has at least one of the specified roles.
    Takes roles as arguments: @roles_required('admin', 'editor')
    """
    def decorator(f): # This is the actual decorator that wraps the view
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get the user's roles from the session
            user_roles = set(g.user.get('roles', []))

            # Check that the user has at least one of the roles required
            if not user_roles.intersection(required_roles):
                abort(403) # Forbids access if they don't
            return f(*args, **kwargs)
        return decorated_function
    return decorator # The outer function must return the decorator
