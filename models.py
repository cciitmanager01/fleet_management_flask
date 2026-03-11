from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import enum

db = SQLAlchemy()

class Role(enum.Enum):
    ADMIN = 'Admin'
    DRIVER = 'Driver'

class User(db.Model, UserMixin):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, default=Role.DRIVER)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Vehicle(db.Model):
    __tablename__ = "vehicles"
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(255), unique=True, nullable=False)
    department = db.Column(db.String(255))
    model = db.Column(db.String(255))
    logs = db.relationship('MileageLog', backref='vehicle', lazy=True)

class MileageLog(db.Model):
    __tablename__ = "mileage_logs"
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    driver_name = db.Column(db.String(255))
    odometer = db.Column(db.Integer, nullable=False)
    distance = db.Column(db.Integer, default=0) # Automatically calculated
    date = db.Column(db.Date, nullable=False)