from flask import Flask, jsonify
from config import config
from extensions import init_extensions, create_indexes
import os
from flask_cors import CORS
import os
from dotenv import load_dotenv

load_dotenv()

def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)

    # Load configuration
    app.config.from_object(config[config_name])

    # Validate configuration
    try:
        config[config_name].validate_config()
    except ValueError as e:
        print(f"Configuration error: {e}")
        raise

    # Initialize extensions
    init_extensions(app)

    # Register blueprints
    register_blueprints(app)

    # Create database indexes
    with app.app_context():
        create_indexes()

    # Register error handlers
    register_error_handlers(app)

    CORS(app, origins=[
        "http://localhost:3000",  # Development
        "https://yourdomain.com",  # Replace with your actual domain
        "https://www.yourdomain.com",  # With www
        "https://*.vercel.app"  # Vercel preview domains
    ])

    return app


def register_blueprints(app):
    """Register all blueprints"""
    # Existing blueprints
    from routes.auth import auth_bp
    from routes.trips import trips_bp

    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(trips_bp, url_prefix='/api/trips')

    # NEW BLUEPRINTS for public profiles
    try:
        from routes.users import users_bp
        app.register_blueprint(users_bp, url_prefix='/api/users')
        print("✅ Users blueprint registered successfully")
    except ImportError as e:
        print(f"⚠️ Users blueprint not found: {e}")

    try:
        from routes.reviews import reviews_bp
        app.register_blueprint(reviews_bp, url_prefix='/api/reviews')
        print("✅ Reviews blueprint registered successfully")
    except ImportError as e:
        print(f"⚠️ Reviews blueprint not found: {e}")

    try:
        from routes.messages import messages_bp
        app.register_blueprint(messages_bp, url_prefix='/api/messages')
        print("✅ Messages blueprint registered successfully")
    except ImportError as e:
        print(f"⚠️ Messages blueprint not found: {e}")

    # Add a simple health check route
    @app.route('/')
    def health_check():
        return jsonify({
            "message": "Cargo Hitching API is running!",
            "status": "healthy",
            "version": "1.0.0"
        })

    @app.route('/api')
    def api_info():
        return jsonify({
            "message": "Cargo Hitching API",
            "endpoints": {
                "auth": "/api/auth",
                "trips": "/api/trips",
                "users": "/api/users",
                "reviews": "/api/reviews",
                "messages": "/api/messages"
        }
        })

    @app.route('/api/health')
    def detailed_health():
        """Detailed health check with all available endpoints"""
        return jsonify({
            "message": "API is working",
            "status": "healthy",
            "endpoints": [
                "POST /api/auth/register",
                "POST /api/auth/login",
                "GET  /api/auth/me",
                "GET  /api/trips/search",
                "POST /api/trips/add",
                "GET  /api/trips/my-trips",
                "GET  /api/users/profile/<user_id>",
                "PUT  /api/users/profile",
                "GET  /api/reviews/user/<user_id>",
                "POST /api/reviews/add"
            ]
        }), 200


def register_error_handlers(app):
    """Register error handlers"""

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Not Found",
            "message": "The requested resource was not found on this server.",
            "available_endpoints": {
                "health": "/",
                "api_info": "/api",
                "detailed_health": "/api/health",
                "auth": "/api/auth",
                "trips": "/api/trips",
                "users": "/api/users",
                "reviews": "/api/reviews"
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

if __name__ == '__main__':
    print("🚀 Starting Cargo Hitching API...")
    print("📍 Available endpoints:")
    print("   - Health check: http://localhost:5000/")
    print("   - API info: http://localhost:5000/api")
    print("   - Detailed health: http://localhost:5000/api/health")
    print("   - Auth endpoints: http://localhost:5000/api/auth")
    print("   - Trip endpoints: http://localhost:5000/api/trips")
    print("   - User endpoints: http://localhost:5000/api/users")
    print("   - Review endpoints: http://localhost:5000/api/reviews")
    print("🌍 Frontend: http://localhost:3000")
    print("🔧 Backend:  http://localhost:5000")

    app.run(
        debug=True,
        host='0.0.0.0',
        port=5000
    )