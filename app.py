import csv
from io import StringIO
from datetime import date, timedelta
from functools import wraps
from flask import Flask, render_template, request, redirect, flash, url_for, Response
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func
from models import db, Vehicle, MileageLog, User, Role, Driver

from datetime import datetime # Add this to your imports

# --- CONFIG ---
app = Flask(__name__)
app.config[
    'SQLALCHEMY_DATABASE_URI'] = "postgresql://postgres.ciptpgluzoazqauzzjbp:3Uq7cZ5CIlEaNIBQ@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
app.config['SECRET_KEY'] = "fleet-pro-advanced-v1"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


# --- MODELS ---
class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default='DRIVER')

    def set_password(self, p): self.password_hash = generate_password_hash(p)

    def check_password(self, p): return check_password_hash(self.password_hash, p)

    @property
    def is_admin(self):
        return self.role == 'ADMIN'


class Vehicle(db.Model):
    __tablename__ = 'vehicles'
    id = db.Column(db.Integer, primary_key=True)
    plate_number = db.Column(db.String(255), unique=True, nullable=False)
    department = db.Column(db.String(255))
    model = db.Column(db.String(255))
    last_service_odo = db.Column(db.Integer, default=0)
    service_interval = db.Column(db.Integer, default=5000)
    logs = db.relationship('MileageLog', backref='vehicle', lazy=True, cascade="all, delete-orphan")


