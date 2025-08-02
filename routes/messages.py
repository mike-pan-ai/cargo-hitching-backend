# routes/messages.py
from flask import Blueprint, request, jsonify
from bson import ObjectId
from auth_guard import token_required
from db import get_database
from datetime import datetime

messages_bp = Blueprint('messages', __name__)


def get_db():
    """Get database connection"""
    return get_database()


@messages_bp.route('/send', methods=['POST'])
@token_required
def send_message(current_user):
    """Send a new message"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields
        required_fields = ['recipient_id', 'message', 'trip_id']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        # Validate message content
        message_text = data.get('message', '').strip()
        if len(message_text) < 1:
            return jsonify({'error': 'Message cannot be empty'}), 400
        if len(message_text) > 1000:
            return jsonify({'error': 'Message too long (max 1000 characters)'}), 400

        # Get current user info
        db = get_db()
        users_collection = db.users

        if isinstance(current_user, str):
            sender = users_collection.find_one({"email": current_user})
        else:
            sender = current_user

        if not sender:
            return jsonify({'error': 'Sender not found'}), 404

        # Validate recipient exists
        try:
            recipient = users_collection.find_one({"_id": ObjectId(data['recipient_id'])})
            if not recipient:
                return jsonify({'error': 'Recipient not found'}), 404
        except:
            return jsonify({'error': 'Invalid recipient ID'}), 400

        # Prevent self-messaging
        if str(sender['_id']) == str(data['recipient_id']):
            return jsonify({'error': 'Cannot send message to yourself'}), 400

        # Validate trip exists (optional - for trip context)
        trip_id = data.get('trip_id')
        if trip_id:
            try:
                trips_collection = db.trips
                trip = trips_collection.find_one({"_id": ObjectId(trip_id)})
                if not trip:
                    return jsonify({'error': 'Trip not found'}), 404
            except:
                return jsonify({'error': 'Invalid trip ID'}), 400

        # Create message
        messages_collection = db.messages

        message_doc = {
            'sender_id': sender['_id'],
            'recipient_id': ObjectId(data['recipient_id']),
            'trip_id': ObjectId(trip_id) if trip_id else None,
            'message': message_text,
            'created_at': datetime.utcnow(),
            'read': False,
            'conversation_id': generate_conversation_id(str(sender['_id']), data['recipient_id'])
        }

        result = messages_collection.insert_one(message_doc)

        # Return the created message
        created_message = messages_collection.find_one({"_id": result.inserted_id})

        # Convert ObjectIds to strings for JSON response
        message_response = {
            'id': str(created_message['_id']),
            'sender_id': str(created_message['sender_id']),
            'recipient_id': str(created_message['recipient_id']),
            'trip_id': str(created_message['trip_id']) if created_message['trip_id'] else None,
            'message': created_message['message'],
            'created_at': created_message['created_at'].isoformat() + 'Z',
            'read': created_message['read'],
            'conversation_id': created_message['conversation_id'],
            'sender_name': f"{sender.get('firstname', '')} {sender.get('lastname', '')}".strip() or
                           sender.get('email', '').split('@')[0]
        }

        return jsonify({
            'message': 'Message sent successfully',
            'data': message_response
        }), 201

    except Exception as e:
        print(f"Error sending message: {e}")
        return jsonify({'error': 'Failed to send message'}), 500


@messages_bp.route('/conversation/<user_id>', methods=['GET'])
@token_required
def get_conversation(current_user, user_id):
    """Get conversation between current user and another user"""
    try:
        # Get current user info
        db = get_db()
        users_collection = db.users

        if isinstance(current_user, str):
            sender = users_collection.find_one({"email": current_user})
        else:
            sender = current_user

        if not sender:
            return jsonify({'error': 'User not found'}), 404

        # Validate other user exists
        try:
            other_user = users_collection.find_one({"_id": ObjectId(user_id)})
            if not other_user:
                return jsonify({'error': 'User not found'}), 404
        except:
            return jsonify({'error': 'Invalid user ID'}), 400

        # Generate conversation ID
        conversation_id = generate_conversation_id(str(sender['_id']), user_id)

        # Get messages from conversation
        messages_collection = db.messages
        messages = list(messages_collection.find({
            'conversation_id': conversation_id
        }).sort('created_at', 1))  # Oldest first

        # Mark messages as read (where current user is recipient)
        messages_collection.update_many({
            'conversation_id': conversation_id,
            'recipient_id': sender['_id'],
            'read': False
        }, {
            '$set': {'read': True}
        })

        # Convert to response format
        message_list = []
        for msg in messages:
            message_list.append({
                'id': str(msg['_id']),
                'sender_id': str(msg['sender_id']),
                'recipient_id': str(msg['recipient_id']),
                'trip_id': str(msg['trip_id']) if msg['trip_id'] else None,
                'message': msg['message'],
                'created_at': msg['created_at'].isoformat(),
                'read': msg['read'],
                'is_mine': str(msg['sender_id']) == str(sender['_id'])
            })

        return jsonify({
            'conversation_id': conversation_id,
            'messages': message_list,
            'count': len(message_list),
            'other_user': {
                'id': str(other_user['_id']),
                'name': f"{other_user.get('firstname', '')} {other_user.get('lastname', '')}".strip() or
                        other_user.get('email', '').split('@')[0],
                'email': other_user.get('email', '')
            }
        }), 200

    except Exception as e:
        print(f"Error fetching conversation: {e}")
        return jsonify({'error': 'Failed to fetch conversation'}), 500


@messages_bp.route('/conversations', methods=['GET'])
@token_required
def get_conversations(current_user):
    """Get list of all conversations for current user"""
    try:
        # Get current user info
        db = get_db()
        users_collection = db.users

        if isinstance(current_user, str):
            user = users_collection.find_one({"email": current_user})
        else:
            user = current_user

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Get all unique conversations for this user
        messages_collection = db.messages

        # Find all conversations where user is sender or recipient
        conversations = list(messages_collection.aggregate([
            {
                '$match': {
                    '$or': [
                        {'sender_id': user['_id']},
                        {'recipient_id': user['_id']}
                    ]
                }
            },
            {
                '$sort': {'created_at': -1}
            },
            {
                '$group': {
                    '_id': '$conversation_id',
                    'last_message': {'$first': '$message'},
                    'last_message_time': {'$first': '$created_at'},
                    'last_sender_id': {'$first': '$sender_id'},
                    'trip_id': {'$first': '$trip_id'},
                    'sender_id': {'$first': '$sender_id'},
                    'recipient_id': {'$first': '$recipient_id'}
                }
            },
            {
                '$sort': {'last_message_time': -1}
            }
        ]))

        # Get other user info for each conversation
        conversation_list = []
        for conv in conversations:
            # Determine who the "other user" is
            other_user_id = conv['recipient_id'] if conv['sender_id'] == user['_id'] else conv['sender_id']

            # Get other user info
            other_user = users_collection.find_one({"_id": other_user_id})
            if not other_user:
                continue

            # Count unread messages
            unread_count = messages_collection.count_documents({
                'conversation_id': conv['_id'],
                'recipient_id': user['_id'],
                'read': False
            })

            conversation_list.append({
                'conversation_id': conv['_id'],
                'other_user': {
                    'id': str(other_user['_id']),
                    'name': f"{other_user.get('firstname', '')} {other_user.get('lastname', '')}".strip() or
                            other_user.get('email', '').split('@')[0],
                    'email': other_user.get('email', '')
                },
                'last_message': conv['last_message'],
                'last_message_time': conv['last_message_time'].isoformat(),
                'unread_count': unread_count,
                'trip_id': str(conv['trip_id']) if conv['trip_id'] else None
            })

        return jsonify({
            'conversations': conversation_list,
            'count': len(conversation_list)
        }), 200

    except Exception as e:
        print(f"Error fetching conversations: {e}")
        return jsonify({'error': 'Failed to fetch conversations'}), 500


@messages_bp.route('/mark-read', methods=['POST'])
@token_required
def mark_messages_read(current_user):
    """Mark messages as read"""
    try:
        data = request.get_json()

        if not data or 'conversation_id' not in data:
            return jsonify({'error': 'conversation_id is required'}), 400

        # Get current user info
        db = get_db()
        users_collection = db.users

        if isinstance(current_user, str):
            user = users_collection.find_one({"email": current_user})
        else:
            user = current_user

        if not user:
            return jsonify({'error': 'User not found'}), 404

        # Mark messages as read
        messages_collection = db.messages
        result = messages_collection.update_many({
            'conversation_id': data['conversation_id'],
            'recipient_id': user['_id'],
            'read': False
        }, {
            '$set': {'read': True}
        })

        return jsonify({
            'message': 'Messages marked as read',
            'updated_count': result.modified_count
        }), 200

    except Exception as e:
        print(f"Error marking messages as read: {e}")
        return jsonify({'error': 'Failed to mark messages as read'}), 500


def generate_conversation_id(user1_id, user2_id):
    """Generate a consistent conversation ID for two users"""
    # Sort IDs to ensure same conversation ID regardless of who starts the conversation
    ids = sorted([str(user1_id), str(user2_id)])
    return f"{ids[0]}_{ids[1]}"