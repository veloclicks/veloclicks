from flask import request, jsonify, current_app
import jwt
import datetime

from app.auth import auth_bp
from app.models import db, User


@auth_bp.route('/register', methods=['POST'])
def register():
    print('/register api called')
    data = request.get_json()
    print(f"/register for user: {data['username']}, {data['email']}")

    print(f"firstname field: '{data.get('firstname')}' (type: {type(data.get('firstname'))})")
    print(f"lastname field: '{data.get('lastname')}' (type: {type(data.get('lastname'))})")

    if User.query.filter_by(username=data['username']).first():
        return jsonify({'message': 'Username already exists'}), 400

    if User.query.filter_by(email=data['email']).first():
        return jsonify({'message': 'Email already in use'}), 400

    user = User(
        username=data['username'],
        email=data['email'],
        firstname=data['firstname'],
        lastname=data['lastname']
    )
    user.set_password(data['password'])

    print(f"Created user object - firstname: '{user.firstname}', lastname: '{user.lastname}'")

    db.session.add(user)
    db.session.commit()

    print(f"User saved to database with ID: {user.id}")
    print(f"Saved user - firstname: '{user.firstname}', lastname: '{user.lastname}'")

    return jsonify({'message': 'User created successfully'}), 201


@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    print('/login for user \n', data['username'])

    user = User.query.filter_by(username=data['username']).first()

    if not user or not user.check_password(data['password']):
        return jsonify({'message': 'Invalid username or password'}), 401

    token = jwt.encode({
        'user_id': user.id,
        'email': user.email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, current_app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({'token': token}), 200