class MileageLog(db.Model):
    __tablename__ = 'mileage_logs'
    id = db.Column(db.Integer, primary_key=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicles.id"), nullable=False)
    driver_name = db.Column(db.String(255))
    odometer = db.Column(db.Integer, nullable=False)
    distance = db.Column(db.Integer, default=0)
    date = db.Column(db.Date, nullable=False)


# --- SECURITY & HARDCODED ADMIN ---
class HardcodedAdmin(UserMixin):
    def __init__(self):
        self.id = "9999"
        self.username = "admin"
        self.role = "ADMIN"
        self.is_admin = True


@login_manager.user_loader
def load_user(user_id):
    if user_id == "9999": return HardcodedAdmin()
    return User.query.get(int(user_id))


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not getattr(current_user, 'is_admin', False):
            flash("Admin access required.", "danger")
            return redirect(url_for('login'))
        return f(*args, **kwargs)

    return decorated_function


# --- AUTH ROUTES ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        u, p = request.form.get('username'), request.form.get('password')
        if u == 'admin' and p == 'admin123':
            login_user(HardcodedAdmin())
            return redirect(url_for('dashboard'))
        user = User.query.filter_by(username=u).first()
        if user and user.check_password(p):
            login_user(user)
            return redirect(url_for('dashboard') if user.is_admin else url_for('index'))
        flash("Invalid Credentials", "danger")
    return render_template('login.html')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- CORE ROUTES ---

# Add Driver to your imports
from models import db, Vehicle, MileageLog, User, Role, Driver


# --- NEW DRIVER MANAGEMENT ROUTES ---

@app.route('/manage_drivers')
@login_required
@admin_only
def manage_drivers():
    drivers = Driver.query.all()
    return render_template('manage_drivers.html', drivers=drivers)


@app.route('/add_driver', methods=['POST'])
@login_required
@admin_only
def add_driver():
    name = request.form.get('name')
    emp_id = request.form.get('employee_id')
    new_driver = Driver(name=name, employee_id=emp_id)
    db.session.add(new_driver)
    db.session.commit()
    flash(f"Driver {name} added successfully!", "success")
    return redirect(url_for('manage_drivers'))


@app.route('/edit_driver/<int:id>', methods=['POST'])
@login_required
@admin_only
def edit_driver(id):
    driver = Driver.query.get_or_404(id)
    driver.name = request.form.get('name')
    driver.employee_id = request.form.get('employee_id')
    db.session.commit()
    flash("Driver updated!", "success")
    return redirect(url_for('manage_drivers'))


@app.route('/delete_driver/<int:id>')
@login_required
@admin_only
def delete_driver(id):
    driver = Driver.query.get_or_404(id)
    # Check if driver has logs before deleting, or just set is_active=False
    db.session.delete(driver)
    db.session.commit()
    flash("Driver removed from system.", "success")
    return redirect(url_for('manage_drivers'))


# --- UPDATED SUBMISSION ROUTES ---

@app.route('/')
@login_required
def index():
    if current_user.id == "9999":
        return redirect(url_for('dashboard'))
    vehicles = Vehicle.query.all()
    drivers = Driver.query.filter_by(is_active=True).all()  # Fetch active drivers
    return render_template('index.html', vehicles=vehicles, drivers=drivers)


@app.route('/submit_mileage', methods=['POST'])
@login_required
def submit_mileage():
    v_id = request.form.get('vehicle_id')
    d_id = request.form.get('driver_id')  # Get ID from dropdown
    try:
        new_odo = int(request.form.get('odometer'))
        last_log = MileageLog.query.filter_by(vehicle_id=v_id).order_by(MileageLog.id.desc()).first()

        old_odo = last_log.odometer if last_log else new_odo
        distance = new_odo - old_odo

        if distance < 0:
            flash(f"Error: Reading lower than previous ({old_odo})", "danger")
        else:
            log = MileageLog(
                vehicle_id=v_id,
                driver_id=d_id,  # Link to the Driver ID
                odometer=new_odo,
                distance=distance,
                date=date.today()
            )
            db.session.add(log)
            db.session.commit()
            flash(f"Success! Traveled {distance} km", "success")
    except Exception as e:
        flash(f"Invalid Input: {str(e)}", "danger")
    return redirect(url_for('index'))

# --- NEW: THE DAILY LOGS ROUTE (Fixed) ---
@app.route('/daily_logs')
@login_required
def daily_logs():
    # 1. Get today's date
    today = date.today()

    # 2. Query logs specifically for today
    # We use join(Vehicle) to make sure we can see plate numbers in the template
    logs = MileageLog.query.filter_by(date=today).order_by(MileageLog.id.desc()).all()

    # 3. Calculate total KM (Safety Fix: handle None values with "or 0")
    today_total_km = sum(log.distance or 0 for log in logs)

    # 4. Render the specific template
    return render_template('daily_logs.html',
                           logs=logs,
                           today=today,
                           today_total_km=today_total_km)


# --- ADMIN DASHBOARD & ANALYTICS ---

@app.route('/dashboard')
@login_required
@admin_only
def dashboard():
    vehicles = Vehicle.query.all()
    report = []
    for v in vehicles:
        last = MileageLog.query.filter_by(vehicle_id=v.id).order_by(MileageLog.id.desc()).first()
        odo = last.odometer if last else 0
        is_due = (odo - v.last_service_odo) >= v.service_interval
        report.append({
            'plate': v.plate_number, 'dept': v.department, 'model': v.model,
            'odo': odo, 'dist': last.distance if last else 0,
            'is_due': is_due
        })
    return render_template('dashboard.html', report=report)


from datetime import datetime  # Add this to your imports


@app.route('/analytics')
@login_required
@admin_only
def analytics():
    # 1. Get Parameters
    period = request.args.get('period', 'monthly')
    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    today = date.today()
    end_date = today

    # 2. Determine Date Range
    if period == 'daily':
        start_date = today
    elif period == 'weekly':
        start_date = today - timedelta(days=7)
    elif period == 'custom' and start_str and end_str:
        try:
            start_date = datetime.strptime(start_str, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_str, '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid custom date format", "danger")
            start_date = today.replace(day=1)
    else:  # Default Monthly
        start_date = today.replace(day=1)

    # 3. Query Statistics
    stats = db.session.query(
        Vehicle.plate_number,
        Vehicle.department,
        func.count(MileageLog.id).label('total_trips'),
        func.sum(MileageLog.distance).label('total_km'),
        func.avg(MileageLog.distance).label('avg_km')
    ).join(MileageLog).filter(
        MileageLog.date >= start_date,
        MileageLog.date <= end_date,
        MileageLog.distance > 0
    ).group_by(Vehicle.id).all()

    # 4. Calculate Summary Totals
    total_km = sum(s.total_km for s in stats) if stats else 0
    total_trips = sum(s.total_trips for s in stats) if stats else 0
    fleet_avg = total_km / total_trips if total_trips > 0 else 0

    return render_template('analytics.html',
                           stats=stats,
                           period=period,
                           start_date=start_date,
                           end_date=end_date,
                           total_km=total_km,
                           total_trips=total_trips,
                           fleet_avg=fleet_avg)


@app.route('/history')
@login_required
@admin_only
def history():
    logs = MileageLog.query.order_by(MileageLog.date.desc(), MileageLog.id.desc()).all()
    return render_template('history.html', logs=logs)


# --- USER & VEHICLE MGMT ---

@app.route('/manage_users')
@login_required
@admin_only
def manage_users():
    return render_template('manage_users.html', users=User.query.all())


@app.route('/add_user', methods=['POST'])
@login_required
@admin_only
def add_user():
    u = User(username=request.form.get('username'), role=request.form.get('role'))
    u.set_password(request.form.get('password'))
    db.session.add(u);
    db.session.commit()
    flash("User added.", "success")
    return redirect(url_for('manage_users'))


@app.route('/add_vehicle', methods=['POST'])
@login_required
@admin_only
def add_vehicle():
    db.session.add(Vehicle(plate_number=request.form.get('plate').upper(), department=request.form.get('dept'),
                           model=request.form.get('model')))
    db.session.commit()
    flash("Vehicle registered.", "success")
    return redirect(url_for('dashboard'))


@app.route('/delete_log/<int:id>')
@login_required
@admin_only
def delete_log(id):
    db.session.delete(MileageLog.query.get_or_404(id));
    db.session.commit()
    flash("Entry deleted.", "warning")
    return redirect(url_for('history'))


@app.route('/export_csv')
@login_required
@admin_only
def export_csv():
    logs = MileageLog.query.all()

    def generate():
        data = StringIO();
        writer = csv.writer(data)
        writer.writerow(['Date', 'Plate', 'Dept', 'Driver', 'Odometer', 'Distance'])
        yield data.getvalue();
        data.seek(0);
        data.truncate(0)
        for l in logs:
            writer.writerow(
                [l.date, l.vehicle.plate_number, l.vehicle.department, l.driver_name, l.odometer, l.distance])
            yield data.getvalue();
            data.seek(0);
            data.truncate(0)

    return Response(generate(), mimetype='text/csv', headers={"Content-Disposition": "attachment;filename=report.csv"})


if __name__ == '__main__':
    with app.app_context(): db.create_all()
    app.run(debug=True)