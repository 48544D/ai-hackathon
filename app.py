from flask import Flask, render_template, request, session, redirect
import requests
from bs4 import BeautifulSoup
import secrets
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///qcmtest.db'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600
db = SQLAlchemy(app)
app.secret_key = 'secretkey'

API_KEY = 'sec_FFGeJckvwYFWHlPUGCaApolPdbebtS75'


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return '<User %r>' % self.id


class Prof(User):
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    courses = db.relationship('Course', backref='prof')

    def __init__(self, name, username, password, email, type):
        super().__init__(name=name, username=username,
                         password=password, email=email, type=type)


class Student(User):
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)

    def __init__(self, name, username, password, email, type):
        super().__init__(name=name, username=username,
                         password=password, email=email, type=type)


class Classe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    professor_id = db.Column(
        db.Integer, db.ForeignKey('prof.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey(
        'student.id'), nullable=False)
    name = db.Column(db.String(120), nullable=False)


class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    pdf_url = db.Column(db.String(200), nullable=False)
    num_qst = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    prof_id = db.Column(db.Integer, db.ForeignKey('prof.id'))

    def __repr__(self):
        return '<Course %r>' % self.id

    def __init__(self, pdf_url, num_qst, name, prof_id):
        self.pdf_url = pdf_url
        self.num_qst = num_qst
        self.name = name
        self.prof_id = prof_id


class Score(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return '<Score %r>' % self.id


class Admin(User):
    id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)

    def __repr__(self):
        return '<Admin %r>' % self.id

    def __init__(self, name, username, password, email, type):
        super().__init__(name=name, username=username,
                         password=password, email=email, type=type)


def add_pdf_via_url(pdf_url):
    headers = {
        'x-api-key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {'url': pdf_url}

    response = requests.post(
        'https://api.chatpdf.com/v1/sources/add-url', headers=headers, json=data)

    if response.status_code == 200:
        return response.json()['sourceId']
    else:
        return None


def send_chat_message(source_id, question):
    headers = {
        'x-api-key': API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'sourceId': source_id,
        'messages': [
            {
                "role": "user",
                "content": question
            }
        ]
    }

    response = requests.post(
        'https://api.chatpdf.com/v1/chats/message', headers=headers, json=data)

    if response.status_code == 200:
        return response.json()['content']
    else:
        return None


def parse_qcm_html(qcm_html):
    qcm_list = []
    soup = BeautifulSoup(qcm_html, 'html.parser')

    questions = soup.find_all('h1')
    answers = soup.find_all('strong')

    for i, question in enumerate(questions):
        q_text = question.text
        options_tag = question.find_next_sibling('p')
        options = [opt.strip()
                   for opt in options_tag.find_all(text=True, recursive=False)]
        correct_answer = answers[i].text.strip()

        qcm_item = {
            "question_id": i + 1,
            "question": q_text,
            "options": options,
            "answer": correct_answer
        }
        qcm_list.append(qcm_item)

    return qcm_list


@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']

        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user:
            if user.password == password:
                session['username'] = username

                if user.type == 'prof':
                    return redirect('/prof')
                elif user.type == 'etudiant':
                    return redirect('/etudiant')
                else:
                    return redirect('/admin')

            else:
                return 'Password incorrect'
        else:
            return 'User not found'

    else:
        return render_template('user/login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form['nom']
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        user_type = request.form['type']  # Changed 'type' to 'user_type'

        if user_type == 'prof':
            user = Prof(name=nom, username=username,
                        password=password, email=email, type='prof')
        elif user_type == 'etudiant':  # Changed 'etudiant' to 'student'
            user = Student(name=nom, username=username,
                           password=password, email=email, type='etudiant')
        else:
            user = Admin(name=nom, username=username,
                         password=password, email=email, type='admin')

        try:
            db.session.add(user)
            db.session.commit()
            return redirect('/')
        except Exception as e:  # Catch specific exceptions to handle potential errors
            print(f"Error: {e}")
            return 'There was an issue adding your task'

    else:
        return render_template('user/register.html')


@app.route('/temp', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        pdf_url = request.form['pdf_url']
        n = request.form['num']
        question = ''
        if int(n) == 3:
            question = 'Vous devez générer ' + \
                str(n) + ' questions à choix multiples (QCM) avec les réponses. Pour chaque question, utilisez la balise <h1> pour le texte de la question, la balise <p> pour les choix de réponse, séparés par des balises <br>, et la balise <strong> pour la réponse correcte. Chaque question doit être séparée par une balise <hr>.'
        elif (int(n) == 5 or int(n) == 4):
            question = 'Vous devez générer ' + \
                str(n) + ' questions à choix multiples (QCM) avec les réponses. Utilisez la balise <h1> pour le texte de la question, la balise <p> pour tous les choix de réponse, séparés par des balises <br>, puis la balise <strong> pour la réponse correcte. Chaque question doit être séparée par une balise <hr>.'

        source_id = add_pdf_via_url(pdf_url)
        if source_id:
            answer = send_chat_message(source_id, question)
            if answer:
                print(answer)
                qcm_list = parse_qcm_html(answer)
                session['qcm_list'] = qcm_list
                return render_template('result.html', qcm_list=qcm_list)
        else:
            return render_template('error.html')

    return render_template('index.html')


@app.route('/validate_answers', methods=['POST'])
def validate_answers():
    # Get the selected answers from the form
    selected_answers = {f'q{i}': request.form[f'question{i}']
                        for i in range(1, len(session['qcm_list']) + 1)}

    # Calculate the score
    score = 0
    for i, question in enumerate(session['qcm_list'], 1):

        if "Réponse: " + selected_answers[f'q{i}'] == str(question['answer']):
            score += 1

    return render_template('score.html', score=score, total=len(session['qcm_list']))


@app.route('/prof', methods=['GET'])
def prof():
    professor = Prof.query.filter_by(username=session['username']).first()

    return render_template('prof/index.html', professor=professor)


@app.route('/prof/create', methods=['POST', 'GET'])
def create():
    return render_template('prof/create.html')


@app.route('/cours/create', methods=['POST'])
def create_cours():
    pdf_url = request.form['pdf_url']
    num_qst = request.form['num']
    prof_id = Prof.query.filter_by(username=session['username']).first().id
    name = request.form['name']
    cours = Course(pdf_url=pdf_url, num_qst=num_qst,
                   prof_id=prof_id, name=name)
    try:
        print(cours)
        db.session.add(cours)
        db.session.commit()
        return redirect('/prof')
    except:
        return 'There was an issue adding your task'


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
