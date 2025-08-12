""" Contains all the authorization decorators to control database access """
from functools import wraps
from flask import session, redirect, g, abort
from database import user_services, reservation_services

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

def reservation_owner_or_admin_required(f):
    """
    NOTE - Must be called after login_required decorator

    A decorator to ensure a user EITHER is owner of the reservation
    OR is an Admin.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Get the user's id field from Flask's g object
        current_user = g.user
        # Get the reservation_id from the URL
        query_reservation_id = kwargs.get('reservation_id')  # Get ID from URL
        if not query_reservation_id:
            abort(500, "Decorator couldn't find reservation ID in URL.")
        # Use the service function to query the collection
        resource = reservation_services.find_reservation_by_id(query_reservation_id)
        if not resource:
            abort(404, "Resource not found.")
        # Attach the found resource to the 'g' object
        g.reservation = resource

        # Check for ownership using the user's public UUID
        owner_id = resource.get('user_id')
        user_id = current_user.get('id')

        # Check for logged in admin or user match
        is_admin = 'admin' in current_user.get('roles', [])
        is_owner = (owner_id and user_id and owner_id == user_id)

        if is_admin or is_owner:
            # If authorized, call the original view function
            return f(*args, **kwargs)
        else:
            # If not authorized, 403 Forbidden
            abort(403)
    return decorated_function
