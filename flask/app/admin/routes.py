from flask import request, jsonify
from dateutil import parser

from app.admin import admin_bp
from app.models import db, User, Activity


# IMPORTANT: leave the root route to the Elastic Beanstalk Load Balancer health check
@admin_bp.route('/', methods=['GET'])
def EB_healthcheck():
    print('>>>>>>>> healthcheck')
    return 'OK', 200


@admin_bp.route('/health', methods=['GET'])
def health():
    return {'status': 'ok'}, 200


@admin_bp.route('/db_tools', methods=['GET'])
def get_db_info():
    print('get_db_info()')
    samples = db.session.query(Activity.start_date).limit(5).all()
    for (d,) in samples:
        try:
            parsed = parser.isoparse(d)
            print(f"{d} ✅ ISO8601")
        except Exception:
            print(f"{d} ❌ not ISO8601")
    return {'status': 'ok'}, 200


@admin_bp.route('/listusers', methods=['GET'])
def list_users():
    print("list_users()")
    try:
        users = db.session.query(User).all()
        return jsonify([str(u) for u in users])
    except Exception as e:
        db.session.rollback()
        return f'An error occurred: {str(e)}', 500
