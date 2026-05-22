from flask import request, jsonify, g

from app.profile import profile_bp
from app.profile.tools import get_profile, update_profile
from app.common.auth import require_auth


@profile_bp.route('/profile', methods=['GET', 'PUT'])
@require_auth
def profile():
    user_id = g.user_id

    if request.method == 'GET':
        profile_data = get_profile(user_id)
        if not profile_data:
            return jsonify({'message': 'User not found'}), 404
        return jsonify(profile_data), 200

    data = request.get_json()
    result = update_profile(user_id, data)
    if result['success']:
        return jsonify({'message': 'Profile updated successfully'}), 200
    return jsonify({'error': result['error']}), 400
