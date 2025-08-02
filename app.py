from flask import Flask, jsonify
from flask_cors import CORS
from config import config
from models import db
import os


def create_app():
    """Application factory pattern"""
    app = Flask(__name__)

    # Load configuration
    config_name = os.getenv('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])

    # Initialize extensions
    db.init_app(app)

    # Configure CORS
    CORS(app, origins=app.config['CORS_ORIGINS'])

    # Create tables within application context
    with app.app_context():
        try:
            db.create_all()
            print("✅ Database tables created successfully")
        except Exception as e:
            print(f"⚠️ Database initialization warning: {e}")
            # Continue anyway - tables might already exist

    # Register blueprints
    register_blueprints(app)

    # Register error handlers
    register_error_handlers(app)

    return app


def register_blueprints(app):
    """Register application blueprints"""
    try:
        from routes.auth import auth_bp
        app.register_blueprint(auth_bp, url_prefix='/api/auth')
        print("✅ Auth blueprint registered successfully")
    except ImportError as e:
        print(f"⚠️ Auth blueprint not found: {e}")

    try:
        from routes.trips import trips_bp
        app.register_blueprint(trips_bp, url_prefix='/api/trips')
        print("✅ Trips blueprint registered successfully")
    except ImportError as e:
        print(f"⚠️ Trips blueprint not found: {e}")

    try:
        from routes.users import users_bp
        app.register_blueprint(users_bp, url_prefix='/api/users')
        print("✅ Users blueprint registered successfully")
    except ImportError as e:
        print(f"⚠️ Users blueprint not found: {e}")

    try:
        from routes.messages import messages_bp
        app.register_blueprint(messages_bp, url_prefix='/api/messages')
        print("✅ Messages blueprint registered successfully")
    except ImportError as e:
        print(f"⚠️ Messages blueprint not found: {e}")


def register_error_handlers(app):
    """Register error handlers"""

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Not Found",
            "message": "The requested resource was not found.",
            "endpoints": {
                "auth": "/api/auth",
                "trips": "/api/trips",
                "users": "/api/users",
                "messages": "/api/messages"
            }
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "error": "Internal Server Error",
            "message": "An internal server error occurred."
        }), 500

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({
            "error": "Bad Request",
            "message": "The request could not be understood by the server."
        }), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({
            "error": "Unauthorized",
            "message": "Authentication is required to access this resource."
        }), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({
            "error": "Forbidden",
            "message": "You don't have permission to access this resource."
        }), 403


# Create app instance
app = create_app()


# Health check routes
@app.route('/')
def health_check():
    return jsonify({
        "message": "Cargo Hitching API",
        "status": "healthy",
        "database": "postgresql",
        "version": "2.0"
    })


@app.route('/api')
def api_info():
    return jsonify({
        "message": "Cargo Hitching API",
        "endpoints": {
            "auth": "/api/auth",
            "trips": "/api/trips",
            "users": "/api/users",
            "messages": "/api/messages"
        }
    })


@app.route('/api/health')
def detailed_health():
    try:
        # Test database connection - FIXED FOR SQLALCHEMY 2.0
        from sqlalchemy import text
        db.session.execute(text('SELECT 1'))
        db.session.commit()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"

    return jsonify({
        "status": "healthy",
        "database": db_status,
        "environment": os.getenv('FLASK_ENV', 'development'),
        "endpoints": {
            "auth": "/api/auth - Authentication endpoints",
            "trips": "/api/trips - Trip management",
            "users": "/api/users - User profiles",
            "messages": "/api/messages - Messaging system"
        }
    })


if __name__ == '__main__':
    import os

    # Get port from environment variable (Railway sets this)
    port = int(os.environ.get('PORT', 5000))

    # Set debug based on environment
    debug_mode = os.getenv('FLASK_ENV', 'production') == 'development'

    print(f"🚀 Starting Cargo Hitching API on port {port}...")
    print("📍 Available endpoints:")
    print("   - Health check: /")
    print("   - API info: /api")
    print("   - Detailed health: /api/health")
    print("   - Auth endpoints: /api/auth")
    print("   - Trip endpoints: /api/trips")
    print("   - User endpoints: /api/users")
    print("   - Message endpoints: /api/messages")

    app.run(
        debug=debug_mode,
        host='0.0.0.0',
        port=port
    )