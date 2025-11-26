from flask import Blueprint, request, jsonify
from app.models import db, User, Activity
# from app.models.car import Car  # Not currently used
from datetime import datetime

main_bp = Blueprint('main', __name__)

# IMPORTANT : leave the root route to the Elastic Beanstalk Load Balancer health check, it performs a GET to '/' every 5 seconds and expects a '200'
@main_bp.route('/', methods=['GET'])
def EB_healthcheck():
    print('>>>>>>>> healthcheck')
    return 'OK', 200




# this is used by react to check flak is running
@main_bp.route('/health', methods=['GET'])
def health():
    return {'status':'ok'}, 200


from dateutil import parser

@main_bp.route('/db_tools', methods=['GET'])
def get_db_info():
    print('get_db_info()')
    samples = db.session.query(Activity.start_date).limit(5).all()


    for (d,) in samples:
        try:
            parsed = parser.isoparse(d)  # strict ISO8601 check
            print(f"{d} ✅ ISO8601")
        except Exception:
            print(f"{d} ❌ not ISO8601")
            
    return {'status':'ok'}, 200



@main_bp.route('/register', methods=['POST'])
def register_user():
    try:
        data = request.get_json()
        print('\n\nData\n\n',data,'\n\n')
        new_user = User(
            email = data["email"],
            age = data["age"],
            timestamp = datetime.utcnow()
        )
        db.session.add(new_user)
        db.session.commit()
        return 'User added', 200
    except Exception as e:
        db.session.rollback()
        return f'An error occurred: {str(e)}', 500


@main_bp.route('/listusers', methods=['GET'])
def list_users():
    print("list_users()")
    try:
        users = db.session.query(User).all()
        # calling the __str__ representation defined in the model 
        return jsonify([str(u) for u in users])
    except Exception as e:
        db.session.rollback()
        return f'An error occurred: {str(e)}', 500
