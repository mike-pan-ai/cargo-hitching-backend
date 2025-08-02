from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import uuid

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    phone = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    trips = db.relationship('Trip', backref='user', lazy=True, cascade='all, delete-orphan')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy=True)
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'phone': self.phone,
            'is_verified': self.is_verified,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Trip(db.Model):
    __tablename__ = 'trips'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    country_from = db.Column(db.String(100), nullable=False)
    country_to = db.Column(db.String(100), nullable=False)
    date = db.Column(db.Date, nullable=False)
    departure_time = db.Column(db.Time)
    rate_per_kg = db.Column(db.Numeric(8, 2), nullable=False)
    available_cargo_space = db.Column(db.Integer, nullable=False)
    description = db.Column(db.Text)
    currency = db.Column(db.String(3), default='EUR')
    contact_info = db.Column(db.Text)
    status = db.Column(db.String(20), default='active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    messages = db.relationship('Message', backref='trip', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'country_from': self.country_from,
            'country_to': self.country_to,
            'date': self.date.isoformat() if self.date else None,
            'departure_time': self.departure_time.strftime('%H:%M') if self.departure_time else None,
            'rate_per_kg': float(self.rate_per_kg) if self.rate_per_kg else None,
            'available_cargo_space': self.available_cargo_space,
            'description': self.description,
            'currency': self.currency,
            'contact_info': self.contact_info,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Message(db.Model):
    __tablename__ = 'messages'

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    recipient_id = db.Column(db.String(36), db.ForeignKey('users.id'), nullable=False)
    trip_id = db.Column(db.String(36), db.ForeignKey('trips.id'))
    message = db.Column(db.Text, nullable=False)
    conversation_id = db.Column(db.String(255), nullable=False)
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'trip_id': self.trip_id,
            'message': self.message,
            'conversation_id': self.conversation_id,
            'read': self.read,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }