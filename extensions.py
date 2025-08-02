# extensions.py
from flask_mail import Mail
from flask_cors import CORS
from pymongo import MongoClient
import os

# Initialize extensions
mail = Mail()
cors = CORS()

# Database connection
_client = None
_db = None


def get_db_client():
    """Get MongoDB client (singleton pattern)"""
    global _client
    if _client is None:
        try:
            _client = MongoClient(os.getenv('MONGO_URI'))
            # Test connection
            _client.admin.command('ping')
        except Exception as e:
            print(f"Failed to connect to MongoDB: {e}")
            raise
    return _client


def get_database(db_name=None):
    """Get database instance"""
    global _db
    if _db is None:
        client = get_db_client()
        db_name = db_name or os.getenv('DATABASE_NAME', 'cargo_hitching_app')
        _db = client.get_database(db_name)
    return _db


def init_extensions(app):
    """Initialize all extensions with app"""
    mail.init_app(app)
    cors.init_app(app, origins=app.config['CORS_ORIGINS'])

    # Initialize database connection
    try:
        get_database()
        print("✓ Database connection established")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")
        raise


def create_indexes():
    """Create database indexes for better performance"""
    try:
        db = get_database()

        # User collection indexes
        db.users.create_index("email", unique=True)
        db.users.create_index("is_verified")

        # Trip collection indexes
        db.trips.create_index("user_id")
        db.trips.create_index("country_from")
        db.trips.create_index("country_to")
        db.trips.create_index("date")
        db.trips.create_index("status")
        db.trips.create_index("rate_per_kg")
        db.trips.create_index("available_cargo_space")

        # Compound indexes for common queries
        db.trips.create_index([("country_from", 1), ("country_to", 1)])
        db.trips.create_index([("country_from", 1), ("date", 1)])
        db.trips.create_index([("status", 1), ("date", 1)])

        print("✓ Database indexes created successfully")

    except Exception as e:
        print(f"✗ Error creating database indexes: {e}")


def close_db_connection():
    """Close database connection"""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None