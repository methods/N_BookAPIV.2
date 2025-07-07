""" Contains all the authorization decorators to control database access """
from functools import wraps

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # To be implemented
        pass
    return decorated_function

def roles_required(*required_roles):
    # To be implemented
    pass