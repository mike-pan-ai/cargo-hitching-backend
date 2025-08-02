import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration class"""

    # Basic Flask config
    SECRET_KEY = os.getenv('JWT_SECRET', 'fallback-secret-key')
    DEBUG = False
    TESTING = False

    # Database config
    MONGO_URI = os.getenv('MONGO_URI')
    DATABASE_NAME = 'cargo_hitching_app'

    # JWT config
    JWT_SECRET = os.getenv('JWT_SECRET')
    JWT_ACCESS_TOKEN_EXPIRES_HOURS = 24
    JWT_EMAIL_VERIFICATION_EXPIRES_HOURS = 48

    # Mail config
    MAIL_SERVER = os.getenv('MAIL_SERVER')
    MAIL_PORT = int(os.getenv('MAIL_PORT', 587))
    MAIL_USERNAME = os.getenv('MAIL_USERNAME')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD')
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_USERNAME')

    # Application config
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file upload
    CORS_ORIGINS = ['http://localhost:3000', 'http://localhost:5173']  # Common dev ports

    @staticmethod
    def validate_config():
        """Validate that all required environment variables are set"""
        required_vars = [
            'MONGO_URI',
            'JWT_SECRET',
            'MAIL_SERVER',
            'MAIL_USERNAME',
            'MAIL_PASSWORD'
        ]

        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

        return True


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    CORS_ORIGINS = ['*']  # Allow all origins in development


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    # Override CORS_ORIGINS with specific production domains
    CORS_ORIGINS = [
        'https://seasonship.com',
        'https://www.seasonship.com',  # With www prefix
        'https://*.vercel.app'         # Vercel preview domains
    ]


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DATABASE_NAME = 'cargo_hitching_app_test'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}