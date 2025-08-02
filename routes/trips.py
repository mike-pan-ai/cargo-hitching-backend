from flask import Blueprint, request, jsonify
from db import TripModel, convert_objectid_to_string
from auth_guard import token_required, optional_token
from datetime import datetime
import re

trips_bp = Blueprint('trips', __name__)


def validate_date(date_str):
    """Validate date in DDMMYYYY format"""
    try:
        if len(date_str) != 8 or not date_str.isdigit():
            return False, "Date must be in DDMMYYYY format"

        day = int(date_str[:2])
        month = int(date_str[2:4])
        year = int(date_str[4:])

        # Basic validation
        if month < 1 or month > 12:
            return False, "Invalid month"
        if day < 1 or day > 31:
            return False, "Invalid day"
        if year < datetime.now().year:
            return False, "Date cannot be in the past"

        # Create datetime object to validate the date
        trip_date = datetime(year, month, day)
        if trip_date < datetime.now():
            return False, "Date cannot be in the past"

        return True, "Valid date"

    except ValueError:
        return False, "Invalid date format"


def validate_trip_data(data):
    """Validate trip creation data"""
    errors = []

    # Required fields
    required_fields = ['country_from', 'country_to', 'date', 'rate_per_kg', 'available_cargo_space']
    for field in required_fields:
        if not data.get(field):
            errors.append(f"{field} is required")

    if errors:
        return False, errors

    # Validate countries
    country_from = data.get('country_from', '').strip()
    country_to = data.get('country_to', '').strip()

    if len(country_from) < 2:
        errors.append("Country from must be at least 2 characters")
    if len(country_to) < 2:
        errors.append("Country to must be at least 2 characters")
    if country_from.lower() == country_to.lower():
        errors.append("Departure and destination countries cannot be the same")

    # Validate date
    date_valid, date_msg = validate_date(data.get('date', ''))
    if not date_valid:
        errors.append(date_msg)

    # Validate numeric fields
    try:
        rate_per_kg = float(data.get('rate_per_kg', 0))
        if rate_per_kg <= 0:
            errors.append("Rate per kg must be greater than 0")
    except (ValueError, TypeError):
        errors.append("Rate per kg must be a valid number")

    try:
        cargo_space = float(data.get('available_cargo_space', 0))
        if cargo_space <= 0:
            errors.append("Available cargo space must be greater than 0")
        if cargo_space > 10000:  # Reasonable limit
            errors.append("Available cargo space seems unreasonably large")
    except (ValueError, TypeError):
        errors.append("Available cargo space must be a valid number")

    # Validate departure time if provided
    departure_time = data.get('departure_time', '').strip()
    if departure_time:
        time_pattern = r'^([01]?[0-9]|2[0-3]):[0-5][0-9]$'
        if not re.match(time_pattern, departure_time):
            errors.append("Departure time must be in HH:MM format")

    return len(errors) == 0, errors


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

        # Create trip
        trip_id = TripModel.create_trip(str(current_user['_id']), data)

        # Get the created trip
        trip = TripModel.find_by_id(trip_id)
        trip = convert_objectid_to_string(trip)

        return jsonify({
            "message": "Trip created successfully",
            "trip_id": trip_id,
            "trip": trip
        }), 201

    except Exception as e:
        print(f"Error creating trip: {e}")
        return jsonify({"error": "Failed to create trip"}), 500


@trips_bp.route('/search', methods=['GET'])
@optional_token
def search_trips(current_user):
    """Search for trips with optional filters - excludes current user's own trips"""
    try:
        filters = {
            'country_from': request.args.get('country_from'),
            'country_to': request.args.get('country_to'),
            'date': request.args.get('date'),
            'max_rate': request.args.get('max_rate'),
            'min_space': request.args.get('min_space')
        }

        # Remove None values
        filters = {k: v for k, v in filters.items() if v is not None}

        # Get trips
        trips_list = TripModel.search_trips(filters)

        # Convert ObjectIds to strings
        for trip in trips_list:
            trip = convert_objectid_to_string(trip)

        # IMPORTANT: Filter out current user's own trips on backend
        if current_user:
            current_user_id = str(current_user['_id'])
            trips_list = [trip for trip in trips_list if str(trip.get('user_id', '')) != current_user_id]

        return jsonify({
            "trips": trips_list,
            "count": len(trips_list),
            "filters_applied": filters
        }), 200

    except Exception as e:
        print(f"Error searching trips: {e}")
        return jsonify({"error": "Failed to search trips"}), 500


@trips_bp.route('/my-trips', methods=['GET'])
@token_required
def get_my_trips(current_user):
    """Get current user's trips - exclude deleted trips"""
    try:
        status = request.args.get('status')  # Optional status filter

        trips_list = TripModel.find_by_user(str(current_user['_id']), status)

        # Filter out deleted trips from user's view
        trips_list = [trip for trip in trips_list if trip.get('status') != 'deleted']

        # Convert ObjectIds to strings
        for trip in trips_list:
            trip = convert_objectid_to_string(trip)

        return jsonify({
            "trips": trips_list,
            "count": len(trips_list)
        }), 200

    except Exception as e:
        print(f"Error fetching user trips: {e}")
        return jsonify({"error": "Failed to fetch trips"}), 500


