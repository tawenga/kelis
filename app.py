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
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://kelis:password@localhost/kelis'
#app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
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
    return jsonify({ 'status': False })

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

#get profile of own class
@app.route('/api/profiles/myclass', methods=['POST'])
def get_my_class_profiles():
    my_class = request.json.get('my_class')
    user_profiles = UserProfile.query.filter_by(course_name_and_year = my_class).order_by(UserProfile.thumbs_up.desc()).all()
    return jsonify({
        'user_profiles': [user_profile.to_json() for user_profile in user_profiles],
    })

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


@app.route("/api/search",  methods=['POST'])
def w_search():
    keyword = request.json.get('keyword')
    user_profiles = UserProfile.query.msearch(keyword).order_by(UserProfile.thumbs_up.desc()).all()
    return jsonify({
        'user_profiles': [user_profile.to_json() for user_profile in user_profiles],
    })

@app.route("/api/like",  methods=['POST'])
def like():
    like = Like.from_json(request.json)
    db.session.add(like)
    db.session.commit()
    return jsonify(like.to_json())\

@app.route("/api/unlike",  methods=['POST'])
def unlike():
    unlike = Unlike.from_json(request.json)
    db.session.add(unlike)
    db.session.commit()
    return jsonify(unlike.to_json())

#get all ids user has liked
@app.route('/api/likes/<int:id>', methods=['GET'])
def get_likes(id):
    likes = Like.query.filter_by(liker_id = id).all()
    return jsonify({
        'likes': [like.to_json() for like in likes],
    })

#get all ids user has unliked
@app.route('/api/unlikes/<int:id>', methods=['GET'])
def get_unlikes(id):
    unlikes = Unlike.query.filter_by(unliker_id = id).all()
    return jsonify({
        'unlikes': [unlike.to_json() for unlike in unlikes],
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
    __searchable__ = ['username']
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer)
    username = db.Column(db.String(64), unique=True, index=True)
    course_name_and_year = db.Column(db.String(64), index=True)
    photo = db.Column(db.String(255))
    thumbs_up = db.Column(db.Integer)
    thumbs_down = db.Column(db.Integer)

    def to_json(self):
        user_profile_json = {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'course_name_and_year': self.course_name_and_year,
            'photo': self.photo,
            'thumbs_up': self.thumbs_up,
            'thumbs_down': self.thumbs_down
        }
        return user_profile_json

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

class Like(db.Model):
    __tablename__ = 'likes'
    id = db.Column(db.Integer, primary_key=True)
    liker_id = db.Column(db.Integer)
    liked_id = db.Column(db.Integer)

    def to_json(self):
        like_json = {
            'liker_id': self.liker_id,
            'liked': self.liked_id
        }
        return like_json

    @staticmethod
    def from_json(like):
        liker_id = like.get('liker_id')
        liked_id = like.get('liked_id')

        return Like(liker_id = liker_id, liked_id = liked_id)

    def __repr__(self):
        return '<Row %r>' % self.id

class Unlike(db.Model):
    __tablename__ = 'unlikes'
    id = db.Column(db.Integer, primary_key=True)
    unliker_id = db.Column(db.Integer)
    unliked_id = db.Column(db.Integer)

    def to_json(self):
        unlike_json = {
            'unliker_id': self.unliker_id,
            'unliked_id': self.unliked_id
        }
        return unlike_json

    @staticmethod
    def from_json(unlike):
        unliker_id = unlike.get('unliker_id')
        unliked_id = unlike.get('unliked_id')

        return Unlike(unliker_id=unliker_id, unliked_id=unliked_id)

    def __repr__(self):
        return '<Row %r>' % self.id

def make_shell_context():
    return dict(app=app, db=db, User=User, UserProfile=UserProfile, Like=Like, Unlike=Unlike)

manager.add_command("shell", Shell(make_context=make_shell_context))
manager.add_command('db', MigrateCommand)

if __name__ == '__main__':
    search.create_index(update=True)
    manager.run()
