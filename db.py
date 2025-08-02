from extensions import get_database
from datetime import datetime
from bson import ObjectId
from typing import Optional, Dict, List, Any

# Get database instance
db = get_database()

# Collection references
users = db.users
trips = db.trips
negotiations = db.negotiations


class UserModel:
    """User data model with helper methods"""

    @staticmethod
    def create_user(email: str, hashed_password: bytes, **kwargs) -> str:
        """Create a new user and return the user ID"""
        user_data = {
            "email": email.lower().strip(),
            "password": hashed_password,
            "is_verified": False,
            "first_name": kwargs.get('first_name', ''),
            "last_name": kwargs.get('last_name', ''),
            "phone": kwargs.get('phone', ''),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = users.insert_one(user_data)
        return str(result.inserted_id)

    @staticmethod
    def find_by_email(email: str) -> Optional[Dict]:
        """Find user by email"""
        return users.find_one({"email": email.lower().strip()})

    @staticmethod
    def find_by_id(user_id: str) -> Optional[Dict]:
        """Find user by ID"""
        try:
            return users.find_one({"_id": ObjectId(user_id)})
        except Exception:
            return None

    @staticmethod
    def verify_email(email: str) -> bool:
        """Mark user email as verified"""
        result = users.update_one(
            {"email": email.lower().strip()},
            {"$set": {"is_verified": True, "updated_at": datetime.utcnow()}}
        )
        return result.modified_count > 0

    @staticmethod
    def update_user(user_id: str, update_data: Dict) -> bool:
        """Update user data"""
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = users.update_one(
                {"_id": ObjectId(user_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception:
            return False


class TripModel:
    """Trip data model with helper methods"""

    @staticmethod
    def create_trip(user_id: str, trip_data: Dict) -> str:
        """Create a new trip and return the trip ID"""
        trip = {
            "user_id": ObjectId(user_id),
            "country_from": trip_data['country_from'].strip(),
            "country_to": trip_data['country_to'].strip(),
            "date": trip_data['date'],
            "departure_time": trip_data.get('departure_time', ''),
            "rate_per_kg": float(trip_data['rate_per_kg']),
            "available_cargo_space": float(trip_data['available_cargo_space']),
            "original_cargo_space": float(trip_data['available_cargo_space']),
            "currency": trip_data.get('currency', 'USD'),
            "description": trip_data.get('description', ''),
            "contact_info": trip_data.get('contact_info', ''),
            "status": "active",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        result = trips.insert_one(trip)
        return str(result.inserted_id)

    @staticmethod
    def find_by_id(trip_id: str) -> Optional[Dict]:
        """Find trip by ID"""
        try:
            return trips.find_one({"_id": ObjectId(trip_id)})
        except Exception:
            return None

    @staticmethod
    def find_by_user(user_id: str, status: str = None) -> List[Dict]:
        """Find trips by user ID"""
        try:
            query = {"user_id": ObjectId(user_id)}
            if status:
                query["status"] = status
            else:
                # If no specific status requested, exclude deleted trips
                query["status"] = {"$ne": "deleted"}
            return list(trips.find(query).sort("created_at", -1))
        except Exception:
            return []


    @staticmethod
    def search_trips(filters):
        """Search trips with filters, optionally excluding specific user"""
        try:
            # Build MongoDB query
            query = {"status": "active"}  # Only show active trips

            # Handle user exclusion
            exclude_user_id = filters.pop('exclude_user_id', None)
            if exclude_user_id:
                query["user_id"] = {"$ne": ObjectId(exclude_user_id)}
                print(f"DEBUG - MongoDB query excluding user: {exclude_user_id}")
                print(f"DEBUG - Full query: {query}")

            # Handle other filters (your existing code)
            if 'country_from' in filters:
                query["country_from"] = {"$regex": filters['country_from'], "$options": "i"}

            if 'country_to' in filters:
                query["country_to"] = {"$regex": filters['country_to'], "$options": "i"}

            if 'date' in filters:
                query["date"] = filters['date']

            if 'max_rate' in filters:
                try:
                    query["rate_per_kg"] = {"$lte": float(filters['max_rate'])}
                except (ValueError, TypeError):
                    pass

            if 'min_space' in filters:
                try:
                    query["available_cargo_space"] = {"$gte": int(filters['min_space'])}
                except (ValueError, TypeError):
                    pass

            print(f"DEBUG - Final MongoDB query: {query}")

            # Execute search
            results = list(trips.find(query).sort("created_at", -1))
            print(f"DEBUG - MongoDB returned {len(results)} trips")

            return results

        except Exception as e:
            print(f"Error in search_trips: {e}")
            return []

    @staticmethod
    def update_trip(trip_id: str, update_data: Dict) -> bool:
        """Update trip data"""
        try:
            update_data["updated_at"] = datetime.utcnow()
            result = trips.update_one(
                {"_id": ObjectId(trip_id)},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception:
            return False

    @staticmethod
    def delete_trip(trip_id: str) -> bool:
        """Soft delete trip by changing status"""
        try:
            result = trips.update_one(
                {"_id": ObjectId(trip_id)},
                {"$set": {"status": "deleted", "updated_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception:
            return False


def convert_objectid_to_string(doc: Dict) -> Dict:
    """Convert ObjectId fields to strings for JSON serialization"""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    if doc and "user_id" in doc:
        doc["user_id"] = str(doc["user_id"])
    return doc