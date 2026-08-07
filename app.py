from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user
)
from dotenv import load_dotenv
import os
import json
from flask import request
from sqlalchemy import Text
from werkzeug.security import generate_password_hash, check_password_hash
from flask_socketio import (
    SocketIO,
    emit,
    join_room
)
load_dotenv()
app = Flask(__name__)
socketio = SocketIO(
    app,
    cors_allowed_origins="*"
)

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL")

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ----------------------------------
# MODELS
# ----------------------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(200))
    role = db.Column(db.String(20))


class Session(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    session_name = db.Column(db.String(100))
    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

class SessionStudent(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    session_id = db.Column(
        db.Integer,
        db.ForeignKey('session.id'),
        nullable=False
    )

    student_id = db.Column(
        db.Integer,
        db.ForeignKey('user.id'),
        nullable=False
    )

class WhiteboardData(db.Model):

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    session_id = db.Column(
        db.Integer,
        unique=True,
        nullable=False
    )

    board_json = db.Column(
        Text,
        default="[]"
    )


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ----------------------------------
# CREATE TABLES
# ----------------------------------

with app.app_context():
    db.create_all()

    teacher = User.query.filter_by(username='teacher1').first()

    if not teacher:
        teacher = User(
            username='teacher1',
            password=generate_password_hash('1234'),
            role='teacher'
        )
        db.session.add(teacher)

    student1 = User.query.filter_by(username='student1').first()

    if not student1:
        student1 = User(
            username='student1',
            password=generate_password_hash('1234'),
            role='student'
        )
        db.session.add(student1)

    student2 = User.query.filter_by(username='student2').first()

    if not student2:
        student2 = User(
            username='student2',
            password=generate_password_hash('1234'),
            role='student'
        )
        db.session.add(student2)


    db.session.commit()

# ----------------------------------
# LOGIN
# ----------------------------------

@app.route('/', methods=['GET'])
def home():

    if current_user.is_authenticated:
        return redirect('/dashboard')

    return redirect('/login')


@app.route('/login', methods=['GET', 'POST'])
def login():

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            if user.role == 'teacher':
                return redirect('/dashboard')
            else:

                return redirect('/student-dashboard')

        return "Invalid Login"

    return render_template("login.html")


# ----------------------------------
# DASHBOARD
# ----------------------------------

from flask import render_template

@app.route('/dashboard')
@login_required
def dashboard():

    sessions = Session.query.filter_by(
        teacher_id=current_user.id
    ).all()

    students = User.query.filter_by(
        role='student'
    ).all()


    session_students = {}

    for session in sessions:

        links = SessionStudent.query.filter_by(
            session_id=session.id
        ).all()

        names = []

        for link in links:

            student = db.session.get(
                User,
                link.student_id
            )

            if student:
                names.append(student.username)

        session_students[session.id] = names

    return render_template(
        "dashboard.html",
        sessions=sessions,
        students=students,
        session_students=session_students
    )


# ----------------------------------
# CREATE SESSION
# ----------------------------------

@app.route('/create-session', methods=['GET', 'POST'])
@login_required
def create_session():

    if request.method == 'POST':

        session_name = request.form['session_name']

        new_session = Session(
            session_name=session_name,
            teacher_id=current_user.id
        )

        db.session.add(new_session)
        db.session.commit()


        selected_students = request.form.getlist('students')

        for student_name in selected_students:

            student = User.query.filter_by(
                username=student_name
            ).first()

            if student:

                link = SessionStudent(
                    session_id=new_session.id,
                    student_id=student.id
                )

                db.session.add(link)

        db.session.commit()

        all_links = SessionStudent.query.all()

        for link in all_links:
            print(
                "Session:",
                link.session_id,
                "Student:",
                link.student_id
            )

        return redirect('/dashboard')




@app.route('/delete-session/<int:session_id>')
@login_required
def delete_session(session_id):

    session = db.session.get(Session, session_id)

    if session and session.teacher_id == current_user.id:

        SessionStudent.query.filter_by(
            session_id=session_id
        ).delete()

        db.session.delete(session)

        db.session.commit()

    return redirect('/dashboard')
# ----------------------------------
# Student Dashboard
# ----------------------------------

from flask import render_template

@app.route('/student-dashboard')
@login_required
def student_dashboard():

    if current_user.role != 'student':
        return "Access Denied"

    student_links = SessionStudent.query.filter_by(
        student_id=current_user.id
    ).all()

    sessions = []

    for link in student_links:

        session = db.session.get(
            Session,
            link.session_id
        )

        if session:
            sessions.append(session)

    print("Student:", current_user.username)
    print("Sessions Found:", len(sessions))

    return render_template(
        'student_dashboard.html',
        sessions=sessions
    )


from flask import render_template

@app.route('/student/session/<int:session_id>')
@login_required
def student_session(session_id):

    if current_user.role != 'student':
        return "Access Denied"

    return render_template(
        'student_session.html',
        session_id=session_id
    )


# ----------------------------------
# Teacher Session
# ----------------------------------

@app.route('/teacher/session/<int:session_id>')
@login_required
def teacher_session(session_id):

    if current_user.role != 'teacher':
        return "Access Denied"

    return render_template(
        'teacher_session.html',
        session_id=session_id
    )

# ----------------------------------
# LOGOUT
# ----------------------------------

@app.route('/logout')
@login_required
def logout():

    logout_user()

    return redirect('/login')


# ----------------------------------
# SOCKETIO EVENTS
# ----------------------------------

from flask_socketio import emit

@socketio.on("draw")
def handle_draw(data):
    print(data)
    session_id = data["session_id"]

    board = WhiteboardData.query.filter_by(
        session_id=session_id
    ).first()

    if not board:
        board = WhiteboardData(
            session_id=session_id,
            board_json="[]"
        )
        db.session.add(board)
        db.session.commit()

    history = json.loads(
        board.board_json
    )

    history.append(data)

    board.board_json = json.dumps(
        history
    )

    db.session.commit()

    room = f"session_{session_id}"

    emit(
        "draw",
        data,
        room=room,
        include_self=False
    )

@socketio.on("clear_board")
def handle_clear(data):

    session_id = data["session_id"]

    board = WhiteboardData.query.filter_by(
        session_id=session_id
    ).first()

    if board:

        board.board_json = "[]"

        db.session.commit()

    room = f"session_{session_id}"

    emit(
        "clear_board",
        room=room,
        include_self=False
    )

@socketio.on("join_session")
def handle_join(data):

    session_id = data["session_id"]

    room = f"session_{session_id}"

    join_room(room)

    board = WhiteboardData.query.filter_by(
        session_id=session_id
    ).first()

    history = []

    if board:
        history = json.loads(
            board.board_json
        )

    emit(
        "load_board",
        history,
        room=request.sid
    )


@socketio.on('board_update')
def handle_board_update(data):

    room = f"session_{data['session_id']}"

    emit(
        'board_update',
        data,
        room=room,
        include_self=False
    )

# ----------------------------------
# RUN
# ----------------------------------

if __name__ == '__main__':
    socketio.run(
        app,
        host="0.0.0.0",
        port=5000
    )
