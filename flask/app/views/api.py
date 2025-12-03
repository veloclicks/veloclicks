from flask import Blueprint
from flask import current_app

from flask import request, jsonify
import jwt

from app.models import db, User
from app.training.zone_utils import populate_zones, get_user_zones
from app.models.training_zone import ZoneType

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

        user = User.query.get(user_id)
        if not user:
            return jsonify({'message': 'User not found'}), 404

        if request.method == 'GET':
            # Debug logging for profile data
            import logging
            logging.debug(f"Profile request for user_id: {user_id}")
            logging.debug(f"User firstname: '{user.firstname}' (type: {type(user.firstname)})")
            logging.debug(f"User lastname: '{user.lastname}' (type: {type(user.lastname)})")

            profile_data = {
                'username': user.username,
                'email': user.email,
                'firstname': user.firstname,
                'lastname': user.lastname,
                'sex': user.sex,
                'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
                'ftp': user.ftp,
                'max_heart_rate': user.max_heart_rate,
                'resting_heart_rate': user.resting_heart_rate,
                'strava_access_token': user.strava_access_token,
                'strava_refresh_token': user.strava_refresh_token,
                'token_expiry_epoch': user.token_expiry_epoch,
                'zones': get_user_zones(user_id)
            }

            print(f"/profile Returning profile data: {profile_data}")
            return jsonify(profile_data), 200

        elif request.method == 'PUT':
            data = request.get_json()

            # Handle FTP changes and regenerate power zones
            if 'ftp' in data and data['ftp']:
                ftp_value = int(data['ftp']) if data['ftp'] else None
                if ftp_value and ftp_value != user.ftp:
                    user.ftp = ftp_value
                    populate_zones(user.id, ZoneType.POWER, user.ftp)

            # Handle max heart rate changes and regenerate heart rate zones
            if 'max_heart_rate' in data and data['max_heart_rate']:
                max_hr_value = int(data['max_heart_rate']) if data['max_heart_rate'] else None
                if max_hr_value and max_hr_value != user.max_heart_rate:
                    user.max_heart_rate = max_hr_value
                    populate_zones(user.id, ZoneType.HEART_RATE, user.max_heart_rate)

            # Handle resting heart rate (no zone regeneration needed)
            if 'resting_heart_rate' in data:
                resting_hr_value = int(data['resting_heart_rate']) if data['resting_heart_rate'] else None
                user.resting_heart_rate = resting_hr_value

            # List of other fields that can be updated
            updatable_fields = ['firstname', 'lastname', 'sex', 'date_of_birth']

            # Update fields that are present in the request
            for field in updatable_fields:
                if field in data:
                    value = data[field]

                    # Special handling for date field
                    if field == 'date_of_birth' and value:
                        value = datetime.datetime.strptime(value, '%Y-%m-%d').date()
                    elif field == 'date_of_birth' and not value:
                        value = None

                    setattr(user, field, value)

            db.session.commit()
            return jsonify({'message': 'Profile updated successfully'}), 200

    except jwt.ExpiredSignatureError:
        return jsonify({'message': 'Token has expired'}), 401
    except (jwt.InvalidTokenError, IndexError):
        return jsonify({'message': 'Invalid token'}), 401
    except ValueError as e:
        return jsonify({'message': f'Invalid date format: {str(e)}'}), 400




