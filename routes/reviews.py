# routes/reviews.py
from flask import Blueprint, request, jsonify
from bson import ObjectId
from auth_guard import token_required
from db import get_database
from datetime import datetime

reviews_bp = Blueprint('reviews', __name__)


def get_db():
    """Get database connection"""
    return get_database()


@reviews_bp.route('/user/<user_id>', methods=['GET'])
def get_user_reviews(user_id):
    """Get reviews for a specific user"""
    try:
        db = get_db()

        # For now, return empty array since we haven't implemented reviews yet
        # This is a placeholder that allows the frontend to work

        # In the future, this would query a reviews collection:
        # reviews_collection = db.reviews
        # reviews = list(reviews_collection.find({"reviewed_user_id": ObjectId(user_id)}).sort("created_at", -1).limit(10))

        # Mock data structure for future implementation:
        mock_reviews = []

        # Uncomment this when you want to test with sample data:
        # mock_reviews = [
        #     {
        #         "_id": "sample_review_1",
        #         "reviewer_name": "John Doe",
        #         "rating": 5,
        #         "review": "Excellent service! Very reliable and professional.",
        #         "created_at": datetime.utcnow(),
        #         "trip_id": "sample_trip_id"
        #     },
        #     {
        #         "_id": "sample_review_2",
        #         "reviewer_name": "Jane Smith",
        #         "rating": 4,
        #         "review": "Good experience overall. Would work with again.",
        #         "created_at": datetime.utcnow(),
        #         "trip_id": "sample_trip_id_2"
        #     }
        # ]

        return jsonify(mock_reviews), 200

    except Exception as e:
        print(f"Error fetching reviews: {e}")
        return jsonify({'error': 'Server error'}), 500


@reviews_bp.route('/add', methods=['POST'])
@token_required
def add_review(current_user):
    """Add a new review for a user (future feature)"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['reviewed_user_id', 'rating', 'review']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        # Validate rating
        rating = data.get('rating')
        if not isinstance(rating, int) or rating < 1 or rating > 5:
            return jsonify({'error': 'Rating must be between 1 and 5'}), 400

        # Validate review text
        review_text = data.get('review', '').strip()
        if len(review_text) < 10:
            return jsonify({'error': 'Review must be at least 10 characters'}), 400
        if len(review_text) > 500:
            return jsonify({'error': 'Review cannot exceed 500 characters'}), 400

        # Get current user info
        db = get_db()
        users_collection = db.users

        if isinstance(current_user, str):
            user = users_collection.find_one({"email": current_user})
        else:
            user = current_user

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Prevent self-reviews
        if str(data['reviewed_user_id']) == str(user['_id']):
            return jsonify({'error': 'Cannot review yourself'}), 400

        # Check if reviewed user exists
        reviewed_user = users_collection.find_one({"_id": ObjectId(data['reviewed_user_id'])})
        if not reviewed_user:
            return jsonify({'error': 'Reviewed user not found'}), 404

        # For now, just return success message
        # In future implementation, you would:
        # 1. Create reviews collection
        # 2. Check if user already reviewed this person for this trip
        # 3. Insert the review
        # 4. Update user's average rating

        return jsonify({
            'message': 'Review system not yet implemented',
            'note': 'This endpoint is ready for future development'
        }), 200

    except Exception as e:
        print(f"Error adding review: {e}")
        return jsonify({'error': 'Server error'}), 500


@reviews_bp.route('/stats/<user_id>', methods=['GET'])
def get_review_stats(user_id):
    """Get review statistics for a user"""
    try:
        # For now, return default stats
        # In future implementation, this would calculate real statistics

        default_stats = {
            'total_reviews': 0,
            'average_rating': 0.0,
            'rating_breakdown': {
                '5': 0,
                '4': 0,
                '3': 0,
                '2': 0,
                '1': 0
            }
        }

        # Mock data for testing (uncomment to test):
        # default_stats = {
        #     'total_reviews': 15,
        #     'average_rating': 4.3,
        #     'rating_breakdown': {
        #         '5': 8,
        #         '4': 5,
        #         '3': 2,
        #         '2': 0,
        #         '1': 0
        #     }
        # }

        return jsonify(default_stats), 200

    except Exception as e:
        print(f"Error fetching review stats: {e}")
        return jsonify({'error': 'Server error'}), 500


@reviews_bp.route('/my-reviews', methods=['GET'])
@token_required
def get_my_reviews(current_user):
    """Get reviews that the current user has written"""
    try:
        # For now, return empty array
        # In future implementation, this would query reviews by reviewer_id

        return jsonify({
            'reviews': [],
            'count': 0,
            'message': 'Review system not yet implemented'
        }), 200

    except Exception as e:
        print(f"Error fetching my reviews: {e}")
        return jsonify({'error': 'Server error'}), 500

# Future endpoints for full review system:
# - PUT /reviews/<review_id> (update own review)
# - DELETE /reviews/<review_id> (delete own review)
# - GET /reviews/pending (reviews waiting to be written after completed trips)
# - POST /reviews/report (report inappropriate reviews)