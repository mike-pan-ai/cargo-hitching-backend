from flask import Blueprint, request, jsonify
from models import db, Message, User, Trip
from auth_guard import token_required
from datetime import datetime
from sqlalchemy import or_, and_, desc

messages_bp = Blueprint('messages', __name__)


def generate_conversation_id(user1_id, user2_id):
    """Generate a consistent conversation ID for two users"""
    # Sort IDs to ensure same conversation ID regardless of who starts the conversation
    ids = sorted([str(user1_id), str(user2_id)])
    return f"{ids[0]}_{ids[1]}"


@messages_bp.route('/send', methods=['POST'])
@token_required
def send_message(current_user):
    """Send a new message"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Validate required fields - trip_id is optional
        required_fields = ['recipient_id', 'message']
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} is required'}), 400

        # Validate message content
        message_text = data.get('message', '').strip()
        if len(message_text) < 1:
            return jsonify({'error': 'Message cannot be empty'}), 400
        if len(message_text) > 1000:
            return jsonify({'error': 'Message too long (max 1000 characters)'}), 400

        # Verify recipient exists
        recipient = User.query.get(data['recipient_id'])
        if not recipient:
            return jsonify({'error': 'Recipient not found'}), 404

        # Prevent self-messaging
        if str(current_user.id) == str(data['recipient_id']):
            return jsonify({'error': 'Cannot send message to yourself'}), 400

        # Validate trip exists (optional - for trip context)
        trip_id = data.get('trip_id')
        if trip_id:
            trip = Trip.query.get(trip_id)
            if not trip:
                return jsonify({'error': 'Trip not found'}), 404

        # Create message
        new_message = Message(
            sender_id=current_user.id,
            recipient_id=data['recipient_id'],
            trip_id=trip_id,
            message=message_text,
            conversation_id=generate_conversation_id(current_user.id, data['recipient_id']),
            read=False
        )

        db.session.add(new_message)
        db.session.commit()

        # Return the created message
        message_response = new_message.to_dict()
        message_response['is_mine'] = True

        return jsonify({
            'message': 'Message sent successfully',
            'message_data': message_response
        }), 201

    except Exception as e:
        db.session.rollback()
        print(f"Error sending message: {e}")
        return jsonify({'error': 'Failed to send message'}), 500


@messages_bp.route('/conversation/<user_id>', methods=['GET'])
@token_required
def get_conversation(current_user, user_id):
    """Get conversation between current user and specified user"""
    try:
        # Verify other user exists
        other_user = User.query.get(user_id)
        if not other_user:
            return jsonify({'error': 'User not found'}), 404

        # Generate conversation ID
        conversation_id = generate_conversation_id(current_user.id, user_id)

        # Get all messages in this conversation
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.created_at.asc()).all()

        # Convert messages to dict and add is_mine flag
        messages_list = []
        for message in messages:
            message_dict = message.to_dict()
            message_dict['is_mine'] = message.sender_id == current_user.id
            messages_list.append(message_dict)

        # Mark messages as read (messages sent TO current user)
        unread_messages = Message.query.filter_by(
            conversation_id=conversation_id,
            recipient_id=current_user.id,
            read=False
        ).all()

        for msg in unread_messages:
            msg.read = True

        if unread_messages:
            db.session.commit()

        return jsonify({
            'messages': messages_list,
            'other_user': {
                'id': other_user.id,
                'name': f"{other_user.first_name} {other_user.last_name}".strip() or other_user.email.split('@')[0],
                'email': other_user.email
            },
            'conversation_id': conversation_id
        }), 200

    except Exception as e:
        print(f"Error getting conversation: {e}")
        return jsonify({'error': 'Failed to get conversation'}), 500


@messages_bp.route('/conversations', methods=['GET'])
@token_required
def get_conversations(current_user):
    """Get list of all conversations for current user"""
    try:
        # Get all unique conversation IDs where user is involved
        sent_conversations = db.session.query(Message.conversation_id).filter_by(
            sender_id=current_user.id
        ).distinct().subquery()

        received_conversations = db.session.query(Message.conversation_id).filter_by(
            recipient_id=current_user.id
        ).distinct().subquery()

        # Get the latest message from each conversation
        from sqlalchemy import text
        conversations_query = db.session.execute(text("""
            SELECT DISTINCT conversation_id,
                   (SELECT message FROM messages m2 
                    WHERE m2.conversation_id = m1.conversation_id 
                    ORDER BY m2.created_at DESC LIMIT 1) as last_message,
                   (SELECT created_at FROM messages m3 
                    WHERE m3.conversation_id = m1.conversation_id 
                    ORDER BY m3.created_at DESC LIMIT 1) as last_message_time,
                   (SELECT sender_id FROM messages m4 
                    WHERE m4.conversation_id = m1.conversation_id 
                    ORDER BY m4.created_at DESC LIMIT 1) as last_sender_id
            FROM messages m1 
            WHERE (sender_id = :user_id OR recipient_id = :user_id)
            ORDER BY last_message_time DESC
        """), {'user_id': current_user.id})

        conversation_list = []
        for conv in conversations_query:
            # Determine who the "other user" is
            conv_parts = conv.conversation_id.split('_')
            other_user_id = conv_parts[1] if conv_parts[0] == current_user.id else conv_parts[0]

            # Get other user info
            other_user = User.query.get(other_user_id)
            if not other_user:
                continue

            # Count unread messages
            unread_count = Message.query.filter_by(
                conversation_id=conv.conversation_id,
                recipient_id=current_user.id,
                read=False
            ).count()

            conversation_list.append({
                'conversation_id': conv.conversation_id,
                'other_user': {
                    'id': other_user.id,
                    'name': f"{other_user.first_name} {other_user.last_name}".strip() or other_user.email.split('@')[0],
                    'email': other_user.email
                },
                'last_message': conv.last_message,
                'last_message_time': conv.last_message_time.isoformat() if conv.last_message_time else None,
                'unread_count': unread_count,
                'is_last_message_mine': conv.last_sender_id == current_user.id
            })

        return jsonify({
            'conversations': conversation_list,
            'total_conversations': len(conversation_list)
        }), 200

    except Exception as e:
        print(f"Error getting conversations: {e}")
        return jsonify({'error': 'Failed to get conversations'}), 500


@messages_bp.route('/mark-read', methods=['POST'])
@token_required
def mark_messages_as_read(current_user):
    """Mark messages as read"""
    try:
        data = request.get_json()
        conversation_id = data.get('conversation_id')

        if not conversation_id:
            return jsonify({'error': 'conversation_id is required'}), 400

        # Mark all unread messages in this conversation as read
        unread_messages = Message.query.filter_by(
            conversation_id=conversation_id,
            recipient_id=current_user.id,
            read=False
        ).all()

        for message in unread_messages:
            message.read = True

        db.session.commit()

        return jsonify({
            'message': 'Messages marked as read',
            'updated_count': len(unread_messages)
        }), 200

    except Exception as e:
        db.session.rollback()
        print(f"Error marking messages as read: {e}")
        return jsonify({'error': 'Failed to mark messages as read'}), 500


@messages_bp.route('/<user_id>', methods=['GET'])
@token_required
def get_messages_with_user(current_user, user_id):
    """Alternative endpoint - same as /conversation/<user_id>"""
    return get_conversation(current_user, user_id)