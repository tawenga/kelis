from flask import Flask, g, request, abort
from flask import jsonify
from flask_script import Manager
from flask_script import Shell
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, MigrateCommand
from flask_httpauth import HTTPBasicAuth
from passlib.apps import custom_app_context as pwd_context
from flask_msearch import Search
import os


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
#app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://kelis:password@localhost/kelis'
#app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'postgresql://kelis:password@localhost/kelis')
app.config['SQLALCHEMY_COMMIT_ON_TEARDOWN'] = True
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['MSEARCH_INDEX_NAME'] = 'whoosh_index'
app.config['MSEARCH_BACKEND'] = 'whoosh'
app.config['MSEARCH_ENABLE'] = True
manager = Manager(app)
db = SQLAlchemy(app)
migrate = Migrate(app, db)
auth = HTTPBasicAuth()
search = Search()
search.init_app(app)


@app.route('/api/users', methods = ['POST'])
def new_user():
    username = request.json.get('username')
    password = request.json.get('password')
    if username is None or password is None:
        abort(400) # missing arguments
    if User.query.filter_by(username = username).first() is not None:
        abort(400) # existing user
    user = User(username = username)
    user.hash_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({ 'id': user.id })

@auth.verify_password
def verify_password(username, password):
    user = User.query.filter_by(username = username).first()
    if not user or not user.verify_password(password):
        return False
    g.user = user
    return True

@auth.login_required
@app.route('/api/login', methods=['POST'])
def login():
    username = request.json.get('username')
    user = User.query.filter_by(username = username).first()
    if user is not None:
        return jsonify({ 'id': user.id, 'status': True })
    return jsonify({ 'status': True })

@app.route('/api/users/<int:id>')
def get_user(id):
    user = User.query.get_or_404(id)
    return jsonify(user.to_json())

#get all profiles
@app.route('/api/profiles', methods=['GET'])
def get_user_profiles():
    user_profiles = UserProfile.query.order_by(UserProfile.thumbs_up.desc()).all()
    return jsonify({
        'user_profiles': [user_profile.to_json() for user_profile in user_profiles],
    })

#create new profile
@app.route('/api/profiles', methods=['POST'])
def new_profile():
    profile = UserProfile.from_json(request.json)
    db.session.add(profile)
    db.session.commit()
    return jsonify(profile.to_json())

#get single profile
@app.route('/api/profiles/<int:id>')
def get_profiles(id):
    user_profile = UserProfile.query.get_or_404(id)
    return jsonify(user_profile.to_json())

#edit profile
@app.route('/api/profiles/<int:id>', methods=['PUT'])
def update_profile(id):
    user_profile = UserProfile.query.get(id)

    user_id = request.json['user_id']
    username = request.json['username']
    course_name_and_year = request.json['course_name_and_year']
    photo = request.json['photo']
    thumbs_up = request.json['thumbs_up']
    thumbs_down = request.json['thumbs_down']

    user_profile.user_id = user_id
    user_profile.username = username
    user_profile.course_name_and_year = course_name_and_year
    user_profile.photo = photo
    user_profile.thumbs_up = thumbs_up
    user_profile.thumbs_down = thumbs_down

    db.session.commit()
    return jsonify(user_profile.to_json())

# views.py
@app.route("/api/search",  methods=['POST'])
def w_search():
    keyword = request.json.get('keyword')
    user_profiles = UserProfile.query.msearch(keyword).all()
    #user_profiles = UserProfile.query.msearch(keyword).order_by(UserProfile.thumbs_up.desc()).all()   ##switch to this
    return jsonify({
        'user_profiles': [user_profile.to_json() for user_profile in user_profiles],
    })


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True)
    password_hash = db.Column(db.String(128))

    def hash_password(self, password):
        self.password_hash = pwd_context.encrypt(password)

    def verify_password(self, password):
        return pwd_context.verify(password, self.password_hash)


    def __repr__(self):
        return '<User %r>' % self.username


class UserProfile(db.Model):
    __tablename__ = 'user_profiles'
    __searchable__ = ['username', 'course_name_and_year']
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(64), unique=True, index=True)
    course_name_and_year = db.Column(db.String(64), index=True)
    photo = db.Column(db.String(64))
    thumbs_up = db.Column(db.Integer)
    thumbs_down = db.Column(db.Integer)

    def to_json(self):
        json_user_profile = {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'course_name_and_year': self.course_name_and_year,
            'photo': self.photo,
            'thumbs_up': self.thumbs_up,
            'thumbs_down': self.thumbs_down
        }
        return json_user_profile

    @staticmethod
    def from_json(user_profile):
        user_id = user_profile.get('user_id')
        username = user_profile.get('username')
        course_name_and_year = user_profile.get('course_name_and_year')
        photo = user_profile.get('photo')
        thumbs_up = user_profile.get('thumbs_up')
        thumbs_down = user_profile.get('thumbs_down')
        return UserProfile(user_id = user_id,
                           username = username,
                           course_name_and_year = course_name_and_year,
                           photo = photo,
                           thumbs_up = thumbs_up,
                           thumbs_down = thumbs_down)

    def __repr__(self):
        return '<UserProfile %r>' % self.username

def make_shell_context():
    return dict(app=app, db=db, User=User, UserProfile=UserProfile)

manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    search.create_index(update=True)
    manager.run()
