from flask import Blueprint, request, jsonify
from models import db, Trip, User
from auth_guard import token_required, optional_token
from datetime import datetime, date
import re
from sqlalchemy import and_, or_

trips_bp = Blueprint('trips', __name__)


def validate_trip_data(data):
    """Validate trip creation/update data"""
    errors = []

    # Required fields for creation
    required_fields = ['country_from', 'country_to', 'date', 'rate_per_kg', 'available_cargo_space']
    for field in required_fields:
        if field not in data or not data[field]:
            errors.append(f"{field} is required")

    # Validate date format (DDMMYYYY)
    if 'date' in data and data['date']:
        date_pattern = r'^\d{8}$'  # DDMMYYYY format
        if not re.match(date_pattern, str(data['date'])):
            errors.append("Date must be in DDMMYYYY format")
        else:
            try:
                # Parse DDMMYYYY format
                date_str = str(data['date'])
                day = int(date_str[:2])
                month = int(date_str[2:4])
                year = int(date_str[4:8])

                # Validate date components
                if not (1 <= day <= 31):
                    errors.append("Invalid day in date")
                elif not (1 <= month <= 12):
                    errors.append("Invalid month in date")
                elif year < datetime.now().year:
                    errors.append("Year cannot be in the past")
                else:
                    # Check if date is valid and not in the past
                    trip_date = date(year, month, day)
                    if trip_date < date.today():
                        errors.append("Date cannot be in the past")
            except ValueError:
                errors.append("Invalid date")

    # Validate departure time format (HH:MM)
    if 'departure_time' in data and data['departure_time']:
        time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        if not re.match(time_pattern, data['departure_time']):
            errors.append("Departure time must be in HH:MM format")

    # Validate numeric fields
    if 'rate_per_kg' in data:
        try:
            rate = float(data['rate_per_kg'])
            if rate <= 0:
                errors.append("Rate per kg must be greater than 0")
        except (ValueError, TypeError):
            errors.append("Rate per kg must be a valid number")

    if 'available_cargo_space' in data:
        try:
            space = int(data['available_cargo_space'])
            if space <= 0:
                errors.append("Available cargo space must be greater than 0")
        except (ValueError, TypeError):
            errors.append("Available cargo space must be a valid number")

    # Validate string lengths
    string_fields = {
        'country_from': 100,
        'country_to': 100,
        'description': 1000,
        'currency': 3,
        'contact_info': 500
    }

    for field, max_length in string_fields.items():
        if field in data and data[field] and len(str(data[field])) > max_length:
            errors.append(f"{field} must be less than {max_length} characters")

    return len(errors) == 0, errors


def parse_date_from_ddmmyyyy(date_str):
    """Convert DDMMYYYY string to date object"""
    try:
        date_str = str(date_str)
        day = int(date_str[:2])
        month = int(date_str[2:4])
        year = int(date_str[4:8])
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


