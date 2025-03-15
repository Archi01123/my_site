from flask import Flask, render_template, request, redirect, session, flash, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import inspect
import re
import random
from functools import wraps
import threading
import time
import requests
from datetime import timedelta
# from flask_socketio import SocketIO, emit не используется в pyhtonanywhere

def keep_alive():
    while True:
        try:
            requests.get("https://tema2.pythonanywhere.com")
            print("Keep-alive запрос отправлен")
        except Exception as e:
            print(f"Ошибка при отправке keep-alive запроса: {e}")
        time.sleep(1140) # Каждые 19 минут (1140 секунд)

thread = threading.Thread(target=keep_alive)
thread.daemon = True # Завершение потока при остановке приложения
thread.start()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///new_flask.db'
app.config['SECRET_KEY'] = 'secret_key_here'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# socketio = SocketIO(app)

# Установите время жизни сессии (например, 5 минут)
app.permanent_session_lifetime = timedelta(minutes=2)

# Глобальное множество для хранения активных пользователей
active_users_list = set()

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(300), nullable=False)
    text = db.Column(db.Text, nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), nullable=False)
    phone_number = db.Column(db.String(20), unique=True, nullable=False)
    bank_name = db.Column(db.String(100), nullable=False)
    amount = db.Column(db.Float, nullable=False)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Для доступа необходимо войти в систему', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function



@app.before_request
def before_request():
    # Делаем сессию постоянной (это необходимо для работы таймера)
    session.permanent = True
    # Помечаем сессию как измененную, чтобы обновить таймер активности
    session.modified = True

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template('dashboard.html')

@app.route("/register", methods=["POST", "GET"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        phone_number = request.form["phone_number"]
        bank_name = request.form["bank_name"]
        amount = float(request.form["amount"])

        # Проверка формата номера телефона
        if not re.match(r'^9\d{9}$', phone_number):
            flash("Неправильно введен номер. Пример: 9876543210", "error")
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(phone_number=phone_number).first()
        if existing_user:
            flash("Пользователь с таким номером уже зарегистрирован в базе.", "error")
            return redirect(url_for('register')) # Перенаправляем на страницу регистрации

        new_user = User(username=username, phone_number=phone_number, bank_name=bank_name, amount=amount)
        db.session.add(new_user)
        db.session.commit()

        session["username"] = username
        # flash(f"Добро пожаловать, {username}!", "success")
        return redirect(url_for('dashboard'))
    else:
        return render_template('register.html')

@app.route("/login", methods=["POST", "GET"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        phone_number = request.form["phone_number"]

        # Проверка формата номера телефона
        if not re.match(r'^9\d{9}$', phone_number):
            flash("Неправильно введен номер. Пример: 9876543210", "error")
            return redirect(url_for('login'))

        user = User.query.filter_by(phone_number=phone_number).first()
        if user and user.username == username:
            session["username"] = username
             # Добавляем пользователя в список активных
            active_users_list.add(username)
            # flash(f"Добро пожаловать, {username}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Вы не зарегистрированы. Вам нужно зарегистрироваться.", "error")
            return redirect(url_for('login'))
    else:
        return render_template('login.html')

@app.route("/logout")
def logout():
    username = session.get("username")
    if username and username in active_users_list:
        active_users_list.remove(username)  # Удаляем пользователя из списка активных
    session.pop("username", None)
    return redirect('/')

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/create", methods=["POST", "GET"])
@login_required
def create():
    if request.method == "POST":
        try:
            title = request.form["title"]
            text = request.form["text"]
            post = Post(title=title, text=text)
            db.session.add(post)
            db.session.commit()
            return redirect('/')
        except Exception as e:
            flash(f"Ошибка при создании поста: {e}", "error")
            return redirect(url_for('create'))
    else:
        return render_template('create.html')

@app.route("/about")
def about():
    return render_template('about.html')

@app.route("/random_user")
@login_required
def random_user():
    users = User.query.all()
    if users:
        user = random.choice(users)
        session['random_user_id'] = user.id  # Сохраняем ID случайного пользователя в сессии
    else:
        flash("В базе данных нет пользователей.", "info")
        return redirect(url_for('index'))
    return render_template('random_user.html', user=user)

@app.route("/show_phone/")
@login_required
def show_phone():
    random_user_id = session.pop('random_user_id', None)  # Получаем ID из сессии и удаляем его
    if not random_user_id:
        flash("Сначала выберите случайного пользователя.", "error")
        return redirect(url_for('random_user'))

    user = User.query.get(random_user_id)
    if not user:
        flash("Пользователь не найден.", "error")
        return redirect(url_for('index'))

    return render_template('show_phone.html', user=user)

@app.route("/next_random_user")
@login_required
def next_random_user():
    users = User.query.all()
    if users:
        user = random.choice(users)
        session['random_user_id'] = user.id # Обновляем ID пользователя в сессии
        return redirect(url_for('random_user'))
    else:
        flash("В базе данных нет пользователей.", "info")
        return redirect(url_for('index'))

@app.context_processor
def inject_variables():
    total_users = User.query.count()
    active_users = len(active_users_list)
    return dict(total_users=total_users, current_users=active_users)


# messages = [] # List to store messages

# # Chat functionality
# @socketio.on('connect')
# def connect():
#     print('Client connected')

# @socketio.on('disconnect')
# def disconnect():
#     print('Client disconnected')

# @socketio.on('message')
# def handle_message(message):
#     print(f'Received message: {message}')
#     emit('message', message, broadcast=True)

if __name__ == "__main__":
    with app.app_context():
        engine = db.engine
        inspector = inspect(engine)
        if not inspector.has_table('user'):
            db.create_all()
    # socketio.run(app)
    # app.run(debug=True)
