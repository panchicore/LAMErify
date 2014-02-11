import settings
from functools import wraps
from flask import request, abort

def require_apikey(view_function):
    @wraps(view_function)
    def decorated_function(*args, **kwargs):
        if request.args.get('api_key') and \
                        request.args.get('api_key') == settings.API_KEY:
            return view_function(*args, **kwargs)
        else:
            abort(401)
    return decorated_function
