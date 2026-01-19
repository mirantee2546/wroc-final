from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import requests
import json
import os
import crcmod

app = Flask(__name__)
app.config['SECRET_KEY'] = 'wroc_secure_2026'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wroc.db'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024 
db = SQLAlchemy(app)

# --- 🟢 ข้อมูลการตั้งค่า 🟢 ---
LINE_ACCESS_TOKEN = "JaRlTPLo2VkS+K73UswKn21OE6sIBB2Wy7OniW8Y5HX8pxxY2q/S7xHTAj/cRVkikgF3OizUdBT4kI86zIlvetZfjjJPVPLNLlCxrD4mEBAkcqclALRhT6JTKl1P41Ge/QzAnjU08YefjbPnguue6QdB04t89/1O/w1cDnyilFU="
MY_LINE_USER_ID = "Ub5278cd7ddc621de485b982940e21ef1"
PROMPTPAY_ID = "0981810233" 

def generate_promptpay_payload(phone_number, amount):
    amount = "{:0.2f}".format(float(amount))
    target = phone_number.replace('-', '').replace(' ', '')
    if len(target) <= 10:
        target = "0066" + target[1:]
        target = target.rjust(13, '0')
    payload = "000201010211"
    account_info = "0010A000000677010111" + "0113" + target
    payload += "29" + str(len(account_info)).zfill(2) + account_info
    payload += "5303764"
    payload += "54" + str(len(amount)).zfill(2) + amount
    payload += "5802TH6304"
    crc_func = crcmod.predefined.mkCrcFun('xmodem')
    payload += hex(crc_func(payload.encode('ascii'))).upper()[2:].zfill(4)
    return payload

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    balance = db.Column(db.Float, default=0.0)
    is_admin = db.Column(db.Boolean, default=False)

class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    username = db.Column(db.String(50))
    service = db.Column(db.String(100))
    link = db.Column(db.String(255))
    quantity = db.Column(db.Integer)
    price = db.Column(db.Float)
    status = db.Column(db.String(50), default='Pending') 
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

with app.app_context():
    db.create_all()

@app.route('/')
def home():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        orders = Order.query.filter_by(user_id=user.id).order_by(Order.created_at.desc()).all()
        return render_template('index.html', user=user, orders=orders)
    return redirect(url_for('login'))

@app.route('/order', methods=['POST'])
def order_action():
    if 'user_id' not in session: return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    service = request.form.get('service')
    link = request.form.get('link')
    quantity = int(request.form.get('quantity'))
    prices = {'FB_LIKE': 0.1, 'IG_FOLLOW': 0.2, 'TK_VIEW': 0.05}
    total_price = quantity * prices.get(service, 0.1)
    
    new_order = Order(user_id=user.id, username=user.username, service=service, link=link, quantity=quantity, price=total_price, status='Waiting Payment')
    db.session.add(new_order); db.session.commit()

    if user.balance >= total_price:
        user.balance -= total_price; new_order.status = 'Pending'; db.session.commit()
        return redirect(url_for('home'))
    return redirect(url_for('checkout', order_id=new_order.id))

@app.route('/checkout/<int:order_id>')
def checkout(order_id):
    order = Order.query.get(order_id)
    qr_payload = generate_promptpay_payload(PROMPTPAY_ID, order.price)
    return render_template('checkout.html', order=order, qr_payload=qr_payload)

@app.route('/confirm_payment/<int:order_id>', methods=['POST'])
def confirm_payment(order_id):
    order = Order.query.get(order_id)
    file = request.files.get('slip')
    if file:
        if not os.path.exists('static/uploads'): os.makedirs('static/uploads')
        file.save(os.path.join('static/uploads', secure_filename(f"wroc_slip_{order.id}.png")))
        msg = f"📩 WROC แจ้งโอนเงิน: #{order.id}\n👤 {order.username}\n💰 {order.price} ฿"
        requests.post("https://api.line.me/v2/bot/message/push", headers={"Authorization": f"Bearer {LINE_ACCESS_TOKEN}"}, json={"to": MY_LINE_USER_ID, "messages": [{"type": "text", "text": msg}]})
        flash('แจ้งโอนเรียบร้อย รอตรวจสอบ', 'success'); return redirect(url_for('home'))
    return redirect(url_for('checkout', order_id=order_id))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and check_password_hash(user.password, request.form.get('password')):
            session['user_id'] = user.id
            return redirect(url_for('home'))
        return "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        hashed_pw = generate_password_hash(request.form.get('password'))
        new_user = User(username=request.form.get('username'), password=hashed_pw)
        db.session.add(new_user)
        try:
            db.session.commit()
            return redirect(url_for('login'))
        except:
            return "ชื่อนี้ถูกใช้ไปแล้ว"
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)