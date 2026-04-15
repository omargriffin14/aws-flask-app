from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import time
import os
import boto3
import json

app = Flask(__name__)

def get_secret():
    secret_name = "flask/db-credentials"
    region_name = "us-east-1"
    client = boto3.client('secretsmanager', region_name=region_name)
    response = client.get_secret_value(SecretId=secret_name)
    return json.loads(response['SecretString'])

secrets = get_secret()

DB_USER = secrets['DB_USER']
DB_PASSWORD = secrets['DB_PASSWORD']
DB_HOST = secrets['DB_HOST']
DB_NAME = secrets['DB_NAME']

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:3306/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

class Task(db.Model):
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    task = db.Column(db.String(255), nullable=False)

def init_db():
    retries = 5
    while retries:
        try:
            with app.app_context():
                db.create_all()
            break
        except Exception as e:
            retries -= 1
            print(f'Database not ready, retrying... ({e})')
            time.sleep(5)

init_db()

@app.route('/')
def index():
    tasks = Task.query.all()
    return render_template('index.html', tasks=tasks)

@app.route('/add', methods=['POST'])
def add():
    task = request.form.get('task')
    if task:
        new_task = Task(task=task)
        db.session.add(new_task)
        db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
