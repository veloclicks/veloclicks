"""
Profile management tools.
Reusable functions for getting and updating user profiles.
"""

import datetime
import logging
from typing import Dict, Any, Optional

from app.models import db, User
from app.profile.training_zones import populate_zones, get_user_zones
from app.models.training_zone import ZoneType

logger = logging.getLogger(__name__)


def get_profile(user_id: int) -> Optional[Dict[str, Any]]:
    """
    Get user profile data.

    Args:
        user_id: ID of the user

    Returns:
        Dictionary containing profile data, or None if user not found
    """
    user = User.query.get(user_id)
    if not user:
        return None

    return {
        'username': user.username,
        'email': user.email,
        'firstname': user.firstname,
        'lastname': user.lastname,
        'sex': user.sex,
        'date_of_birth': user.date_of_birth.isoformat() if user.date_of_birth else None,
        'ftp': user.ftp,
        'max_heart_rate': user.max_heart_rate,
        'resting_heart_rate': user.resting_heart_rate,
        'membership_type': user.membership_type.value if user.membership_type else None,
        'strava_access_token': user.strava_access_token,
        'strava_refresh_token': user.strava_refresh_token,
        'token_expiry_epoch': user.token_expiry_epoch,
        'zones': get_user_zones(user_id)
    }


def update_profile(user_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update user profile data.

    Args:
        user_id: ID of the user
        data: Dictionary containing fields to update

    Returns:
        Dictionary with 'success' and optional 'error' keys
    """
    try:
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'error': 'User not found'}

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
        return {'success': True}

    except ValueError as e:
        db.session.rollback()
        return {'success': False, 'error': f'Invalid date format: {str(e)}'}
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating profile for user {user_id}: {str(e)}")
        return {'success': False, 'error': str(e)}
