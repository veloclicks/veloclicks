from flask import request, jsonify, current_app
import jwt

from app.profile import profile_bp
from app.profile.tools import get_profile, update_profile


@profile_bp.route('/profile', methods=['GET', 'PUT'])
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