# NEW ROUTE: Get trips by specific user ID (for public profiles)
@trips_bp.route('/user/<user_id>', methods=['GET'])
def get_user_trips(user_id):
    """Get trips posted by a specific user (for their public profile)"""
    try:
        # Only return active trips for public viewing
        trips_list = TripModel.find_by_user(user_id, status='active')

        # Limit to last 10 trips for performance
        trips_list = trips_list[:10]

        # Convert ObjectIds to strings
        for trip in trips_list:
            trip = convert_objectid_to_string(trip)

        return jsonify(trips_list), 200  # Returns array directly

    except Exception as e:
        print(f"Error fetching user trips: {e}")
        return jsonify({"error": "Failed to fetch user trips"}), 500


@trips_bp.route('/<trip_id>', methods=['GET'])
@optional_token
def get_trip(current_user, trip_id):
    """Get a specific trip by ID"""
    try:
        trip = TripModel.find_by_id(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        # Check if trip is active or if user is the owner
        if trip['status'] != 'active':
            if not current_user or str(trip['user_id']) != str(current_user['_id']):
                return jsonify({"error": "Trip not found"}), 404

        trip = convert_objectid_to_string(trip)

        return jsonify({"trip": trip}), 200

    except Exception as e:
        print(f"Error fetching trip: {e}")
        return jsonify({"error": "Failed to fetch trip"}), 500


@trips_bp.route('/<trip_id>/update', methods=['PUT'])
@token_required
def update_trip(current_user, trip_id):
    """Update a trip (only by owner)"""
    try:
        # Find trip and verify ownership
        trip = TripModel.find_by_id(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        if str(trip['user_id']) != str(current_user['_id']):
            return jsonify({"error": "Unauthorized to update this trip"}), 403

        data = request.json
        if not data:
            return jsonify({"error": "No data provided"}), 400

        # Validate updateable fields
        updatable_fields = [
            'country_from', 'country_to', 'date', 'departure_time',
            'rate_per_kg', 'available_cargo_space', 'currency',
            'description', 'contact_info', 'status'
        ]

        update_data = {}
        for field in updatable_fields:
            if field in data:
                update_data[field] = data[field]

        if not update_data:
            return jsonify({"error": "No valid fields to update"}), 400

        # Validate specific fields if they're being updated
        if 'date' in update_data:
            date_valid, date_msg = validate_date(update_data['date'])
            if not date_valid:
                return jsonify({"error": date_msg}), 400

        if 'rate_per_kg' in update_data:
            try:
                rate = float(update_data['rate_per_kg'])
                if rate <= 0:
                    return jsonify({"error": "Rate must be greater than 0"}), 400
                update_data['rate_per_kg'] = rate
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid rate format"}), 400

        if 'available_cargo_space' in update_data:
            try:
                space = float(update_data['available_cargo_space'])
                if space <= 0:
                    return jsonify({"error": "Cargo space must be greater than 0"}), 400
                update_data['available_cargo_space'] = space
            except (ValueError, TypeError):
                return jsonify({"error": "Invalid cargo space format"}), 400

        # Update trip
        success = TripModel.update_trip(trip_id, update_data)
        if not success:
            return jsonify({"error": "Failed to update trip"}), 500

        return jsonify({"message": "Trip updated successfully"}), 200

    except Exception as e:
        print(f"Error updating trip: {e}")
        return jsonify({"error": "Failed to update trip"}), 500


@trips_bp.route('/<trip_id>/delete', methods=['DELETE'])
@token_required
def delete_trip(current_user, trip_id):
    """Delete a trip (only by owner)"""
    try:
        # Find trip and verify ownership
        trip = TripModel.find_by_id(trip_id)
        if not trip:
            return jsonify({"error": "Trip not found"}), 404

        if str(trip['user_id']) != str(current_user['_id']):
            return jsonify({"error": "Unauthorized to delete this trip"}), 403

        # Soft delete the trip
        success = TripModel.delete_trip(trip_id)
        if not success:
            return jsonify({"error": "Failed to delete trip"}), 500

        return jsonify({"message": "Trip deleted successfully"}), 200

    except Exception as e:
        print(f"Error deleting trip: {e}")
        return jsonify({"error": "Failed to delete trip"}), 500


@trips_bp.route('/stats', methods=['GET'])
@token_required
def get_trip_stats(current_user):
    """Get trip statistics for the current user"""
    try:
        user_id = str(current_user['_id'])

        # Get all user trips (excluding deleted ones)
        all_trips = TripModel.find_by_user(user_id)
        all_trips = [trip for trip in all_trips if trip.get('status') != 'deleted']

        # Calculate statistics
        stats = {
            'total_trips': len(all_trips),
            'active_trips': len([t for t in all_trips if t['status'] == 'active']),
            'completed_trips': len([t for t in all_trips if t['status'] == 'completed']),
            'cancelled_trips': len([t for t in all_trips if t['status'] == 'cancelled']),
            'total_cargo_space_offered': sum(
                t.get('original_cargo_space', t.get('available_cargo_space', 0)) for t in all_trips),
            'average_rate': sum(t['rate_per_kg'] for t in all_trips) / len(all_trips) if all_trips else 0
        }

        return jsonify({"stats": stats}), 200

    except Exception as e:
        print(f"Error calculating stats: {e}")
        return jsonify({"error": "Failed to calculate statistics"}), 500
