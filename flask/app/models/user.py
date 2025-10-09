from app.model import db
from werkzeug.security import generate_password_hash, check_password_hash

class User(db.Model):
    __tablename__ = 'vc_user'

    # table attributes
    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username    = db.Column(db.String(), unique=True, nullable=False)
    email       = db.Column(db.String(50), unique=True, nullable=False)
    
    password_hash = db.Column(db.String(512))
    
    firstname   = db.Column(db.String(), nullable=True)
    lastname    = db.Column(db.String(), nullable=True)
    sex         = db.Column(db.String(10), nullable=True)  # 'Male', 'Female', 'Other'
    date_of_birth = db.Column(db.Date, nullable=True)
    ftp         = db.Column(db.Integer, nullable=True)     # Functional Threshold Power
    max_heart_rate = db.Column(db.Integer, nullable=True)

    strava_access_token = db.Column(db.String(128), nullable=True)
    strava_refresh_token = db.Column(db.String(128), nullable=True)
    token_expiry_epoch = db.Column(db.Integer, nullable=True)
    
    last_synch_epoch = db.Column(db.Integer, nullable=True) # epoch of last activity synched
    earliest_synch_epoch = db.Column(db.Integer, nullable=True) # epoch of earliest activity synchd
    
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    '''
    def __init__(self, username):
        self.username = username        
    
    def register_user_if_not_exist(self):        
        db_user = User.query.filter(User.username == self.username).all()
        if not db_user:
            db.session.add(self)
            db.session.commit()
        
        return True
    
    def get_by_username(username):        
        db_user = User.query.filter(User.username == username).first()
        return db_user
    '''
    
    
    def __repr__(self):
        return f"<User {self.username}>"