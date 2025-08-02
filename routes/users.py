# routes/users.py
from flask import Blueprint, request, jsonify
from bson import ObjectId
from auth_guard import token_required
from db import get_database

users_bp = Blueprint('users', __name__)


def get_db():
    """Get database connection"""
    return get_database()


@users_bp.route('/profile/<user_id>', methods=['GET'])
def get_public_profile(user_id):
    """Get public profile information for any user"""
    try:
        db = get_db()
        users_collection = db.users

        # Find user by ID
        user = users_collection.find_one({"_id": ObjectId(user_id)})

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Return only public information (no password!)
        public_profile = {
            'id': str(user['_id']),
            'firstname': user.get('firstname', ''),
            'lastname': user.get('lastname', ''),
            'email': user.get('email', ''),
            'phone': user.get('phone', ''),
            'company': user.get('company', ''),
            'website': user.get('website', ''),
            'bio': user.get('bio', ''),
            'is_verified': user.get('is_verified', False),
            'created_at': user.get('created_at', ''),
            'member_since': user.get('created_at', '')
        }

        return jsonify(public_profile), 200

    except Exception as e:
        print(f"Error fetching profile: {e}")
        return jsonify({'error': 'Server error'}), 500


@users_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile(current_user):
    """Update current user's profile information"""
    try:
        db = get_db()
        users_collection = db.users

        # Get request data
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Find current user
        if isinstance(current_user, str):
            # If current_user is email (from auth_guard)
            user = users_collection.find_one({"email": current_user})
        else:
            # If current_user is already user object
            user = current_user

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Prepare update data - only allow specific fields
        allowed_fields = ['firstname', 'lastname', 'phone', 'company', 'website', 'bio']
        update_data = {}

        for field in allowed_fields:
            if field in data:
                # Basic validation
                value = data[field]
                if isinstance(value, str):
                    value = value.strip()

                # Field-specific validation
                if field == 'phone' and value:
                    # Basic phone validation (optional)
                    if len(value) < 10:
                        return jsonify({'error': 'Phone number must be at least 10 digits'}), 400

                if field == 'website' and value:
                    # Basic URL validation
                    if not (value.startswith('http://') or value.startswith('https://')):
                        value = 'https://' + value

                if field == 'bio' and value:
                    # Limit bio length
                    if len(value) > 500:
                        return jsonify({'error': 'Bio cannot exceed 500 characters'}), 400

                update_data[field] = value

        if not update_data:
            return jsonify({'error': 'No valid fields to update'}), 400

        # Add updated timestamp
        from datetime import datetime
        update_data['updated_at'] = datetime.utcnow()

        # Update user in database
        result = users_collection.update_one(
            {"_id": user['_id']},
            {"$set": update_data}
        )

        if result.modified_count == 0:
            return jsonify({'error': 'No changes made'}), 400

        return jsonify({'message': 'Profile updated successfully'}), 200

    except Exception as e:
        print(f"Error updating profile: {e}")
        return jsonify({'error': 'Server error'}), 500


@users_bp.route('/profile', methods=['GET'])
@token_required
def get_my_profile(current_user):
    """Get current user's own profile (private view with all fields)"""
    try:
        db = get_db()
        users_collection = db.users

        # Find current user
        if isinstance(current_user, str):
            user = users_collection.find_one({"email": current_user})
        else:
            user = current_user

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Return private profile (includes more fields than public)
        private_profile = {
            'id': str(user['_id']),
            'firstname': user.get('firstname', ''),
            'lastname': user.get('lastname', ''),
            'email': user.get('email', ''),
            'phone': user.get('phone', ''),
            'company': user.get('company', ''),
            'website': user.get('website', ''),
            'bio': user.get('bio', ''),
            'is_verified': user.get('is_verified', False),
            'created_at': user.get('created_at', ''),
            'updated_at': user.get('updated_at', ''),
            'member_since': user.get('created_at', '')
        }

        return jsonify(private_profile), 200

    except Exception as e:
        print(f"Error fetching own profile: {e}")
        return jsonify({'error': 'Server error'}), 500


@users_bp.route('/search', methods=['GET'])
def search_users():
    """Search for users (basic functionality)"""
    try:
        query = request.args.get('q', '').strip()

        if not query or len(query) < 2:
            return jsonify({'error': 'Search query must be at least 2 characters'}), 400

        db = get_db()
        users_collection = db.users

        # Search in firstname, lastname, company
        search_criteria = {
            "$or": [
                {"firstname": {"$regex": query, "$options": "i"}},
                {"lastname": {"$regex": query, "$options": "i"}},
                {"company": {"$regex": query, "$options": "i"}}
            ],
            "is_verified": True  # Only show verified users
        }

        users = list(users_collection.find(search_criteria).limit(10))

        # Return public info only
        results = []
        for user in users:
            results.append({
                'id': str(user['_id']),
                'firstname': user.get('firstname', ''),
                'lastname': user.get('lastname', ''),
                'company': user.get('company', ''),
                'member_since': user.get('created_at', '')
            })

        return jsonify({
            'users': results,
            'count': len(results),
            'query': query
        }), 200

    except Exception as e:
        print(f"Error searching users: {e}")
        return jsonify({'error': 'Server error'}), 500