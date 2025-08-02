from flask import Blueprint, request, jsonify
from flask_mail import Message
from extensions import mail
from db import UserModel
from auth_guard import create_access_token, create_verification_token, verify_email_token, create_password_reset_token, \
    verify_password_reset_token
from auth_guard import token_required
import bcrypt
import os
import re
from datetime import datetime, timedelta
import jwt
from bson import ObjectId

auth_bp = Blueprint('auth', __name__)


def validate_email(email):
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, "Valid password"


def create_remember_token(user):
    """Create a long-lived remember token (30 days)"""
    payload = {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "type": "remember",
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, os.getenv("JWT_SECRET"), algorithm="HS256")


def create_session_token(user, remember_me=False):
    """Create session token with different expiration based on remember_me"""
    if remember_me:
        # Short-lived access token (1 hour) when using remember me
        exp_time = datetime.utcnow() + timedelta(hours=1)
    else:
        # Regular session token (8 hours)
        exp_time = datetime.utcnow() + timedelta(hours=8)

    payload = {
        "user_id": str(user["_id"]),
        "email": user["email"],
        "type": "access",
        "exp": exp_time
    }
    return jwt.encode(payload, os.getenv("JWT_SECRET"), algorithm="HS256")


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400

        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        first_name = data.get("first_name", "").strip()
        last_name = data.get("last_name", "").strip()
        phone = data.get("phone", "").strip()

        # Validation
        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        if not validate_email(email):
            return jsonify({"error": "Invalid email format"}), 400

        is_valid_password, password_msg = validate_password(password)
        if not is_valid_password:
            return jsonify({"error": password_msg}), 400

        # Check if user already exists
        if UserModel.find_by_email(email):
            return jsonify({"error": "Email already registered"}), 409

        # Hash password
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        # Create user
        user_id = UserModel.create_user(
            email=email,
            hashed_password=hashed_pw,
            first_name=first_name,
            last_name=last_name,
            phone=phone
        )

        # Create verification token
        verification_token = create_verification_token(email)
        verify_link = f"http://localhost:5000/api/auth/verify/{verification_token}"

        # Send verification email
        msg = Message(
            subject="Verify Your Email - Cargo Hitching App",
            sender=os.getenv("MAIL_USERNAME"),
            recipients=[email],
            body=f"""
            Welcome to Cargo Hitching App!

            Please click the link below to verify your email address:
            {verify_link}

            This link will expire in 48 hours.

            If you didn't create this account, please ignore this email.
            """
        )

        try:
            mail.send(msg)
            print(f"Verification email sent to {email}")
        except Exception as e:
            print(f"Failed to send email: {e}")
            # Don't fail registration if email fails - user can request resend
            return jsonify({
                "message": "User registered successfully, but verification email failed to send. Please contact support.",
                "user_id": user_id
            }), 201

        return jsonify({
            "message": "User registered successfully. Please check your email to verify your account.",
            "user_id": user_id
        }), 201

    except Exception as e:
        print(f"Registration error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route('/login', methods=['POST'])
def login():
    """Login user and return access token with optional remember me functionality"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400

        email = data.get("email", "").strip().lower()
        password = data.get("password", "")
        remember_me = data.get("remember_me", False)

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        # Find user
        user = UserModel.find_by_email(email)
        if not user:
            return jsonify({"error": "Invalid email or password"}), 401

        # Check password
        if not bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            return jsonify({"error": "Invalid email or password"}), 401

        # Check if email is verified
        if not user.get("is_verified", False):
            return jsonify({
                "error": "Please verify your email before logging in",
                "hint": "Check your email for verification link or request a new one"
            }), 401

        # Create tokens based on remember_me preference
        access_token = create_session_token(user, remember_me)

        response_data = {
            "message": "Login successful",
            "token": access_token,
            "user": {
                "_id": str(user["_id"]),
                "email": user["email"],
                "first_name": user.get("first_name", ""),
                "last_name": user.get("last_name", ""),
                "phone": user.get("phone", ""),
                "is_verified": user.get("is_verified", False)
            }
        }

        # Add remember token if remember_me is enabled
        if remember_me:
            remember_token = create_remember_token(user)
            response_data["rememberToken"] = remember_token

        return jsonify(response_data), 200

    except Exception as e:
        print(f"Login error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route('/verify-token', methods=['POST'])
def verify_token():
    """Verify if a token is valid and return user data"""
    try:
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        # Verify token
        try:
            payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid token"}), 401

        # Get user from database
        user = UserModel.find_by_id(payload["user_id"])
        if not user:
            return jsonify({"error": "User not found"}), 401

        user_data = {
            "_id": str(user["_id"]),
            "email": user["email"],
            "first_name": user.get("first_name", ""),
            "last_name": user.get("last_name", ""),
            "phone": user.get("phone", ""),
            "is_verified": user.get("is_verified", False)
        }

        return jsonify({"user": user_data, "valid": True}), 200

    except Exception as e:
        print(f"Token verification error: {e}")
        return jsonify({"error": "Token verification failed"}), 401


@auth_bp.route('/refresh-token', methods=['POST'])
def refresh_token():
    """Refresh access token using remember token"""
    try:
        token = None
        auth_header = request.headers.get('Authorization')

        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"error": "Token is missing"}), 401

        # Verify remember token
        try:
            payload = jwt.decode(token, os.getenv("JWT_SECRET"), algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"error": "Remember token expired"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"error": "Invalid remember token"}), 401

        # Check if it's a remember token
        if payload.get("type") != "remember":
            return jsonify({"error": "Invalid token type for refresh"}), 401

        # Get user from database
        user = UserModel.find_by_id(payload["user_id"])
        if not user:
            return jsonify({"error": "User not found"}), 401

        # Create new access token (1 hour expiration for remember tokens)
        new_access_token = create_session_token(user, remember_me=True)

        return jsonify({"token": new_access_token}), 200

    except Exception as e:
        print(f"Token refresh error: {e}")
        return jsonify({"error": "Token refresh failed"}), 401


@auth_bp.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    """Verify user email with token"""
    try:
        # Verify token
        email = verify_email_token(token)
        if not email:
            return jsonify({"error": "Invalid or expired verification token"}), 400

        # Update user verification status
        success = UserModel.verify_email(email)
        if not success:
            return jsonify({"error": "User not found or already verified"}), 400

        return jsonify({"message": "Email verified successfully! You can now log in."}), 200

    except Exception as e:
        print(f"Email verification error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route('/resend-verification', methods=['POST'])
def resend_verification():
    """Resend verification email"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400

        email = data.get("email", "").strip().lower()
        if not email:
            return jsonify({"error": "Email is required"}), 400

        # Find user
        user = UserModel.find_by_email(email)
        if not user:
            return jsonify({"error": "Email not found"}), 404

        if user.get("is_verified", False):
            return jsonify({"error": "Email is already verified"}), 400

        # Create new verification token
        verification_token = create_verification_token(email)
        verify_link = f"http://localhost:5000/api/auth/verify/{verification_token}"

        # Send verification email
        msg = Message(
            subject="Verify Your Email - Cargo Hitching App",
            sender=os.getenv("MAIL_USERNAME"),
            recipients=[email],
            body=f"""
            Please click the link below to verify your email address:
            {verify_link}

            This link will expire in 48 hours.
            """
        )

        mail.send(msg)
        return jsonify({"message": "Verification email sent successfully"}), 200

    except Exception as e:
        print(f"Resend verification error: {e}")
        return jsonify({"error": "Failed to send verification email"}), 500


@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    """Send password reset email"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400

        email = data.get("email", "").strip().lower()
        if not email:
            return jsonify({"error": "Email is required"}), 400

        # Find user
        user = UserModel.find_by_email(email)
        if not user:
            # Don't reveal if email exists for security
            return jsonify({"message": "If the email exists, a password reset link has been sent"}), 200

        # Create password reset token
        reset_token = create_password_reset_token(email)
        reset_link = f"http://localhost:5000/api/auth/reset-password/{reset_token}"

        # Send reset email
        msg = Message(
            subject="Reset Your Password - Cargo Hitching App",
            sender=os.getenv("MAIL_USERNAME"),
            recipients=[email],
            body=f"""
            You requested a password reset for your Cargo Hitching App account.

            Click the link below to reset your password:
            {reset_link}

            This link will expire in 1 hour for security reasons.

            If you didn't request this reset, please ignore this email.
            """
        )

        mail.send(msg)
        return jsonify({"message": "If the email exists, a password reset link has been sent"}), 200

    except Exception as e:
        print(f"Forgot password error: {e}")
        return jsonify({"error": "Failed to send reset email"}), 500


@auth_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password(token):
    """Reset password with token"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "JSON data required"}), 400

        new_password = data.get("password", "")
        if not new_password:
            return jsonify({"error": "New password is required"}), 400

        # Validate new password
        is_valid_password, password_msg = validate_password(new_password)
        if not is_valid_password:
            return jsonify({"error": password_msg}), 400

        # Verify reset token
        email = verify_password_reset_token(token)
        if not email:
            return jsonify({"error": "Invalid or expired reset token"}), 400

        # Find user
        user = UserModel.find_by_email(email)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Hash new password
        hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        # Update password
        success = UserModel.update_user(str(user["_id"]), {"password": hashed_pw})
        if not success:
            return jsonify({"error": "Failed to update password"}), 500

        return jsonify({"message": "Password reset successfully. You can now log in with your new password."}), 200

    except Exception as e:
        print(f"Reset password error: {e}")
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.route('/change-password', methods=['POST'])
def change_password():
    """Change password for authenticated user"""
    from auth_guard import token_required

    @token_required
    def _change_password(current_user):
        try:
            data = request.json
            if not data:
                return jsonify({"error": "JSON data required"}), 400

            current_password = data.get("current_password", "")
            new_password = data.get("new_password", "")

            if not current_password or not new_password:
                return jsonify({"error": "Current password and new password are required"}), 400

            # Verify current password
            if not bcrypt.checkpw(current_password.encode('utf-8'), current_user["password"]):
                return jsonify({"error": "Current password is incorrect"}), 401

            # Validate new password
            is_valid_password, password_msg = validate_password(new_password)
            if not is_valid_password:
                return jsonify({"error": password_msg}), 400

            # Hash new password
            hashed_pw = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

            # Update password
            success = UserModel.update_user(str(current_user["_id"]), {"password": hashed_pw})
            if not success:
                return jsonify({"error": "Failed to update password"}), 500

            return jsonify({"message": "Password changed successfully"}), 200

        except Exception as e:
            print(f"Change password error: {e}")
            return jsonify({"error": "Internal server error"}), 500

    return _change_password()


@auth_bp.route('/profile', methods=['GET'])
def get_profile():
    """Get user profile"""
    from auth_guard import token_required

    @token_required
    def _get_profile(current_user):
        try:
            profile = {
                "id": str(current_user["_id"]),
                "email": current_user["email"],
                "first_name": current_user.get("first_name", ""),
                "last_name": current_user.get("last_name", ""),
                "phone": current_user.get("phone", ""),
                "is_verified": current_user.get("is_verified", False),
                "created_at": current_user.get("created_at"),
                "updated_at": current_user.get("updated_at")
            }
            return jsonify({"profile": profile}), 200

        except Exception as e:
            print(f"Get profile error: {e}")
            return jsonify({"error": "Internal server error"}), 500

    return _get_profile()


@auth_bp.route('/profile', methods=['PUT'])
def update_profile():
    """Update user profile"""
    from auth_guard import token_required

    @token_required
    def _update_profile(current_user):
        try:
            data = request.json
            if not data:
                return jsonify({"error": "JSON data required"}), 400

            # Fields that can be updated
            updatable_fields = ['first_name', 'last_name', 'phone']
            update_data = {}

            for field in updatable_fields:
                if field in data:
                    update_data[field] = data[field].strip() if isinstance(data[field], str) else data[field]

            if not update_data:
                return jsonify({"error": "No valid fields to update"}), 400

            # Update user
            success = UserModel.update_user(str(current_user["_id"]), update_data)
            if not success:
                return jsonify({"error": "Failed to update profile"}), 500

            return jsonify({"message": "Profile updated successfully"}), 200

        except Exception as e:
            print(f"Update profile error: {e}")
            return jsonify({"error": "Internal server error"}), 500

    return _update_profile()


# Add this endpoint to your existing routes/auth.py file

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user(current_user):
    """Get current logged-in user's information"""
    try:
        # The current_user comes from your @token_required decorator
        # Based on your auth_guard.py, it should be the email
        # We need to get the full user object from database

        from db import users  # Import your users collection

        # Find the full user object
        if isinstance(current_user, str):
            # If current_user is just an email (from your auth_guard)
            user = users.find_one({"email": current_user})
        else:
            # If current_user is already a user object
            user = current_user

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Return user info (no password!)
        user_info = {
            'id': str(user['_id']),
            'firstname': user.get('firstname', ''),
            'lastname': user.get('lastname', ''),
            'email': user.get('email', ''),
            'phone': user.get('phone', ''),
            'company': user.get('company', ''),
            'website': user.get('website', ''),
            'bio': user.get('bio', ''),
            'is_verified': user.get('is_verified', False),
            'created_at': user.get('created_at', '')
        }

        return jsonify(user_info), 200

    except Exception as e:
        print(f"Error fetching current user: {e}")
        return jsonify({'error': 'Server error'}), 500