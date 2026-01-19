from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash # เพิ่มบรรทัดนี้

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=0.0)

    # ฟังก์ชันสำหรับเข้ารหัสรหัสผ่าน (ป้องกันการอ่านรหัสผ่านตรงๆ)
    def set_password(self, password):
        self.password = generate_password_hash(password)

    # ฟังก์ชันสำหรับตรวจสอบรหัสผ่านตอน Login
    def check_password(self, password):
        return check_password_hash(self.password, password)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    service_name = db.Column(db.String(100))
    url_link = db.Column(db.String(255))
    quantity = db.Column(db.Integer)
    total_price = db.Column(db.Float)
    status = db.Column(db.String(20), default='Pending')