from flask import Flask, render_template, request, abort
from flask_socketio import SocketIO, join_room, leave_room, emit
import secrets
import re

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-me!'
socketio = SocketIO(app, cors_allowed_origins="*", logger=True, engineio_logger=True)

rooms = {}  # {room_id: {'messages': [], 'users': set()}}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/chat/<room_id>')
def chat(room_id):
    if not re.match(r'^[A-Z0-9]{6}$', room_id.upper()):
        abort(404)
    return render_template('chat.html', room_id=room_id)

@socketio.on('create_room')
def create_room(data):
    """Create room and auto-join creator"""
    room_id = secrets.token_hex(3).upper()
    rooms[room_id] = {'messages': [], 'users': set()}
    username = data.get('username', 'Creator')
    
    # Auto-join creator to their own room
    join_room(room_id)
    rooms[room_id]['users'].add(request.sid)
    
    link = f"{request.host_url.rstrip('/')}/chat/{room_id}"
    emit('room_created', {'room_id': room_id, 'link': link, 'msg': f'Room {room_id} created! Share: {link}'})

@socketio.on('join')
def on_join(data):
    room_id = data['room'].upper()
    username = data.get('username', 'Anonymous')
    
    # Create room if doesn't exist (for direct joins)
    if room_id not in rooms:
        rooms[room_id] = {'messages': [], 'users': set()}
    
    join_room(room_id)
    rooms[room_id]['users'].add(request.sid)
    
    # Send room status to all
    user_count = len(rooms[room_id]['users'])
    emit('status', {'msg': f'{username} joined. Users: {user_count}'}, room=room_id)
    emit('messages', {'messages': rooms[room_id]['messages']}, room=room_id)

@socketio.on('leave')
def on_leave(data):
    room_id = data['room'].upper()
    if room_id in rooms:
        leave_room(room_id)
        rooms[room_id]['users'].discard(request.sid)
        if not rooms[room_id]['users']:
            del rooms[room_id]
            emit('room_deleted', {'msg': 'Room deleted - no users left!'}, room=room_id)
        else:
            emit('status', {'msg': f'Users left: {len(rooms[room_id]["users"])}'}, room=room_id)

@socketio.on('message')
def handle_message(data):
    room_id = data['room'].upper()
    if room_id in rooms:
        msg = {'user': data['user'], 'text': data['text'], 'time': data['time']}
        rooms[room_id]['messages'].append(msg)
        emit('message', msg, room=room_id)

@socketio.on('disconnect')
def handle_disconnect():
    for room_id in list(rooms.keys()):
        if request.sid in rooms[room_id]['users']:
            rooms[room_id]['users'].discard(request.sid)
            if not rooms[room_id]['users']:
                del rooms[room_id]
            break

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0')
