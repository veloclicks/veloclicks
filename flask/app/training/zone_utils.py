"""
Training zone calculation and management utilities.

Based on Coggan 7-zone power model and standard heart rate zones.
"""

from app.models import db, TrainingZone, User
from app.models.training_zone import ZoneType


# Power zone definitions based on FTP (Coggan 7-zone model + Sweet Spot)
# Format: (name, display_name, min_pct, max_pct, sort_order)
POWER_ZONE_DEFINITIONS = [
    ('z1', 'Z1 - Active Recovery', 0.00, 0.55, 1),
    ('z2', 'Z2 - Endurance', 0.56, 0.75, 2),
    ('z3', 'Z3 - Tempo', 0.76, 0.90, 3),
    ('sweet_spot', 'Sweet Spot', 0.88, 0.94, 4),
    ('z4', 'Z4 - Threshold', 0.91, 1.05, 5),
    ('z5', 'Z5 - VO2 Max', 1.06, 1.20, 6),
    ('z6', 'Z6 - Anaerobic', 1.21, 1.50, 7),
    ('z7', 'Z7 - Neuromuscular', 1.51, 9999.99, 8),  # Open-ended upper limit
]

# Heart rate zone definitions based on max HR
# Format: (name, display_name, min_pct, max_pct, sort_order)
HR_ZONE_DEFINITIONS = [
    ('z1', 'Z1 - Recovery', 0.00, 0.60, 1),
    ('z2', 'Z2 - Aerobic', 0.61, 0.70, 2),
    ('z3', 'Z3 - Tempo', 0.71, 0.80, 3),
    ('z4', 'Z4 - Threshold', 0.81, 0.90, 4),
    ('z5', 'Z5 - Maximum', 0.91, 1.50, 5),  # Upper limit accounts for HR spikes
]


def calculate_zones(baseline_value, zone_definitions):
    """
    Calculate training zones from baseline value and zone definitions.

    Args:
        baseline_value: FTP (watts) for power zones, max HR (bpm) for heart rate zones
        zone_definitions: List of tuples (name, display_name, min_pct, max_pct, sort_order)

    Returns:
        List of zone dictionaries with name, display_name, min, max, sort_order
    """
    if not baseline_value or baseline_value <= 0:
        return []

    zones = []
    for name, display_name, min_pct, max_pct, sort_order in zone_definitions:
        min_value = int(baseline_value * min_pct)
        max_value = int(baseline_value * max_pct)

        zones.append({
            'name': name,
            'display_name': display_name,
            'min': min_value,
            'max': max_value,
            'sort_order': sort_order
        })

    return zones


def populate_zones(user_id, zone_type, baseline_value):
    """
    Populate or update training zones for a specific zone type.

    Args:
        user_id: User ID
        zone_type: ZoneType.POWER or ZoneType.HEART_RATE
        baseline_value: FTP (watts) for power zones, max HR (bpm) for heart rate zones

    Returns:
        Dictionary with count of zones created
    """
    if not baseline_value or baseline_value <= 0:
        return {'error': 'Invalid baseline value'}

    # Delete existing zones of this type for this user
    TrainingZone.query.filter_by(user_id=user_id, type=zone_type).delete()

    # Get zone definitions based on type
    if zone_type == ZoneType.POWER:
        definitions = POWER_ZONE_DEFINITIONS
    elif zone_type == ZoneType.HEART_RATE:
        definitions = HR_ZONE_DEFINITIONS
    else:
        return {'error': 'Invalid zone type'}

    # Calculate zones
    zone_data_list = calculate_zones(baseline_value, definitions)

    # Create zone records
    zones_created = 0
    for zone_data in zone_data_list:
        zone = TrainingZone(
            user_id=user_id,
            type=zone_type,
            name=zone_data['name'],
            display_name=zone_data['display_name'],
            min=zone_data['min'],
            max=zone_data['max'],
            sort_order=zone_data['sort_order']
        )
        db.session.add(zone)
        zones_created += 1

    db.session.commit()

    return {
        'zones_created': zones_created,
        'zone_type': zone_type.value
    }


def get_user_zones(user_id, zone_type=None):
    """
    Get all training zones for a user, optionally filtered by type.

    Args:
        user_id: User ID
        zone_type: Optional ZoneType filter (POWER or HEART_RATE)

    Returns:
        List of zone dictionaries
    """
    query = TrainingZone.query.filter_by(user_id=user_id)

    if zone_type:
        query = query.filter_by(type=zone_type)

    zones = query.order_by(TrainingZone.type, TrainingZone.sort_order).all()

    return [zone.to_dict() for zone in zones]