@trips_bp.route('/add', methods=['POST'])
@token_required
def add_trip(current_user):
    """Create a new trip"""
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate trip data
        is_valid, validation_errors = validate_trip_data(data)
        if not is_valid:
            return jsonify({"error": "Validation failed", "details": validation_errors}), 400

        # Parse date
        trip_date = parse_date_from_ddmmyyyy(data['date'])
        if not trip_date:
            return jsonify({"error": "Invalid date format"}), 400

        # Parse departure time if provided
        departure_time = None
        if data.get('departure_time'):
            try:
                time_parts = data['departure_time'].split(':')
                departure_time = datetime.strptime(data['departure_time'], '%H:%M').time()
            except ValueError:
                return jsonify({"error": "Invalid departure time format"}), 400

        # Create trip
        new_trip = Trip(
            user_id=current_user.id,
            country_from=data['country_from'],
            country_to=data['country_to'],
            date=trip_date,
            departure_time=departure_time,
            rate_per_kg=float(data['rate_per_kg']),
            available_cargo_space=int(data['available_cargo_space']),
            description=data.get('description', ''),
            currency=data.get('currency', 'EUR'),
            contact_info=data.get('contact_info', ''),
            status='active'
        )

        db.session.add(new_trip)
        db.session.commit()

        return jsonify({
            "message": "Trip created successfully",
            "trip_id": new_trip.id,
            "trip": new_trip.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error creating trip: {e}")
        return jsonify({"error": "Failed to create trip"}), 500


@trips_bp.route('/search', methods=['GET'])
@optional_token
def search_trips(current_user):
    """Search for trips with optional filters - excludes current user's own trips"""
    try:
        # Build query
        query = Trip.query.filter(Trip.status == 'active')

        # Exclude current user's trips if user is logged in
        if current_user:
            query = query.filter(Trip.user_id != current_user.id)

        # Apply filters
        country_from = request.args.get('country_from')
        if country_from:
            query = query.filter(Trip.country_from.ilike(f'%{country_from}%'))

        country_to = request.args.get('country_to')
        if country_to:
            query = query.filter(Trip.country_to.ilike(f'%{country_to}%'))

        date_filter = request.args.get('date')
        if date_filter:
            trip_date = parse_date_from_ddmmyyyy(date_filter)
            if trip_date:
                query = query.filter(Trip.date == trip_date)

        max_rate = request.args.get('max_rate')
        if max_rate:
            try:
                query = query.filter(Trip.rate_per_kg <= float(max_rate))
            except ValueError:
                pass

        min_space = request.args.get('min_space')
        if min_space:
            try:
                query = query.filter(Trip.available_cargo_space >= int(min_space))
            except ValueError:
                pass

        # Execute query and get results
        trips = query.order_by(Trip.created_at.desc()).all()

        # Convert to dict and add user info
        trips_list = []
        for trip in trips:
            trip_dict = trip.to_dict()
            # Add user name for display
            user = User.query.get(trip.user_id)
            if user:
                trip_dict['user_name'] = f"{user.first_name} {user.last_name}".strip() or user.email.split('@')[0]
            trips_list.append(trip_dict)

        return jsonify(trips_list), 200

    except Exception as e:
        print(f"Error searching trips: {e}")
        return jsonify({"error": "Failed to search trips"}), 500


@trips_bp.route('/my-trips', methods=['GET'])
@token_required
def get_my_trips(current_user):
    """Get current user's trips"""
    try:
        status_filter = request.args.get('status', 'all')

        query = Trip.query.filter_by(user_id=current_user.id)

        if status_filter != 'all':
            query = query.filter_by(status=status_filter)

        trips = query.order_by(Trip.created_at.desc()).all()
        trips_list = [trip.to_dict() for trip in trips]

        return jsonify({
            "trips": trips_list,
            "count": len(trips_list)
        }), 200

    except Exception as e:
        print(f"Error getting user trips: {e}")
        return jsonify({"error": "Failed to get trips"}), 500


@trips_bp.route('/<trip_id>', methods=['GET'])
def get_trip(trip_id):
    """Get specific trip by ID"""
    try:
        trip = Trip.query.get(trip_id)

        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        trip_dict = trip.to_dict()

        # Add user info
        user = User.query.get(trip.user_id)
        if user:
            trip_dict['user_name'] = f"{user.first_name} {user.last_name}".strip() or user.email.split('@')[0]
            trip_dict['user_email'] = user.email

        return jsonify(trip_dict), 200

    except Exception as e:
        print(f"Error getting trip: {e}")
        return jsonify({"error": "Failed to get trip"}), 500


@trips_bp.route('/user/<user_id>', methods=['GET'])
def get_user_trips(user_id):
    """Get trips by specific user (for public profile)"""
    try:
        # Verify user exists
        user = User.query.get(user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        # Get user's active trips
        trips = Trip.query.filter_by(
            user_id=user_id,
            status='active'
        ).order_by(Trip.created_at.desc()).limit(10).all()

        trips_list = [trip.to_dict() for trip in trips]

        return jsonify(trips_list), 200

    except Exception as e:
        print(f"Error getting user trips: {e}")
        return jsonify({"error": "Failed to get user trips"}), 500


@trips_bp.route('/<trip_id>/update', methods=['PUT'])
@token_required
def update_trip(current_user, trip_id):
    """Update a trip"""
    try:
        trip = Trip.query.get(trip_id)

        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        if trip.user_id != current_user.id:
            return jsonify({"error": "Unauthorized - not your trip"}), 403

        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Update allowed fields
        updatable_fields = [
            'country_from', 'country_to', 'date', 'rate_per_kg',
            'available_cargo_space', 'description', 'currency',
            'contact_info', 'departure_time', 'status'
        ]

        for field in updatable_fields:
            if field in data:
                if field == 'date' and data[field]:
                    trip_date = parse_date_from_ddmmyyyy(data[field])
                    if trip_date:
                        trip.date = trip_date
                elif field == 'departure_time' and data[field]:
                    try:
                        trip.departure_time = datetime.strptime(data[field], '%H:%M').time()
                    except ValueError:
                        return jsonify({"error": "Invalid departure time format"}), 400
                else:
                    setattr(trip, field, data[field])

        db.session.commit()

        return jsonify({
            "message": "Trip updated successfully",
            "trip": trip.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error updating trip: {e}")
        return jsonify({"error": "Failed to update trip"}), 500


@trips_bp.route('/<trip_id>/delete', methods=['DELETE'])
@token_required
def delete_trip(current_user, trip_id):
    """Delete a trip"""
    try:
        trip = Trip.query.get(trip_id)

        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        if trip.user_id != current_user.id:
            return jsonify({"error": "Unauthorized - not your trip"}), 403

        db.session.delete(trip)
        db.session.commit()

        return jsonify({"message": "Trip deleted successfully"}), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error deleting trip: {e}")
        return jsonify({"error": "Failed to delete trip"}), 500


@trips_bp.route('/stats', methods=['GET'])
@token_required
def get_trip_stats(current_user):
    """Get trip statistics for current user"""
    try:
        total_trips = Trip.query.filter_by(user_id=current_user.id).count()
        active_trips = Trip.query.filter_by(user_id=current_user.id, status='active').count()

        return jsonify({
            "total_trips": total_trips,
            "active_trips": active_trips,
            "completed_trips": total_trips - active_trips
        }), 200

    except Exception as e:
        print(f"Error getting trip stats: {e}")
        return jsonify({"error": "Failed to get trip statistics"}), 500


@trips_bp.route('', methods=['GET'])
def get_all_trips():
    """Get all active trips"""
    try:
        # Your existing search logic (copy from search_trips function)
        # Or call the same function that /search uses
        return search_trips()  # Reuse your search logic
    except Exception as e:
        return jsonify({"error": str(e)}), 500