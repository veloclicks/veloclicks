from flask import Blueprint
from flask import current_app

from flask import request, jsonify
import jwt

from app.models import db, User
from app.profile.tools import get_profile, update_profile

import datetime


api_bp = Blueprint('api', __name__, url_prefix='/api')


# Registration endpoint
@api_bp.route('/register', methods=['POST'])
def register():
    print('/register api called')
    data = request.get_json()
    print(f"/register for user: {data['username']}, {data['email']}")

    # Debug log the specific fields we're looking for
    print(f"firstname field: '{data.get('firstname')}' (type: {type(data.get('firstname'))})")
    print(f"lastname field: '{data.get('lastname')}' (type: {type(data.get('lastname'))})")
    
    # Check if user already exists
    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already exists'}), 400
    
    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already in use'}), 400
    
    # Create new user
    user = User(
        username=data['username'],
        email=data['email'],
        firstname=data['firstname'],
        lastname=data['lastname']
    )
    user.set_password(data['password'])

    # Debug log the user object before saving
    print(f"Created user object - firstname: '{user.firstname}', lastname: '{user.lastname}'")

    db.session.add(user)
    db.session.commit()

    # Debug log after saving
    print(f"User saved to database with ID: {user.id}")
    print(f"Saved user - firstname: '{user.firstname}', lastname: '{user.lastname}'")
    
    return jsonify({'message': 'User created successfully'}), 201



# Login endpoint
@api_bp.route('/login', methods=['POST'])
def login():
    
    data = request.get_json()
    print('/login for user \n', data['username'])
    
    # Find user by username
    user = User.query.filter_by(username=data['username']).first()
    
    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid username or password'}), 401
    
    # Generate JWT token
    token = jwt.encode({
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, current_app.config['SECRET_KEY'], algorithm='HS256')
    
    return jsonify({'token': token}), 200


# User profile endpoint - supports both GET and PUT
@api_bp.route('/profile', methods=['GET', 'PUT'])
def profile():
    auth_header = request.headers.get('Authorization')

    if not auth_header:
        return jsonify({'message': 'Token is missing'}), 401

    try:
        token = auth_header.split(' ')[1]
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload['user_id']

        if request.method == 'GET':
            profile_data = get_profile(user_id)
            if not profile_data:
                return jsonify({'message': 'User not found'}), 404

            print(f"/profile Returning profile data: {profile_data}")
            return jsonify(profile_data), 200

        elif request.method == 'PUT':
            data = request.get_json()
            result = update_profile(user_id, data)

            if result['success']:
                return jsonify({'message': 'Profile updated successfully'}), 200
            else:
                return jsonify({'error': result['error']}), 400

    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except (jwt.InvalidTokenError, IndexError):
        return jsonify({'message': 'Invalid token'}), 401
