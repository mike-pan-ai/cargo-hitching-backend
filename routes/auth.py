from flask import Blueprint, request, jsonify, current_app
from models import db, User
from auth_guard import token_required, generate_token, generate_verification_token, verify_verification_token
import bcrypt
import re
from email_validator import validate_email, EmailNotValidError

auth_bp = Blueprint('auth', __name__)


def validate_password(password):
    """Validate password strength"""
    if len(password) < 6:
        return False, "Password must be at least 6 characters long"
    return True, ""


def validate_user_data(data, is_registration=True):
    """Validate user registration/login data"""
    errors = []

    # Email validation
    if 'email' not in data or not data['email']:
        errors.append("Email is required")
    else:
        try:
            validate_email(data['email'])
        except EmailNotValidError:
            errors.append("Invalid email format")

    # Password validation
    if 'password' not in data or not data['password']:
        errors.append("Password is required")
    elif is_registration:
        is_valid, message = validate_password(data['password'])
        if not is_valid:
            errors.append(message)

    # Registration-specific validation
    if is_registration:
        if 'first_name' in data and data['first_name'] and len(data['first_name']) > 100:
            errors.append("First name must be less than 100 characters")
        if 'last_name' in data and data['last_name'] and len(data['last_name']) > 100:
            errors.append("Last name must be less than 100 characters")
        if 'phone' in data and data['phone'] and len(data['phone']) > 20:
            errors.append("Phone number must be less than 20 characters")

    return len(errors) == 0, errors


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate input data
        is_valid, validation_errors = validate_user_data(data, is_registration=True)
        if not is_valid:
            return jsonify({
                "error": "Validation failed",
                "details": validation_errors
            }), 400

        # Check if user already exists
        existing_user = User.query.filter_by(email=data['email'].lower()).first()
        if existing_user:
            return jsonify({"error": "User with this email already exists"}), 400

        # Hash password
        password_hash = bcrypt.hashpw(
            data['password'].encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        # Create new user
        new_user = User(
            email=data['email'].lower(),
            password_hash=password_hash,
            first_name=data.get('first_name', ''),
            last_name=data.get('last_name', ''),
            phone=data.get('phone', ''),
            is_verified=False  # Email verification required
        )

        db.session.add(new_user)
        db.session.commit()

        # Generate verification token (optional - for email verification)
        verification_token = generate_verification_token(new_user)

        return jsonify({
            "message": "User registered successfully",
            "user_id": new_user.id,
            "email": new_user.email,
            "verification_token": verification_token,
            "note": "Please verify your email address"
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Registration error: {e}")
        return jsonify({"error": "Registration failed"}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return token"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate input data
        is_valid, validation_errors = validate_user_data(data, is_registration=False)
        if not is_valid:
            return jsonify({
                "error": "Validation failed",
                "details": validation_errors
            }), 400

        # Find user
        user = User.query.filter_by(email=data['email'].lower()).first()

        if not user:
            return jsonify({"error": "Invalid email or password"}), 401

        # Check password
        if not bcrypt.checkpw(data['password'].encode('utf-8'), user.password_hash.encode('utf-8')):
            return jsonify({"error": "Invalid email or password"}), 401

        # Generate token
        token = generate_token(user)

        return jsonify({
            "message": "Login successful",
            "token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "is_verified": user.is_verified
            }
        }), 200

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"error": "Login failed"}), 500


@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """Get current user information"""
    return jsonify({
        "user": current_user.to_dict()
    }), 200


@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    """Verify email address"""
    try:
        user = verify_verification_token(token)

        if not user:
            return jsonify({"error": "Invalid or expired verification token"}), 400

        if user.is_verified:
            return jsonify({"message": "Email already verified"}), 200

        # Mark user as verified
        user.is_verified = True
        db.session.commit()

        return jsonify({
            "message": "Email verified successfully",
            "user_id": user.id
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Email verification error: {e}")
        return jsonify({"error": "Email verification failed"}), 500


@auth_bp.route('/profile', methods=['GET'])
@token_required
def get_profile(current_user):
    """Get user profile"""
    return jsonify({
        "profile": current_user.to_dict()
    }), 200


@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    """Update user profile"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Update allowed fields
        if 'first_name' in data:
            current_user.first_name = data['first_name'][:100]
        if 'last_name' in data:
            current_user.last_name = data['last_name'][:100]
        if 'phone' in data:
            current_user.phone = data['phone'][:20]

        db.session.commit()

        return jsonify({
            "message": "Profile updated successfully",
            "user": current_user.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Profile update error: {e}")
        return jsonify({"error": "Profile update failed"}), 500