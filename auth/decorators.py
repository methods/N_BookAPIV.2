""" Contains all the authorization decorators to control database access """
from functools import wraps
from flask import session, redirect
from database import user_services

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        #
        user_id = session.get('user_id')
        if session.get('user_id') is None:
            return redirect('http://localhost:5000/auth/login')

        # Load the user from the database
        user = user_services.find_user_by_id(user_id)
        return f(*args, **kwargs)
    return decorated_function

def roles_required(*required_roles):
    # To be implemented
    pass