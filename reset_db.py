from flask import Flask, render_template, request, redirect, flash, url_for
from flask_migrate import Migrate
from datetime import date
from config import DATABASE_URL, SECRET_KEY
from models import db, Vehicle, MileageLog, User, Role
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from functools import wraps

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
migrate = Migrate(app, db)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


class HardcodedAdmin(UserMixin):
    def __init__(self):
        self.id = "9999"
        self.username = "admin"
        self.role = Role.ADMIN


@login_manager.user_loader
def load_user(user_id):
    if user_id == "9999":
        return HardcodedAdmin()
    return User.query.get(int(user_id))


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))

        # Check if user is the hardcoded admin OR a DB admin
        is_admin = False
        if current_user.id == "9999":
            is_admin = True
        elif hasattr(current_user, 'role') and current_user.role == Role.ADMIN:
            is_admin = True

        if not is_admin:
            flash("Admin access only!", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u = request.form.get('username')
        p = request.form.get('password')
        if u == 'admin' and p == 'admin123':
            login_user(HardcodedAdmin())
            return redirect(url_for('dashboard'))
        user = User.query.filter_by(username=u).first()
        if user and user.check_password(p):
            login_user(user)
            return redirect(url_for('dashboard') if user.role == Role.ADMIN else url_for('index'))
        flash("Invalid Credentials", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


@app.route('/')
@login_required
def index():
    if current_user.id == "9999":
        return redirect(url_for('dashboard'))
    vehicles = Vehicle.query.all()
    return render_template('index.html', vehicles=vehicles)


@app.route('/submit_mileage', methods=['POST'])
@login_required
def submit_mileage():
    v_id = request.form.get('vehicle_id')
    try:
        new_odo = int(request.form.get('odometer'))
        last_log = MileageLog.query.filter_by(vehicle_id=v_id).order_by(MileageLog.id.desc()).first()

        old_odo = last_log.odometer if last_log else new_odo
        distance = new_odo - old_odo

        if distance < 0:
            flash(f"Error: Reading lower than previous ({old_odo})", "danger")
        else:
            log = MileageLog(vehicle_id=v_id, driver_name=current_user.username, odometer=new_odo, distance=distance,
                             date=date.today())
            db.session.add(log)
            db.session.commit()
            flash(f"Success! Traveled {distance} km", "success")
    except:
        flash("Invalid Input", "danger")
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
@admin_only
def dashboard():
    vehicles = Vehicle.query.all()
    report = []
    for v in vehicles:
        last = MileageLog.query.filter_by(vehicle_id=v.id).order_by(MileageLog.id.desc()).first()
        report.append({
            'plate': v.plate_number,
            'dept': v.department,
            'odo': last.odometer if last else 0,
            'last_dist': last.distance if last else 0,
            'total_trips': MileageLog.query.filter_by(vehicle_id=v.id).count()
        })
    return render_template('dashboard.html', report=report)


@app.route('/add_vehicle', methods=['POST'])
@login_required
@admin_only
def add_vehicle():
    p = request.form.get('plate').upper()
    d = request.form.get('dept')
    m = request.form.get('model')
    db.session.add(Vehicle(plate_number=p, department=d, model=m))
    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/manage_users')
@login_required
@admin_only
def manage_users():
    users = User.query.all()
    return render_template('manage_users.html', users=users, roles=Role)


@app.route('/add_user', methods=['POST'])
@login_required
@admin_only
def add_user():
    u = User(username=request.form.get('username'), role=Role[request.form.get('role')])
    u.set_password(request.form.get('password'))
    db.session.add(u)
    db.session.commit()
    return redirect(url_for('manage_users'))


if __name__ == '__main__':
    app.run(debug=True)