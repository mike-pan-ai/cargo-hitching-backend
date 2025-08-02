from flask import Blueprint, request, jsonify
from models import db, User, Trip

users_bp = Blueprint('users', __name__)


@users_bp.route('/profile/<user_id>', methods=['GET'])
def get_public_profile(user_id):
    """Get public profile of a user"""
    try:
        # Find user
        user = User.query.get(user_id)

        if not user:
            return jsonify({
                'error': 'User not found',
                'message': 'This user account no longer exists',
                'user_id': user_id
            }), 404

        # Get user's basic public info
        profile_data = {
            'id': user.id,
            'name': f"{user.first_name} {user.last_name}".strip() or 'Anonymous User',
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'phone': user.phone,
            'member_since': user.created_at.isoformat() if user.created_at else None,
            'is_verified': user.is_verified
        }

        # Get user's trip statistics
        total_trips = Trip.query.filter_by(user_id=user_id).count()
        active_trips = Trip.query.filter_by(user_id=user_id, status='active').count()

        profile_data['trip_stats'] = {
            'total_trips': total_trips,
            'active_trips': active_trips,
            'completed_trips': total_trips - active_trips
        }

        # Get recent trips (last 5 active trips)
        recent_trips = Trip.query.filter_by(
            user_id=user_id,
            status='active'
        ).order_by(Trip.created_at.desc()).limit(5).all()

        profile_data['recent_trips'] = [trip.to_dict() for trip in recent_trips]

        return jsonify(profile_data), 200

    except Exception as e:
        print(f"Error getting public profile: {e}")
        return jsonify({'error': 'Failed to get user profile'}), 500