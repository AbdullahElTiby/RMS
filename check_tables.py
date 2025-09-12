from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///restaurant.db'
db = SQLAlchemy(app)

class Table(db.Model):
    __tablename__ = 'tables'
    id = db.Column(db.Integer, primary_key=True)
    table_number = db.Column(db.Integer, unique=True, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default='available')
    location = db.Column(db.String(100))

with app.app_context():
    tables = Table.query.all()
    print("Tables:")
    for t in tables:
        print(f"ID: {t.id}, Number: {t.table_number}, Capacity: {t.capacity}, Status: {t.status}, Location: {t.location}")
    available = [t for t in tables if t.status == 'available']
    print(f"Available tables: {len(available)}")
