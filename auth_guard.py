from functools import wraps
from flask import request, jsonify, current_app
import jwt
from models import User


def token_required(f):
    """Decorator to require authentication token"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401

        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            # Decode the token
            data = jwt.decode(
                token,
                current_app.config['JWT_SECRET'],
                algorithms=['HS256']
            )

            # Get user from database
            current_user = User.query.filter_by(id=data['user_id']).first()

            if not current_user:
                return jsonify({'error': 'Invalid token - user not found'}), 401

        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        except Exception as e:
            return jsonify({'error': f'Token validation failed: {str(e)}'}), 401

        # Pass current_user to the decorated function
        return f(current_user, *args, **kwargs)

    return decorated_function


def optional_token(f):
    """Decorator for optional authentication - provides user if token exists"""

    @wraps(f)
    def decorated_function(*args, **kwargs):
        current_user = None
        auth_header = request.headers.get('Authorization')

        if auth_header:
            try:
                token = auth_header.split(' ')[1]  # Bearer <token>
                data = jwt.decode(
                    token,
                    current_app.config['JWT_SECRET'],
                    algorithms=['HS256']
                )
                current_user = User.query.filter_by(id=data['user_id']).first()
            except (IndexError, jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                # Token is invalid, but that's okay for optional auth
                pass

        return f(current_user, *args, **kwargs)

    return decorated_function


def generate_token(user):
    """Generate JWT token for user"""
    import datetime

    payload = {
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(
            hours=current_app.config.get('JWT_ACCESS_TOKEN_EXPIRES_HOURS', 24)
        ),
        'iat': datetime.datetime.utcnow()
    }

    return jwt.encode(
        payload,
        current_app.config['JWT_SECRET'],
        algorithm='HS256'
    )


def generate_verification_token(user):
    """Generate email verification token"""
    import datetime

    payload = {
        'user_id': user.id,
        'email': user.email,
        'purpose': 'email_verification',
        'exp': datetime.datetime.utcnow() + datetime.timedelta(
            hours=current_app.config.get('JWT_EMAIL_VERIFICATION_EXPIRES_HOURS', 48)
        ),
        'iat': datetime.datetime.utcnow()
    }

    return jwt.encode(
        payload,
        current_app.config['JWT_SECRET'],
        algorithm='HS256'
    )


def verify_verification_token(token):
    """Verify email verification token"""
    try:
        data = jwt.decode(
            token,
            current_app.config['JWT_SECRET'],
            algorithms=['HS256']
        )

        if data.get('purpose') != 'email_verification':
            return None

        user = User.query.filter_by(id=data['user_id']).first()
        return user

    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None