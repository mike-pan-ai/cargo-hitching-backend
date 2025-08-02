from functools import wraps
from flask import request, jsonify, current_app
from db import UserModel
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any


def extract_token_from_header() -> Optional[str]:
    """Extract JWT token from Authorization header"""
    if 'Authorization' not in request.headers:
        return None

    auth_header = request.headers['Authorization']
    try:
        # Expected format: "Bearer <token>"
        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None
        return parts[1]
    except (IndexError, AttributeError):
        return None


def decode_jwt_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode JWT token and return payload"""
    try:
        payload = jwt.decode(
            token,
            os.getenv('JWT_SECRET'),
            algorithms=["HS256"]
        )
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
    except Exception:
        return None


def create_access_token(user_data: Dict) -> str:
    """Create JWT access token"""
    payload = {
        'user_id': str(user_data['_id']),
        'email': user_data['email'],
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow(),
        'type': 'access'
    }

    return jwt.encode(payload, os.getenv('JWT_SECRET'), algorithm='HS256')


def create_verification_token(email: str) -> str:
    """Create JWT token for email verification"""
    payload = {
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=48),
        'iat': datetime.utcnow(),
        'type': 'verification'
    }

    return jwt.encode(payload, os.getenv('JWT_SECRET'), algorithm='HS256')


def token_required(f):
    """Decorator that requires a valid JWT token"""

    @wraps(f)
    def decorated(*args, **kwargs):
        # Extract token from header
        token = extract_token_from_header()
        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        # Decode token
        payload = decode_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        # Check token type
        if payload.get('type') != 'access':
            return jsonify({'error': 'Invalid token type'}), 401

        # Find user
        user = UserModel.find_by_email(payload.get('email'))
        if not user:
            return jsonify({'error': 'User not found'}), 401

        # Check if user is verified
        if not user.get('is_verified', False):
            return jsonify({'error': 'Email not verified'}), 401

        # Pass user object to the decorated function
        return f(user, *args, **kwargs)

    return decorated


def optional_token(f):
    """Decorator where token is optional"""

    @wraps(f)
    def decorated(*args, **kwargs):
        current_user = None

        # Try to extract and decode token
        token = extract_token_from_header()
        if token:
            payload = decode_jwt_token(token)
            if payload and payload.get('type') == 'access':
                current_user = UserModel.find_by_email(payload.get('email'))

        return f(current_user, *args, **kwargs)

    return decorated


def admin_required(f):
    """Decorator that requires admin privileges"""

    @wraps(f)
    def decorated(*args, **kwargs):
        # First check for valid token
        token = extract_token_from_header()
        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        payload = decode_jwt_token(token)
        if not payload:
            return jsonify({'error': 'Invalid or expired token'}), 401

        # Find user
        user = UserModel.find_by_email(payload.get('email'))
        if not user:
            return jsonify({'error': 'User not found'}), 401

        # Check admin status
        if not user.get('is_admin', False):
            return jsonify({'error': 'Admin privileges required'}), 403

        return f(user, *args, **kwargs)

    return decorated


def verify_password_reset_token(token: str) -> Optional[str]:
    """Verify password reset token and return email"""
    payload = decode_jwt_token(token)
    if not payload or payload.get('type') != 'password_reset':
        return None
    return payload.get('email')


def verify_email_token(token: str) -> Optional[str]:
    """Verify email verification token and return email"""
    payload = decode_jwt_token(token)
    if not payload or payload.get('type') != 'verification':
        return None
    return payload.get('email')


def create_password_reset_token(email: str) -> str:
    """Create JWT token for password reset"""
    payload = {
        'email': email,
        'exp': datetime.utcnow() + timedelta(hours=1),  # Short expiry for security
        'iat': datetime.utcnow(),
        'type': 'password_reset'
    }

    return jwt.encode(payload, os.getenv('JWT_SECRET'), algorithm='HS256')