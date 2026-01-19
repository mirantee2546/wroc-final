from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Order
from linebot import LineBotApi
from linebot.models import TextSendMessage

# LINE Configuration
LINE_CHANNEL_ACCESS_TOKEN = 'sJqu5ROglXJpMK4l976CaezwEtwB4QS9z/iugKPOJVdx+zQCgEP9+iRP74IfG/NYjQeQw0nTD1bAiGHlUDdyhgtr13u/RHyHkjQRM6brS3lLZ1bN/lSgXk7IKD3jSSwZojoUZ+dZhyOQ8+zRGwCeTgdB04t89/1O/w1cDnyilFU='
LINE_ADMIN_USER_ID = 'Uc96074081e475c7ba28fcb730b80e16e' 

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)

def send_line_message(message):
    try:
        line_bot_api.push_message(LINE_ADMIN_USER_ID, TextSendMessage(text=message))
    except Exception as e:
        print(f"Error: {e}")

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wroc_database.db'
app.config['SECRET_KEY'] = 'dev-key-123'

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# --- ROUTES สำหรับลูกค้า ---

@app.route('/')
@login_required
def index():
    services = [
        {'id': 1, 'name': 'ปั้มไลค์ Facebook', 'price': 0.05},
        {'id': 2, 'name': 'เพิ่มผู้ติดตาม IG', 'price': 0.10}
    ]
    return render_template('index.html', services=services)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if User.query.filter_by(username=username).first():
            return "ชื่อผู้ใช้นี้ถูกใช้ไปแล้ว"
        
        new_user = User(username=username)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            # ถ้าเป็น Admin1 ให้ไปหน้าแอดมินโดยตรง
            if user.username == 'Admin1':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('index'))
        return "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
    return render_template('login.html')

@app.route('/order', methods=['POST'])
@login_required
def place_order():
    quantity = int(request.form.get('quantity'))
    service_id = request.form.get('service')
    link = request.form.get('link')
    
    price_per_unit = 0.05 if service_id == '1' else 0.10
    total_cost = quantity * price_per_unit

    if current_user.balance < total_cost:
        return "<h3>ยอดเงินไม่เพียงพอ! <a href='/topup'>ไปหน้าเติมเงิน</a></h3>"

    current_user.balance -= total_cost
    new_order = Order(
        user_id=current_user.id,
        service_name="บริการ ID: " + service_id,
        url_link=link,
        quantity=quantity,
        total_price=total_cost,
        status='Pending'
    )
    db.session.add(new_order)
    db.session.commit()
    
    # ส่งแจ้งเตือนเข้า LINE
   # แก้ไขส่วนการส่งแจ้งเตือนเข้า LINE ให้มีลิงก์งาน
    message_to_admin = (
        f"🔔 มีออเดอร์ใหม่!\n"
        f"👤 ผู้สั่ง: {current_user.username}\n"
        f"🛠 บริการ: {new_order.service_name}\n"
        f"🔢 จำนวน: {quantity}\n"
        f"🔗 ลิงก์งาน: {link}"  # เพิ่มบรรทัดนี้เพื่อส่งลิงก์เข้าไป
    )
    
    send_line_message(message_to_admin)
    
    return redirect(url_for('view_history'))

@app.route('/history')
@login_required
def view_history():
    orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.id.desc()).all()
    return render_template('history.html', orders=orders)

@app.route('/topup', methods=['GET', 'POST'])
@login_required
def topup():
    if request.method == 'POST':
        amount = float(request.form.get('amount'))
        current_user.balance += amount
        db.session.commit()
        return redirect(url_for('index'))
    # แก้ไขบรรทัดนี้ให้ส่ง user=current_user เข้าไปด้วย
    return render_template('topup.html', user=current_user)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- ROUTES สำหรับ ADMIN (ต้องเป็น Admin1 เท่านั้น) ---

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.username == 'Admin1' and user.check_password(password):
            login_user(user)
            return redirect(url_for('admin_dashboard'))
        flash("สิทธิ์แอดมินไม่ถูกต้อง", "danger")
    return render_template('admin_login.html')

@app.route('/admin')
@login_required
def admin_dashboard():
    if current_user.username != 'Admin1':
        logout_user()
        return redirect(url_for('admin_login'))
    all_orders = Order.query.order_by(Order.id.desc()).all()
    return render_template('admin.html', orders=all_orders)

@app.route('/update_status/<int:order_id>/<string:new_status>')
@login_required
def update_status(order_id, new_status):
    if current_user.username != 'Admin1':
        return "Unauthorized", 403
    order = Order.query.get(order_id)
    if order:
        order.status = new_status
        db.session.commit()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/refund/<int:order_id>')
@login_required
def refund_order(order_id):
    if current_user.username != 'Admin1':
        return "Unauthorized", 403
    order = Order.query.get(order_id)
    if order and order.status != 'Canceled':
        user = User.query.get(order.user_id)
        user.balance += order.total_price
        order.status = 'Canceled'
        db.session.commit()
    return redirect(url_for('admin_dashboard'))
@app.route('/dashboard')
@login_required
def dashboard():
    # นับจำนวนออเดอร์แยกตามสถานะของลูกค้าคนนั้นๆ
    total_orders = Order.query.filter_by(user_id=current_user.id).count()
    pending_orders = Order.query.filter_by(user_id=current_user.id, status='Pending').count()
    completed_orders = Order.query.filter_by(user_id=current_user.id, status='Completed').count()
    
    # ดึง 5 ออเดอร์ล่าสุดมาโชว์ในตาราง
    recent_orders = Order.query.filter_by(user_id=current_user.id).order_by(Order.id.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                           total=total_orders, 
                           pending=pending_orders, 
                           completed=completed_orders,
                           orders=recent_orders)

# ... โค้ดส่วนอื่นๆ ของคุณ ...

# ใส่ไว้ก่อนบรรทัดรันแอป เพื่อให้ระบบสร้างตาราง User และ Order อัตโนมัติบน Render
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run()